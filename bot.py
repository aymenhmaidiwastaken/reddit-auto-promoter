import random
import time
import logging
import json
import schedule
from datetime import datetime

from config import (
    SUBREDDITS, COMMENTS_PER_HOUR, POSTS_PER_HOUR,
    UPVOTES_PER_HOUR, PROMO_PRODUCT_NAME, CHROME_PATH
)
from reddit_client import RedditBot
from ollama_brain import generate_comment, generate_post, analyze_post_relevance, verify_comment_quality

import sys

class SafeStreamHandler(logging.StreamHandler):
    """Stream handler that replaces unencodable characters instead of crashing."""
    def emit(self, record):
        try:
            msg = self.format(record)
            stream = self.stream
            # Replace characters that can't be encoded by the console
            msg = msg.encode(stream.encoding or 'utf-8', errors='replace').decode(stream.encoding or 'utf-8', errors='replace')
            stream.write(msg + self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        SafeStreamHandler(),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ]
)
logger = logging.getLogger("reddit_bot")

# Track activity for reporting
activity_log = []


def log_activity(action, subreddit, details=""):
    entry = {
        "time": datetime.now().isoformat(),
        "action": action,
        "subreddit": subreddit,
        "details": details,
    }
    activity_log.append(entry)
    # Keep log file updated
    with open("activity_log.json", "w") as f:
        json.dump(activity_log[-500:], f, indent=2)


def run_comment_cycle(bot, niches=None):
    """Find relevant posts and comment on them."""
    if niches is None:
        niches = list(SUBREDDITS.keys())

    niche = random.choice(niches)
    subs = SUBREDDITS[niche]
    sub = random.choice(subs)
    sub_name = sub["name"].replace("r/", "")

    logger.info(f"--- Comment cycle: r/{sub_name} ({niche}) ---")

    # Mix of hot and new posts
    if random.random() < 0.4:
        posts = bot.get_new_posts(sub_name, limit=15)
        logger.info(f"Fetched {len(posts)} new posts")
    else:
        posts = bot.get_hot_posts(sub_name, limit=25)
        logger.info(f"Fetched {len(posts)} hot posts")

    if not posts:
        logger.warning(f"No posts found in r/{sub_name}")
        return

    # Score posts for relevance
    scored = []
    for post in posts[:10]:
        score = analyze_post_relevance(post["title"], post["body"], sub_name)
        scored.append((post, score))
        logger.info(f"  [{score}/10] {post['title'][:60]}")

    # Sort by relevance, pick from top candidates
    scored.sort(key=lambda x: x[1], reverse=True)
    best = scored[:3]

    if not best or best[0][1] < 3:
        logger.info("No sufficiently relevant posts found, engaging genuinely")
        post = random.choice(posts)
        promote = False
    else:
        post, score = random.choice(best)
        promote = score >= 7 and random.random() < 0.5

    # Fetch full post body if missing — critical for quality comments
    if not post.get("body"):
        logger.info("Fetching full post body for context...")
        post["body"] = bot.fetch_post_body(post)

    # Try generating a comment up to 3 times (may skip if quality too low)
    comment = None
    for attempt in range(3):
        comment = generate_comment(post["title"], post["body"], sub_name, promote=promote)

        if comment is None:
            logger.info(f"  Comment skipped (attempt {attempt+1}/3) — AI slop or not relevant")
            # Try a different post on retry
            if attempt < 2 and len(posts) > 1:
                post = random.choice(posts)
                if not post.get("body"):
                    post["body"] = bot.fetch_post_body(post)
                promote = False  # don't promote on retries
            continue

        # Layer 3: AI self-review — ask the model if this comment would get removed
        if not verify_comment_quality(comment, post["title"], post["body"], sub_name):
            logger.info(f"  Comment failed quality check (attempt {attempt+1}/3): {comment[:80]}...")
            comment = None
            continue

        break  # comment passed all checks

    if not comment:
        logger.warning("All comment attempts failed quality checks, skipping this cycle")
        return

    logger.info(f"Generated comment (passed all checks): {comment[:100]}...")

    if bot.comment_on_post(post, comment):
        log_activity("comment", sub_name, f"Post: {post['title'][:80]} | Comment: {comment[:100]}")
        logger.info("Comment posted successfully!")
    else:
        logger.error("Failed to post comment")


def run_post_cycle(bot, niches=None):
    """Create a promotional post in a relevant subreddit."""
    if niches is None:
        niches = list(SUBREDDITS.keys())

    niche = random.choice(niches)
    subs = SUBREDDITS[niche]

    # Prefer smaller subs for posts (less moderation, more visibility)
    smaller_subs = [s for s in subs if "K" in s.get("subscribers", "1M") and
                    int(s["subscribers"].replace("K", "").split(".")[0]) < 500]
    if smaller_subs:
        sub = random.choice(smaller_subs)
    else:
        sub = random.choice(subs)

    sub_name = sub["name"].replace("r/", "")
    logger.info(f"--- Post cycle: r/{sub_name} ({niche}) ---")

    title, body = generate_post(sub_name, niche)
    logger.info(f"Generated post: {title}")
    logger.info(f"Body: {body[:150]}...")

    result = bot.create_post(sub_name, title, body)
    if result:
        log_activity("post", sub_name, f"Title: {title}")
        logger.info("Post created successfully!")
    else:
        logger.error("Failed to create post")


def run_upvote_cycle(bot, niches=None):
    """Upvote relevant posts to boost visibility."""
    if niches is None:
        niches = list(SUBREDDITS.keys())

    niche = random.choice(niches)
    subs = SUBREDDITS[niche]
    sub = random.choice(subs)
    sub_name = sub["name"].replace("r/", "")

    posts = bot.get_new_posts(sub_name, limit=10)
    if not posts:
        return

    # Upvote a couple posts that mention our product or are in our space
    for post in posts[:3]:
        score = analyze_post_relevance(post["title"], post["body"], sub_name)
        if score >= 4:
            if bot.upvote_post(post):
                log_activity("upvote", sub_name, f"Post: {post['title'][:80]}")


def run_scheduled(bot, niches):
    """Main scheduled loop."""
    logger.info("=== Starting scheduled cycle ===")

    # Comments
    for _ in range(COMMENTS_PER_HOUR):
        try:
            run_comment_cycle(bot, niches)
            bot._delay()
        except Exception as e:
            logger.error(f"Comment cycle error: {e}")

    # Posts (less frequent)
    if random.random() < (POSTS_PER_HOUR / 3.0):  # spread out
        try:
            run_post_cycle(bot, niches)
            bot._delay()
        except Exception as e:
            logger.error(f"Post cycle error: {e}")

    # Upvotes
    for _ in range(min(UPVOTES_PER_HOUR, 2)):
        try:
            run_upvote_cycle(bot, niches)
            time.sleep(random.uniform(10, 30))
        except Exception as e:
            logger.error(f"Upvote cycle error: {e}")

    logger.info("=== Cycle complete ===")
    stats = bot.get_stats()
    for s in stats:
        logger.info(f"  {s['username']}: {s['actions']} total actions")


def interactive_menu(bot, initial_niches=None):
    """Interactive CLI menu for manual control."""
    niches = initial_niches or list(SUBREDDITS.keys())

    while True:
        nice_niches = [n.replace("_", " ").title() for n in niches]
        print("\n" + "=" * 50)
        print(f"  REDDIT BOT - {PROMO_PRODUCT_NAME}")
        print("=" * 50)
        print(f"  Targeting: {', '.join(nice_niches)}")
        print(f"  Accounts: {len(bot.rotator.clients)}")
        print("-" * 50)
        print(f"  1) Run comment cycle ({COMMENTS_PER_HOUR} comments)")
        print(f"  2) Run post cycle ({POSTS_PER_HOUR} post)")
        print(f"  3) Run upvote cycle ({UPVOTES_PER_HOUR} upvotes)")
        print("  4) Run full cycle (comments + post + upvotes)")
        print("  5) Start auto-pilot (runs continuously)")
        print("  6) Preview comment (generate without posting)")
        print("  7) Preview post (generate without posting)")
        print("  8) View activity log")
        print("  9) View account stats")
        print("  10) Select niches to target")
        print("  0) Exit")
        print("-" * 50)

        choice = input("  Choose: ").strip()

        if choice == "1":
            print(f"\n  Running {COMMENTS_PER_HOUR} comment(s)...")
            for i in range(COMMENTS_PER_HOUR):
                print(f"\n  --- Comment {i+1}/{COMMENTS_PER_HOUR} ---")
                try:
                    run_comment_cycle(bot, niches)
                    if i < COMMENTS_PER_HOUR - 1:
                        bot._delay()
                except Exception as e:
                    logger.error(f"Comment cycle error: {e}")

        elif choice == "2":
            print(f"\n  Running {POSTS_PER_HOUR} post(s)...")
            for i in range(POSTS_PER_HOUR):
                print(f"\n  --- Post {i+1}/{POSTS_PER_HOUR} ---")
                try:
                    run_post_cycle(bot, niches)
                    if i < POSTS_PER_HOUR - 1:
                        bot._delay()
                except Exception as e:
                    logger.error(f"Post cycle error: {e}")

        elif choice == "3":
            print(f"\n  Running {UPVOTES_PER_HOUR} upvote(s)...")
            for i in range(UPVOTES_PER_HOUR):
                print(f"\n  --- Upvote {i+1}/{UPVOTES_PER_HOUR} ---")
                try:
                    run_upvote_cycle(bot, niches)
                    if i < UPVOTES_PER_HOUR - 1:
                        time.sleep(random.uniform(10, 30))
                except Exception as e:
                    logger.error(f"Upvote cycle error: {e}")

        elif choice == "4":
            print(f"\n  Running full cycle continuously...")
            print(f"  {COMMENTS_PER_HOUR} comments/hr, {POSTS_PER_HOUR} posts/hr, {UPVOTES_PER_HOUR} upvotes/hr")
            print("  Press Ctrl+C to stop\n")
            try:
                while True:
                    run_scheduled(bot, niches)
                    pause = random.uniform(30, 120)
                    logger.info(f"Cycle done. Next cycle in {pause:.0f}s...")
                    time.sleep(pause)
            except KeyboardInterrupt:
                print("\n  Stopped.")

        elif choice == "5":
            print(f"\n  Starting auto-pilot mode...")
            print(f"  {COMMENTS_PER_HOUR} comments/hr, {POSTS_PER_HOUR} posts/hr, {UPVOTES_PER_HOUR} upvotes/hr")
            print("  Press Ctrl+C to stop\n")
            schedule.every(60 // max(COMMENTS_PER_HOUR, 1)).minutes.do(
                run_scheduled, bot=bot, niches=niches
            )
            try:
                run_scheduled(bot, niches)  # run once immediately
                while True:
                    schedule.run_pending()
                    time.sleep(30)
            except KeyboardInterrupt:
                print("\n  Auto-pilot stopped.")
                schedule.clear()

        elif choice == "6":
            niche = random.choice(niches)
            subs = SUBREDDITS[niche]
            sub = random.choice(subs)
            sub_name = sub["name"].replace("r/", "")
            posts = bot.get_hot_posts(sub_name, limit=10)
            if posts:
                post = random.choice(posts[:5])
                # Fetch full body if not available from listing
                if not post.get("body"):
                    print(f"\n  Fetching post content...")
                    post["body"] = bot.fetch_post_body(post)
                print(f"\n  Sub: r/{sub_name}")
                print(f"  Post: {post['title']}")
                if post.get("body"):
                    body_preview = post["body"][:500]
                    if len(post["body"]) > 500:
                        body_preview += "..."
                    print(f"  Body: {body_preview}")
                else:
                    print("  Body: (no text)")
                print()
                comment = generate_comment(post["title"], post["body"], sub_name, promote=True)
                if comment is None:
                    print("  [BLOCKED] Comment was AI slop or not relevant — would not post")
                else:
                    quality_ok = verify_comment_quality(comment, post["title"], post["body"], sub_name)
                    status = "PASS" if quality_ok else "FAIL"
                    print(f"  Generated comment [{status}]:")
                    print(f"  > {comment}")
                print()
            else:
                print("  No posts found. Try again.")

        elif choice == "7":
            niche = random.choice(niches)
            subs = SUBREDDITS[niche]
            sub = random.choice(subs)
            sub_name = sub["name"].replace("r/", "")
            title, body = generate_post(sub_name, niche)
            print(f"\n  Sub: r/{sub_name}")
            print(f"  Title: {title}")
            print(f"  Body: {body}\n")

        elif choice == "8":
            if activity_log:
                print(f"\n  Last 10 actions:")
                for entry in activity_log[-10:]:
                    print(f"  [{entry['time'][:19]}] {entry['action']} in r/{entry['subreddit']}: {entry['details'][:60]}")
            else:
                print("  No activity yet.")

        elif choice == "9":
            stats = bot.get_stats()
            print("\n  Account Stats:")
            for s in stats:
                print(f"  {s['username']}: {s['actions']} actions")

        elif choice == "10":
            niches = select_niches()

        elif choice == "0":
            print("  Bye!")
            break

        else:
            print("  Invalid choice")


def select_niches():
    """Let user pick which niches to target at startup."""
    all_niches = list(SUBREDDITS.keys())

    print("\n  Which niches do you want to target?")
    print("-" * 50)
    for i, niche in enumerate(all_niches):
        nice_name = niche.replace("_", " ").title()
        sub_count = len(SUBREDDITS[niche])
        subs_preview = ", ".join(s["name"] for s in SUBREDDITS[niche][:3])
        print(f"  {i+1}) {nice_name} ({sub_count} subs)")
        print(f"     {subs_preview}...")
    print(f"  {len(all_niches)+1}) All of the above")
    print("-" * 50)

    while True:
        sel = input("  Enter numbers separated by commas: ").strip()
        try:
            indices = [int(x.strip()) for x in sel.split(",")]

            # Check if "All" was selected
            if len(all_niches) + 1 in indices:
                print(f"  Selected: ALL niches")
                return all_niches

            selected = []
            for idx in indices:
                if 1 <= idx <= len(all_niches):
                    selected.append(all_niches[idx - 1])
                else:
                    print(f"  Invalid number: {idx}")
                    selected = []
                    break

            if selected:
                nice_names = [n.replace("_", " ").title() for n in selected]
                print(f"  Selected: {', '.join(nice_names)}")
                return selected
        except ValueError:
            pass
        print("  Invalid input. Enter numbers like: 1,3,5")


if __name__ == "__main__":
    print("=" * 50)
    print(f"  REDDIT BOT - {PROMO_PRODUCT_NAME}")
    print("=" * 50)
    print()
    print("  No credentials needed!")
    print("  Browsers will open for you to log in manually.")
    print("  Sessions are saved — you only log in once.")
    print()

    # Ask how many accounts
    while True:
        try:
            num = input("  How many Reddit accounts? ").strip()
            num_accounts = int(num)
            if num_accounts < 1:
                print("  Need at least 1 account.")
                continue
            break
        except ValueError:
            print("  Enter a number.")

    # Select niches before launching browsers
    niches = select_niches()

    bot = None
    try:
        bot = RedditBot(num_accounts=num_accounts, chrome_path=CHROME_PATH or None)
        interactive_menu(bot, initial_niches=niches)
    except RuntimeError as e:
        logger.error(f"Fatal: {e}")
        print(f"\nError: {e}")
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        if bot:
            bot.close()
            print("All browsers closed.")
