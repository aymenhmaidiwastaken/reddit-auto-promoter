import os
import json
from dotenv import load_dotenv

load_dotenv()

# Load subreddit database
def load_subreddits():
    with open(os.path.join(os.path.dirname(__file__), "subreddits.json"), "r") as f:
        return json.load(f)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

PROMO_PRODUCT_NAME = os.getenv("PROMO_PRODUCT_NAME", "MyProduct")
PROMO_PRODUCT_URL = os.getenv("PROMO_PRODUCT_URL", "https://example.com")
PROMO_PRODUCT_DESCRIPTION = os.getenv("PROMO_PRODUCT_DESCRIPTION", "A cool product")

COMMENTS_PER_HOUR = int(os.getenv("COMMENTS_PER_HOUR", "3"))
POSTS_PER_HOUR = int(os.getenv("POSTS_PER_HOUR", "1"))
UPVOTES_PER_HOUR = int(os.getenv("UPVOTES_PER_HOUR", "5"))

MIN_DELAY = int(os.getenv("MIN_DELAY_SECONDS", "60"))
MAX_DELAY = int(os.getenv("MAX_DELAY_SECONDS", "300"))

# Chrome path (optional, auto-detected if not set)
CHROME_PATH = os.getenv("CHROME_PATH", "")

# Timing profile: "fast", "normal", "slow", "careful"
TIMING_PROFILE = os.getenv("TIMING_PROFILE", "normal")

SUBREDDITS = load_subreddits()
