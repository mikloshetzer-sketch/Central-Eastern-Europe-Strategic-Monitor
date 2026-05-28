import json
import os
import re
import time
from datetime import datetime, timezone
from urllib.parse import quote_plus

import requests


COUNTRIES = {
    "hungary": {
        "name": "Hungary",
        "keywords": ["Hungary", "Budapest", "Hungarian government", "Orbán", "Viktor Orban"],
        "coords": [47.4979, 19.0402],
    },
    "poland": {
        "name": "Poland",
        "keywords": ["Poland", "Warsaw", "Polish government", "NATO eastern flank"],
        "coords": [52.2297, 21.0122],
    },
    "slovakia": {
        "name": "Slovakia",
        "keywords": ["Slovakia", "Bratislava", "Slovak government", "Fico"],
        "coords": [48.1486, 17.1077],
    },
    "czechia": {
        "name": "Czechia",
        "keywords": ["Czechia", "Czech Republic", "Prague", "Czech government"],
        "coords": [50.0755, 14.4378],
    },
    "romania": {
        "name": "Romania",
        "keywords": ["Romania", "Bucharest", "Black Sea security", "Romanian government"],
        "coords": [44.4268, 26.1025],
    },
    "estonia": {
        "name": "Estonia",
        "keywords": ["Estonia", "Tallinn", "Baltic security", "Estonian government"],
        "coords": [59.437, 24.7536],
    },
    "latvia": {
        "name": "Latvia",
        "keywords": ["Latvia", "Riga", "Baltic security", "Latvian government"],
        "coords": [56.9496, 24.1052],
    },
    "lithuania": {
        "name": "Lithuania",
        "keywords": ["Lithuania", "Vilnius", "Kaliningrad", "Lithuanian government"],
        "coords": [54.6872, 25.2797],
    },
}


TOPIC_RULES = {
    "Military security": [
        "nato", "military", "defence", "defense", "army", "troops", "border",
        "missile", "drone", "airspace", "deterrence"
    ],
    "Ukraine war": [
        "ukraine", "kyiv", "russia", "russian", "war", "sanctions", "frontline"
    ],
    "Cyber security": [
        "cyber", "hack", "ransomware", "disinformation", "information warfare"
    ],
    "Energy security": [
        "energy", "gas", "oil", "pipeline", "electricity", "nuclear", "lng"
    ],
    "Domestic political stability": [
        "election", "government", "parliament", "protest", "coalition",
        "opposition", "corruption", "rule of law"
    ],
    "EU policy": [
        "european union", "eu", "brussels", "commission", "council", "funds"
    ],
}


NEGATIVE_WORDS = [
    "crisis", "threat", "attack", "war", "tension", "conflict", "protest",
    "corruption", "sanction", "risk", "pressure", "hybrid", "spy", "espionage"
]

POSITIVE_WORDS = [
    "cooperation", "agreement", "support", "growth", "stable", "investment",
    "security assistance", "resilience", "modernisation", "coordination"
]


def ensure_dirs():
    os.makedirs("docs/data", exist_ok=True)


def gdelt_query(country_name, keywords, max_records=10):
    query = " OR ".join([f'"{kw}"' if " " in kw else kw for kw in keywords])
    query = f"({query})"

    url = (
        "https://api.gdeltproject.org/api/v2/doc/doc"
        f"?query={quote_plus(query)}"
        "&mode=artlist"
        "&format=json"
        "&sort=hybridrel"
        f"&maxrecords={max_records}"
    )

    try:
        response = requests.get(url, timeout=25)
        response.raise_for_status()
        data = response.json()
        return data.get("articles", [])
    except Exception as exc:
        print(f"[WARN] GDELT fetch failed for {country_name}: {exc}")
        return []


def clean_text(value):
    if not value:
        return ""
    value = re.sub(r"\s+", " ", str(value))
    return value.strip()


def detect_topic(text):
    lower = text.lower()
    scores = {}

    for topic, words in TOPIC_RULES.items():
        score = sum(1 for word in words if word in lower)
        if score > 0:
            scores[topic] = score

    if not scores:
        return "General strategic affairs"

    return max(scores, key=scores.get)


def sentiment_score(text):
    lower = text.lower()
    negative = sum(1 for word in NEGATIVE_WORDS if word in lower)
    positive = sum(1 for word in POSITIVE_WORDS if word in lower)
    return positive - negative


def risk_from_articles(articles):
    if not articles:
        return 45

    risk = 45

    for article in articles:
        text = f"{article.get('title', '')} {article.get('seendate', '')}".lower()

        if any(word in text for word in ["war", "attack", "military", "nato", "border", "drone"]):
            risk += 4
        if any(word in text for word in ["cyber", "hybrid", "disinformation"]):
            risk += 3
        if any(word in text for word in ["protest", "crisis", "corruption"]):
            risk += 2
        if any(word in text for word in ["cooperation", "agreement", "stable"]):
            risk -= 1

    return max(20, min(90, risk))


def risk_level(score):
    if score >= 75:
        return "HIGH"
    if score >= 55:
        return "ELEVATED"
    if score >= 40:
        return "GUARDED"
    return "LOW"


def political_mood(score):
    if score >= 70:
        return "ALERT"
    if score >= 60:
        return "TENSE"
    if score >= 50:
        return "POLARISED"
    if score >= 40:
        return "WATCHFUL"
    return "STABLE"


def security_trend(score):
    if score >= 70:
        return "RISING"
    if score >= 55:
        return "VOLATILE"
    return "STABLE"


def build_country_status(country_id, config):
    articles = gdelt_query(config["name"], config["keywords"], max_records=12)

    normalized_articles = []
    topic_counter = {}

    for item in articles:
        title = clean_text(item.get("title"))
        url = clean_text(item.get("url"))
        source = clean_text(item.get("sourceCountry") or item.get("domain"))
        seen_date = clean_text(item.get("seendate"))

        if not title:
            continue

        topic = detect_topic(title)
        topic_counter[topic] = topic_counter.get(topic, 0) + 1

        normalized_articles.append({
            "title": title,
            "url": url,
            "source": source,
            "seen_date": seen_date,
            "topic": topic
        })

    score = risk_from_articles(normalized_articles)

    if topic_counter:
        main_topic = max(topic_counter, key=topic_counter.get)
    else:
        main_topic = "General strategic affairs"

    if normalized_articles:
        latest_event = normalized_articles[0]["title"]
        top_narrative = f"Current coverage is mainly focused on {main_topic.lower()}."
    else:
        latest_event = "No fresh GDELT article was available during this run."
        top_narrative = "No strong narrative detected. Dashboard is using fallback status."

    social_signal = sentiment_score(" ".join([a["title"] for a in normalized_articles]))

    return {
        "id": country_id,
        "country": config["name"],
        "risk_level": risk_level(score),
        "risk_score": score,
        "political_mood": political_mood(score),
        "social_signal": social_signal,
        "security_trend": security_trend(score),
        "top_narrative": top_narrative,
        "main_topic": main_topic,
        "article_count": len(normalized_articles),
        "latest_event": latest_event,
        "coordinates": config["coords"],
        "top_articles": normalized_articles[:6]
    }


def build_latest_status():
    countries = []

    for country_id, config in COUNTRIES.items():
        print(f"[INFO] Fetching news for {config['name']}...")
        countries.append(build_country_status(country_id, config))
        time.sleep(1)

    avg_risk = round(sum(c["risk_score"] for c in countries) / len(countries))
    stability_score = max(0, min(100, 100 - avg_risk))

    all_topics = {}
    for country in countries:
        topic = country["main_topic"]
        all_topics[topic] = all_topics.get(topic, 0) + 1

    top_topics = sorted(all_topics, key=all_topics.get, reverse=True)[:5]

    latest_status = {
        "last_update": datetime.now(timezone.utc).isoformat(),
        "regional_summary": {
            "overall_risk": risk_level(avg_risk),
            "regional_stability_score": stability_score,
            "regional_risk_score": avg_risk,
            "main_trend": "Automated GDELT-based monitoring of political, security and strategic narratives.",
            "top_topics": top_topics
        },
        "countries": countries
    }

    return latest_status


def main():
    ensure_dirs()

    latest_status = build_latest_status()

    output_path = "docs/data/latest_status.json"

    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(latest_status, file, ensure_ascii=False, indent=2)

    print(f"[OK] Saved latest status to {output_path}")


if __name__ == "__main__":
    main()
