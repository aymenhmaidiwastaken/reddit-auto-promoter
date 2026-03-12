"""
Browser automation client using undetected-chromedriver.
Real visible Chrome browser with anti-detection measures.
Manual login — no credentials stored.
"""

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException,
    ElementClickInterceptedException, StaleElementReferenceException
)
import random
import time
import math
import logging
import os
import subprocess
import re as _re

from fingerprint import FingerprintProfile, FingerprintManager
from timing import HumanTiming

logger = logging.getLogger("reddit_bot")


class HumanMouse:
    """Simulates human-like mouse movements using Bezier curves."""

    @staticmethod
    def bezier_curve(start, end, control_points=2, num_steps=25):
        """Generate points along a bezier curve for natural mouse movement."""
        points = [start]

        controls = []
        for _ in range(control_points):
            cx = start[0] + (end[0] - start[0]) * random.uniform(0.2, 0.8) + random.randint(-50, 50)
            cy = start[1] + (end[1] - start[1]) * random.uniform(0.2, 0.8) + random.randint(-50, 50)
            controls.append((cx, cy))

        all_points = [start] + controls + [end]
        n = len(all_points) - 1

        for i in range(1, num_steps + 1):
            t = i / num_steps
            t = t * t * (3 - 2 * t)  # smoothstep

            x = 0
            y = 0
            for j, point in enumerate(all_points):
                coeff = math.comb(n, j) * (t ** j) * ((1 - t) ** (n - j))
                x += coeff * point[0]
                y += coeff * point[1]

            x += random.gauss(0, 0.5)
            y += random.gauss(0, 0.5)

            points.append((int(x), int(y)))

        return points

    @staticmethod
    def move_to_element(driver, element, timing):
        """Move mouse to element with human-like movement."""
        try:
            actions = ActionChains(driver)
            size = element.size
            x_offset = random.randint(-size['width'] // 4, size['width'] // 4)
            y_offset = random.randint(-size['height'] // 4, size['height'] // 4)

            actions.move_to_element_with_offset(element, x_offset, y_offset)
            time.sleep(timing.click_delay())
            actions.perform()
        except Exception:
            ActionChains(driver).move_to_element(element).perform()


class HumanKeyboard:
    """Simulates human-like keyboard input."""

    @staticmethod
    def type_text(element, text, timing):
        """Type text with realistic speed and occasional errors."""
        profile = timing._get_profile()
        wpm = random.uniform(*profile["typing_wpm"])
        base_delay = 60 / (wpm * 5)

        for i, char in enumerate(text):
            delay = base_delay * random.uniform(0.5, 1.8)

            if i > 0 and text[i - 1] in ".!?,;:\n":
                delay += random.uniform(0.3, 1.0)

            if char == " ":
                delay *= random.uniform(1.0, 2.0)

            if random.random() < 0.03 and char.isalpha():
                wrong = random.choice("abcdefghijklmnopqrstuvwxyz")
                element.send_keys(wrong)
                time.sleep(random.uniform(0.1, 0.4))
                element.send_keys(Keys.BACKSPACE)
                time.sleep(random.uniform(0.05, 0.2))

            element.send_keys(char)
            time.sleep(delay)

            if random.random() < 0.02:
                time.sleep(random.uniform(0.5, 2.0))


class BrowserSession:
    """Manages a single browser session for one Reddit account."""

    REDDIT_URL = "https://www.reddit.com"
    OLD_REDDIT_URL = "https://old.reddit.com"

    def __init__(self, account_label, fingerprint, timing, chrome_path=None):
        self.account_label = account_label  # e.g. "Account 1"
        self.username = None  # detected after manual login
        self.fingerprint = fingerprint
        self.timing = timing
        self.chrome_path = chrome_path
        self.driver = None
        self.logged_in = False

    def _detect_chrome_version(self):
        """Detect installed Chrome major version."""
        # Common Chrome paths on Windows
        paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        ]
        if self.chrome_path:
            paths.insert(0, self.chrome_path)

        for path in paths:
            if os.path.exists(path):
                try:
                    result = subprocess.run(
                        [path, "--version"],
                        capture_output=True, text=True, timeout=10
                    )
                    match = _re.search(r"(\d+)\.", result.stdout)
                    if match:
                        return int(match.group(1))
                except Exception:
                    pass

        # Fallback: try registry on Windows
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Google\Chrome\BLBeacon"
            )
            version, _ = winreg.QueryValueEx(key, "version")
            winreg.CloseKey(key)
            match = _re.search(r"(\d+)\.", version)
            if match:
                return int(match.group(1))
        except Exception:
            pass

        return None

    def _kill_stale_chrome(self):
        """Kill any Chrome processes using our profile directory."""
        profile_dir = os.path.join(
            os.path.dirname(__file__), "chrome_profiles", self.account_label.replace(" ", "_")
        )
        try:
            # On Windows, find chrome processes and kill ones using our profile
            result = subprocess.run(
                ["wmic", "process", "where", "name='chrome.exe'", "get",
                 "processid,commandline"],
                capture_output=True, text=True, timeout=10
            )
            for line in result.stdout.split("\n"):
                if profile_dir.replace("\\", "/") in line or profile_dir in line:
                    match = _re.search(r"(\d+)\s*$", line.strip())
                    if match:
                        pid = match.group(1)
                        subprocess.run(["taskkill", "/F", "/PID", pid],
                                       capture_output=True, timeout=5)
                        logger.info(f"Killed stale Chrome process (PID {pid})")
                        time.sleep(1)
        except Exception:
            pass

        # Also remove lock file if it exists
        lock_file = os.path.join(profile_dir, "lockfile")
        singleton_lock = os.path.join(profile_dir, "SingletonLock")
        for f in [lock_file, singleton_lock]:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except Exception:
                pass

    def start(self):
        """Launch browser with anti-detection settings. Retries on failure."""
        # Detect Chrome version first (only need to do once)
        chrome_version = self._detect_chrome_version()
        if chrome_version:
            logger.info(f"Detected Chrome version: {chrome_version}")

        max_retries = 2
        for attempt in range(max_retries + 1):
            if attempt > 0:
                logger.info(f"Retry {attempt}/{max_retries} — cleaning up and trying again...")
                self._kill_stale_chrome()
                time.sleep(3)

            options = uc.ChromeOptions()

            options.add_argument(f"--window-size={self.fingerprint.screen_width},{self.fingerprint.screen_height}")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--disable-infobars")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--no-first-run")
            options.add_argument("--no-default-browser-check")
            options.add_argument("--disable-popup-blocking")
            options.add_argument(f"--lang={self.fingerprint.languages[0]}")
            options.add_argument(f"--timezone={self.fingerprint.timezone}")

            # Separate profile per account (persists cookies/login across runs)
            profile_dir = os.path.join(
                os.path.dirname(__file__), "chrome_profiles", self.account_label.replace(" ", "_")
            )
            os.makedirs(profile_dir, exist_ok=True)
            options.add_argument(f"--user-data-dir={profile_dir}")

            prefs = {
                "credentials_enable_service": False,
                "profile.password_manager_enabled": False,
                "profile.default_content_setting_values.notifications": 2,
            }
            options.add_experimental_option("prefs", prefs)

            try:
                kwargs = {
                    "options": options,
                    "use_subprocess": True,
                }
                if self.chrome_path:
                    kwargs["browser_executable_path"] = self.chrome_path
                if chrome_version:
                    kwargs["version_main"] = chrome_version

                self.driver = uc.Chrome(**kwargs)
                self._inject_stealth()

                logger.info(f"Browser started for {self.account_label}")
                return True

            except Exception as e:
                logger.error(f"Failed to start browser for {self.account_label} (attempt {attempt+1}): {e}")
                # Clean up any partial driver
                try:
                    if self.driver:
                        self.driver.quit()
                        self.driver = None
                except Exception:
                    pass

        return False

    def _inject_stealth(self):
        """Inject fingerprint spoofing JavaScript."""
        stealth_js = self.fingerprint.get_stealth_js()
        try:
            self.driver.execute_script(stealth_js)
            self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": stealth_js
            })
            logger.info(f"Stealth fingerprint injected for {self.account_label}")
        except Exception as e:
            logger.warning(f"Could not inject stealth scripts: {e}")

    def is_logged_in(self):
        """Check if the browser is already logged into Reddit (from saved cookies)."""
        try:
            self.driver.get(self.REDDIT_URL)
            time.sleep(3)

            # Look for logged-in indicators
            indicators = [
                (By.CSS_SELECTOR, '[data-testid="user-drawer-button"]'),
                (By.CSS_SELECTOR, '#USER_DROPDOWN_ID'),
                (By.CSS_SELECTOR, 'button[id*="USER"]'),
                (By.CSS_SELECTOR, 'a[href*="/user/"]'),
            ]

            for by, selector in indicators:
                try:
                    elem = self.driver.find_element(by, selector)
                    if elem:
                        self.logged_in = True
                        self._detect_username()
                        return True
                except NoSuchElementException:
                    continue

            # Check cookies
            cookies = self.driver.get_cookies()
            for cookie in cookies:
                if cookie.get("name") in ["reddit_session", "token_v2", "session_tracker"]:
                    self.logged_in = True
                    self._detect_username()
                    return True

            return False
        except Exception:
            return False

    def _detect_username(self):
        """Try to detect the logged-in username from the page (no extra navigation)."""
        try:
            # Try user profile link on current page
            selectors = [
                'a[href*="/user/"]',
                '[data-testid="user-drawer-button"]',
            ]
            for sel in selectors:
                try:
                    elems = self.driver.find_elements(By.CSS_SELECTOR, sel)
                    for elem in elems:
                        href = elem.get_attribute("href") or ""
                        if "/user/" in href:
                            parts = href.split("/user/")
                            if len(parts) > 1:
                                name = parts[1].strip("/").split("/")[0].split("?")[0]
                                if name and name not in ("me", ""):
                                    self.username = name
                                    return
                        text = elem.text.strip()
                        if text and text.startswith("u/"):
                            self.username = text[2:]
                            return
                except NoSuchElementException:
                    continue
        except Exception:
            pass

        if not self.username:
            self.username = self.account_label

    def open_login_page(self):
        """Navigate to Reddit login page for manual login."""
        self.driver.get(f"{self.REDDIT_URL}/login")

    def wait_for_manual_login(self, timeout=300, check_interval=3):
        """
        Wait for the user to manually log in.
        Polls every check_interval seconds, up to timeout seconds.
        Returns True if login detected, False if timed out.
        """
        start = time.time()
        while time.time() - start < timeout:
            try:
                current_url = self.driver.current_url

                # If redirected away from login, probably logged in
                if "/login" not in current_url and "reddit.com" in current_url:
                    time.sleep(2)  # let page settle
                    if self._check_logged_in_indicators():
                        self.logged_in = True
                        self._detect_username()
                        return True

                # Also check indicators on the login page itself (some flows stay on same URL)
                if self._check_logged_in_indicators():
                    self.logged_in = True
                    self._detect_username()
                    return True

            except Exception:
                pass

            time.sleep(check_interval)

        return False

    def _check_logged_in_indicators(self):
        """Quick check for login indicators without navigating."""
        indicators = [
            (By.CSS_SELECTOR, '[data-testid="user-drawer-button"]'),
            (By.CSS_SELECTOR, '#USER_DROPDOWN_ID'),
            (By.CSS_SELECTOR, 'button[id*="USER"]'),
        ]
        for by, selector in indicators:
            try:
                elem = self.driver.find_element(by, selector)
                if elem and elem.is_displayed():
                    return True
            except NoSuchElementException:
                continue

        # Check cookies
        try:
            cookies = self.driver.get_cookies()
            for cookie in cookies:
                if cookie.get("name") in ["reddit_session", "token_v2", "session_tracker"]:
                    return True
        except Exception:
            pass

        return False

    def is_alive(self):
        """Check if the browser session is still active."""
        try:
            _ = self.driver.current_url
            return True
        except Exception:
            return False

    def reconnect(self):
        """Restart the browser if the session died."""
        logger.warning(f"Browser session lost for {self.account_label}. Reconnecting...")
        try:
            if self.driver:
                try:
                    self.driver.quit()
                except Exception:
                    pass
                self.driver = None
        except Exception:
            pass

        if self.start():
            # Profile dir has saved cookies, so check if still logged in
            time.sleep(2)
            if self.is_logged_in():
                logger.info(f"Reconnected and still logged in as {self.username}")
                return True
            else:
                logger.warning(f"Reconnected but not logged in. Opening login page...")
                self.open_login_page()
                if self.wait_for_manual_login(timeout=120):
                    return True
                else:
                    logger.error(f"Could not re-login {self.account_label}")
                    return False
        return False

    def _ensure_alive(self):
        """Ensure browser is alive, reconnect if needed. Returns True if usable."""
        if not self.driver or not self.is_alive():
            return self.reconnect()
        return True

    def navigate_to_subreddit(self, subreddit_name):
        """Navigate to a subreddit with human-like browsing."""
        if not self._ensure_alive():
            return
        url = f"{self.REDDIT_URL}/r/{subreddit_name}"
        self.driver.get(url)
        time.sleep(self.timing.page_load_wait())
        self._human_scroll(scroll_count=random.randint(1, 3))

    def get_posts(self, subreddit_name, sort="hot", limit=15):
        """Fetch posts from a subreddit by browsing it."""
        if not self._ensure_alive():
            return []
        if sort == "new":
            url = f"{self.REDDIT_URL}/r/{subreddit_name}/new/"
        else:
            url = f"{self.REDDIT_URL}/r/{subreddit_name}/hot/"

        self.driver.get(url)

        # Wait for posts to actually load (up to 15s)
        try:
            WebDriverWait(self.driver, 15).until(
                lambda d: d.execute_script(
                    "return document.querySelectorAll('shreddit-post, [data-testid=\"post-container\"], .Post, .thing.link').length > 0"
                )
            )
        except TimeoutException:
            logger.warning(f"Timed out waiting for posts to load in r/{subreddit_name}")

        time.sleep(random.uniform(1, 2))
        self._human_scroll(scroll_count=random.randint(2, 5))
        time.sleep(random.uniform(1, 2))

        # Use JavaScript to extract post data — works with shreddit-post shadow DOM
        posts = self._extract_posts_via_js(subreddit_name, limit)

        # Fallback: if JS extraction found nothing, try old-school DOM
        if not posts:
            posts = self._extract_posts_via_dom(subreddit_name, limit)

        logger.info(f"Found {len(posts)} posts in r/{subreddit_name}")
        return posts

    def _extract_posts_via_js(self, subreddit_name, limit):
        """Extract posts using JavaScript — handles shreddit-post web components."""
        try:
            js_code = """
            const posts = [];
            // New Reddit: shreddit-post elements have attributes with all data
            document.querySelectorAll('shreddit-post').forEach(el => {
                const title = el.getAttribute('post-title') || '';
                const permalink = el.getAttribute('permalink') || el.getAttribute('content-href') || '';
                const postId = el.getAttribute('id') || el.getAttribute('thingid') || '';
                const score = el.getAttribute('score') || '0';
                const commentCount = el.getAttribute('comment-count') || '0';

                if (title && permalink) {
                    posts.push({
                        id: postId,
                        title: title,
                        body: '',
                        permalink: permalink,
                        score: parseInt(score) || 0,
                        num_comments: parseInt(commentCount) || 0,
                        url: permalink.startsWith('http') ? permalink : 'https://www.reddit.com' + permalink,
                    });
                }
            });
            return posts;
            """
            raw_posts = self.driver.execute_script(js_code)

            if not raw_posts:
                return []

            posts = []
            for p in raw_posts[:limit]:
                if p.get("title"):
                    p["subreddit"] = subreddit_name
                    p["element"] = None
                    posts.append(p)
            return posts

        except Exception as e:
            logger.debug(f"JS post extraction failed: {e}")
            return []

    def _extract_posts_via_dom(self, subreddit_name, limit):
        """Fallback: extract posts via traditional DOM selectors."""
        posts = []
        try:
            # Try old Reddit selectors
            selectors = [
                '[data-testid="post-container"]',
                '.Post',
                '.thing.link',
            ]
            post_elements = []
            for selector in selectors:
                try:
                    post_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if post_elements:
                        break
                except Exception:
                    continue

            for elem in post_elements[:limit]:
                try:
                    title = ""
                    for sel in ['h3', '.title a', 'a.title', '[data-testid="post-title"]']:
                        try:
                            title_elem = elem.find_element(By.CSS_SELECTOR, sel)
                            title = title_elem.text.strip()
                            if title:
                                break
                        except NoSuchElementException:
                            continue

                    if not title:
                        continue

                    body = ""
                    for sel in ['[data-testid="post-body"]', '.md', '.post-content']:
                        try:
                            body_elem = elem.find_element(By.CSS_SELECTOR, sel)
                            body = body_elem.text.strip()
                            if body:
                                break
                        except NoSuchElementException:
                            continue

                    url = ""
                    try:
                        link = elem.find_element(By.CSS_SELECTOR, 'a[data-click-id="body"], a.title')
                        url = link.get_attribute("href") or ""
                    except NoSuchElementException:
                        pass

                    post_id = elem.get_attribute("id") or elem.get_attribute("data-fullname") or ""

                    posts.append({
                        "id": post_id,
                        "title": title,
                        "body": body,
                        "score": 0,
                        "num_comments": 0,
                        "url": url,
                        "subreddit": subreddit_name,
                        "element": elem,
                    })
                except (StaleElementReferenceException, Exception):
                    continue
        except Exception as e:
            logger.error(f"DOM post extraction failed: {e}")

        return posts

    def fetch_post_body(self, post):
        """Navigate to a post and scrape its full body text."""
        if not self._ensure_alive():
            return ""
        try:
            url = post.get("url", "")
            if not url or url == "https://www.reddit.com":
                return ""

            self.driver.get(url)

            # Wait for post content to load
            try:
                WebDriverWait(self.driver, 15).until(
                    lambda d: d.execute_script(
                        "return document.querySelectorAll('shreddit-post, [data-testid=\"post-container\"]').length > 0"
                    )
                )
            except TimeoutException:
                pass
            time.sleep(random.uniform(1, 2))

            # Try JS extraction first (shreddit elements)
            body = self.driver.execute_script("""
                // Try multiple selectors for post body
                const selectors = [
                    '[data-testid="post-body"]',
                    '[slot="text-body"]',
                    '.Post .md',
                    '.post-content',
                    'div[data-click-id="text"]',
                    '.expando .md',
                ];
                for (const sel of selectors) {
                    const el = document.querySelector(sel);
                    if (el && el.innerText.trim()) return el.innerText.trim();
                }
                // Try shreddit-post body
                const shredditPost = document.querySelector('shreddit-post');
                if (shredditPost) {
                    const bodyEl = shredditPost.querySelector('[slot="text-body"]');
                    if (bodyEl) return bodyEl.innerText.trim();
                }
                return '';
            """) or ""

            return body

        except Exception as e:
            logger.debug(f"Failed to fetch post body: {e}")
            return ""

    def comment_on_post(self, post, comment_text):
        """Navigate to a post and leave a comment."""
        if not self._ensure_alive():
            return False
        try:
            url = post.get("url", "")
            if not url or url == "https://www.reddit.com":
                # Build URL from post data if missing
                permalink = post.get("permalink", "")
                sub = post.get("subreddit", "")
                post_id = post.get("id", "")
                if permalink:
                    url = f"https://www.reddit.com{permalink}" if not permalink.startswith("http") else permalink
                elif sub and post_id:
                    url = f"https://www.reddit.com/r/{sub}/comments/{post_id}/"

            if not url or url == "https://www.reddit.com":
                logger.error(f"No valid URL for post: {post.get('title', '?')[:50]}")
                return False

            logger.info(f"Navigating to: {url}")

            # Force a real page load (not cached) by navigating away first if already on same page
            current = self.driver.current_url
            if current and url.rstrip("/") in current.rstrip("/"):
                self.driver.get("about:blank")
                time.sleep(0.5)

            self.driver.get(url)

            # Wait for Reddit post page to actually load
            try:
                WebDriverWait(self.driver, 20).until(
                    lambda d: "reddit.com" in d.current_url and d.execute_script(
                        "return document.readyState === 'complete' && "
                        "document.querySelectorAll('shreddit-post, shreddit-composer, [data-testid=\"post-container\"]').length > 0"
                    )
                )
                logger.info(f"Post page loaded: {self.driver.current_url}")
            except TimeoutException:
                logger.warning(f"Post page slow to load, current URL: {self.driver.current_url}")
                # Force reload
                self.driver.refresh()
                time.sleep(5)

            # Scroll to top so post is visible
            self.driver.execute_script("window.scrollTo(0, 0)")
            time.sleep(random.uniform(1, 2))

            # Simulate reading the post
            post_content = post.get("title", "") + " " + post.get("body", "")
            read_time = self.timing.reading_delay(len(post_content))
            self.timing.wait(read_time, "reading post")

            self._human_scroll(scroll_count=random.randint(1, 3))
            time.sleep(random.uniform(0.5, 1.5))

            # Strategy 1: Try to find and use the comment box directly
            comment_box = self._find_comment_box()
            if comment_box:
                try:
                    HumanMouse.move_to_element(self.driver, comment_box, self.timing)
                    time.sleep(self.timing.click_delay())
                    comment_box.click()
                    time.sleep(random.uniform(0.5, 1.0))

                    # After clicking, the box might transform — re-find it
                    time.sleep(1)
                    active_box = self._find_active_comment_box()
                    if active_box:
                        comment_box = active_box

                    HumanKeyboard.type_text(comment_box, comment_text, self.timing)
                    time.sleep(self.timing.pre_submit_pause())

                    submit_btn = self._find_submit_button()
                    if submit_btn:
                        HumanMouse.move_to_element(self.driver, submit_btn, self.timing)
                        time.sleep(self.timing.click_delay())
                        submit_btn.click()
                        time.sleep(random.uniform(2, 4))
                        display_name = self.username or self.account_label
                        logger.info(f"[{display_name}] Comment posted successfully")
                        return True
                except Exception as e:
                    logger.debug(f"Strategy 1 failed: {e}")

            # Strategy 2: Use JavaScript to find and interact with comment area
            logger.info("Trying JS-based comment approach...")
            success = self._comment_via_js(comment_text)
            if success:
                display_name = self.username or self.account_label
                logger.info(f"[{display_name}] Comment posted successfully (JS)")
                return True

            # Strategy 3: Use keyboard shortcut / tab navigation
            logger.info("Trying keyboard-based comment approach...")
            success = self._comment_via_keyboard(comment_text)
            if success:
                display_name = self.username or self.account_label
                logger.info(f"[{display_name}] Comment posted successfully (keyboard)")
                return True

            # Debug: save screenshot and page info
            self._debug_dump("comment_fail")
            logger.error("All comment strategies failed — debug screenshot saved")
            return False

        except Exception as e:
            logger.error(f"Error commenting: {e}")
            return False

    def _debug_dump(self, prefix):
        """Save a screenshot and page HTML for debugging."""
        try:
            debug_dir = os.path.join(os.path.dirname(__file__), "debug")
            os.makedirs(debug_dir, exist_ok=True)

            import datetime
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

            # Screenshot
            screenshot_path = os.path.join(debug_dir, f"{prefix}_{ts}.png")
            self.driver.save_screenshot(screenshot_path)
            logger.info(f"Debug screenshot: {screenshot_path}")

            # Current URL
            logger.info(f"Debug URL: {self.driver.current_url}")

            # Dump comment-related elements found on page
            info = self.driver.execute_script("""
                const results = {};
                results.url = window.location.href;
                results.title = document.title;
                results.textareas = document.querySelectorAll('textarea').length;
                results.contenteditables = document.querySelectorAll('[contenteditable="true"]').length;
                results.shreddit_composers = document.querySelectorAll('shreddit-composer').length;
                results.faceplate_forms = document.querySelectorAll('faceplate-form').length;
                results.buttons = [];
                document.querySelectorAll('button').forEach(b => {
                    if (b.offsetHeight > 0) results.buttons.push(b.textContent.trim().substring(0, 50));
                });
                results.iframes = document.querySelectorAll('iframe').length;

                // Check for comment-related elements
                const commentSelectors = [
                    'shreddit-comment-action-row',
                    'comment-body-header',
                    '[data-testid="comment-composer"]',
                    'shreddit-async-loader[bundlename*="comment"]',
                    '[slot="comment-composer"]',
                ];
                results.comment_elements = {};
                for (const sel of commentSelectors) {
                    results.comment_elements[sel] = document.querySelectorAll(sel).length;
                }

                return results;
            """)
            logger.info(f"Debug page info: {info}")

        except Exception as e:
            logger.debug(f"Debug dump failed: {e}")

    def _comment_via_js(self, comment_text):
        """Use JavaScript to find comment box, insert text, and submit."""
        try:
            # Step 1: Find, activate, and scroll to the comment input via shadow DOM
            self.driver.execute_script("""
                const composer = document.querySelector('shreddit-composer');
                if (composer) {
                    composer.scrollIntoView({block: 'center'});
                    composer.click();
                }
            """)
            time.sleep(2)

            # Step 2: Type text using JS that works through shadow DOM
            # We type in chunks to simulate human behavior
            escaped_text = comment_text.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")
            profile = self.timing._get_profile()
            wpm = random.uniform(*profile["typing_wpm"])
            char_delay = 60 / (wpm * 5)  # seconds per character

            # Type in word-sized chunks with delays between them
            words = comment_text.split(" ")
            typed_so_far = ""
            for i, word in enumerate(words):
                if i > 0:
                    typed_so_far += " "
                typed_so_far += word

                escaped = typed_so_far.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")
                self.driver.execute_script(f"""
                    function findInput(root) {{
                        const inputs = root.querySelectorAll('textarea, div[contenteditable="true"], div[role="textbox"]');
                        for (const el of inputs) {{
                            if (el.offsetHeight > 0) return el;
                        }}
                        const children = root.querySelectorAll('*');
                        for (const child of children) {{
                            if (child.shadowRoot) {{
                                const found = findInput(child.shadowRoot);
                                if (found) return found;
                            }}
                        }}
                        return null;
                    }}

                    const composer = document.querySelector('shreddit-composer');
                    let input = null;
                    if (composer) {{
                        if (composer.shadowRoot) input = findInput(composer.shadowRoot);
                        if (!input) input = findInput(composer);
                    }}
                    if (!input) input = findInput(document);

                    if (input) {{
                        if (input.tagName === 'TEXTAREA' || input.tagName === 'INPUT') {{
                            input.value = `{escaped}`;
                            input.dispatchEvent(new Event('input', {{bubbles: true}}));
                            input.dispatchEvent(new Event('change', {{bubbles: true}}));
                        }} else {{
                            input.textContent = `{escaped}`;
                            input.innerHTML = `{escaped}`;
                            input.dispatchEvent(new Event('input', {{bubbles: true}}));
                            input.dispatchEvent(new InputEvent('input', {{bubbles: true, data: ' ', inputType: 'insertText'}}));
                        }}
                    }}
                """)

                # Human-like delay between words
                delay = char_delay * len(word) * random.uniform(0.8, 1.5)
                if random.random() < 0.1:  # occasional thinking pause
                    delay += random.uniform(0.5, 2.0)
                time.sleep(delay)

            logger.info("Comment text inserted via JS")
            time.sleep(self.timing.pre_submit_pause())

            # Step 3: Find and click submit button
            submit_btn = self._find_submit_button()
            if submit_btn:
                HumanMouse.move_to_element(self.driver, submit_btn, self.timing)
                time.sleep(self.timing.click_delay())
                submit_btn.click()
                time.sleep(random.uniform(2, 4))
                return True

            # Fallback: try Ctrl+Enter on the active element
            try:
                active = self.driver.switch_to.active_element
                active.send_keys(Keys.CONTROL + Keys.RETURN)
                time.sleep(random.uniform(2, 4))
                return True
            except Exception:
                pass

            # Last fallback: click any visible "Comment" button via JS
            clicked = self.driver.execute_script("""
                function findBtn(root) {
                    const buttons = root.querySelectorAll('button');
                    for (const btn of buttons) {
                        const text = btn.textContent.trim().toLowerCase();
                        if ((text === 'comment' || text === 'reply') && btn.offsetHeight > 0 && !btn.disabled) {
                            btn.click();
                            return true;
                        }
                    }
                    const children = root.querySelectorAll('*');
                    for (const child of children) {
                        if (child.shadowRoot) {
                            const found = findBtn(child.shadowRoot);
                            if (found) return found;
                        }
                    }
                    return false;
                }
                const composer = document.querySelector('shreddit-composer');
                if (composer && composer.shadowRoot && findBtn(composer.shadowRoot)) return true;
                if (composer && findBtn(composer)) return true;
                return findBtn(document);
            """)
            if clicked:
                time.sleep(random.uniform(2, 4))
                return True

            return False

        except Exception as e:
            logger.debug(f"JS comment approach failed: {e}")
            return False

    def _comment_via_keyboard(self, comment_text):
        """Last resort: use Tab to navigate to comment box and type."""
        try:
            body = self.driver.find_element(By.TAG_NAME, "body")
            # Tab through the page to find an input
            for _ in range(20):
                body.send_keys(Keys.TAB)
                time.sleep(0.3)
                active = self.driver.switch_to.active_element
                tag = active.tag_name.lower() if active else ""
                editable = active.get_attribute("contenteditable") if active else ""
                if tag in ("textarea", "input") or editable == "true":
                    placeholder = (active.get_attribute("placeholder") or "").lower()
                    if any(kw in placeholder for kw in ["comment", "thought", "reply", "add"]) or editable == "true":
                        HumanKeyboard.type_text(active, comment_text, self.timing)
                        time.sleep(self.timing.pre_submit_pause())
                        active.send_keys(Keys.CONTROL + Keys.RETURN)
                        time.sleep(random.uniform(2, 4))
                        return True
            return False
        except Exception as e:
            logger.debug(f"Keyboard comment approach failed: {e}")
            return False

    def create_post(self, subreddit_name, title, body):
        """Create a new post in a subreddit via new Reddit UI."""
        if not self._ensure_alive():
            return False
        try:
            # Navigate to the submit page
            self.driver.get(f"{self.REDDIT_URL}/r/{subreddit_name}/submit")
            time.sleep(self.timing.page_load_wait() + random.uniform(2, 4))

            # Click "Text" tab if present (via JS to handle shadow DOM)
            self.driver.execute_script("""
                // Try standard tab buttons
                const tabs = document.querySelectorAll('button[role="tab"]');
                for (const tab of tabs) {
                    if (tab.textContent.trim().toLowerCase().includes('text')) {
                        tab.click();
                        return;
                    }
                }
                // Try first tab (usually text)
                if (tabs.length > 0) tabs[0].click();
            """)
            time.sleep(random.uniform(0.5, 1.5))

            # Find title field — try multiple approaches
            title_field = self.driver.execute_script("""
                function findInShadow(root, selectors) {
                    for (const sel of selectors) {
                        const el = root.querySelector(sel);
                        if (el && el.offsetHeight > 0) return el;
                    }
                    const children = root.querySelectorAll('*');
                    for (const child of children) {
                        if (child.shadowRoot) {
                            const found = findInShadow(child.shadowRoot, selectors);
                            if (found) return found;
                        }
                    }
                    return null;
                }
                const selectors = [
                    'textarea[placeholder*="Title"]',
                    'textarea[name="title"]',
                    'input[name="title"]',
                    'textarea[aria-label*="itle"]',
                    'input[placeholder*="Title"]',
                    '[data-testid="post-title-input"]',
                ];
                // Try direct first
                for (const sel of selectors) {
                    const el = document.querySelector(sel);
                    if (el && el.offsetHeight > 0) return el;
                }
                // Try shadow DOM
                return findInShadow(document, selectors);
            """)

            if not title_field:
                logger.error("Could not find title field on submit page")
                self._debug_dump("create_post_no_title")
                return False

            # Type title
            HumanMouse.move_to_element(self.driver, title_field, self.timing)
            title_field.click()
            time.sleep(random.uniform(0.3, 0.8))
            HumanKeyboard.type_text(title_field, title, self.timing)
            time.sleep(random.uniform(0.5, 1.5))

            # Find body field
            body_field = self.driver.execute_script("""
                function findInShadow(root, selectors) {
                    for (const sel of selectors) {
                        const el = root.querySelector(sel);
                        if (el && el.offsetHeight > 0) return el;
                    }
                    const children = root.querySelectorAll('*');
                    for (const child of children) {
                        if (child.shadowRoot) {
                            const found = findInShadow(child.shadowRoot, selectors);
                            if (found) return found;
                        }
                    }
                    return null;
                }
                const selectors = [
                    'div[contenteditable="true"]',
                    'textarea[placeholder*="Text"]',
                    'textarea[placeholder*="body"]',
                    'div[role="textbox"]',
                    '.DraftEditor-root',
                    'textarea[name="body"]',
                    '[data-testid="post-body-input"]',
                ];
                for (const sel of selectors) {
                    const el = document.querySelector(sel);
                    if (el && el.offsetHeight > 0) return el;
                }
                return findInShadow(document, selectors);
            """)

            if body_field:
                HumanMouse.move_to_element(self.driver, body_field, self.timing)
                body_field.click()
                time.sleep(random.uniform(0.3, 0.8))

                # Try typing directly first, fall back to JS insertion
                try:
                    HumanKeyboard.type_text(body_field, body, self.timing)
                except Exception:
                    # JS fallback for shadow DOM / contenteditable
                    self.driver.execute_script("""
                        const el = arguments[0];
                        const text = arguments[1];
                        if (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT') {
                            el.value = text;
                        } else {
                            el.textContent = text;
                        }
                        el.dispatchEvent(new Event('input', {bubbles: true}));
                        el.dispatchEvent(new Event('change', {bubbles: true}));
                    """, body_field, body)
            else:
                logger.warning("Could not find body field, posting title-only")

            time.sleep(self.timing.pre_submit_pause())

            # Find submit button via JS
            submitted = self.driver.execute_script("""
                function findInShadow(root) {
                    const buttons = root.querySelectorAll('button');
                    for (const btn of buttons) {
                        const text = btn.textContent.trim().toLowerCase();
                        const type = btn.getAttribute('type') || '';
                        if ((text === 'post' || text === 'submit' || text === 'submit post'
                             || type === 'submit')
                            && btn.offsetHeight > 0 && !btn.disabled) {
                            return btn;
                        }
                    }
                    const children = root.querySelectorAll('*');
                    for (const child of children) {
                        if (child.shadowRoot) {
                            const found = findInShadow(child.shadowRoot);
                            if (found) return found;
                        }
                    }
                    return null;
                }
                const btn = findInShadow(document);
                if (btn) {
                    btn.click();
                    return true;
                }
                return false;
            """)

            if not submitted:
                # Fallback: find by button text without shadow DOM
                buttons = self.driver.find_elements(By.TAG_NAME, "button")
                for b in buttons:
                    try:
                        text = b.text.strip().lower()
                        if text in ["post", "submit", "submit post"] and b.is_displayed() and b.is_enabled():
                            HumanMouse.move_to_element(self.driver, b, self.timing)
                            time.sleep(self.timing.click_delay())
                            b.click()
                            submitted = True
                            break
                    except StaleElementReferenceException:
                        continue

            if not submitted:
                logger.error("Could not find submit/post button")
                self._debug_dump("create_post_no_submit")
                return False

            time.sleep(random.uniform(3, 6))
            display_name = self.username or self.account_label
            logger.info(f"[{display_name}] Post created in r/{subreddit_name}")
            return True

        except Exception as e:
            logger.error(f"Error creating post: {e}")
            self._debug_dump("create_post_error")
            return False

    def upvote_post(self, post):
        """Upvote a post — handles shadow DOM in new Reddit UI."""
        if not self._ensure_alive():
            return False
        try:
            url = post.get("url", "")
            if url:
                self.driver.get(url)
                time.sleep(self.timing.page_load_wait())

            # Use JS to find upvote button, piercing shadow DOM
            upvoted = self.driver.execute_script("""
                function findUpvote(root) {
                    // Look for upvote buttons by aria-label or icon
                    const buttons = root.querySelectorAll('button');
                    for (const btn of buttons) {
                        const label = (btn.getAttribute('aria-label') || '').toLowerCase();
                        const id = (btn.getAttribute('data-click-id') || '').toLowerCase();
                        if ((label === 'upvote' || id === 'upvote') && btn.offsetHeight > 0) {
                            // Check if already upvoted
                            const pressed = btn.getAttribute('aria-pressed');
                            if (pressed === 'true') return 'already';
                            btn.click();
                            return 'clicked';
                        }
                    }
                    // Check shadow roots
                    const children = root.querySelectorAll('*');
                    for (const child of children) {
                        if (child.shadowRoot) {
                            const result = findUpvote(child.shadowRoot);
                            if (result) return result;
                        }
                    }
                    return null;
                }

                // Try shreddit-post first (listing page)
                const posts = document.querySelectorAll('shreddit-post');
                if (posts.length > 0) {
                    const post = posts[0];
                    if (post.shadowRoot) {
                        const result = findUpvote(post.shadowRoot);
                        if (result) return result;
                    }
                    const result = findUpvote(post);
                    if (result) return result;
                }

                // Try from document root
                return findUpvote(document);
            """)

            display_name = self.username or self.account_label
            if upvoted == 'clicked':
                logger.info(f"[{display_name}] Upvoted post")
                time.sleep(random.uniform(0.5, 1.5))
                return True
            elif upvoted == 'already':
                logger.info(f"[{display_name}] Post already upvoted, skipping")
                return True
            else:
                logger.warning("Could not find upvote button")
                return False

        except Exception as e:
            logger.error(f"Error upvoting: {e}")
            return False

    def _find_comment_box(self):
        """Find the comment input area — pierces shadow DOM."""
        # First scroll down to make comment area visible
        self.driver.execute_script(
            "document.querySelector('shreddit-composer, [slot=\"comment-composer\"]')?.scrollIntoView({behavior: 'smooth', block: 'center'});"
        )
        time.sleep(1)

        # Use JS to traverse shadow DOM and find the actual input
        elem = self.driver.execute_script("""
            function findInShadow(root) {
                // Check direct children
                let ta = root.querySelector('div[contenteditable="true"], textarea, div[role="textbox"]');
                if (ta && ta.offsetHeight > 0) return ta;

                // Check shadow roots of children
                const children = root.querySelectorAll('*');
                for (const child of children) {
                    if (child.shadowRoot) {
                        const found = findInShadow(child.shadowRoot);
                        if (found) return found;
                    }
                }
                return null;
            }

            // Start from shreddit-composer
            const composer = document.querySelector('shreddit-composer');
            if (composer) {
                // Try direct first
                let ta = composer.querySelector('div[contenteditable="true"], textarea');
                if (ta && ta.offsetHeight > 0) return ta;
                // Try shadow DOM
                if (composer.shadowRoot) {
                    let found = findInShadow(composer.shadowRoot);
                    if (found) return found;
                }
            }

            // Try faceplate-form
            const form = document.querySelector('faceplate-form');
            if (form) {
                let ta = form.querySelector('div[contenteditable="true"], textarea');
                if (ta && ta.offsetHeight > 0) return ta;
                if (form.shadowRoot) {
                    let found = findInShadow(form.shadowRoot);
                    if (found) return found;
                }
            }

            // Try from document root (recursive shadow DOM search)
            return findInShadow(document);
        """)

        if elem:
            return elem

        # Fallback: standard CSS selectors
        selectors = [
            'div[contenteditable="true"]',
            'textarea[placeholder*="comment" i]',
            'textarea[placeholder*="Add a comment" i]',
            'div[role="textbox"]',
        ]
        for sel in selectors:
            try:
                el = self.driver.find_element(By.CSS_SELECTOR, sel)
                if el.is_displayed():
                    return el
            except NoSuchElementException:
                continue

        return None

    def _find_active_comment_box(self):
        """Find the currently active/focused comment input after clicking."""
        elem = self.driver.execute_script("""
            // Check active element first
            if (document.activeElement &&
                (document.activeElement.contentEditable === 'true' ||
                 document.activeElement.tagName === 'TEXTAREA')) {
                return document.activeElement;
            }

            // Search shadow DOM
            function findActive(root) {
                const els = root.querySelectorAll('div[contenteditable="true"], textarea');
                for (const el of els) {
                    if (el.offsetHeight > 20) return el;
                }
                const children = root.querySelectorAll('*');
                for (const child of children) {
                    if (child.shadowRoot) {
                        const found = findActive(child.shadowRoot);
                        if (found) return found;
                    }
                }
                return null;
            }

            const composer = document.querySelector('shreddit-composer');
            if (composer) {
                if (composer.shadowRoot) {
                    const found = findActive(composer.shadowRoot);
                    if (found) return found;
                }
                const found = findActive(composer);
                if (found) return found;
            }
            return findActive(document);
        """)
        return elem

    def _find_submit_button(self):
        """Find the comment submit button — pierces shadow DOM."""
        btn = self.driver.execute_script("""
            function findButton(root) {
                // Look for submit buttons
                const buttons = root.querySelectorAll('button');
                for (const btn of buttons) {
                    const text = btn.textContent.trim().toLowerCase();
                    const type = btn.getAttribute('type') || '';
                    if ((text === 'comment' || text === 'reply' || text === 'submit' || type === 'submit')
                        && btn.offsetHeight > 0 && !btn.disabled) {
                        return btn;
                    }
                }
                // Check shadow roots
                const children = root.querySelectorAll('*');
                for (const child of children) {
                    if (child.shadowRoot) {
                        const found = findButton(child.shadowRoot);
                        if (found) return found;
                    }
                }
                return null;
            }

            // Start from composer
            const composer = document.querySelector('shreddit-composer');
            if (composer) {
                if (composer.shadowRoot) {
                    const found = findButton(composer.shadowRoot);
                    if (found) return found;
                }
                const found = findButton(composer);
                if (found) return found;
            }

            // Try faceplate-form
            const form = document.querySelector('faceplate-form');
            if (form) {
                if (form.shadowRoot) {
                    const found = findButton(form.shadowRoot);
                    if (found) return found;
                }
                const found = findButton(form);
                if (found) return found;
            }

            return findButton(document);
        """)

        if btn:
            return btn

        # Fallback: standard search
        try:
            buttons = self.driver.find_elements(By.TAG_NAME, "button")
            for b in buttons:
                try:
                    text = b.text.strip().lower()
                    if text in ["comment", "reply", "submit"]:
                        if b.is_displayed() and b.is_enabled():
                            return b
                except StaleElementReferenceException:
                    continue
        except Exception:
            pass

        return None

    def _human_scroll(self, scroll_count=3):
        """Scroll the page like a human."""
        for _ in range(scroll_count):
            scroll_amount = random.randint(200, 600)
            self.driver.execute_script(f"window.scrollBy(0, {scroll_amount})")
            time.sleep(self.timing.scroll_pause())

            if random.random() < 0.15:
                up_amount = random.randint(50, 150)
                self.driver.execute_script(f"window.scrollBy(0, -{up_amount})")
                time.sleep(self.timing.scroll_pause())

    def close(self):
        """Close the browser."""
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None
            display_name = self.username or self.account_label
            logger.info(f"Browser closed for {display_name}")
