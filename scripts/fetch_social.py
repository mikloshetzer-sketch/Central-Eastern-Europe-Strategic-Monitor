import json
import os
import re
import time
from datetime import datetime, timezone, timedelta
import email.utils

import feedparser
import requests


SOCIAL_OVERLAY_PATH = "docs/data/social_overlay.json"
SOCIAL_LATEST_PATH = "docs/data/social_latest.json"

MAX_AGE_DAYS = 7

X_BEARER_TOKEN = os.getenv("X_BEARER_TOKEN", "").strip()
X_API_URL = "https://api.x.com/2/tweets/search/recent"
X_MAX_RESULTS_PER_QUERY = 10
X_SLEEP_SECONDS = 1


COUNTRIES = [
    {
        "id": "hungary",
        "name_en": "Hungary",
        "name_hu": "Magyarország",
        "x_query": "(Hungary OR Hungarian OR Budapest OR Orban OR Orbán OR Fidesz)",
        "keywords": ["hungary", "hungarian", "budapest", "orban", "orbán", "fidesz", "magyarország", "magyar"],
        "strong_keywords": ["orban", "orbán", "fidesz", "budapest", "hungarian government", "magyar kormány"]
    },
    {
        "id": "poland",
        "name_en": "Poland",
        "name_hu": "Lengyelország",
        "x_query": "(Poland OR Polish OR Warsaw OR Warszawa OR Tusk OR Duda)",
        "keywords": ["poland", "polish", "warsaw", "warszawa", "polska", "tusk", "duda", "pis"],
        "strong_keywords": ["warsaw", "warszawa", "tusk", "duda", "polish government", "polska"]
    },
    {
        "id": "slovakia",
        "name_en": "Slovakia",
        "name_hu": "Szlovákia",
        "x_query": "(Slovakia OR Slovak OR Bratislava OR Fico)",
        "keywords": ["slovakia", "slovak", "bratislava", "fico", "slovensko", "slovenská", "slovensky"],
        "strong_keywords": ["fico", "bratislava", "slovak government", "slovensko"]
    },
    {
        "id": "czechia",
        "name_en": "Czechia",
        "name_hu": "Csehország",
        "x_query": "(Czechia OR Czech OR Prague OR Praha OR Fiala)",
        "keywords": ["czechia", "czech republic", "czech", "prague", "praha", "česko", "česká", "fiala"],
        "strong_keywords": ["prague", "praha", "fiala", "czech government", "česko"]
    },
    {
        "id": "romania",
        "name_en": "Romania",
        "name_hu": "Románia",
        "x_query": "(Romania OR Romanian OR Bucharest OR Bucuresti OR București)",
        "keywords": ["romania", "romanian", "bucharest", "bucuresti", "bucurești", "românia", "român"],
        "strong_keywords": ["bucharest", "bucurești", "romanian government", "românia", "black sea"]
    },
    {
        "id": "estonia",
        "name_en": "Estonia",
        "name_hu": "Észtország",
        "x_query": "(Estonia OR Estonian OR Tallinn OR Eesti)",
        "keywords": ["estonia", "estonian", "tallinn", "eesti", "eesti valitsus"],
        "strong_keywords": ["tallinn", "estonian government", "eesti", "cyber security"]
    },
    {
        "id": "latvia",
        "name_en": "Latvia",
        "name_hu": "Lettország",
        "x_query": "(Latvia OR Latvian OR Riga OR Rīga OR Latvija)",
        "keywords": ["latvia", "latvian", "riga", "rīga", "latvija", "latvijas"],
        "strong_keywords": ["riga", "rīga", "latvian government", "latvija"]
    },
    {
        "id": "lithuania",
        "name_en": "Lithuania",
        "name_hu": "Litvánia",
        "x_query": "(Lithuania OR Lithuanian OR Vilnius OR Lietuva OR Kaliningrad)",
        "keywords": ["lithuania", "lithuanian", "vilnius", "lietuva", "kaliningrad", "baltarusija", "belarus"],
        "strong_keywords": ["vilnius", "lithuanian government", "lietuva", "kaliningrad", "belarus border"]
    }
]


FEEDS = [
    ("reddit", "https://www.reddit.com/r/europe/.rss", "europe"),
    ("reddit", "https://www.reddit.com/r/geopolitics/.rss", "geopolitics"),
    ("reddit", "https://www.reddit.com/r/NATO/.rss", "nato"),
    ("reddit", "https://www.reddit.com/r/ukraine/.rss", "ukraine"),

    ("reddit", "https://www.reddit.com/r/hungary/.rss", "hungary"),
    ("reddit", "https://www.reddit.com/r/poland/.rss", "poland"),
    ("reddit", "https://www.reddit.com/r/Polska/.rss", "polska"),
    ("reddit", "https://www.reddit.com/r/slovakia/.rss", "slovakia"),
    ("reddit", "https://www.reddit.com/r/czech/.rss", "czech"),
    ("reddit", "https://www.reddit.com/r/Romania/.rss", "romania"),
    ("reddit", "https://www.reddit.com/r/Eesti/.rss", "eesti"),
    ("reddit", "https://www.reddit.com/r/latvia/.rss", "latvia"),
    ("reddit", "https://www.reddit.com/r/lithuania/.rss", "lithuania"),

    ("mastodon", "https://mastodon.social/tags/hungary.rss", "hungary"),
    ("mastodon", "https://mastodon.social/tags/poland.rss", "poland"),
    ("mastodon", "https://mastodon.social/tags/slovakia.rss", "slovakia"),
    ("mastodon", "https://mastodon.social/tags/czechia.rss", "czechia"),
    ("mastodon", "https://mastodon.social/tags/czechrepublic.rss", "czechrepublic"),
    ("mastodon", "https://mastodon.social/tags/romania.rss", "romania"),
    ("mastodon", "https://mastodon.social/tags/estonia.rss", "estonia"),
    ("mastodon", "https://mastodon.social/tags/latvia.rss", "latvia"),
    ("mastodon", "https://mastodon.social/tags/lithuania.rss", "lithuania"),

    ("mastodon", "https://mastodon.social/tags/nato.rss", "nato"),
    ("mastodon", "https://mastodon.social/tags/eu.rss", "eu"),
    ("mastodon", "https://mastodon.social/tags/ukraine.rss", "ukraine"),
    ("mastodon", "https://mastodon.social/tags/russia.rss", "russia"),
    ("mastodon", "https://mastodon.social/tags/cybersecurity.rss", "cybersecurity")
]


EVENT_CATEGORIES = {
    "security": [
        "security", "nato", "military", "defence", "defense", "border",
        "army", "troops", "drone", "missile", "airspace", "deterrence",
        "biztonság", "katonai", "védelem", "határ", "hadsereg"
    ],
    "ukraine_russia": [
        "ukraine", "ukrainian", "russia", "russian", "war", "kyiv",
        "moscow", "kremlin", "sanctions", "ukrajna", "oroszország",
        "háború", "szankció"
    ],
    "eu_rule_of_law": [
        "european union", "eu", "brussels", "commission", "rule of law",
        "eu funds", "democracy", "európai unió", "brüsszel", "jogállamiság"
    ],
    "government_crisis": [
        "government", "parliament", "opposition", "election", "coalition",
        "resignation", "president", "prime minister", "corruption",
        "kormány", "parlament", "választás", "ellenzék", "korrupció"
    ],
    "protest": [
        "protest", "demonstration", "strike", "riot", "unrest",
        "tüntetés", "sztrájk", "tiltakozás"
    ],
    "cyber_disinformation": [
        "cyber", "hack", "ransomware", "disinformation", "propaganda",
        "hybrid", "kiber", "kibertámadás", "dezinformáció"
    ],
    "energy_economy": [
        "energy", "gas", "oil", "pipeline", "inflation", "economy",
        "nuclear", "energia", "gáz", "olaj", "infláció", "gazdaság"
    ],
    "migration_border": [
        "migration", "migrant", "refugee", "asylum", "border pressure",
        "migráció", "menekült", "határnyomás"
    ],
    "foreign_influence": [
        "china", "russia", "belarus", "foreign influence", "espionage",
        "spy", "kína", "orosz", "belarusz", "külső befolyás"
    ]
}


CATEGORY_LABELS_HU = {
    "security": "Biztonsági kockázat",
    "ukraine_russia": "Ukrajna és Oroszország",
    "eu_rule_of_law": "EU / jogállamiság",
    "government_crisis": "Belpolitikai feszültség",
    "protest": "Tiltakozás",
    "cyber_disinformation": "Kiber és dezinformáció",
    "energy_economy": "Energia és gazdaság",
    "migration_border": "Migráció és határnyomás",
    "foreign_influence": "Külső befolyás",
    "uncategorized": "Nincs kategória"
}


CATEGORY_WEIGHTS = {
    "security": 10,
    "ukraine_russia": 9,
    "cyber_disinformation": 8,
    "government_crisis": 8,
    "protest": 7,
    "foreign_influence": 7,
    "migration_border": 6,
    "eu_rule_of_law": 5,
    "energy_economy": 4
}


RISK_CATEGORY_WEIGHTS = {
    "security": 5,
    "ukraine_russia": 5,
    "cyber_disinformation": 4,
    "government_crisis": 4,
    "protest": 4,
    "foreign_influence": 3,
    "migration_border": 3,
    "eu_rule_of_law": 2,
    "energy_economy": 1
}


NEGATIVE_WORDS = [
    "threat", "attack", "war", "crisis", "risk", "tension", "conflict",
    "corruption", "protest", "pressure", "hybrid", "sabotage",
    "instability", "violence", "spy", "espionage", "sanctions",
    "fenyegetés", "támadás", "háború", "válság", "kockázat",
    "feszültség", "konfliktus", "korrupció", "tüntetés"
]


POSITIVE_WORDS = [
    "agreement", "reform", "growth", "cooperation", "investment",
    "stability", "dialogue", "progress", "development", "support",
    "partnership", "coordination", "resilience",
    "megállapodás", "reform", "együttműködés", "támogatás",
    "stabilitás", "fejlődés"
]


NOISE_WORDS = [
    "football", "basketball", "travel", "tourism", "hotel", "food",
    "recipe", "movie", "film", "music", "concert", "dating",
    "gaming", "crypto", "bitcoin", "nft", "casino", "betting",
    "amazon", "discount", "sale", "coupon", "fashion", "meme",
    "visa question", "tourist", "itinerary", "airport", "train from",
    "bus from", "cheap way", "restaurant", "where can i buy",
    "eurovision", "song contest"
]


LOW_QUALITY_PATTERNS = [
    "what do you think", "how do i get", "cheap way", "travel to",
    "moving to", "visiting", "tourist", "restaurant", "hotel",
    "airport", "train station", "bus ticket", "song", "movie",
    "football", "basketball", "where can i buy", "discount", "sale",
    "meme", "funny", "joke"
]


TRUSTED_SOURCE_HINTS = [
    "reuters", "apnews", "associated press", "bbc", "dw.com",
    "politico", "euractiv", "euronews", "rferl", "rfe/rl",
    "nato", "osce", "united nations", "european commission",
    "consilium.europa.eu", "theguardian.com", "guardian",
    "aljazeera", "bne intellinews"
]


def strip_html(text):
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&nbsp;", " ")
    text = text.replace("&amp;", "&")
    text = text.replace("&quot;", '"')
    text = text.replace("&#39;", "'")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_text(text):
    text = strip_html(text)
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"@\w+", " ", text)
    text = re.sub(r"#", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_feed(url):
    feedparser.USER_AGENT = "CEE-Strategic-Social-Monitor/1.1"
    return feedparser.parse(url)


def parse_date(value):
    if not value:
        return None
    try:
        parsed = email.utils.parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def parse_iso_date(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None
    def is_recent(published):
    parsed = parse_date(published) or parse_iso_date(published)

    if not parsed:
        return False

    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)

    return parsed >= cutoff


def has_any(text_lc, words):
    return any(word.lower() in text_lc for word in words)


def count_hits(text_lc, words):
    return sum(1 for word in words if word.lower() in text_lc)


def is_noise(text_lc):
    return has_any(text_lc, NOISE_WORDS)


def is_low_quality(text_lc):
    return has_any(text_lc, LOW_QUALITY_PATTERNS)


def is_trusted_source(text_lc):
    return has_any(text_lc, TRUSTED_SOURCE_HINTS)


def detect_event_categories(text_lc):
    categories = []

    for category, keywords in EVENT_CATEGORIES.items():

        hits = count_hits(text_lc, keywords)

        if hits > 0:
            categories.append({
                "category": category,
                "label": CATEGORY_LABELS_HU.get(category, category),
                "hits": hits,
                "weight": CATEGORY_WEIGHTS.get(category, 5)
            })

    categories = sorted(
        categories,
        key=lambda item: (item["weight"], item["hits"]),
        reverse=True
    )

    return categories


def main_event_category(text_lc):
    categories = detect_event_categories(text_lc)

    if not categories:
        return "uncategorized"

    return categories[0]["category"]


def geopolitical_score(text_lc):
    categories = detect_event_categories(text_lc)

    if not categories:
        return 0

    score = 0

    for item in categories:
        score += item["weight"] * item["hits"]

    if is_trusted_source(text_lc):
        score += 4

    if has_any(text_lc, NEGATIVE_WORDS):
        score += 3

    if has_any(text_lc, POSITIVE_WORDS):
        score += 1

    if is_noise(text_lc):
        score -= 12

    if is_low_quality(text_lc):
        score -= 14

    return max(score, 0)


def match_country_with_confidence(text_lc):
    results = []

    for country in COUNTRIES:

        weak_hits = count_hits(
            text_lc,
            country["keywords"]
        )

        strong_hits = count_hits(
            text_lc,
            country["strong_keywords"]
        )

        if weak_hits == 0 and strong_hits == 0:
            continue

        confidence = weak_hits + strong_hits * 3

        if confidence > 0:
            results.append({
                "id": country["id"],
                "confidence": confidence
            })

    results = sorted(
        results,
        key=lambda item: item["confidence"],
        reverse=True
    )

    return results


def filtered_country_matches(text_lc, source_type):
    matches = match_country_with_confidence(text_lc)

    if not matches:
        return [], {}

    top_confidence = matches[0]["confidence"]

    accepted = []

    for item in matches:

        confidence = item["confidence"]

        if source_type == "x":

            if confidence >= 3:
                accepted.append(item["id"])

            elif confidence >= 2 and confidence >= top_confidence:
                accepted.append(item["id"])

        else:

            if confidence >= 2:
                accepted.append(item["id"])

            elif confidence >= 1 and top_confidence <= 2:
                accepted.append(item["id"])

    accepted = accepted[:3]

    confidence_map = {
        item["id"]: item["confidence"]
        for item in matches
    }

    return accepted, confidence_map


def source_reliability(text_lc, source_type):

    if is_trusted_source(text_lc):
        return 5

    if source_type == "mastodon":
        return 3

    if source_type == "x":
        return 2

    if source_type == "reddit":
        return 1

    return 1


def quality_score(text_lc, source_type):

    score = geopolitical_score(text_lc)

    if source_type == "reddit":
        score -= 2

    if source_type == "x":
        score -= 1

    score += source_reliability(text_lc, source_type)

    return max(score, 0)


def passes_quality_filter(text_lc, countries, source_type):

    if not countries:
        return False

    if is_noise(text_lc):
        return False

    if is_low_quality(text_lc):
        return False

    categories = detect_event_categories(text_lc)

    if not categories:
        return False

    g_score = geopolitical_score(text_lc)
    q_score = quality_score(text_lc, source_type)

    if source_type == "x":
        return g_score >= 9 and q_score >= 9

    if source_type == "reddit":
        return g_score >= 8 and q_score >= 7

    if source_type == "mastodon":
        return g_score >= 6 and q_score >= 6

    return g_score >= 8


def calculate_social_index(
    mentions,
    negative_hits,
    positive_hits,
    trusted_hits,
    engagement_total,
    quality_total,
    geopolitical_total,
    category_counts
):
    """
    Javított normalizált social score.
    Nem fut minden ország automatikusan 100-ra.
    """

    mention_score = min(
        mentions * 2,
        25
    )

    negative_score = min(
        negative_hits * 5,
        25
    )

    trusted_score = min(
        trusted_hits * 3,
        12
    )

    engagement_score = min(
        engagement_total // 50,
        8
    )

    quality_score_part = min(
        quality_total // 35,
        12
    )

    geopolitical_score_part = min(
        geopolitical_total // 60,
        14
    )

    category_score = 0

    for category, count in category_counts.items():

        weight = RISK_CATEGORY_WEIGHTS.get(
            category,
            1
        )

        partial = min(
            count * weight,
            12
        )

        category_score += partial

    category_score = min(
        category_score,
        18
    )

    positive_penalty = min(
        positive_hits * 3,
        15
    )

    raw_score = (
        mention_score
        + negative_score
        + trusted_score
        + engagement_score
        + quality_score_part
        + geopolitical_score_part
        + category_score
        - positive_penalty
    )

    final_score = max(
        0,
        min(
            round(raw_score),
            100
        )
    )

    return final_score


def collect_rss_posts():

    all_posts = []
    seen = set()

    for source_type, url, tag in FEEDS:

        print(f"Feed lekérése: {source_type} / {tag}")

        try:
            feed = parse_feed(url)
            entries = getattr(feed, "entries", [])

        except Exception as exc:
            print(f"Hiba: {exc}")
            continue

        for entry in entries:

            title = getattr(entry, "title", "") or ""
            link = getattr(entry, "link", "") or ""
            summary = getattr(entry, "summary", "") or ""
            published = getattr(entry, "published", "") or ""

            if not is_recent(published):
                continue

            full_text = f"{title} {summary} {link}"

            text_plain = normalize_text(full_text)
            text_lc = text_plain.lower()

            countries, confidence_map = filtered_country_matches(
                text_lc,
                source_type
            )

            if not passes_quality_filter(
                text_lc,
                countries,
                source_type
            ):
                continue

            key = link or text_plain[:180]

            if key in seen:
                continue

            seen.add(key)

            all_posts.append({
                "title": strip_html(title)[:180],
                "text": strip_html(summary)[:360],
                "url": link,
                "source": source_type,
                "tag": tag,
                "seen_date": published,
                "matched_countries": countries,
                "country_confidence": confidence_map,
                "event_category": main_event_category(text_lc),
                "event_category_label": CATEGORY_LABELS_HU.get(
                    main_event_category(text_lc),
                    main_event_category(text_lc)
                ),
                "event_categories": detect_event_categories(text_lc),
                "geopolitical_score": geopolitical_score(text_lc),
                "quality_score": quality_score(text_lc, source_type),
                "source_reliability": source_reliability(text_lc, source_type),
                "trusted_source_hint": is_trusted_source(text_lc),
                "engagement": 0,
                "raw_engagement": 0
            })

    return all_posts


def analyze_country(country_id, posts):

    related = [
        post for post in posts
        if country_id in post.get("matched_countries", [])
    ]

    mentions = len(related)

    negative_hits = 0
    positive_hits = 0
    trusted_hits = 0

    engagement_total = 0
    quality_total = 0
    geopolitical_total = 0

    source_counts = {
        "reddit": 0,
        "mastodon": 0,
        "x": 0
    }

    category_counts = {}
    topic_rows = {}

    for post in related:

        text = (
            f"{post.get('title', '')} "
            f"{post.get('text', '')}"
        ).lower()

        source = post.get("source", "")

        category = post.get(
            "event_category",
            "uncategorized"
        )

        category_label = post.get(
            "event_category_label",
            CATEGORY_LABELS_HU.get(category, category)
        )

        engagement_total += int(
            post.get("engagement", 0) or 0
        )

        quality_total += int(
            post.get("quality_score", 0) or 0
        )

        geopolitical_total += int(
            post.get("geopolitical_score", 0) or 0
        )

        if post.get("trusted_source_hint"):
            trusted_hits += 1

        source_counts[source] = (
            source_counts.get(source, 0) + 1
        )

        category_counts[category] = (
            category_counts.get(category, 0) + 1
        )

        topic_rows[category_label] = (
            topic_rows.get(category_label, 0) + 1
        )

        if has_any(text, NEGATIVE_WORDS):
            negative_hits += 1

        if has_any(text, POSITIVE_WORDS):
            positive_hits += 1

    index = calculate_social_index(
        mentions=mentions,
        negative_hits=negative_hits,
        positive_hits=positive_hits,
        trusted_hits=trusted_hits,
        engagement_total=engagement_total,
        quality_total=quality_total,
        geopolitical_total=geopolitical_total,
        category_counts=category_counts
    )

    main_social_topic = (
        max(topic_rows, key=topic_rows.get)
        if topic_rows
        else "No dominant social topic"
    )

    topics = [
        {
            "name": name,
            "count": count
        }
        for name, count in sorted(
            topic_rows.items(),
            key=lambda item: item[1],
            reverse=True
        )
    ][:6]

    return {
        "mentions": mentions,
        "negative": negative_hits,
        "positive": positive_hits,
        "index": index,
        "x_mentions": source_counts.get("x", 0),
        "reddit_mentions": source_counts.get("reddit", 0),
        "mastodon_mentions": source_counts.get("mastodon", 0),
        "main_social_topic": main_social_topic,
        "reliable_sources": trusted_hits,
        "geopolitical_score": geopolitical_total,
        "topics": topics,
        "source_status": "active"
    }


def save_json(path, data):

    os.makedirs(
        os.path.dirname(path),
        exist_ok=True
    )

    with open(path, "w", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2
        )


def main():

    print("CEE social monitoring indítása...")

    posts = collect_rss_posts()

    print(f"Összes releváns social találat: {len(posts)}")

    overlay = {
        "last_update": datetime.now(timezone.utc).isoformat(),
        "source_status": "active",
        "source": "Reddit RSS + Mastodon hashtag RSS",
        "countries": {}
    }

    for country in COUNTRIES:

        overlay["countries"][country["id"]] = analyze_country(
            country["id"],
            posts
        )

    latest = {
        "updated_at": datetime.now(timezone.utc).strftime(
            "%Y-%m-%d %H:%M UTC"
        ),
        "countries": [
            {
                "id": country["id"],
                "name_en": country["name_en"],
                "name_hu": country["name_hu"],
                "social_signal": overlay["countries"].get(
                    country["id"],
                    {}
                )
            }
            for country in COUNTRIES
        ]
    }

    save_json(
        SOCIAL_OVERLAY_PATH,
        overlay
    )

    save_json(
        SOCIAL_LATEST_PATH,
        latest
    )

    print(f"Mentve: {SOCIAL_OVERLAY_PATH}")
    print(f"Mentve: {SOCIAL_LATEST_PATH}")


if __name__ == "__main__":
    main()    
