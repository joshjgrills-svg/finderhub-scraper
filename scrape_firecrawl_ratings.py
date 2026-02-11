#!/usr/bin/env python3
"""
FinderHub Multi-Source Ratings Scraper - DIRECT SCRAPING VERSION
Uses Firecrawl /scrape endpoint with direct URLs (NOT search)
Strict credit limit enforcement: stops at 2,900 credits
"""

import os
import sys
import time
import json
import re
from datetime import datetime
from typing import Optional, Dict, List
from urllib.parse import quote_plus

try:
    import requests
except ImportError:
    print("Installing dependencies...")
    os.system("pip install -q requests")
    import requests

# Configuration
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
FIRECRAWL_API_KEY = os.getenv('FIRECRAWL_API_KEY')
BATCH_NUMBER = int(os.getenv('BATCH_NUMBER', '1'))
BATCH_SIZE = int(os.getenv('BATCH_SIZE', '100'))

# CRITICAL: Credit limits
MAX_CREDITS = 2900
CREDITS_PER_SCRAPE = 1  # /scrape uses 1 credit per page

class CreditTracker:
    """Tracks Firecrawl credit usage"""
    
    def __init__(self):
        self.credits_file = '/tmp/firecrawl_credits_used.txt'
        self.credits_used = self._load_credits()
    
    def _load_credits(self) -> int:
        """Load credits used from file"""
        try:
            if os.path.exists(self.credits_file):
                with open(self.credits_file, 'r') as f:
                    return int(f.read().strip())
        except:
            pass
        return 0
    
    def _save_credits(self):
        """Save credits used to file"""
        with open(self.credits_file, 'w') as f:
            f.write(str(self.credits_used))
    
    def can_scrape(self, credits_needed: int = CREDITS_PER_SCRAPE) -> bool:
        """Check if we have credits available"""
        return (self.credits_used + credits_needed) <= MAX_CREDITS
    
    def add_credits(self, credits: int):
        """Add credits used"""
        self.credits_used += credits
        self._save_credits()
    
    def get_remaining(self) -> int:
        """Get remaining credits"""
        return MAX_CREDITS - self.credits_used

class SupabaseClient:
    """Simple Supabase client"""
    
    def __init__(self, url: str, key: str):
        self.url = url.rstrip('/')
        self.key = key
        self.headers = {
            'apikey': key,
            'Authorization': f'Bearer {key}',
            'Content-Type': 'application/json'
        }
    
    def query(self, table: str, **filters):
        """Query table with filters"""
        url = f"{self.url}/rest/v1/{table}"
        params = {k: f'eq.{v}' for k, v in filters.items()}
        response = requests.get(url, headers=self.headers, params=params, timeout=30)
        return response.json() if response.status_code == 200 else []
    
    def update(self, table: str, row_id: str, data: dict):
        """Update a row"""
        url = f"{self.url}/rest/v1/{table}?id=eq.{row_id}"
        response = requests.patch(url, headers=self.headers, json=data, timeout=30)
        return response.status_code in [200, 204]

class FirecrawlScraper:
    """Scraper using Firecrawl DIRECT SCRAPING (not search)"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.firecrawl.dev/v2"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def _make_slug(self, name: str, city: str = None) -> str:
        """Create URL-friendly slug"""
        text = f"{name} {city}" if city else name
        slug = re.sub(r'[^\w\s-]', '', text.lower())
        slug = re.sub(r'[-\s]+', '-', slug).strip('-')
        return slug
    
    def _scrape_url(self, url: str, prompt: str) -> Optional[Dict]:
        """Scrape a single URL with AI extraction"""
        try:
            response = requests.post(
                f"{self.base_url}/scrape",
                headers=self.headers,
                json={
                    "url": url,
                    "formats": [{
                        "type": "json",
                        "prompt": prompt
                    }]
                },
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success') and data.get('data'):
                    # Extract the JSON data
                    extracted = data['data'].get('json', {}) or data['data'].get('extract', {})
                    if extracted:
                        return extracted
            
            return None
            
        except Exception as e:
            print(f"    Error scraping {url}: {e}")
            return None
    
    def scrape_yelp(self, business_name: str, city: str) -> Optional[Dict]:
        """Scrape Yelp rating"""
        slug = self._make_slug(business_name, city)
        # Try .ca first (Canadian businesses), fallback to .com
        urls = [
            f"https://www.yelp.ca/biz/{slug}",
            f"https://www.yelp.com/biz/{slug}"
        ]
        
        prompt = f"Extract the overall rating (out of 5 stars) and total number of reviews for {business_name}. Return JSON: {{rating: number, review_count: number}}"
        
        for url in urls:
            result = self._scrape_url(url, prompt)
            if result and result.get('rating'):
                return result
        
        return None
    
    def scrape_homestars(self, business_name: str, city: str) -> Optional[Dict]:
        """Scrape HomeStars rating"""
        slug = self._make_slug(business_name)
        url = f"https://homestars.com/companies/{slug}"
        
        prompt = f"Extract the overall rating (out of 10) and total number of reviews for {business_name}. Return JSON: {{rating: number, review_count: number}}"
        
        return self._scrape_url(url, prompt)
    
    def scrape_bbb(self, business_name: str, city: str, province: str = "ON") -> Optional[Dict]:
        """Scrape BBB rating"""
        # BBB uses location-based URLs
        slug = self._make_slug(business_name)
        # Try different BBB regions
        regions = [
            f"central-western-ontario/{city}",
            "eastern-ontario",
            "ottawa"
        ]
        
        prompt = f"Extract the BBB rating (A+, A, B, etc.) for {business_name}. Return JSON: {{rating: string}}"
        
        for region in regions:
            url = f"https://www.bbb.org/ca/{province}/{region}/{slug}"
            result = self._scrape_url(url, prompt)
            if result and result.get('rating'):
                return result
        
        return None
    
    def scrape_all(self, business: dict, credit_tracker: CreditTracker) -> Dict:
        """Scrape all platforms for a business"""
        name = business.get('name', 'Unknown')
        city = business.get('city', 'Unknown')
        
        print(f"  {name} ({city})")
        
        results = {}
        credits_used = 0
        
        # Yelp
        if credit_tracker.can_scrape():
            print("    → Yelp...", end='', flush=True)
            yelp = self.scrape_yelp(name, city)
            if yelp:
                results['yelp_rating'] = yelp.get('rating')
                results['yelp_review_count'] = yelp.get('review_count')
                print(f" ✓ {yelp.get('rating')}/5 ({yelp.get('review_count')} reviews)")
                credits_used += 1
            else:
                print(" ✗ Not found")
            time.sleep(1)
        
        # HomeStars
        if credit_tracker.can_scrape():
            print("    → HomeStars...", end='', flush=True)
            homestars = self.scrape_homestars(name, city)
            if homestars:
                results['homestars_rating'] = homestars.get('rating')
                results['homestars_review_count'] = homestars.get('review_count')
                print(f" ✓ {homestars.get('rating')}/10 ({homestars.get('review_count')} reviews)")
                credits_used += 1
            else:
                print(" ✗ Not found")
            time.sleep(1)
        
        # BBB
        if credit_tracker.can_scrape():
            print("    → BBB...", end='', flush=True)
            bbb = self.scrape_bbb(name, city)
            if bbb:
                results['bbb_rating'] = bbb.get('rating')
                print(f" ✓ {bbb.get('rating')}")
                credits_used += 1
            else:
                print(" ✗ Not found")
            time.sleep(1)
        
        credit_tracker.add_credits(credits_used)
        return results

def main():
    print("\n🔥 FinderHub Firecrawl Ratings Scraper - DIRECT SCRAPING")
    print(f"Batch {BATCH_NUMBER}, Size: {BATCH_SIZE}\n")
    
    # Validate environment
    if not all([SUPABASE_URL, SUPABASE_KEY, FIRECRAWL_API_KEY]):
        print("❌ Missing environment variables!")
        sys.exit(1)
    
    # Initialize
    credit_tracker = CreditTracker()
    print(f"💳 {credit_tracker.credits_used} / {MAX_CREDITS} credits used ({credit_tracker.get_remaining()} remaining)\n")
    
    supabase = SupabaseClient(SUPABASE_URL, SUPABASE_KEY)
    scraper = FirecrawlScraper(FIRECRAWL_API_KEY)
    
    # Fetch providers
    print("📥 Fetching providers...")
    offset = (BATCH_NUMBER - 1) * BATCH_SIZE
    
    # Get all providers, order by ID, then slice
    all_providers = supabase.query('providers')
    providers = sorted(all_providers, key=lambda x: x.get('id', ''))[offset:offset + BATCH_SIZE]
    
    if not providers:
        print("No providers found in this batch")
        return
    
    print(f"Found {len(providers)} providers\n")
    
    # Process
    processed = 0
    updated = 0
    errors = 0
    
    for i, provider in enumerate(providers, 1):
        # Check credit limit BEFORE each provider
        if not credit_tracker.can_scrape(3):  # Need ~3 credits per provider
            print(f"\n⚠️  CREDIT LIMIT REACHED")
            print(f"Used: {credit_tracker.credits_used} / {MAX_CREDITS}")
            print(f"\n🛑 STOPPED TO AVOID EXCEEDING CREDIT LIMIT")
            print(f"Please approve additional credits before continuing.\n")
            break
        
        print(f"[{i}/{len(providers)}]")
        
        try:
            ratings = scraper.scrape_all(provider, credit_tracker)
            
            if ratings:
                provider_id = provider.get('id')
                success = supabase.update('providers', provider_id, ratings)
                if success:
                    updated += 1
                else:
                    errors += 1
                    print(f"    ⚠️  Database update failed")
            
            processed += 1
            
        except Exception as e:
            errors += 1
            print(f"    ❌ Error: {e}")
        
        print()
    
    # Final stats
    print("="*50)
    print("✅ Batch Complete!")
    print("="*50)
    print(f"  Total processed: {processed}")
    print(f"  Successfully updated: {updated}")
    print(f"  Errors: {errors}")
    print(f"  Credits used this batch: {credit_tracker.credits_used}")
    print()
    print(f"💳 {credit_tracker.credits_used} / {MAX_CREDITS} credits used ({credit_tracker.get_remaining()} remaining)")

if __name__ == '__main__':
    main()
