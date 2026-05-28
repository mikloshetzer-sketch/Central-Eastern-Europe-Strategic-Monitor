import json
import os
import re
import time
from datetime import datetime, timezone
from urllib.parse import quote_plus

import feedparser
import requests


CONFIG_PATH = "docs/data/news_sources_config.json"
OUTPUT_PATH = "docs/data/latest_status.json"
RAW_NEWS_PATH = "docs/data/raw_news.json"


TOPIC_RULES = {
    "Military security": [
        "nato", "military", "defence", "defense", "army", "troops", "border",
        "missile", "drone", "airspace", "deterrence", "hadsereg", "katonai",
        "határ", "védelem", "wojsko", "bezpieczeństwo", "bezpečnost",
        "securitate", "julgeolek", "drošība", "saugumas"
    ],
    "Ukraine war": [
        "ukraine", "ukrajna", "ukraina", "ucraina", "russia", "oroszország",
        "rosja", "rusko", "rusia", "venemaa", "krievija", "rusija", "war",
        "háború", "vojna", "wojna", "karš"
    ],
    "Cyber security": [
        "cyber", "kiber", "hack", "ransomware", "disinformation",
        "dezinformáció", "kibertámadás", "kiberatak", "kybernetický",
        "kibernetinė", "küberrünnak", "kiberuzbrukums"
    ],
    "Energy security": [
        "energy", "energia", "gas", "oil", "pipeline", "electricity",
        "nuclear", "lng", "gáz", "olaj", "vezeték", "energiaellátás"
    ],
    "Domestic political stability": [
        "election", "government", "parliament", "protest", "coalition",
        "opposition", "corruption", "rule of law", "választás", "kormány",
        "parlament", "tüntetés", "korrupció", "koalíció"
    ],
    "EU policy": [
        "european union", "eu", "brussels", "commission", "council",
        "funds", "európai unió", "brüsszel", "bizottság"
    ],
}


NEGATIVE_WORDS = [
    "crisis", "threat", "attack", "war", "tension", "conflict", "protest",
    "corruption", "sanction", "risk", "pressure", "hybrid", "spy",
    "háború", "válság", "fenyegetés", "támadás", "tüntetés", "korrupció"
]

POSITIVE_WORDS = [
    "cooperation", "agreement", "support", "growth", "stable", "investment",
    "resilience", "modernisation", "coordination", "együttműködés",
    "megállapodás", "támogatás", "stabil", "beruházás"
]


COUNTRY_COORDS = {
    "hungary": [47.4979, 19.0402],
    "poland": [52.2297, 21.0122],
    "slovakia": [48.1486, 17.1077],
    "czechia": [50.0755, 14.4378],
    "romania": [44.4268, 26.1025],
    "estonia": [59.437, 24.7536],
    "latvia": [56.9496, 24.1052],
    "lithuania": [54.6872, 25.2797],
}


def ensure_dirs():
    os.makedirs("docs/data", exist_ok=True)


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


def clean_text(value):
    if not value:
        return ""
    value = re.sub(r"\s+", " ", str(value))
    return value.strip()


def normalize_url(url):
    return clean_text(url).split("?")[0].strip()


def build_gdelt_query(country_config):
    keywords = []

    keywords.extend(country_config.get("gdelt_keywords_en", []))
    keywords.extend(country_config.get("local_keywords", [])[:5])

    terms = []
    for keyword in keywords:
        if " " in keyword:
            terms.append(f'"{keyword}"')
        else:
            terms.append(keyword)

    return " OR ".join(terms)


def fetch_gdelt(country_id, country_config, max_records=15):
    query = build_gdelt_query(country_config)

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
        articles = data.get("articles", [])
    except Exception as exc:
        print(f"[WARN] GDELT failed for {country_id}: {exc}")
        return []

    output = []

    for item in articles:
        title = clean_text(item.get("title"))
        article_url = normalize_url(item.get("url"))
        domain = clean_text(item.get("domain"))
        seen_date = clean_text(item.get("seendate"))

        if not title or not article_url:
            continue

        output.append({
            "country_id": country_id,
            "source_type": "gdelt",
            "title": title,
            "url": article_url,
            "source": domain,
            "published": seen_date,
            "summary": "",
            "language": country_config.get("language", ""),
            "matched_keywords": [],
        })

    return output


def keyword_match_score(text, keywords):
    lower = text.lower()
    matches = []

    for keyword in keywords:
        k = keyword.lower()
        if k and k in lower:
            matches.append(keyword)

    return matches


def fetch_rss_local(country_id, country_config):
    rss_sources = country_config.get("rss_sources", [])
    local_keywords = country_config.get("local_keywords", [])
    english_keywords = country_config.get("gdelt_keywords_en", [])
    keywords = local_keywords + english_keywords

    output = []

    for feed_url in rss_sources:
        try:
            feed = feedparser.parse(feed_url)
        except Exception as exc:
            print(f"[WARN] RSS parse failed for {feed_url}: {exc}")
            continue

        source_title = clean_text(feed.feed.get("title", feed_url))

        for entry in feed.entries[:30]:
            title = clean_text(entry.get("title"))
            link = normalize_url(entry.get("link"))
            summary = clean_text(entry.get("summary") or entry.get("description"))
            published = clean_text(
                entry.get("published")
                or entry.get("updated")
                or entry.get("created")
            )

            combined = f"{title} {summary}"
            matched_keywords = keyword_match_score(combined, keywords)

            if not title or not link:
                continue

            if not matched_keywords:
                continue

            output.append({
                "country_id": country_id,
                "source_type": "rss_local",
                "title": title,
                "url": link,
                "source": source_title,
                "published": published,
                "summary": summary[:500],
                "language": country_config.get("language", ""),
                "matched_keywords": matched_keywords[:8],
            })

    return output


def deduplicate_articles(articles):
    seen_urls = set()
    seen_titles = set()
    unique = []

    for article in articles:
        url = normalize_url(article.get("url", ""))
        title_key = clean_text(article.get("title", "")).lower()

        title_key = re.sub(r"[^a-zA-Z0-9áéíóöőúüűÁÉÍÓÖŐÚÜŰčďěľĺňôŕšťžąęłńóśźżăâîșț\s]", "", title_key)
        title_key = re.sub(r"\s+", " ", title_key).strip()

        if url and url in seen_urls:
            continue

        if title_key and title_key in seen_titles:
            continue

        if url:
            seen_urls.add(url)

        if title_key:
            seen_titles.add(title_key)

        unique.append(article)

    return unique


def detect_topic(text):
    lower = text.lower()
    scores = {}

    for topic, words in TOPIC_RULES.items():
        score = sum(1 for word in words if word.lower() in lower)
        if score > 0:
            scores[topic] = score

    if not scores:
        return "General strategic affairs"

    return max(scores, key=scores.get)


def sentiment_score(text):
    lower = text.lower()
    negative = sum(1 for word in NEGATIVE_WORDS if word.lower() in lower)
    positive = sum(1 for word in POSITIVE_WORDS if word.lower() in lower)
    return positive - negative


def risk_from_articles(articles):
    if not articles:
        return 40

    risk = 42

    for article in articles:
        text = f"{article.get('title', '')} {article.get('summary', '')}".lower()

        if any(word in text for word in ["war", "háború", "wojna", "vojna", "karš"]):
            risk += 5
        if any(word in text for word in ["attack", "támadás", "drone", "missile"]):
            risk += 5
        if any(word in text for word in ["military", "nato", "border", "katonai", "határ"]):
            risk += 4
        if any(word in text for word in ["cyber", "kiber", "hybrid", "disinformation"]):
            risk += 3
        if any(word in text for word in ["protest", "tüntetés", "crisis", "válság", "corruption"]):
            risk += 2
        if any(word in text for word in ["cooperation", "agreement", "stable", "együttműködés"]):
            risk -= 1

    article_volume_bonus = min(10, len(articles) // 3)
    risk += article_volume_bonus

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
    if score >= 75:
        return "ALERT"
    if score >= 65:
        return "TENSE"
    if score >= 55:
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


def build_country_status(country_id, country_config, articles):
    topic_counter = {}

    for article in articles:
        text = f"{article.get('title', '')} {article.get('summary', '')}"
        topic = detect_topic(text)
        article["topic"] = topic
        topic_counter[topic] = topic_counter.get(topic, 0) + 1

    score = risk_from_articles(articles)

    if topic_counter:
        main_topic = max(topic_counter, key=topic_counter.get)
    else:
        main_topic = "General strategic affairs"

    if articles:
        latest_event = articles[0]["title"]
        top_narrative = f"Current coverage is mainly focused on {main_topic.lower()}."
    else:
        latest_event = "No fresh article was available during this run."
        top_narrative = "No strong narrative detected. Dashboard is using fallback status."

    social_signal = sentiment_score(" ".join([a.get("title", "") for a in articles]))

    return {
        "id": country_id,
        "country": country_config.get("name_en", country_id),
        "country_local": country_config.get("name_local", ""),
        "risk_level": risk_level(score),
        "risk_score": score,
        "political_mood": political_mood(score),
        "social_signal": social_signal,
        "security_trend": security_trend(score),
        "top_narrative": top_narrative,
        "main_topic": main_topic,
        "article_count": len(articles),
        "latest_event": latest_event,
        "coordinates": COUNTRY_COORDS.get(country_id, [0, 0]),
        "top_articles": articles[:8]
    }


def build_latest_status(config):
    countries_output = []
    raw_news = {}

    countries = config.get("countries", {})

    for country_id, country_config in countries.items():
        print(f"[INFO] Fetching news for {country_config.get('name_en', country_id)}...")

        gdelt_articles = fetch_gdelt(country_id, country_config)
        time.sleep(1)

        rss_articles = fetch_rss_local(country_id, country_config)

        articles = deduplicate_articles(gdelt_articles + rss_articles)

        articles = sorted(
            articles,
            key=lambda x: x.get("published", ""),
            reverse=True
        )

        raw_news[country_id] = articles

        status = build_country_status(country_id, country_config, articles)
        countries_output.append(status)

    avg_risk = round(sum(c["risk_score"] for c in countries_output) / len(countries_output))
    stability_score = max(0, min(100, 100 - avg_risk))

    all_topics = {}
    for country in countries_output:
        topic = country["main_topic"]
        all_topics[topic] = all_topics.get(topic, 0) + 1

    top_topics = sorted(all_topics, key=all_topics.get, reverse=True)[:5]

    latest_status = {
        "last_update": datetime.now(timezone.utc).isoformat(),
        "regional_summary": {
            "overall_risk": risk_level(avg_risk),
            "regional_stability_score": stability_score,
            "regional_risk_score": avg_risk,
            "main_trend": "Automated monitoring based on GDELT, local RSS sources and local-language keyword filtering.",
            "top_topics": top_topics
        },
        "countries": countries_output
    }

    return latest_status, raw_news


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def main():
    ensure_dirs()
    config = load_config()

    latest_status, raw_news = build_latest_status(config)

    save_json(OUTPUT_PATH, latest_status)
    save_json(RAW_NEWS_PATH, {
        "last_update": datetime.now(timezone.utc).isoformat(),
        "items": raw_news
    })

    print(f"[OK] Saved latest status to {OUTPUT_PATH}")
    print(f"[OK] Saved raw news to {RAW_NEWS_PATH}")


if __name__ == "__main__":
    main()
