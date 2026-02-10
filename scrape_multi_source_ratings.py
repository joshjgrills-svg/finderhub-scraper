#!/usr/bin/env python3
"""
FinderHub Multi-Source Ratings Scraper
Uses web search grounding to extract ratings from multiple platforms:
- Yelp
- HomeStars  
- Google Reviews
- BBB (Better Business Bureau)
- Facebook
- TrustedPros
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
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')  # Need to add this to GitHub secrets

class MultiSourceRatingsScraper:
    """Scraper that uses web search to find ratings across multiple platforms"""
    
    def __init__(self, anthropic_key: str):
        self.anthropic_key = anthropic_key
        self.session = requests.Session()
        
    def search_for_ratings(self, business_name: str, city: str) -> Dict:
        """
        Use Anthropic's web search to find ratings across all platforms
        """
        # Search query targeting multiple review platforms
        query = f"{business_name} {city} reviews ratings yelp homestars google bbb facebook"
        
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
                    "max_tokens": 2000,
                    "tools": [{
                        "type": "web_search_20250305",
                        "name": "web_search"
                    }],
                    "messages": [{
                        "role": "user",
                        "content": f"Find ratings and review counts for {business_name} in {city} from these platforms: Yelp, HomeStars, Google Reviews, BBB, Facebook, TrustedPros. Return ONLY a JSON object with this exact structure: {{\"yelp_rating\": float or null, \"yelp_reviews\": int or null, \"homestars_rating\": float or null, \"homestars_reviews\": int or null, \"google_rating\": float or null, \"google_reviews\": int or null, \"bbb_rating\": string or null, \"facebook_rating\": float or null, \"facebook_reviews\": int or null, \"trustedpros_rating\": float or null, \"trustedpros_reviews\": int or null}}. Use null for any platform where you cannot find data."
                    }]
                },
                timeout=60
            )
            
            if response.status_code != 200:
                print(f"API error: {response.status_code} - {response.text}")
                return self._empty_result()
            
            data = response.json()
            
            # Extract the text response
            content = data.get('content', [])
            for block in content:
                if block.get('type') == 'text':
                    text = block.get('text', '')
                    # Try to parse JSON from the response
                    try:
                        # Clean the response - remove markdown code blocks if present
                        text = text.strip()
                        if text.startswith('```'):
                            text = '\n'.join(text.split('\n')[1:-1])
                        if text.startswith('json'):
                            text = text[4:].strip()
                        
                        ratings = json.loads(text)
                        return ratings
                    except json.JSONDecodeError:
                        print(f"Could not parse JSON from response: {text[:200]}")
                        return self._empty_result()
            
            return self._empty_result()
            
        except Exception as e:
            print(f"Error searching for {business_name}: {e}")
            return self._empty_result()
    
    def _empty_result(self) -> Dict:
        """Return empty result structure"""
        return {
            'yelp_rating': None,
            'yelp_reviews': None,
            'homestars_rating': None,
            'homestars_reviews': None,
            'google_rating': None,
            'google_reviews': None,
            'bbb_rating': None,
            'facebook_rating': None,
            'facebook_reviews': None,
            'trustedpros_rating': None,
            'trustedpros_reviews': None
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
    
    def get_batch_providers(self, batch_number: int, batch_size: int) -> List[Dict]:
        """Get a batch of providers to scrape"""
        offset = (batch_number - 1) * batch_size
        
        # Get providers that don't have multi-source ratings yet
        params = {
            'select': 'id,business_name,city',
            'yelp_rating': 'is.null',
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
    
    def update_provider(self, provider_id: str, ratings: Dict) -> bool:
        """Update provider with multi-source ratings"""
        update_data = {
            'yelp_rating': ratings.get('yelp_rating'),
            'yelp_review_count': ratings.get('yelp_reviews'),
            'homestars_rating': ratings.get('homestars_rating'),
            'homestars_review_count': ratings.get('homestars_reviews'),
            'google_rating': ratings.get('google_rating'),
            'google_review_count': ratings.get('google_reviews'),
            'bbb_rating': ratings.get('bbb_rating'),
            'facebook_rating': ratings.get('facebook_rating'),
            'facebook_review_count': ratings.get('facebook_reviews'),
        }
        
        # Add TrustedPros if we have it
        if ratings.get('trustedpros_rating'):
            update_data['trustedpros_rating'] = ratings.get('trustedpros_rating')
            update_data['trustedpros_review_count'] = ratings.get('trustedpros_reviews')
        
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
    print(f"🚀 FinderHub Multi-Source Ratings Scraper - Batch {BATCH_NUMBER}")
    print(f"📦 Batch size: {BATCH_SIZE}")
    print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Initialize clients
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ Error: SUPABASE_URL and SUPABASE_KEY must be set")
        sys.exit(1)
    
    if not ANTHROPIC_API_KEY:
        print("❌ Error: ANTHROPIC_API_KEY must be set")
        sys.exit(1)
    
    print(f"🔑 Using API key: {SUPABASE_KEY[:15]}...")
    
    supabase = SupabaseClient(SUPABASE_URL, SUPABASE_KEY)
    scraper = MultiSourceRatingsScraper(ANTHROPIC_API_KEY)
    
    # Get providers to scrape
    print(f"📥 Fetching providers for batch {BATCH_NUMBER}...")
    providers = supabase.get_batch_providers(BATCH_NUMBER, BATCH_SIZE)
    
    if not providers:
        print(f"✅ No more providers to scrape in batch {BATCH_NUMBER}")
        return
    
    print(f"Found {len(providers)} providers to scrape\n")
    
    # Scrape each provider
    stats = {
        'total': len(providers),
        'success': 0,
        'errors': 0,
        'platforms_found': {
            'yelp': 0,
            'homestars': 0,
            'google': 0,
            'bbb': 0,
            'facebook': 0,
            'trustedpros': 0
        }
    }
    
    for i, provider in enumerate(providers, 1):
        print(f"[{i}/{len(providers)}] {provider['business_name']} ({provider['city']})")
        
        # Search for ratings
        ratings = scraper.search_for_ratings(
            provider['business_name'],
            provider['city']
        )
        
        # Count platforms found
        if ratings.get('yelp_rating'):
            stats['platforms_found']['yelp'] += 1
        if ratings.get('homestars_rating'):
            stats['platforms_found']['homestars'] += 1
        if ratings.get('google_rating'):
            stats['platforms_found']['google'] += 1
        if ratings.get('bbb_rating'):
            stats['platforms_found']['bbb'] += 1
        if ratings.get('facebook_rating'):
            stats['platforms_found']['facebook'] += 1
        if ratings.get('trustedpros_rating'):
            stats['platforms_found']['trustedpros'] += 1
        
        # Update database
        if supabase.update_provider(provider['id'], ratings):
            stats['success'] += 1
            
            # Print what we found
            found = []
            if ratings.get('yelp_rating'):
                found.append(f"Yelp: {ratings['yelp_rating']}")
            if ratings.get('homestars_rating'):
                found.append(f"HomeStars: {ratings['homestars_rating']}")
            if ratings.get('google_rating'):
                found.append(f"Google: {ratings['google_rating']}")
            if ratings.get('bbb_rating'):
                found.append(f"BBB: {ratings['bbb_rating']}")
            if ratings.get('facebook_rating'):
                found.append(f"Facebook: {ratings['facebook_rating']}")
            
            if found:
                print(f"   ✅ Found: {', '.join(found)}")
            else:
                print(f"   ⚠️  No ratings found")
        else:
            stats['errors'] += 1
            print(f"   ❌ Database update failed")
        
        # Rate limiting: pause between requests
        if i < len(providers):
            delay = random.uniform(3, 6)
            time.sleep(delay)
    
    # Print summary
    print(f"\n✅ Batch {BATCH_NUMBER} Complete!")
    print(f"📊 Stats:")
    print(f"   Total processed: {stats['total']}")
    print(f"   Successful updates: {stats['success']}")
    print(f"   Errors: {stats['errors']}")
    print(f"\n🌐 Platform Coverage:")
    for platform, count in stats['platforms_found'].items():
        percentage = (count / stats['total'] * 100) if stats['total'] > 0 else 0
        print(f"   {platform.capitalize()}: {count}/{stats['total']} ({percentage:.1f}%)")
    print(f"\n⏰ Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == '__main__':
    main()
