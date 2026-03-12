"""
Browser fingerprint management system.
Generates and applies consistent, realistic browser fingerprints
to avoid detection by anti-bot systems.
"""

import random
import json
import os
import hashlib
import logging

logger = logging.getLogger("reddit_bot")

# Realistic screen resolutions (common ones)
SCREEN_RESOLUTIONS = [
    (1920, 1080), (1366, 768), (1536, 864), (1440, 900),
    (1280, 720), (1600, 900), (2560, 1440), (1280, 800),
    (1680, 1050), (1920, 1200), (2560, 1080), (3440, 1440),
    (1360, 768), (1280, 1024),
]

# Common timezone offsets
TIMEZONES = [
    ("America/New_York", -5), ("America/Chicago", -6),
    ("America/Denver", -7), ("America/Los_Angeles", -8),
    ("Europe/London", 0), ("Europe/Paris", 1),
    ("Europe/Berlin", 1), ("Australia/Sydney", 11),
    ("Asia/Tokyo", 9), ("America/Toronto", -5),
]

# Common platform/OS combos
PLATFORMS = [
    {"platform": "Win32", "oscpu": "Windows NT 10.0; Win64; x64"},
    {"platform": "Win32", "oscpu": "Windows NT 10.0; Win64; x64"},
    {"platform": "Win32", "oscpu": "Windows NT 10.0; Win64; x64"},
    {"platform": "MacIntel", "oscpu": "Intel Mac OS X 10_15_7"},
    {"platform": "MacIntel", "oscpu": "Intel Mac OS X 14_0"},
    {"platform": "Linux x86_64", "oscpu": "Linux x86_64"},
]

# WebGL vendors/renderers
WEBGL_CONFIGS = [
    {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)"},
    {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce GTX 1660 SUPER Direct3D11 vs_5_0 ps_5_0, D3D11)"},
    {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 4070 Direct3D11 vs_5_0 ps_5_0, D3D11)"},
    {"vendor": "Google Inc. (AMD)", "renderer": "ANGLE (AMD, AMD Radeon RX 580 Direct3D11 vs_5_0 ps_5_0, D3D11)"},
    {"vendor": "Google Inc. (AMD)", "renderer": "ANGLE (AMD, AMD Radeon RX 6700 XT Direct3D11 vs_5_0 ps_5_0, D3D11)"},
    {"vendor": "Google Inc. (Intel)", "renderer": "ANGLE (Intel, Intel(R) UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0, D3D11)"},
    {"vendor": "Google Inc. (Intel)", "renderer": "ANGLE (Intel, Intel(R) Iris(R) Xe Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)"},
    {"vendor": "Google Inc. (Apple)", "renderer": "ANGLE (Apple, Apple M1, OpenGL 4.1)"},
    {"vendor": "Google Inc. (Apple)", "renderer": "ANGLE (Apple, Apple M2, OpenGL 4.1)"},
]

# Common fonts available on different systems
FONT_SETS = {
    "windows": [
        "Arial", "Arial Black", "Calibri", "Cambria", "Comic Sans MS",
        "Consolas", "Courier New", "Georgia", "Impact", "Lucida Console",
        "Segoe UI", "Tahoma", "Times New Roman", "Trebuchet MS", "Verdana",
    ],
    "mac": [
        "Arial", "Avenir", "Courier New", "Georgia", "Helvetica",
        "Helvetica Neue", "Lucida Grande", "Menlo", "Monaco", "Optima",
        "Palatino", "SF Pro", "Times New Roman", "Trebuchet MS", "Verdana",
    ],
    "linux": [
        "Arial", "Courier New", "DejaVu Sans", "DejaVu Serif",
        "FreeMono", "FreeSans", "Georgia", "Liberation Mono",
        "Liberation Sans", "Noto Sans", "Times New Roman", "Ubuntu",
    ],
}

# Common Chrome versions (keep updated)
CHROME_VERSIONS = [
    "120.0.6099.130", "120.0.6099.199", "121.0.6167.85",
    "121.0.6167.160", "122.0.6261.69", "122.0.6261.112",
    "123.0.6312.58", "123.0.6312.106", "124.0.6367.91",
    "124.0.6367.118", "125.0.6422.60", "125.0.6422.112",
]

# Common languages
LANGUAGES = [
    ["en-US", "en"], ["en-US", "en", "es"],
    ["en-GB", "en"], ["en-CA", "en"],
    ["en-AU", "en"], ["en-US", "en", "fr"],
]


class FingerprintProfile:
    """Represents a complete browser fingerprint for one account."""

    def __init__(self, account_id=None):
        self.account_id = account_id
        self._generate()

    def _generate(self):
        """Generate a new consistent fingerprint."""
        # Use account_id as seed for consistency across sessions
        if self.account_id:
            seed = int(hashlib.md5(self.account_id.encode()).hexdigest()[:8], 16)
            rng = random.Random(seed)
        else:
            rng = random.Random()

        platform = rng.choice(PLATFORMS)
        self.platform = platform["platform"]
        self.oscpu = platform["oscpu"]

        self.screen = rng.choice(SCREEN_RESOLUTIONS)
        self.screen_width = self.screen[0]
        self.screen_height = self.screen[1]
        # Available area is slightly smaller (taskbar)
        self.avail_height = self.screen_height - rng.choice([40, 48, 56, 64, 72])
        self.avail_width = self.screen_width

        self.color_depth = rng.choice([24, 24, 24, 32])
        self.pixel_ratio = rng.choice([1, 1, 1, 1.25, 1.5, 2])

        tz = rng.choice(TIMEZONES)
        self.timezone = tz[0]
        self.timezone_offset = tz[1] * -60  # JS uses inverted minutes

        self.webgl = rng.choice(WEBGL_CONFIGS)
        self.chrome_version = rng.choice(CHROME_VERSIONS)

        self.languages = rng.choice(LANGUAGES)
        self.hardware_concurrency = rng.choice([4, 8, 8, 12, 16])
        self.device_memory = rng.choice([4, 8, 8, 16, 16, 32])
        self.max_touch_points = 0  # Desktop

        # Determine font set based on platform
        if "Win" in self.platform:
            base_fonts = FONT_SETS["windows"]
        elif "Mac" in self.platform:
            base_fonts = FONT_SETS["mac"]
        else:
            base_fonts = FONT_SETS["linux"]

        # Randomly remove 1-3 fonts to create variation
        self.fonts = list(base_fonts)
        for _ in range(rng.randint(1, 3)):
            if len(self.fonts) > 8:
                self.fonts.pop(rng.randint(0, len(self.fonts) - 1))

        # Canvas noise seed (unique per profile)
        self.canvas_noise_seed = rng.randint(1, 1000000)

        # Audio context noise
        self.audio_noise = rng.uniform(0.00001, 0.0001)

        # Generate user agent
        self._generate_user_agent(rng)

    def _generate_user_agent(self, rng):
        """Generate a realistic Chrome user agent string."""
        major = self.chrome_version.split(".")[0]

        if "Win" in self.platform:
            self.user_agent = f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{self.chrome_version} Safari/537.36"
        elif "Mac" in self.platform:
            mac_ver = rng.choice(["10_15_7", "14_0", "13_6_1", "14_2"])
            self.user_agent = f"Mozilla/5.0 (Macintosh; Intel Mac OS X {mac_ver}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{self.chrome_version} Safari/537.36"
        else:
            self.user_agent = f"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{self.chrome_version} Safari/537.36"

    def get_stealth_js(self):
        """Generate JavaScript to inject for fingerprint spoofing."""
        return f"""
        // Override navigator properties
        Object.defineProperty(navigator, 'platform', {{get: () => '{self.platform}'}});
        Object.defineProperty(navigator, 'hardwareConcurrency', {{get: () => {self.hardware_concurrency}}});
        Object.defineProperty(navigator, 'deviceMemory', {{get: () => {self.device_memory}}});
        Object.defineProperty(navigator, 'maxTouchPoints', {{get: () => {self.max_touch_points}}});
        Object.defineProperty(navigator, 'languages', {{get: () => {json.dumps(self.languages)}}});

        // Override screen properties
        Object.defineProperty(screen, 'width', {{get: () => {self.screen_width}}});
        Object.defineProperty(screen, 'height', {{get: () => {self.screen_height}}});
        Object.defineProperty(screen, 'availWidth', {{get: () => {self.avail_width}}});
        Object.defineProperty(screen, 'availHeight', {{get: () => {self.avail_height}}});
        Object.defineProperty(screen, 'colorDepth', {{get: () => {self.color_depth}}});
        Object.defineProperty(window, 'devicePixelRatio', {{get: () => {self.pixel_ratio}}});

        // WebGL fingerprint
        const getParameterOrig = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(param) {{
            if (param === 37445) return '{self.webgl["vendor"]}';
            if (param === 37446) return '{self.webgl["renderer"]}';
            return getParameterOrig.call(this, param);
        }};
        const getParameterOrig2 = WebGL2RenderingContext.prototype.getParameter;
        WebGL2RenderingContext.prototype.getParameter = function(param) {{
            if (param === 37445) return '{self.webgl["vendor"]}';
            if (param === 37446) return '{self.webgl["renderer"]}';
            return getParameterOrig2.call(this, param);
        }};

        // Canvas fingerprint noise
        const toDataURLOrig = HTMLCanvasElement.prototype.toDataURL;
        HTMLCanvasElement.prototype.toDataURL = function(type) {{
            const ctx = this.getContext('2d');
            if (ctx) {{
                const imgData = ctx.getImageData(0, 0, this.width, this.height);
                const seed = {self.canvas_noise_seed};
                for (let i = 0; i < imgData.data.length; i += 4) {{
                    // Subtle noise that's consistent per profile
                    const noise = ((seed * (i + 1) * 9301 + 49297) % 233280) / 233280.0;
                    if (noise < 0.1) {{
                        imgData.data[i] = imgData.data[i] ^ 1;
                    }}
                }}
                ctx.putImageData(imgData, 0, 0);
            }}
            return toDataURLOrig.call(this, type);
        }};

        // AudioContext fingerprint
        const origGetFloatFreqData = AnalyserNode.prototype.getFloatFrequencyData;
        AnalyserNode.prototype.getFloatFrequencyData = function(array) {{
            origGetFloatFreqData.call(this, array);
            for (let i = 0; i < array.length; i++) {{
                array[i] += {self.audio_noise} * (i % 2 === 0 ? 1 : -1);
            }}
        }};

        // Timezone
        const origDateTZOffset = Date.prototype.getTimezoneOffset;
        Date.prototype.getTimezoneOffset = function() {{
            return {self.timezone_offset};
        }};

        // Hide automation indicators
        Object.defineProperty(navigator, 'webdriver', {{get: () => undefined}});
        delete navigator.__proto__.webdriver;

        // Chrome runtime (make it look like real Chrome)
        window.chrome = {{
            runtime: {{
                connect: function() {{}},
                sendMessage: function() {{}},
                onMessage: {{addListener: function() {{}}}},
            }},
            loadTimes: function() {{
                return {{
                    commitLoadTime: Date.now() / 1000 - Math.random() * 5,
                    connectionInfo: 'h2',
                    finishDocumentLoadTime: Date.now() / 1000 - Math.random() * 2,
                    finishLoadTime: Date.now() / 1000 - Math.random(),
                    firstPaintAfterLoadTime: 0,
                    firstPaintTime: Date.now() / 1000 - Math.random() * 3,
                    navigationType: 'Other',
                    npnNegotiatedProtocol: 'h2',
                    requestTime: Date.now() / 1000 - Math.random() * 10,
                    startLoadTime: Date.now() / 1000 - Math.random() * 8,
                    wasAlternateProtocolAvailable: false,
                    wasFetchedViaSpdy: true,
                    wasNpnNegotiated: true,
                }};
            }},
            csi: function() {{
                return {{
                    startE: Date.now(),
                    onloadT: Date.now(),
                    pageT: Math.random() * 5000,
                    tran: 15,
                }};
            }},
        }};

        // Permissions API override
        const origQuery = Permissions.prototype.query;
        Permissions.prototype.query = function(desc) {{
            if (desc.name === 'notifications') {{
                return Promise.resolve({{state: Notification.permission, onchange: null}});
            }}
            return origQuery.call(this, desc);
        }};

        // Plugin spoofing (Chrome has PDF plugin)
        Object.defineProperty(navigator, 'plugins', {{
            get: () => {{
                const plugins = [
                    {{name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format'}},
                    {{name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: ''}},
                    {{name: 'Native Client', filename: 'internal-nacl-plugin', description: ''}},
                ];
                plugins.length = 3;
                return plugins;
            }}
        }});

        // Connection API
        if (navigator.connection) {{
            Object.defineProperty(navigator.connection, 'rtt', {{get: () => {random.choice([50, 100, 150, 200])}}});
            Object.defineProperty(navigator.connection, 'downlink', {{get: () => {random.choice([1.5, 2.5, 5, 10])}}});
            Object.defineProperty(navigator.connection, 'effectiveType', {{get: () => '4g'}});
        }}

        console.log('[stealth] Fingerprint applied');
        """

    def to_dict(self):
        """Serialize profile for storage."""
        return {
            "account_id": self.account_id,
            "platform": self.platform,
            "screen": self.screen,
            "user_agent": self.user_agent,
            "timezone": self.timezone,
            "chrome_version": self.chrome_version,
            "languages": self.languages,
            "hardware_concurrency": self.hardware_concurrency,
            "device_memory": self.device_memory,
        }


class FingerprintManager:
    """Manages fingerprint profiles for multiple accounts."""

    STORE_FILE = "fingerprints.json"

    def __init__(self):
        self.profiles = {}
        self._load()

    def _load(self):
        """Load saved fingerprints from disk."""
        store_path = os.path.join(os.path.dirname(__file__), self.STORE_FILE)
        if os.path.exists(store_path):
            try:
                with open(store_path, "r") as f:
                    data = json.load(f)
                logger.info(f"Loaded {len(data)} saved fingerprint profiles")
            except Exception:
                pass

    def _save(self):
        """Save fingerprints to disk."""
        store_path = os.path.join(os.path.dirname(__file__), self.STORE_FILE)
        data = {aid: fp.to_dict() for aid, fp in self.profiles.items()}
        with open(store_path, "w") as f:
            json.dump(data, f, indent=2)

    def get_profile(self, account_id):
        """Get or create a fingerprint profile for an account."""
        if account_id not in self.profiles:
            self.profiles[account_id] = FingerprintProfile(account_id)
            self._save()
            logger.info(f"Generated new fingerprint for {account_id}")
        return self.profiles[account_id]
