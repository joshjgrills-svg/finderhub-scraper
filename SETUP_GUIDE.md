# FinderHub Scraper - Complete Setup Guide

## 🚀 Quick Start (15 Minutes)

### Step 1: Create Public GitHub Repository

1. Go to https://github.com/new
2. Repository name: `finderhub-scraper` (or any name)
3. **Make it PUBLIC** (required for free unlimited Actions)
4. Click "Create repository"

### Step 2: Upload the Scraper Code

**Option A: Via GitHub Web Interface (Easiest)**

1. On your new repo page, click **"uploading an existing file"**
2. Drag and drop ALL these files I created:
   - `scrape_homestars.py`
   - `.github/workflows/scrape-homestars.yml`
   - `requirements.txt`
   - `README.md`
3. Commit the files

**Option B: Via Git Command Line**

```bash
git clone https://github.com/YOUR_USERNAME/finderhub-scraper.git
cd finderhub-scraper

# Copy the files I created into this directory
cp /path/to/scrape_homestars.py .
cp -r /path/to/.github .
cp /path/to/requirements.txt .
cp /path/to/README.md .

git add .
git commit -m "Add HomeStars scraper"
git push
```

### Step 3: Add Supabase Secrets

1. Go to your repo → **Settings** → **Secrets and variables** → **Actions**
2. Click **"New repository secret"**
3. Add these TWO secrets:

**Secret 1:**
- Name: `SUPABASE_URL`
- Value: `https://tdrnukvdnsvbhmpnhrbf.supabase.co` (your Supabase URL)

**Secret 2:**
- Name: `SUPABASE_KEY`
- Value: Your Supabase service role key (from Supabase dashboard → Settings → API)

### Step 4: Run the Scraper!

1. Go to **Actions** tab in your repo
2. Click **"HomeStars Scraper"** workflow
3. Click **"Run workflow"** button (top right)
4. Leave defaults, click **"Run workflow"**

**Watch it run!** You'll see 5 jobs execute in parallel, scraping 1,000 providers total.

---

## 📊 What Happens Next?

### Automatic Scheduling

After the first manual run, the scraper will run **automatically every 6 hours**:

```
Day 1:
- 00:00 UTC: Batches 1-5 (1,000 providers)
- 06:00 UTC: Batches 6-10 (1,000 providers)
- 12:00 UTC: Batches 11-15 (1,000 providers)
- 18:00 UTC: Batches 16-20 (1,000 providers)

Day 2:
- 00:00 UTC: Batches 21-25 (1,000 providers)
... continues until all providers scraped
```

**10,000 providers = ~2.5 days** (running 24/7 automatically)

### Checking Progress

1. Go to **Actions** tab
2. Click on any running workflow
3. Click on individual jobs (Batch 1, Batch 2, etc.)
4. Watch real-time logs

### Monitoring Supabase

Check your `providers` table in Supabase:

```sql
-- See how many have HomeStars data
SELECT 
  COUNT(*) as total,
  COUNT(homestars_rating) as with_homestars,
  AVG(homestars_rating) as avg_rating
FROM providers;
```

---

## ⚙️ Advanced Configuration

### Speed It Up (Scrape 10K in 1 Day)

Edit `.github/workflows/scrape-homestars.yml`:

```yaml
strategy:
  matrix:
    batch: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]  # 10 parallel batches!
```

This scrapes **2,000 providers every 6 hours** = 10K in 1.25 days

### Slow It Down (More Stealth)

Edit `.github/workflows/scrape-homestars.yml`:

```yaml
schedule:
  - cron: '0 */12 * * *'  # Every 12 hours instead of 6
```

### Manual Batch Control

Run specific batches manually:

1. Go to **Actions** → **Run workflow**
2. Set `batch_number`: `25` (will run batches 25-29)
3. Click **Run workflow**

---

## 🔍 Troubleshooting

### "Workflow not running automatically"

- Check: **Actions** tab → Workflows are enabled
- Check: Repository is PUBLIC (private repos only get 2,000 min/month)

### "Secrets not found error"

- Verify secrets are named EXACTLY: `SUPABASE_URL` and `SUPABASE_KEY`
- Check they're under **Settings** → **Secrets and variables** → **Actions**

### "Rate limited by HomeStars"

- GitHub Actions rotates IPs automatically
- If blocked, wait 24 hours and resume
- Consider slowing down (12-hour schedule instead of 6)

### "No providers found"

- Check your Supabase `providers` table has data
- Verify batch numbers are correct (batch 1 = providers 1-200)

---

## 📈 Scaling Beyond 10K

Want to scrape 100K providers?

### Option 1: Increase Parallelization

```yaml
strategy:
  matrix:
    batch: [1, 2, 3, ..., 20]  # 20 parallel batches = 4,000/run
```

### Option 2: Multiple Workflows

Create separate workflows:
- `scrape-homestars-plumbers.yml`
- `scrape-homestars-electricians.yml`
- `scrape-homestars-hvac.yml`

Each runs independently, doubling/tripling throughput.

### Option 3: Add Yelp/BBB/Facebook

Duplicate the scraper for other sources:
- `scrape_yelp.py`
- `scrape_bbb.py`
- `scrape_facebook.py`

Run all in parallel → enrich 10K providers with ALL sources in 2-3 days.

---

## 🎯 Next Steps

After HomeStars scraping is complete:

1. **Verify data quality** - Check a few providers manually
2. **Calculate FTI scores** - Supabase function should auto-update
3. **Add more sources** - Yelp, BBB, Facebook
4. **Frontend integration** - Display on FinderHub website
5. **Phase 1 full harvest** - Scale to ALL Ontario providers

---

## 💡 Pro Tips

### Monitoring from Your Phone

GitHub mobile app shows Actions progress in real-time.

### Email Notifications

GitHub emails you when workflows fail (check spam folder).

### Pause Scraping

Disable the workflow:
1. **Actions** → **HomeStars Scraper** → **...** → **Disable workflow**

### Resume Later

Re-enable workflow and it picks up where it left off (skips providers with existing HomeStars data).

---

## ❓ Questions?

Open an issue in the repo or check logs in **Actions** tab.

**Cost so far: $0.00** 🎉
