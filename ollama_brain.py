import requests
import random
import re
from config import OLLAMA_BASE_URL, OLLAMA_MODEL, PROMO_PRODUCT_NAME, PROMO_PRODUCT_URL, PROMO_PRODUCT_DESCRIPTION

TYPO_MAP = {
    "the": ["teh", "th", "the"],
    "that": ["taht", "that", "thta"],
    "have": ["hve", "have", "ahve"],
    "just": ["jsut", "just", "juts"],
    "really": ["realy", "really", "rlly"],
    "because": ["becuase", "because", "bc", "cuz"],
    "about": ["abut", "about", "abt"],
    "would": ["woudl", "would", "wuold"],
    "their": ["thier", "their", "ther"],
    "definitely": ["definately", "definitly", "definitely", "def"],
    "probably": ["prolly", "probably", "probly"],
    "something": ["somthing", "something", "smth"],
    "actually": ["acutally", "actually", "actualy"],
    "though": ["tho", "though", "thoguh"],
    "people": ["ppl", "people", "poeple"],
    "pretty": ["prety", "pretty", "preety"],
    "interesting": ["intresting", "interesting", "intersting"],
    "different": ["diffrent", "different", "diferent"],
    "awesome": ["awsome", "awesome"],
    "know": ["kno", "know", "knw"],
    "with": ["w/", "with", "with"],
    "you": ["u", "you", "you", "you"],
    "your": ["ur", "your", "your", "your"],
    "before": ["b4", "before", "befroe"],
    "honestly": ["honestly", "honeslty", "tbh"],
}

CASUAL_STARTERS = [
    "", "", "",  # often no starter
    "lol ", "lmao ", "bruh ", "ngl ", "tbh ", "idk ", "yo ", "dude ",
    "ok so ", "wait ", "haha ", "bro ", "man ", "honestly ",
]

CASUAL_ENDERS = [
    "", "", "", "", "", "",  # most of the time no ender
    " lol", " haha", " tbh", " ngl", " fr", " imo",
]


def _inject_typos(text, intensity=0.12):
    """Randomly inject typos to make text feel human-typed."""
    words = text.split()
    result = []
    for word in words:
        lower = word.lower().strip(".,!?;:")
        if lower in TYPO_MAP and random.random() < intensity:
            replacement = random.choice(TYPO_MAP[lower])
            # preserve original punctuation
            trailing = ""
            for ch in reversed(word):
                if ch in ".,!?;:":
                    trailing = ch + trailing
                else:
                    break
            result.append(replacement + trailing)
        else:
            result.append(word)
    return " ".join(result)


def _casualize(text):
    """Make text feel more casual/reddit-like."""
    # Random lowercase for first letter
    if text and random.random() < 0.6:
        text = text[0].lower() + text[1:]

    # Sometimes skip periods at end
    if text.endswith(".") and random.random() < 0.4:
        text = text[:-1]

    # Add casual starter/ender
    if random.random() < 0.3:
        text = random.choice(CASUAL_STARTERS) + text
    if random.random() < 0.25:
        text = text.rstrip(".!") + random.choice(CASUAL_ENDERS)

    # Sometimes remove capitalization after periods
    if random.random() < 0.3:
        text = text.lower()

    # Random double punctuation
    if random.random() < 0.15:
        text = text.replace("!", "!!")
    if random.random() < 0.1:
        text = text.replace("?", "??")

    return text


def _get_subreddit_personality(subreddit_name):
    """Return a personality modifier based on the subreddit culture."""
    sub = subreddit_name.lower()

    personalities = {
        "mobile_dev": {
            "subs": ["androiddev", "iosprogramming", "reactnative", "flutterdev", "mobiledev",
                      "apps", "sideproject", "appbusiness"],
            "tone": "You're a mobile developer who's shipped multiple apps. You know the pain of cross-platform development, App Store rejections, and performance optimization. Talk about frameworks, SDKs, and deployment like someone who lives it daily.",
        },
        "startup": {
            "subs": ["startups", "entrepreneur", "saas", "smallbusiness", "producthunt",
                      "indiehackers", "nocode"],
            "tone": "You're a startup founder who's been through the MVP grind. You know when to build custom vs use off-the-shelf. Mix business strategy with tech reality. Reference fundraising, user acquisition, and product-market fit casually.",
        },
        "ai_ml": {
            "subs": ["artificial", "machinelearning", "chatgpt", "localllama",
                      "learnmachinelearning", "openai", "computervision"],
            "tone": "You're an AI practitioner who integrates ML into real products. You know the difference between hype and practical AI. Talk about model deployment, API integration, and real-world performance. Be excited about what works, skeptical about what doesn't.",
        },
        "gamedev": {
            "subs": ["gamedev", "unity3d", "unrealengine", "indiegaming", "gamedesign",
                      "androidgaming", "iosgaming"],
            "tone": "You're a game developer who's shipped mobile games. You know Unity and Unreal inside out. Talk about game mechanics, optimization, monetization, and player retention like someone in the trenches. Be passionate about game design.",
        },
        "design_ux": {
            "subs": ["ui_design", "userexperience", "web_design", "figmadesign",
                      "graphic_design", "design_critiques", "productmanagement"],
            "tone": "You're a product designer who obsesses over user experience. You think in user flows, not just pixels. Reference Figma, design systems, and usability testing naturally. Appreciate good design and call out bad UX when you see it.",
        },
        "tech_general": {
            "subs": ["technology", "programming", "webdev", "software", "learnprogramming",
                      "cscareerquestions", "freelance"],
            "tone": "You're a seasoned developer who's worked on everything from startups to agencies. You give practical advice based on real experience. Mix technical knowledge with industry wisdom. Be helpful but real about trade-offs.",
        },
    }

    for category, data in personalities.items():
        if any(s in sub for s in data["subs"]):
            return data["tone"]

    return "You're a regular Reddit user. Be casual, helpful, and a bit sarcastic."


# AI slop phrases that get comments flagged and removed
AI_SLOP_PATTERNS = [
    # Generic empathy starters (biggest red flag)
    r"^(man,?\s+)?i feel (you|ya|that)",
    r"^(been there|same here|i can relate|i totally (get|understand|agree))",
    r"^i (totally |completely |absolutely )?(agree|disagree|understand)",
    r"^(i know|ik) (that|the) (feeling|struggle|pain)",
    r"^(yo |dude |bro )?i'?ve been (there|in (your|the same))",
    r"^congrats!?\s",
    r"^(great|nice|awesome|cool) (post|question|point|work)",
    r"^(this is |that'?s )(a )?(great|good|excellent|awesome|nice)",
    # Vague filler with no substance
    r"had (my |our )?(fair )?share of",
    r"(huge|real|total) pain",
    r"game.?changer",
    r"can'?t (stress|emphasize) (this )?enough",
    r"this (is )?so (true|real|relatable)",
    r"couldn'?t agree more",
    r"(100|1000)%\s*(this|agree)",
    # Generic "experience" claims
    r"had similar (issues|problems|struggles|experiences)",
    r"been (doing|working on) (this|that|something similar) for (years|months|a while)",
    r"went through the same (thing|struggle|issue)",
    # Overly enthusiastic validation
    r"(this is |that'?s )(exactly|precisely) (what|how)",
    r"(you'?re|ur) (absolutely|totally|completely) right",
    # AI transition phrases
    r"that (being )?said,",
    r"on (a |the )?(flip|other) (side|hand)",
    r"at the end of the day",
    r"it'?s worth (noting|mentioning)",
    r"(just )?my two cents",
    r"(hope this|that) helps",
    r"(feel free|don'?t hesitate) to",
    # Vague agreement / validation
    r"couldn'?t have said it better",
    r"you('?re| are) (so |absolutely |totally )?right",
    r"(spot|right) on",
    r"(solid|great|good|excellent) (point|advice|take|insight)",
    r"this is (so |really )?(important|true|key|crucial)",
]

AI_SLOP_EXACT = [
    "been there done that",
    "i hear you",
    "preach",
    "this right here",
    "take my upvote",
    "came here to say this",
    "underrated comment",
    "can confirm",
]


def _is_ai_slop(text):
    """Detect AI-generated generic comments that would get flagged."""
    lower = text.lower().strip()

    # Check exact matches
    for phrase in AI_SLOP_EXACT:
        if lower == phrase or lower.startswith(phrase + " ") or lower.startswith(phrase + ","):
            return True

    # Check regex patterns
    for pattern in AI_SLOP_PATTERNS:
        if re.search(pattern, lower):
            return True

    # Check for too many generic filler phrases (2+ = likely slop)
    filler_count = 0
    fillers = [
        "to be honest", "tbh", "ngl", "imo", "imho", "just sayin",
        "at the end of the day", "in my experience", "from my experience",
        "personally", "in my opinion",
    ]
    for filler in fillers:
        if filler in lower:
            filler_count += 1
    if filler_count >= 3:
        return True

    return False


def _is_relevant_to_post(comment, post_title, post_body):
    """Check if a comment actually relates to the specific post content."""
    comment_lower = comment.lower()
    post_text = (post_title + " " + (post_body or "")).lower()

    # Extract key words from post (nouns, tools, names - words 4+ chars)
    post_words = set(re.findall(r'\b[a-z]{4,}\b', post_text))
    comment_words = set(re.findall(r'\b[a-z]{4,}\b', comment_lower))

    # Remove very common words
    stop_words = {
        "this", "that", "with", "from", "have", "been", "your", "about",
        "just", "like", "what", "when", "where", "which", "their", "would",
        "could", "should", "some", "they", "them", "than", "then", "into",
        "also", "more", "very", "much", "well", "here", "there", "does",
        "don't", "dont", "will", "were", "being", "really", "pretty",
        "think", "know", "want", "need", "make", "made", "going", "thing",
        "things", "good", "great", "time", "long", "still", "even",
        "same", "other", "only", "most", "over", "such", "back",
    }
    post_words -= stop_words
    comment_words -= stop_words

    # Need at least some overlap with post-specific words
    overlap = post_words & comment_words
    if len(overlap) < 2 and len(post_words) > 3:
        return False

    return True


def verify_comment_quality(comment, post_title, post_body, subreddit):
    """Final verification using the AI model itself — is this comment good enough to post?"""
    prompt = f"""You are a Reddit moderator for r/{subreddit}. Would this comment get removed for being:
- AI-generated/bot-like
- Generic/not relevant to the post
- Low effort / doesn't add value
- Spam or promotional

POST: {post_title}
{post_body[:300] if post_body else ""}

COMMENT: {comment}

Reply with ONLY "PASS" if the comment is fine, or "FAIL" if it should be removed. Nothing else."""

    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "num_predict": 5,
                }
            },
            timeout=30
        )
        response.raise_for_status()
        result = response.json()["response"].strip().upper()
        return "PASS" in result
    except Exception:
        return True  # if check fails, let it through


def generate_comment(post_title, post_body, subreddit, promote=True):
    """Generate a human-like Reddit comment using Ollama."""

    personality = _get_subreddit_personality(subreddit)

    promo_instruction = ""
    if promote:
        promo_instruction = f"""
PROMOTION CONTEXT (READ CAREFULLY):
- You know about "{PROMO_PRODUCT_NAME}" — a dev agency (mobile apps, games, AI, UX design) at {PROMO_PRODUCT_URL}
- ONLY mention it if the post is DIRECTLY about one of these topics: hiring a dev team, outsourcing app development, looking for an agency, building an MVP, choosing between agencies/freelancers, needing app design or AI integration done
- If the post is about coding problems, IDE setup, tutorials, career advice, or anything technical — DO NOT promote. Just be helpful.
- When you DO mention it, make it feel like a casual aside from personal experience, not the point of your comment. Example: "ended up going with an agency for ours, booma studio did the mobile side" — then move on. Don't dwell on it.
- NEVER include the URL unless someone literally asks for links/recommendations
- NEVER use words like "top-notch", "highly recommend", "game-changer", "check out", "amazing"
- NEVER say "we worked with" or "they've got great devs" — that sounds like a shill
- If the promotion doesn't fit naturally, just skip it entirely and be genuine. A good genuine comment is 10x better than a forced promo.
"""
    else:
        promo_instruction = ""

    body_text = post_body[:800] if post_body else ""

    prompt = f"""You are a real person writing a Reddit comment. Follow these rules EXACTLY:

PERSONALITY: {personality}

CRITICAL RULES — BREAK THESE AND YOUR COMMENT WILL BE REMOVED:
1. Your comment MUST directly reference something SPECIFIC from the post. Mention a specific tool, number, feature, problem, or detail the OP talked about. If the post is about "building a Figma comparison tool", talk about THAT tool specifically — not vague "i've been there" nonsense.
2. If you cannot write something specifically relevant to THIS post, respond with just "SKIP" and nothing else.
3. NEVER write generic comments like "been there done that", "i feel you", "same here". These are instant red flags for moderators.
4. NEVER start with a generic reaction. Jump straight into your specific point.

STYLE RULES:
- Write 1-3 sentences MAX. Reddit comments are SHORT.
- Be casual. Use lowercase often. Skip punctuation sometimes.
- Add genuine value: share a specific tip, ask a specific question, share a specific related experience
- NEVER sound like a corporate account, a bot, or someone with an agenda
- NEVER use these AI-giveaway phrases: "I'd recommend", "You should definitely", "Great question!", "top-notch", "game-changer", "been there done that", "i feel you on that", "i totally get it", "can relate", "huge pain"
- Use Reddit slang sparingly and naturally (ngl, tbh, imo) — max 1 per comment
- Match the energy of the post — if it's a rant, commiserate with specifics. if it's a question, answer it.
- If you mention personal experience, be SPECIFIC ("i used riverpod for state management in my weather app" not "i've had similar issues")

{promo_instruction}

POST TITLE: {post_title}
POST BODY: {body_text if body_text else "(no body text — comment based on title only, be brief)"}
SUBREDDIT: r/{subreddit}

Write ONLY the comment text. Nothing else. No quotes, no labels, no explanations. If you can't write something genuinely relevant, write SKIP."""

    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.9,
                "top_p": 0.95,
                "num_predict": 400,
            }
        },
        timeout=120
    )
    response.raise_for_status()
    text = response.json()["response"].strip()

    # Check if model said SKIP
    if text.strip().upper() == "SKIP":
        return None

    # Clean up any AI artifacts
    text = re.sub(r'^["\']+|["\']+$', '', text)  # remove wrapping quotes
    text = re.sub(r'^(Here\'s|Here is|Comment:|Response:).*?\n', '', text, flags=re.IGNORECASE)
    text = text.strip()

    # Layer 1: AI slop pattern detection
    if _is_ai_slop(text):
        return None

    # Layer 2: Verify comment is relevant to the post
    if not _is_relevant_to_post(text, post_title, body_text):
        return None

    # Apply human-like modifications
    text = _casualize(text)
    text = _inject_typos(text, intensity=random.uniform(0.05, 0.15))

    return text


def generate_post(subreddit, niche):
    """Generate a Reddit post that subtly promotes the product."""

    personality = _get_subreddit_personality(subreddit)

    prompt = f"""You are creating a Reddit post for r/{subreddit}. Follow these rules EXACTLY:

PERSONALITY: {personality}

You are subtly promoting "{PROMO_PRODUCT_NAME}" ({PROMO_PRODUCT_DESCRIPTION}).
URL: {PROMO_PRODUCT_URL}

{PROMO_PRODUCT_NAME} is a development agency that offers: mobile app development (iOS, Android, React Native, Flutter), mobile game development (Unity, Unreal Engine), AI solutions (chatbots, ML, NLP, computer vision), product design & UX (Figma, design systems), and growth strategy.

POST STYLE:
- Make it look like a genuine user sharing their experience or asking a question
- Good formats: "Has anyone tried X?", "Our team needed a mobile app built and here's what happened", "Looking for a good dev agency", personal story about working with a dev studio
- Title should be engaging but not clickbaity
- Body should be 2-5 sentences, casual tone
- Include {PROMO_PRODUCT_NAME} naturally as an agency you worked with or heard about
- NEVER claim they offer services they don't (only mobile apps, games, AI, design, strategy)
- NEVER sound like an ad. Sound like a real person sharing.
- Mix in mentions of other real agencies/alternatives to seem balanced

Respond in this EXACT format:
TITLE: your title here
BODY: your body text here"""

    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.9,
                "top_p": 0.95,
                "num_predict": 300,
            }
        },
        timeout=120
    )
    response.raise_for_status()
    text = response.json()["response"].strip()

    # Parse title and body
    title = ""
    body = ""
    if "TITLE:" in text and "BODY:" in text:
        parts = text.split("BODY:", 1)
        title = parts[0].replace("TITLE:", "").strip()
        body = parts[1].strip()
    else:
        lines = text.split("\n", 1)
        title = lines[0].strip()
        body = lines[1].strip() if len(lines) > 1 else ""

    # Clean up AI junk from title
    title = re.sub(r'^["\']+|["\']+$', '', title)
    title = re.sub(r"^(Here'?s?\s*(the|my|a)?\s*(post|title)?:?\s*)", '', title, flags=re.IGNORECASE)
    title = re.sub(r'^\*+|\*+$', '', title)  # remove markdown bold
    title = title.strip(' \n\t-:')
    body = re.sub(r'^["\']+|["\']+$', '', body)
    body = re.sub(r"^(Here'?s?\s*(the)?\s*body:?\s*)", '', body, flags=re.IGNORECASE)
    body = body.strip()

    body = _casualize(body)
    body = _inject_typos(body, intensity=random.uniform(0.05, 0.12))

    return title, body


def analyze_post_relevance(post_title, post_body, subreddit):
    """Use Ollama to determine if a post is relevant for promotion."""

    prompt = f"""Rate how relevant this Reddit post is for promoting "{PROMO_PRODUCT_NAME}" ({PROMO_PRODUCT_DESCRIPTION}).

Post title: {post_title}
Post body: {post_body[:300] if post_body else "(none)"}
Subreddit: r/{subreddit}

Reply with ONLY a number from 1-10 where:
1-3 = not relevant, skip this post
4-6 = somewhat relevant, could engage
7-10 = highly relevant, perfect opportunity

Reply with ONLY the number, nothing else."""

    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.3,
                "num_predict": 5,
            }
        },
        timeout=30
    )
    response.raise_for_status()
    text = response.json()["response"].strip()

    try:
        score = int(re.search(r'\d+', text).group())
        return min(max(score, 1), 10)
    except (AttributeError, ValueError):
        return 5
