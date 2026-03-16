<p align="center">
  <img src="Logo.png" alt="Reddit Promotion Automation Tool" width="400"/>
</p>

<h1 align="center">Reddit Auto Promoter</h1>
  
<p align="center">
  <b>AI-powered Reddit marketing bot that generates human-like comments and posts to promote your product across targeted subreddits.</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.8+-blue.svg" alt="Python 3.8+"/>
  <img src="https://img.shields.io/badge/ai-ollama%20%2F%20llama3-green.svg" alt="Ollama"/>
  <img src="https://img.shields.io/badge/browser-undetected--chromedriver-orange.svg" alt="Undetected Chromedriver"/>
  <img src="https://img.shields.io/badge/license-MIT-purple.svg" alt="License"/>
</p>

---

## What It Does

This bot automates Reddit marketing by browsing real subreddits, finding relevant posts, and engaging with AI-generated comments and posts that subtly promote your product — all through a real Chrome browser to avoid detection.

### Key Features

- **AI-Powered Content** — Uses local Ollama (Llama 3) to generate context-aware, human-like comments and posts tailored to each subreddit's culture
- **Real Browser Automation** — Runs a visible Chrome browser with `undetected-chromedriver`, no API abuse
- **Multi-Account Rotation** — Rotate between multiple Reddit accounts with cooldown tracking
- **Anti-Detection Suite** — Browser fingerprint spoofing, human-like mouse movements, realistic typing speed, random delays, and typo injection
- **Smart Promotion** — AI scores post relevance (1-10) and only promotes when it naturally fits the conversation
- **3-Layer Quality Filter** — Pattern-based slop detection (100+ patterns), keyword relevance check, and AI self-review to ensure every comment looks genuine
- **60+ Target Subreddits** — Pre-configured across 6 niches: Mobile Dev, Startups, AI/ML, Game Dev, UI/UX, and Tech General
- **Auto-Pilot Mode** — Set it and forget it with scheduled comment, post, and upvote cycles
- **Activity Logging** — Full history tracking to prevent duplicate comments and monitor performance

---

## How It Works

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Chrome      │────▶│  Reddit      │────▶│  Ollama (Local) │
│  Browser     │     │  Browsing    │     │  AI Generation  │
│  (Real)      │◀────│  & Scraping  │◀────│  & Quality Check│
└─────────────┘     └──────────────┘     └─────────────────┘
```

1. **Opens a real Chrome browser** and loads your saved Reddit session
2. **Browses target subreddits** and finds relevant posts
3. **AI generates a response** that fits the subreddit's tone and context
4. **Quality filters** reject anything that looks bot-like or generic
5. **Posts the comment/post** with human-like typing and timing
6. **Logs everything** and rotates to the next account

---

## Quick Start

### Prerequisites

- Python 3.8+
- Google Chrome installed
- [Ollama](https://ollama.ai) running locally with `llama3`

### Installation

```bash
# Clone the repo
git clone https://github.com/aymenhmaidiwastaken/reddit-auto-promoter.git
cd reddit-auto-promoter

# Install dependencies
pip install -r requirements.txt

# Pull the AI model
ollama pull llama3

# Start Ollama server
ollama serve
```

### Configuration

Create a `.env` file in the project root:

```env
# Product to promote
PROMO_PRODUCT_NAME=YourProduct
PROMO_PRODUCT_URL=https://yourproduct.com
PROMO_PRODUCT_DESCRIPTION=Brief description of what your product does

# AI settings
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3

# Rate limits (keep low to avoid detection)
COMMENTS_PER_HOUR=3
POSTS_PER_HOUR=1
UPVOTES_PER_HOUR=5

# Timing: fast, normal, slow, careful
TIMING_PROFILE=normal
```

### Run

```bash
python bot.py
```

On first run, the bot will:
1. Ask how many Reddit accounts to use
2. Open Chrome for each account
3. Wait for you to **manually log in** to Reddit (sessions are saved)
4. Present the interactive menu

---

## Menu Options

| # | Action | Description |
|---|--------|-------------|
| 1 | Comment Cycle | Find relevant posts and comment on them |
| 2 | Post Cycle | Create a new promotional post |
| 3 | Upvote Cycle | Upvote relevant posts in target subreddits |
| 4 | Full Cycle | Run all actions once |
| 5 | Auto-Pilot | Schedule all actions to run automatically |
| 6 | Preview Comment | See what the AI generates without posting |
| 7 | Preview Post | Preview a post without publishing |
| 8 | Activity Log | View recent bot actions |
| 9 | Account Stats | Check account cooldowns and usage |
| 10 | Select Niches | Choose which subreddit categories to target |

---

## Target Niches

| Niche | Example Subreddits |
|-------|--------------------|
| Mobile App Dev | r/androiddev, r/reactnative, r/FlutterDev |
| Startups | r/startups, r/Entrepreneur, r/SaaS, r/indiehackers |
| AI & ML | r/artificial, r/ChatGPT, r/LocalLLaMA |
| Game Dev | r/gamedev, r/Unity3D, r/unrealengine |
| UI/UX Design | r/UI_Design, r/userexperience, r/web_design |
| Tech General | r/programming, r/webdev, r/learnprogramming |

You can customize target subreddits by editing `subreddits.json`.

---

## Anti-Detection Features

| Feature | Description |
|---------|-------------|
| Browser Fingerprinting | Spoofs screen resolution, timezone, user agent, WebGL, fonts |
| Human-Like Timing | Gaussian-distributed delays with fatigue and break simulation |
| Realistic Typing | Variable WPM (25-120), natural pauses, occasional typos |
| Mouse Simulation | Bezier curve mouse movements |
| AI Slop Filter | 100+ patterns to catch and reject generic AI-sounding text |
| Session Persistence | Chrome profiles save login sessions — no credentials stored |

---

## Project Structure

```
├── bot.py               # Main entry point & interactive menu
├── reddit_client.py     # Account rotation & action orchestration
├── browser_client.py    # Selenium browser automation
├── ollama_brain.py      # AI content generation & quality checks
├── fingerprint.py       # Browser fingerprint management
├── timing.py            # Human-like timing simulation
├── config.py            # Configuration loader
├── subreddits.json      # Target subreddit database
├── requirements.txt     # Python dependencies
└── .env                 # Your configuration (not tracked)
```

---

## Tips

- **Start with preview mode** (options 6/7) to see what the bot generates before going live
- **Keep rates low** — 1-2 comments/hour is safest for new setups
- **Warm up new accounts** manually before using them with the bot
- **Monitor logs** — check `bot.log` and `activity_log.json` regularly
- **Use the `careful` timing profile** for maximum stealth

---

## Disclaimer

This tool is provided for **educational purposes only**. Automated interaction with Reddit may violate their [Terms of Service](https://www.redditinc.com/policies/user-agreement). Use at your own risk. The authors are not responsible for any consequences resulting from the use of this tool.

---

## License

MIT License — see [LICENSE](LICENSE) for details.
