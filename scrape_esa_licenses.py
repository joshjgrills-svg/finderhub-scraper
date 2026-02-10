#!/usr/bin/env python3
"""
FinderHub ESA License Scraper
Finds ESA/ECRA license numbers for electricians in Ontario
Uses web search grounding to verify licensing status
"""

import os
import sys
import time
import random
import json
import re
from datetime import datetime
from typing import Optional, Dict, List

try:
    import requests
except ImportError:
    print("Installing dependencies...")
    os.system("pip install -q requests")
    import requests

# Supabase configuration
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
BATCH_NUMBER = int(os.getenv('BATCH_NUMBER', '1'))
BATCH_SIZE = int(os.getenv('BATCH_SIZE', '50'))

# Anthropic API for web search
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')

class ESALicenseScraper:
    """Scraper that uses web search to find ESA license information"""
    
    def __init__(self, anthropic_key: str):
        self.anthropic_key = anthropic_key
        self.session = requests.Session()
        
    def search_for_license(self, business_name: str, city: str, category: str) -> Dict:
        """
        Use Anthropic's web search to find ESA license info
        """
        # Only search for electricians
        if category.lower() not in ['electrician', 'electrical']:
            return self._empty_result()
        
        # Search for ESA license number
        query = f"{business_name} {city} ESA ECRA license number electrician"
        
        try:
            # Call Anthropic API with web search
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": self.anthropic_key,
                    "anthropic-version": "2023-06-01"
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 1500,
                    "tools": [{
                        "type": "web_search_20250305",
                        "name": "web_search"
                    }],
                    "messages": [{
                        "role": "user",
                        "content": f"Find the ESA/ECRA license number for {business_name} in {city}, Ontario. The license number format is 'ECRA/ESA' followed by 7 digits (e.g. ECRA/ESA 7010353). Also determine if they are currently licensed (active/valid) or not. Return ONLY a JSON object: {{\"esa_license_number\": \"ECRA/ESA XXXXXXX\" or null, \"license_status\": \"active\" or \"inactive\" or \"unknown\" or null, \"master_electrician\": true or false or null}}. Use null if you cannot find the information."
                    }]
                },
                timeout=60
            )
            
            if response.status_code != 200:
                print(f"API error: {response.status_code}")
                return self._empty_result()
            
            data = response.json()
            
            # Extract the text response
            content = data.get('content', [])
            for block in content:
                if block.get('type') == 'text':
                    text = block.get('text', '')
                    # Try to parse JSON from the response
                    try:
                        # Clean the response
                        text = text.strip()
                        if text.startswith('```'):
                            text = '\n'.join(text.split('\n')[1:-1])
                        if text.startswith('json'):
                            text = text[4:].strip()
                        
                        license_info = json.loads(text)
                        return license_info
                    except json.JSONDecodeError:
                        # Try to extract license number from text if JSON parsing fails
                        license_match = re.search(r'ECRA/ESA\s*(\d{7})', text)
                        if license_match:
                            return {
                                'esa_license_number': f"ECRA/ESA {license_match.group(1)}",
                                'license_status': 'unknown',
                                'master_electrician': None
                            }
                        return self._empty_result()
            
            return self._empty_result()
            
        except Exception as e:
            print(f"Error searching for {business_name}: {e}")
            return self._empty_result()
    
    def _empty_result(self) -> Dict:
        """Return empty result structure"""
        return {
            'esa_license_number': None,
            'license_status': None,
            'master_electrician': None
        }

class SupabaseClient:
    """Client for new-style Supabase API keys"""
    
    def __init__(self, url: str, key: str):
        self.url = url.rstrip('/')
        self.key = key
        self.headers = {
            'apikey': key,
            'Content-Type': 'application/json',
            'Prefer': 'return=representation'
        }
    
    def get_batch_providers(self, batch_number: int, batch_size: int, category: str = 'electrician') -> List[Dict]:
        """Get a batch of electricians to check for licenses"""
        offset = (batch_number - 1) * batch_size
        
        # Get electricians that don't have ESA license data yet
        # Note: You'll need to add these columns to your providers table:
        # - esa_license_number (TEXT)
        # - license_status (TEXT)
        # - master_electrician (BOOLEAN)
        
        params = {
            'select': 'id,business_name,city,category',
            'category': f'eq.{category}',
            'esa_license_number': 'is.null',
            'limit': batch_size,
            'offset': offset,
            'order': 'id.asc'
        }
        
        try:
            response = requests.get(
                f'{self.url}/rest/v1/providers',
                headers=self.headers,
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Error fetching providers: {response.status_code}")
                print(f"Response: {response.text[:500]}")
                return []
        except Exception as e:
            print(f"Exception fetching providers: {e}")
            return []
    
    def update_provider_license(self, provider_id: str, license_info: Dict) -> bool:
        """Update provider with ESA license information"""
        update_data = {}
        
        if license_info.get('esa_license_number'):
            update_data['esa_license_number'] = license_info['esa_license_number']
        
        if license_info.get('license_status'):
            update_data['license_status'] = license_info['license_status']
        
        if license_info.get('master_electrician') is not None:
            update_data['master_electrician'] = license_info['master_electrician']
        
        # Mark as checked even if no license found
        update_data['license_checked_at'] = datetime.utcnow().isoformat()
        
        if not update_data:
            return True  # Nothing to update but not an error
        
        try:
            response = requests.patch(
                f'{self.url}/rest/v1/providers?id=eq.{provider_id}',
                headers=self.headers,
                json=update_data,
                timeout=30
            )
            
            return response.status_code in [200, 204]
        except Exception as e:
            print(f"Exception updating provider: {e}")
            return False

def main():
    """Main scraping function"""
    print(f"🚀 FinderHub ESA License Scraper - Batch {BATCH_NUMBER}")
    print(f"📦 Batch size: {BATCH_SIZE}")
    print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Initialize clients
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ Error: SUPABASE_URL and SUPABASE_KEY must be set")
        sys.exit(1)
    
    if not ANTHROPIC_API_KEY:
        print("❌ Error: ANTHROPIC_API_KEY must be set")
        sys.exit(1)
    
    supabase = SupabaseClient(SUPABASE_URL, SUPABASE_KEY)
    scraper = ESALicenseScraper(ANTHROPIC_API_KEY)
    
    # Get electricians to check
    print(f"📥 Fetching electricians for batch {BATCH_NUMBER}...")
    providers = supabase.get_batch_providers(BATCH_NUMBER, BATCH_SIZE)
    
    if not providers:
        print(f"✅ No more electricians to check in batch {BATCH_NUMBER}")
        return
    
    print(f"Found {len(providers)} electricians to check\n")
    
    # Check each electrician
    stats = {
        'total': len(providers),
        'licensed': 0,
        'not_found': 0,
        'active': 0,
        'inactive': 0,
        'errors': 0
    }
    
    for i, provider in enumerate(providers, 1):
        print(f"[{i}/{len(providers)}] {provider['business_name']} ({provider['city']})")
        
        # Search for license
        license_info = scraper.search_for_license(
            provider['business_name'],
            provider['city'],
            provider.get('category', 'electrician')
        )
        
        # Update database
        if supabase.update_provider_license(provider['id'], license_info):
            if license_info.get('esa_license_number'):
                stats['licensed'] += 1
                status = license_info.get('license_status', 'unknown')
                if status == 'active':
                    stats['active'] += 1
                elif status == 'inactive':
                    stats['inactive'] += 1
                
                print(f"   ✅ Licensed: {license_info['esa_license_number']} ({status})")
            else:
                stats['not_found'] += 1
                print(f"   ⚠️  No license found")
        else:
            stats['errors'] += 1
            print(f"   ❌ Database update failed")
        
        # Rate limiting
        if i < len(providers):
            delay = random.uniform(4, 7)
            time.sleep(delay)
    
    # Print summary
    print(f"\n✅ Batch {BATCH_NUMBER} Complete!")
    print(f"📊 Stats:")
    print(f"   Total checked: {stats['total']}")
    print(f"   Licensed: {stats['licensed']} ({stats['licensed']/stats['total']*100:.1f}%)")
    print(f"   Active licenses: {stats['active']}")
    print(f"   Inactive licenses: {stats['inactive']}")
    print(f"   No license found: {stats['not_found']}")
    print(f"   Errors: {stats['errors']}")
    print(f"\n⏰ Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == '__main__':
    main()
