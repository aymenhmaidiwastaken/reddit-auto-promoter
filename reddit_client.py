"""
Reddit client using real browser automation.
No credentials stored — opens browsers for manual login.
Sessions persist via Chrome profiles.
"""

import random
import time
import logging
import json
import os
from config import MIN_DELAY, MAX_DELAY
from browser_client import BrowserSession
from fingerprint import FingerprintManager
from timing import HumanTiming

logger = logging.getLogger("reddit_bot")


class AccountRotator:
    """Manages multiple Reddit accounts with browser sessions."""

    def __init__(self, num_accounts, chrome_path=None):
        self.clients = []
        self.current_index = 0
        self.fingerprint_mgr = FingerprintManager()
        self.timing = HumanTiming(speed_profile="normal")
        self.chrome_path = chrome_path
        self._init_clients(num_accounts)

    def _init_clients(self, num_accounts):
        sessions = []

        # Step 1: Launch all browsers
        print(f"\n  Launching {num_accounts} browser(s)...")
        for i in range(num_accounts):
            label = f"Account_{i+1}"
            fingerprint = self.fingerprint_mgr.get_profile(label)

            session = BrowserSession(
                account_label=label,
                fingerprint=fingerprint,
                timing=self.timing,
                chrome_path=self.chrome_path,
            )

            if not session.start():
                logger.error(f"Browser {i+1} failed to start")
                continue

            sessions.append(session)
            print(f"  Browser {i+1} opened.")

        if not sessions:
            raise RuntimeError("No browsers could be started. Check your Chrome installation.")

        # Step 2: Check which ones already have a saved session
        needs_login = []
        for session in sessions:
            print(f"  Checking {session.account_label} for saved session...", end=" ")
            if session.is_logged_in():
                display = session.username or session.account_label
                print(f"Already logged in as {display}!")
                self.clients.append({
                    "session": session,
                    "username": session.username or session.account_label,
                    "last_action": 0,
                    "action_count": 0,
                })
            else:
                print("Not logged in.")
                needs_login.append(session)

        # Step 3: For accounts that need login, open login page and wait
        if needs_login:
            print(f"\n  {len(needs_login)} account(s) need manual login.")
            print("  Opening Reddit login page in each browser...")
            print("  Log in manually in each browser window.")
            print("  You have 5 minutes per account.\n")

            for session in needs_login:
                session.open_login_page()

            # Wait for all to log in
            for session in needs_login:
                print(f"  Waiting for {session.account_label} to log in...", end=" ", flush=True)
                if session.wait_for_manual_login(timeout=300):
                    display = session.username or session.account_label
                    print(f"Logged in as {display}!")
                    self.clients.append({
                        "session": session,
                        "username": session.username or session.account_label,
                        "last_action": 0,
                        "action_count": 0,
                    })
                else:
                    print("Timed out. Skipping.")
                    session.close()

        if not self.clients:
            raise RuntimeError("No accounts were logged in. Cannot continue.")

        print(f"\n  {len(self.clients)} account(s) ready!\n")

    def get_next(self):
        """Get the next account in rotation, respecting cooldowns."""
        attempts = 0
        while attempts < len(self.clients):
            account = self.clients[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.clients)

            elapsed = time.time() - account["last_action"]
            if elapsed >= MIN_DELAY:
                return account

            attempts += 1

        shortest_wait = min(
            MIN_DELAY - (time.time() - acc["last_action"])
            for acc in self.clients
        )
        if shortest_wait > 0:
            logger.info(f"All accounts on cooldown. Waiting {shortest_wait:.0f}s...")
            time.sleep(shortest_wait)

        return self.clients[self.current_index]

    def mark_used(self, account):
        """Mark an account as recently used."""
        account["last_action"] = time.time()
        account["action_count"] += 1

    def close_all(self):
        """Close all browser sessions."""
        for acc in self.clients:
            try:
                acc["session"].close()
            except Exception:
                pass
        logger.info("All browser sessions closed")


class RedditBot:
    """Handles all Reddit interactions via browser automation."""

    HISTORY_FILE = "bot_history.json"

    def __init__(self, num_accounts, chrome_path=None):
        self.rotator = AccountRotator(num_accounts, chrome_path=chrome_path)
        self.timing = HumanTiming(speed_profile="normal")
        self._load_history()

    def _load_history(self):
        """Load persistent history of commented/posted items."""
        try:
            if os.path.exists(self.HISTORY_FILE):
                with open(self.HISTORY_FILE, "r") as f:
                    data = json.load(f)
                self.commented_posts = set(data.get("commented_posts", []))
                self.posted_subs = set(
                    tuple(x) for x in data.get("posted_subs", [])
                )
                logger.info(
                    f"Loaded history: {len(self.commented_posts)} commented, "
                    f"{len(self.posted_subs)} posted"
                )
            else:
                self.commented_posts = set()
                self.posted_subs = set()  # (subreddit, date) tuples
        except Exception as e:
            logger.warning(f"Could not load history: {e}")
            self.commented_posts = set()
            self.posted_subs = set()

    def _save_history(self):
        """Save history to disk so it persists across restarts."""
        try:
            # Keep last 2000 entries to prevent file bloat
            commented = list(self.commented_posts)[-2000:]
            posted = list(self.posted_subs)[-500:]
            with open(self.HISTORY_FILE, "w") as f:
                json.dump({
                    "commented_posts": commented,
                    "posted_subs": [list(x) for x in posted],
                }, f)
        except Exception as e:
            logger.warning(f"Could not save history: {e}")

    def _delay(self):
        """Smart delay between actions using human-like timing."""
        delay = self.timing.between_actions_delay()
        delay = max(MIN_DELAY, min(MAX_DELAY * 2, delay))
        self.timing.wait(delay, "between actions")

        should_break, break_duration = self.timing.should_take_break()
        if should_break:
            self.timing.wait(break_duration, "taking a natural break")
            self.timing.reset_session()

    def get_hot_posts(self, subreddit_name, limit=25):
        """Fetch hot posts from a subreddit via browser."""
        account = self.rotator.get_next()
        session = account["session"]
        try:
            posts = session.get_posts(subreddit_name, sort="hot", limit=limit)
            filtered = []
            for post in posts:
                if post["id"] not in self.commented_posts:
                    post["subreddit"] = subreddit_name
                    filtered.append(post)
            return filtered
        except Exception as e:
            logger.error(f"Error fetching hot posts from r/{subreddit_name}: {e}")
            return []

    def get_new_posts(self, subreddit_name, limit=15):
        """Fetch new posts from a subreddit via browser."""
        account = self.rotator.get_next()
        session = account["session"]
        try:
            posts = session.get_posts(subreddit_name, sort="new", limit=limit)
            filtered = []
            for post in posts:
                if post["id"] not in self.commented_posts:
                    post["subreddit"] = subreddit_name
                    filtered.append(post)
            return filtered
        except Exception as e:
            logger.error(f"Error fetching new posts from r/{subreddit_name}: {e}")
            return []

    def fetch_post_body(self, post):
        """Fetch the full body text of a post by navigating to it."""
        account = self.rotator.get_next()
        session = account["session"]
        try:
            return session.fetch_post_body(post)
        except Exception as e:
            logger.error(f"Error fetching post body: {e}")
            return ""

    def comment_on_post(self, post, comment_text):
        """Leave a comment on a post via browser."""
        account = self.rotator.get_next()
        session = account["session"]
        try:
            success = session.comment_on_post(post, comment_text)
            if success:
                self.commented_posts.add(post["id"])
                self.rotator.mark_used(account)
                self._save_history()
                logger.info(
                    f"[{account['username']}] Commented on "
                    f"'{post['title'][:50]}...' in r/{post.get('subreddit', '?')}"
                )
            return success
        except Exception as e:
            logger.error(f"Error commenting: {e}")
            return False

    def has_posted_recently(self, subreddit_name, days=3):
        """Check if we already posted in this sub recently."""
        from datetime import datetime, timedelta
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        for sub, date in self.posted_subs:
            if sub == subreddit_name and date >= cutoff:
                return True
        return False

    def create_post(self, subreddit_name, title, body):
        """Create a new post in a subreddit via browser."""
        # Check if we already posted in this sub recently
        if self.has_posted_recently(subreddit_name):
            logger.info(f"Already posted in r/{subreddit_name} recently, skipping")
            return None

        account = self.rotator.get_next()
        session = account["session"]
        try:
            success = session.create_post(subreddit_name, title, body)
            if success:
                from datetime import datetime
                self.posted_subs.add((subreddit_name, datetime.now().strftime("%Y-%m-%d")))
                self.rotator.mark_used(account)
                self._save_history()
                logger.info(
                    f"[{account['username']}] Created post "
                    f"'{title[:50]}...' in r/{subreddit_name}"
                )
            return success
        except Exception as e:
            logger.error(f"Error creating post in r/{subreddit_name}: {e}")
            return None

    def upvote_post(self, post):
        """Upvote a post via browser."""
        account = self.rotator.get_next()
        session = account["session"]
        try:
            success = session.upvote_post(post)
            if success:
                self.rotator.mark_used(account)
                logger.info(f"[{account['username']}] Upvoted '{post['title'][:50]}...'")
            return success
        except Exception as e:
            logger.error(f"Error upvoting: {e}")
            return False

    def get_stats(self):
        """Get usage stats for all accounts."""
        stats = []
        for acc in self.rotator.clients:
            stats.append({
                "username": acc["username"],
                "actions": acc["action_count"],
                "last_action": acc["last_action"],
            })
        return stats

    def close(self):
        """Close all browser sessions."""
        self.rotator.close_all()
