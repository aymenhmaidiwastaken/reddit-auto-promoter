"""
Human-like timing system with gaussian delays, typing simulation,
and activity pattern modeling to avoid detection.
"""

import random
import time
import math
import logging
from datetime import datetime

logger = logging.getLogger("reddit_bot")


class HumanTiming:
    """Simulates human-like timing patterns."""

    # Activity windows - humans aren't active 24/7
    # (hour_start, hour_end, activity_weight)
    ACTIVITY_WINDOWS = [
        (6, 9, 0.4),     # early morning - light browsing
        (9, 12, 0.8),    # morning - moderate
        (12, 14, 1.0),   # lunch break - peak
        (14, 17, 0.6),   # afternoon - moderate
        (17, 20, 0.9),   # evening - high
        (20, 23, 1.0),   # night - peak
        (23, 1, 0.3),    # late night - low
        (1, 6, 0.05),    # sleeping - almost none
    ]

    def __init__(self, speed_profile="normal"):
        """
        speed_profile: "fast", "normal", "slow", "careful"
        """
        self.speed_profile = speed_profile
        self.session_start = time.time()
        self.action_count = 0
        self._fatigue_factor = 1.0

        self.profiles = {
            "fast": {"typing_wpm": (80, 120), "read_factor": 0.5, "delay_mult": 0.6},
            "normal": {"typing_wpm": (40, 75), "read_factor": 1.0, "delay_mult": 1.0},
            "slow": {"typing_wpm": (25, 45), "read_factor": 1.5, "delay_mult": 1.5},
            "careful": {"typing_wpm": (30, 55), "read_factor": 2.0, "delay_mult": 2.0},
        }

    def _get_profile(self):
        return self.profiles.get(self.speed_profile, self.profiles["normal"])

    def _update_fatigue(self):
        """Simulate fatigue - humans slow down over time."""
        session_minutes = (time.time() - self.session_start) / 60
        # Fatigue increases logarithmically
        self._fatigue_factor = 1.0 + 0.1 * math.log1p(session_minutes / 30)
        # After many actions, slow down more
        if self.action_count > 10:
            self._fatigue_factor += 0.05 * (self.action_count - 10)

    def _gaussian_delay(self, mean, std_dev, minimum=0.5):
        """Generate a gaussian-distributed delay (always positive)."""
        delay = random.gauss(mean, std_dev)
        return max(minimum, delay)

    def _is_active_hour(self):
        """Check current activity weight based on time of day."""
        hour = datetime.now().hour
        for start, end, weight in self.ACTIVITY_WINDOWS:
            if start <= end:
                if start <= hour < end:
                    return weight
            else:  # wraps midnight
                if hour >= start or hour < end:
                    return weight
        return 0.5

    def typing_delay(self, text):
        """
        Simulate realistic typing time for a given text.
        Returns total seconds it would take a human to type this.
        """
        profile = self._get_profile()
        wpm = random.uniform(*profile["typing_wpm"])
        chars_per_min = wpm * 5  # average 5 chars per word

        base_time = len(text) / chars_per_min * 60

        # Add thinking pauses (humans pause mid-typing)
        num_pauses = max(1, len(text) // 50)
        pause_time = sum(self._gaussian_delay(1.5, 0.8, 0.3) for _ in range(num_pauses))

        # Add correction time (backspace simulation ~5% of chars)
        correction_time = len(text) * 0.05 * 0.15

        total = (base_time + pause_time + correction_time) * self._fatigue_factor
        return total

    def reading_delay(self, text_length):
        """
        Simulate time to read content before responding.
        Average reading speed is ~250 words per minute.
        """
        profile = self._get_profile()
        words = text_length / 5
        wpm = random.uniform(200, 350)
        base_time = (words / wpm) * 60 * profile["read_factor"]

        # Add scroll time
        scroll_time = self._gaussian_delay(1.0, 0.5, 0.3)

        return (base_time + scroll_time) * self._fatigue_factor

    def between_actions_delay(self):
        """
        Delay between major actions (commenting, posting, etc).
        Uses gaussian distribution centered around natural browsing patterns.
        """
        self._update_fatigue()
        self.action_count += 1

        profile = self._get_profile()
        activity = self._is_active_hour()

        # Base delay: 45-180 seconds, gaussian distributed
        base_mean = 90 * profile["delay_mult"]
        base_std = 30

        delay = self._gaussian_delay(base_mean, base_std, 30)

        # Adjust for time of day (less active = longer delays)
        delay /= max(activity, 0.1)

        # Add occasional long pauses (checking phone, getting coffee, etc.)
        if random.random() < 0.08:
            delay += random.uniform(120, 600)  # 2-10 min break
            logger.info("Taking a natural break...")

        # Very occasionally, a very long pause
        if random.random() < 0.02:
            delay += random.uniform(600, 1800)  # 10-30 min break
            logger.info("Extended break (simulating real behavior)...")

        # Fatigue makes us slower
        delay *= self._fatigue_factor

        return delay

    def page_load_wait(self):
        """Wait time after navigating to a new page."""
        return self._gaussian_delay(2.5, 1.0, 1.0)

    def scroll_pause(self):
        """Short pause between scroll actions."""
        return self._gaussian_delay(0.8, 0.4, 0.2)

    def click_delay(self):
        """Delay before clicking (reaction time)."""
        return self._gaussian_delay(0.4, 0.2, 0.1)

    def pre_submit_pause(self):
        """Pause before submitting (re-reading what you wrote)."""
        return self._gaussian_delay(3.0, 1.5, 1.0)

    def wait(self, delay, reason=""):
        """Execute a wait with logging."""
        if reason:
            logger.info(f"Waiting {delay:.1f}s ({reason})...")
        else:
            logger.info(f"Waiting {delay:.1f}s...")
        time.sleep(delay)

    def should_take_break(self):
        """Determine if the bot should take a longer break based on session time."""
        session_minutes = (time.time() - self.session_start) / 60

        # After 45-90 min, suggest a break
        if session_minutes > random.uniform(45, 90) and random.random() < 0.3:
            return True, random.uniform(300, 900)  # 5-15 min

        # After 2+ hours, definitely break
        if session_minutes > 120:
            return True, random.uniform(600, 1800)  # 10-30 min

        return False, 0

    def reset_session(self):
        """Reset session tracking (call after a long break)."""
        self.session_start = time.time()
        self.action_count = 0
        self._fatigue_factor = 1.0
