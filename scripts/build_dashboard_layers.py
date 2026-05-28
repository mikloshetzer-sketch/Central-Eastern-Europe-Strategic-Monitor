import json
import os
from datetime import datetime, timezone


RAW_NEWS_PATH = "docs/data/raw_news.json"
LATEST_STATUS_PATH = "docs/data/latest_status.json"
SECURITY_OVERLAY_PATH = "docs/data/security_overlay.json"
SOCIAL_OVERLAY_PATH = "docs/data/social_overlay.json"
COUNTRY_HISTORY_PATH = "docs/data/history/country_history.json"
OUTPUT_PATH = "docs/data/dashboard_layers.json"


NARRATIVE_RULES = {
    "Biztonsági kockázat": [
        "security", "nato", "defence", "defense", "military", "army", "border",
        "drone", "missile", "airspace", "hybrid", "sabotage",
        "biztonság", "katonai", "védelem", "határ", "hadsereg"
    ],
    "Ukrajna és Oroszország": [
        "ukraine", "ukrajna", "russia", "oroszország", "war", "háború",
        "sanction", "szankció", "kremlin", "moscow", "moszkva"
    ],
    "EU / jogállamiság": [
        "eu", "european union", "brussels", "commission", "rule of law",
        "funds", "európai unió", "brüsszel", "bizottság", "jogállamiság"
    ],
    "Belpolitikai feszültség": [
        "government", "parliament", "opposition", "election", "coalition",
        "protest", "corruption", "kormány", "parlament", "ellenzék",
        "választás", "tüntetés", "korrupció"
    ],
    "Energia és gazdaság": [
        "energy", "gas", "oil", "pipeline", "inflation", "economy",
        "energia", "gáz", "olaj", "vezeték", "infláció", "gazdaság"
    ],
    "Kiber és dezinformáció": [
        "cyber", "hack", "ransomware", "disinformation", "propaganda",
        "kiber", "kibertámadás", "dezinformáció", "propaganda"
    ],
    "Migráció és határnyomás": [
        "migration", "migrant", "refugee", "asylum", "border pressure",
        "migráció", "menekült", "határnyomás"
    ],
    "Külső befolyás": [
        "china", "russia", "belarus", "foreign influence", "influence",
        "kína", "orosz", "belarusz", "külső befolyás"
    ]
}


NEGATIVE_WORDS = [
    "threat", "attack", "war", "crisis", "risk", "tension", "conflict",
    "corruption", "protest", "pressure", "hybrid", "sabotage",
    "fenyegetés", "támadás", "háború", "válság", "kockázat",
    "feszültség", "konfliktus", "korrupció", "tüntetés"
]

POSITIVE_WORDS = [
    "cooperation", "agreement", "support", "stable", "resilience",
    "investment", "growth", "coordination",
    "együttműködés", "megállapodás", "támogatás",
    "stabil", "ellenállóképesség", "beruházás"
]


def load_json(path, fallback):
    if not os.path.exists(path):
        return fallback

    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def text_blob(items):
    parts = []

    for item in items:
        if isinstance(item, dict):
            parts.append(str(item.get("title", "")))
            parts.append(str(item.get("summary", "")))
            parts.append(str(item.get("topic", "")))

    return " ".join(parts).lower()


def score_narratives(text):
    results = []

    for name, keywords in NARRATIVE_RULES.items():
        score = 0

        for keyword in keywords:
            if keyword.lower() in text:
                score += 10

        if score > 0:
            results.append({
                "name": name,
                "score": min(score, 100)
            })

    results = sorted(results, key=lambda x: x["score"], reverse=True)

    return results[:5]


def sentiment_counts(text):
    negative = sum(1 for word in NEGATIVE_WORDS if word in text)
    positive = sum(1 for word in POSITIVE_WORDS if word in text)

    return negative, positive


def build_security_layer(country_id, latest_country, security_overlay, narratives):
    security = security_overlay.get("countries", {}).get(country_id, {})

    base_security = security.get("security_score", 0)
    event_count = security.get("event_count", 0)

    narrative_bonus = 0
    for item in narratives:
        if item["name"] in [
            "Biztonsági kockázat",
            "Ukrajna és Oroszország",
            "Kiber és dezinformáció",
            "Migráció és határnyomás"
        ]:
            narrative_bonus += item["score"] * 0.15

    news_risk = latest_country.get("risk_score", 0)

    final_score = round(
        min(
            100,
            base_security * 0.45 +
            news_risk * 0.35 +
            narrative_bonus +
            min(event_count * 1.2, 15)
        ),
        1
    )

    if final_score >= 70:
        level = "high"
    elif final_score >= 40:
        level = "medium"
    elif final_score >= 20:
        level = "low"
    else:
        level = "minimal"

    main_narrative = "Biztonságpolitikai kockázatok és hibrid nyomás"

    if narratives:
        main_narrative = narratives[0]["name"]

    return {
        "security_risk": final_score,
        "level": level,
        "events": event_count,
        "source": security.get("source", "news_derived"),
        "main_security_narrative": main_narrative
    }


def build_social_layer(country_id, raw_items, social_overlay):
    social = social_overlay.get("countries", {}).get(country_id, {})

    if social.get("source_status") == "active":
        return social

    text = text_blob(raw_items)
    negative, positive = sentiment_counts(text)

    mentions = len(raw_items)
    index = max(0, min(100, 50 + positive * 8 - negative * 7 + mentions))

    narratives = score_narratives(text)

    main_topic = (
        narratives[0]["name"]
        if narratives
        else "Social monitoring not yet active"
    )

    topic_rows = [
        {
            "name": item["name"],
            "count": max(1, round(item["score"] / 10))
        }
        for item in narratives[:4]
    ]

    return {
        "mentions": mentions,
        "negative": negative,
        "positive": positive,
        "index": index,
        "x_mentions": 0,
        "reddit_mentions": 0,
        "mastodon_mentions": 0,
        "main_social_topic": main_topic,
        "reliable_sources": 0,
        "geopolitical_score": sum(item["score"] for item in narratives),
        "topics": topic_rows,
        "source_status": "news_derived_fallback"
    }


def build_combined_history(country_id, country_history, social_layer, security_layer):
    rows = country_history.get("countries", {}).get(country_id, [])

    output = []

    for row in rows:
        news_risk = row.get("risk_score", 0)

        output.append({
            "date": row.get("date"),
            "news_risk": news_risk,
            "social_index": social_layer.get("index", 0),
            "security_risk": security_layer.get("security_risk", 0),
            "combined_score": round(
                news_risk * 0.45 +
                social_layer.get("index", 0) * 0.25 +
                security_layer.get("security_risk", 0) * 0.30,
                1
            )
        })

    return output[-14:]


def main():
    raw_news = load_json(RAW_NEWS_PATH, {"items": {}})
    latest = load_json(LATEST_STATUS_PATH, {"countries": []})
    security_overlay = load_json(SECURITY_OVERLAY_PATH, {"countries": {}})
    social_overlay = load_json(SOCIAL_OVERLAY_PATH, {"countries": {}})
    country_history = load_json(COUNTRY_HISTORY_PATH, {"countries": {}})

    output = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "description": "Prepared visualization layers for the CEE Strategic Monitor dashboard.",
        "countries": {}
    }

    raw_items_by_country = raw_news.get("items", {})

    for country in latest.get("countries", []):
        country_id = country.get("id")
        raw_items = raw_items_by_country.get(country_id, [])

        text = text_blob(raw_items)
        narratives = score_narratives(text)

        social_layer = build_social_layer(
            country_id,
            raw_items,
            social_overlay
        )

        security_layer = build_security_layer(
            country_id,
            country,
            security_overlay,
            narratives
        )

        combined_history = build_combined_history(
            country_id,
            country_history,
            social_layer,
            security_layer
        )

        output["countries"][country_id] = {
            "dominant_narratives": narratives,
            "security_layer": security_layer,
            "social_layer": social_layer,
            "combined_history": combined_history
        }

    save_json(OUTPUT_PATH, output)

    print(f"[OK] Dashboard layers saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
