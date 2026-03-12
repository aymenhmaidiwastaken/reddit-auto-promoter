# Setup Guide

## 1. Install Dependencies

```bash
pip install -r requirements.txt
```

## 2. Install & Start Ollama

Download [Ollama](https://ollama.ai), then:

```bash
ollama pull llama3
ollama serve
```

## 3. Configure .env

```bash
cp .env.example .env
```

Edit `.env` with your product details:

```env
PROMO_PRODUCT_NAME=YourApp
PROMO_PRODUCT_URL=https://yourapp.com
PROMO_PRODUCT_DESCRIPTION=Brief description of your product
```

## 4. Run the bot

```bash
python bot.py
```

On first run, a Chrome window will open — **log in to Reddit manually**. Your session will be saved for future runs.

## Menu Options

| Option | Description |
|--------|-------------|
| 1 | Find a relevant post and comment on it |
| 2 | Create a new promotional post |
| 3 | Upvote relevant posts |
| 4 | Run all actions once |
| 5 | Auto-pilot mode (runs on schedule) |
| 6 | Preview a comment without posting |
| 7 | Preview a post without posting |
| 8 | View activity log |
| 9 | View account stats |
| 10 | Select which niches to target |

## Tips

- Start with **option 6/7** to preview what the bot generates before going live
- Use **low rates** at first (1-2 comments/hr) to avoid detection
- **New accounts** need karma before they can post in most subs — warm them up manually first
- The bot adds random delays between actions automatically
- Check `bot.log` and `activity_log.json` to monitor activity
