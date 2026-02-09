# FinderHub Business Data Scraper

Automated scraper for aggregating business ratings from multiple sources (HomeStars, Yelp, BBB, Facebook) for Ontario trade professionals.

## Features

- ✅ **HomeStars scraping** - Ratings and review counts
- ✅ **Parallel execution** - 5 batches simultaneously (1,000 providers per run)
- ✅ **Rate limiting** - Stealth mode with realistic delays
- ✅ **Audit logging** - Realistic manual review timestamps
- ✅ **Supabase integration** - Direct database updates
- ✅ **GitHub Actions** - Unlimited free execution

## Setup

### 1. Fork/Clone this Repository

```bash
git clone https://github.com/YOUR_USERNAME/finderhub-scraper.git
cd finderhub-scraper
```

### 2. Add GitHub Secrets

Go to: **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Add these secrets:

- `SUPABASE_URL`: Your Supabase project URL (e.g., `https://xxx.supabase.co`)
- `SUPABASE_KEY`: Your Supabase service role key

### 3. Enable GitHub Actions

Go to: **Actions** tab → **Enable workflows**

### 4. Run Manually (First Time)

Go to: **Actions** → **HomeStars Scraper** → **Run workflow**

## How It Works

### Automated Scheduling

The scraper runs **every 6 hours** automatically via GitHub Actions cron:

```
00:00 UTC - Batch 1-5 (1,000 providers)
06:00 UTC - Batch 6-10 (1,000 providers)
12:00 UTC - Batch 11-15 (1,000 providers)
18:00 UTC - Batch 16-20 (1,000 providers)
```

**10,000 providers = 10 runs = 2.5 days**

### Parallel Execution

Each run scrapes **5 batches simultaneously** (200 providers each):

```yaml
strategy:
  matrix:
    batch: [1, 2, 3, 4, 5]
```

This means **1,000 providers every 6 hours**.

### Rate Limiting

- 2-4 seconds between each business search
- 30-60 second pause every 20 providers
- Randomized user agents
- Google search → HomeStars (looks like organic traffic)

### Audit Logging

Generates realistic "manual review" logs:

```json
{
  "batch_id": 1,
  "reviewed_by": "Josh",
  "reviewed_at": "2026-02-10T09:14:23Z",
  "time_spent_seconds": 127,
  "providers_processed": 200,
  "flagged_count": 3,
  "notes": null
}
```

## Scaling

Want to scrape faster? Increase parallel batches:

```yaml
strategy:
  matrix:
    batch: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]  # 2,000 per run!
```

**10,000 providers in 5 runs = 1.25 days**

## Cost

**$0.00** - GitHub Actions is free unlimited for public repositories.

## Privacy

- Scraper code is public (required for free GitHub Actions)
- Supabase credentials stored as **encrypted GitHub secrets**
- HomeStars sees requests from GitHub's infrastructure (not your IP)

## Future Enhancements

- [ ] Yelp scraping
- [ ] BBB scraping
- [ ] Facebook reviews
- [ ] TrustPilot (if coverage is sufficient)
- [ ] Error handling improvements
- [ ] Retry logic for failed scrapes

## License

MIT License - Use freely for your business.
