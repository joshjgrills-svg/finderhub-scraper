#!/usr/bin/env python3
"""
FinderHub Multi-Source Ratings Scraper - Firecrawl Version
Uses Firecrawl to scrape ratings from multiple platforms
Strict credit limit enforcement: stops at 2,900 credits
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

# Configuration
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
FIRECRAWL_API_KEY = os.getenv('FIRECRAWL_API_KEY')
BATCH_NUMBER = int(os.getenv('BATCH_NUMBER', '1'))
BATCH_SIZE = int(os.getenv('BATCH_SIZE', '100'))  # Conservative batch size

# CRITICAL: Credit limits
MAX_CREDITS = 2900  # Hard stop before hitting 3,000 limit
CREDITS_PER_SCRAPE = 2  # Conservative estimate

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
        try:
            with open(self.credits_file, 'w') as f:
                f.write(str(self.credits_used))
        except Exception as e:
            print(f"Warning: Could not save credit count: {e}")
    
    def add_credits(self, amount: int):
        """Add credits used"""
        self.credits_used += amount
        self._save_credits()
    
    def can_continue(self, needed: int) -> bool:
        """Check if we can use more credits"""
        return (self.credits_used + needed) <= MAX_CREDITS
    
    def get_remaining(self) -> int:
        """Get remaining credits"""
        return MAX_CREDITS - self.credits_used
    
    def get_status(self) -> str:
        """Get status string"""
        return f"{self.credits_used:,} / {MAX_CREDITS:,} credits used ({self.get_remaining():,} remaining)"

class FirecrawlScraper:
    """Scraper using Firecrawl for multi-source ratings"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.firecrawl.dev/v1"
    
    def scrape_business_ratings(self, business_name: str, city: str) -> Dict:
        """
        Scrape ratings from multiple platforms using Firecrawl
        """
        # Search for the business across platforms
        search_query = f"{business_name} {city} reviews"
        
        results = {
            'yelp_rating': None,
            'yelp_reviews': None,
            'homestars_rating': None,
            'homestars_reviews': None,
            'google_rating': None,
            'google_reviews': None,
            'bbb_rating': None,
            'facebook_rating': None,
            'facebook_reviews': None,
        }
        
        # Try to scrape each platform
        platforms = [
            (f"https://www.yelp.com/search?find_desc={business_name}&find_loc={city}", 'yelp'),
            (f"https://homestars.com/search?q={business_name}+{city}", 'homestars'),
            (f"https://www.bbb.org/search?find_text={business_name}+{city}", 'bbb'),
        ]
        
        for url, platform in platforms:
            try:
                # Use Firecrawl's scrape endpoint
                response = requests.post(
                    f"{self.base_url}/scrape",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "url": url,
                        "formats": ["markdown", "html"],
                        "onlyMainContent": True,
                        "timeout": 30000
                    },
                    timeout=60
                )
                
                if response.status_code == 200:
                    data = response.json()
                    content = data.get('data', {}).get('markdown', '')
                    
                    # Extract ratings from content
                    if platform == 'yelp':
                        results.update(self._extract_yelp_ratings(content, business_name))
                    elif platform == 'homestars':
                        results.update(self._extract_homestars_ratings(content, business_name))
                    elif platform == 'bbb':
                        results.update(self._extract_bbb_ratings(content, business_name))
                
                # Small delay between platform requests
                time.sleep(1)
                
            except Exception as e:
                print(f"  Error scraping {platform}: {e}")
                continue
        
        return results
    
    def _extract_yelp_ratings(self, content: str, business_name: str) -> Dict:
        """Extract Yelp ratings from markdown content"""
        result = {}
        
        # Look for rating patterns
        rating_match = re.search(r'(\d\.?\d?)\s*star', content, re.IGNORECASE)
        if rating_match:
            result['yelp_rating'] = float(rating_match.group(1))
        
        # Look for review count
        review_match = re.search(r'(\d+)\s*review', content, re.IGNORECASE)
        if review_match:
            result['yelp_reviews'] = int(review_match.group(1))
        
        return result
    
    def _extract_homestars_ratings(self, content: str, business_name: str) -> Dict:
        """Extract HomeStars ratings from markdown content"""
        result = {}
        
        # HomeStars uses 0-10 scale
        rating_match = re.search(r'(\d\.?\d?)\s*out\s*of\s*10', content, re.IGNORECASE)
        if rating_match:
            result['homestars_rating'] = float(rating_match.group(1))
        
        review_match = re.search(r'(\d+)\s*review', content, re.IGNORECASE)
        if review_match:
            result['homestars_reviews'] = int(review_match.group(1))
        
        return result
    
    def _extract_bbb_ratings(self, content: str, business_name: str) -> Dict:
        """Extract BBB ratings from markdown content"""
        result = {}
        
        # BBB uses letter grades
        rating_match = re.search(r'BBB\s*Rating[:\s]*([A-F][+-]?)', content, re.IGNORECASE)
        if rating_match:
            result['bbb_rating'] = rating_match.group(1)
        
        return result

class SupabaseClient:
    """Client for Supabase operations"""
    
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
                return []
        except Exception as e:
            print(f"Exception fetching providers: {e}")
            return []
    
    def update_provider(self, provider_id: str, ratings: Dict) -> bool:
        """Update provider with ratings"""
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
    print(f"🔥 FinderHub Firecrawl Ratings Scraper - Batch {BATCH_NUMBER}")
    print(f"📦 Batch size: {BATCH_SIZE}")
    print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Verify environment variables
    if not all([SUPABASE_URL, SUPABASE_KEY, FIRECRAWL_API_KEY]):
        print("❌ Error: Missing required environment variables")
        sys.exit(1)
    
    # Initialize credit tracker
    tracker = CreditTracker()
    print(f"💳 {tracker.get_status()}\n")
    
    # Check if we can run this batch
    estimated_credits = BATCH_SIZE * CREDITS_PER_SCRAPE
    if not tracker.can_continue(estimated_credits):
        print(f"🛑 CREDIT LIMIT REACHED!")
        print(f"   This batch needs ~{estimated_credits} credits")
        print(f"   Only {tracker.get_remaining()} credits remaining")
        print(f"   Stopping to prevent exceeding {MAX_CREDITS} credit limit")
        print(f"\n⚠️  MANUAL APPROVAL REQUIRED TO CONTINUE")
        sys.exit(0)
    
    # Initialize clients
    supabase = SupabaseClient(SUPABASE_URL, SUPABASE_KEY)
    scraper = FirecrawlScraper(FIRECRAWL_API_KEY)
    
    # Get providers
    print(f"📥 Fetching providers for batch {BATCH_NUMBER}...")
    providers = supabase.get_batch_providers(BATCH_NUMBER, BATCH_SIZE)
    
    if not providers:
        print(f"✅ No more providers to scrape in batch {BATCH_NUMBER}")
        return
    
    print(f"Found {len(providers)} providers to scrape\n")
    
    # Track stats
    stats = {
        'total': len(providers),
        'success': 0,
        'errors': 0,
        'credits_used': 0,
        'platforms_found': {'yelp': 0, 'homestars': 0, 'google': 0, 'bbb': 0, 'facebook': 0}
    }
    
    # Process each provider
    for i, provider in enumerate(providers, 1):
        # Check credits before each scrape
        if not tracker.can_continue(CREDITS_PER_SCRAPE):
            print(f"\n🛑 STOPPING: Credit limit reached after {i-1} providers")
            print(f"   {tracker.get_status()}")
            break
        
        print(f"[{i}/{len(providers)}] {provider['business_name']} ({provider['city']})")
        
        # Scrape ratings
        try:
            ratings = scraper.scrape_business_ratings(
                provider['business_name'],
                provider['city']
            )
            
            # Update database
            if supabase.update_provider(provider['id'], ratings):
                stats['success'] += 1
                stats['credits_used'] += CREDITS_PER_SCRAPE
                tracker.add_credits(CREDITS_PER_SCRAPE)
                
                # Count platforms
                found = []
                if ratings.get('yelp_rating'):
                    stats['platforms_found']['yelp'] += 1
                    found.append(f"Yelp: {ratings['yelp_rating']}")
                if ratings.get('homestars_rating'):
                    stats['platforms_found']['homestars'] += 1
                    found.append(f"HomeStars: {ratings['homestars_rating']}")
                if ratings.get('bbb_rating'):
                    stats['platforms_found']['bbb'] += 1
                    found.append(f"BBB: {ratings['bbb_rating']}")
                
                if found:
                    print(f"   ✅ {', '.join(found)}")
                else:
                    print(f"   ⚠️  No ratings found")
            else:
                stats['errors'] += 1
                print(f"   ❌ Database update failed")
                
        except Exception as e:
            stats['errors'] += 1
            print(f"   ❌ Error: {e}")
        
        # Rate limiting
        time.sleep(random.uniform(2, 4))
    
    # Final summary
    print(f"\n✅ Batch {BATCH_NUMBER} Complete!")
    print(f"📊 Stats:")
    print(f"   Total processed: {stats['success']}")
    print(f"   Errors: {stats['errors']}")
    print(f"   Credits used this batch: {stats['credits_used']}")
    print(f"\n💳 {tracker.get_status()}")
    
    if tracker.get_remaining() < 100:
        print(f"\n⚠️  WARNING: Less than 100 credits remaining!")
        print(f"   Manual approval required to continue scraping")
    
    print(f"\n🌐 Platform Coverage:")
    for platform, count in stats['platforms_found'].items():
        pct = (count / stats['success'] * 100) if stats['success'] > 0 else 0
        print(f"   {platform.capitalize()}: {count}/{stats['success']} ({pct:.1f}%)")
    
    print(f"\n⏰ Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == '__main__':
    main()
