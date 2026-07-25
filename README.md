# Videos Auto Scraper — GitHub Only

সম্পূর্ণ standalone. Lovable, Vercel, Netlify — কিছুই লাগবে না। শুধু GitHub repo + GitHub Pages।

## 🚀 Setup (3 steps)

### 1) Repo তে upload করুন
এই folder/file গুলো আপনার GitHub repo তে push করুন:

```
.github/workflows/scrape.yml   ← auto scraper (প্রতি ১৫ মিনিটে চলে)
scripts/scraper.py             ← Python scraper
scripts/requirements.txt
docs/index.html                ← standalone site (GitHub Pages এ serve হবে)
docs/data.json                 ← scraped data (auto update হবে)
```

### 2) GitHub Actions permission দিন
Repo → **Settings → Actions → General → Workflow permissions** → **"Read and write permissions"** select করুন → Save।

### 3) GitHub Pages enable করুন
Repo → **Settings → Pages** →
- **Source:** Deploy from a branch
- **Branch:** `main` / folder: **`/docs`** → Save

কিছুক্ষণ পর আপনার site live হবে এই URL এ:
```
https://<username>.github.io/<repo>/
```

আপনার জন্য (repo: `Ripon01744/videos`):
```
https://ripon01744.github.io/videos/
```

---

## 🔄 কীভাবে কাজ করে

1. প্রতি **15 মিনিটে** GitHub Actions চালু হয়
2. `scripts/scraper.py` চলে → zmaal.net থেকে সব categories/folders (NEONX, ULLU, MOODX, Models ইত্যাদি) সহ ১০০০ পর্যন্ত video scrape করে
3. `public/data.json` + `docs/data.json` update হয়ে auto commit হয়
4. GitHub Pages instantly নতুন data serve করে
5. আপনার site এ ads ছাড়া সরাসরি video play হয় (native HTML5 player)

## 🎬 Site features
- 🔍 Search (title + description)
- 🏷️ Folder/category filter chips (৬০+ folders)
- 📅 Sort by newest / A–Z
- ▶️ In-page video player (কোনো ads নেই)
- 🔁 Auto-refresh প্রতি ১৫ মিনিটে

## 🧪 Manual test
Actions tab → **Auto Scraper (zmaal.net)** → Run workflow → done।

## ⚠️ Notes
- Repo **Public** হতে হবে (GitHub Pages free tier এর জন্য)
- Video files zmaal.net এর AWS CDN থেকে stream হয় (signed URL, ১৫ মিনিটে refresh)
