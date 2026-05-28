import json
import os
from datetime import datetime, timezone

import requests


SECURITY_REPO_RAW_BASE = (
    "https://raw.githubusercontent.com/"
    "mikloshetzer-sketch/cee-security-map/main/data"
)

OUTPUT_PATH = "docs/data/security_overlay.json"


COUNTRY_ALIASES = {
    "hungary": ["Hungary", "Magyarország", "Budapest"],
    "poland": ["Poland", "Polska", "Warsaw", "Warszawa"],
    "slovakia": ["Slovakia", "Slovensko", "Bratislava"],
    "czechia": ["Czechia", "Czech Republic", "Česko", "Praha", "Prague"],
    "romania": ["Romania", "România", "Bucharest", "București"],
    "estonia": ["Estonia", "Eesti", "Tallinn"],
    "latvia": ["Latvia", "Latvija", "Riga", "Rīga"],
    "lithuania": ["Lithuania", "Lietuva", "Vilnius"],
}


SECURITY_KEYWORDS = [
    "military",
    "defence",
    "defense",
    "army",
    "troops",
    "border",
    "drone",
    "missile",
    "airspace",
    "nato",
    "cyber",
    "hybrid",
    "disinformation",
    "russia",
    "ukraine",
    "belarus",
    "kaliningrad",
    "critical",
    "infrastructure",
    "attack",
    "explosion",
    "sabotage",
    "security",
    "war",
    "crisis",
    "hadsereg",
    "katonai",
    "határ",
    "kiber",
    "támadás",
    "biztonság",
    "infrastruktúra",
]


def ensure_dirs():
    os.makedirs("docs/data", exist_ok=True)


def fetch_json(filename, fallback):
    url = f"{SECURITY_REPO_RAW_BASE}/{filename}"

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        print(f"[WARN] Could not fetch {filename}: {exc}")
        return fallback


def text_of_feature(feature):
    props = feature.get("properties", {}) if isinstance(feature, dict) else {}

    parts = [
        props.get("title", ""),
        props.get("name", ""),
        props.get("summary", ""),
        props.get("description", ""),
        props.get("event", ""),
        props.get("category", ""),
        props.get("source", ""),
        props.get("country", ""),
    ]

    return " ".join(str(p) for p in parts if p)


def text_matches_country(text, country_id):
    lower = text.lower()

    for alias in COUNTRY_ALIASES.get(country_id, []):
        if alias.lower() in lower:
            return True

    return False


def security_score_from_text(text):
    lower = text.lower()
    score = 0

    for keyword in SECURITY_KEYWORDS:
        if keyword.lower() in lower:
            score += 6

    if "critical" in lower:
        score += 15

    if "high" in lower:
        score += 8

    if "infrastructure" in lower or "infrastruktúra" in lower:
        score += 8

    if "cyber" in lower or "kiber" in lower:
        score += 7

    if "border" in lower or "határ" in lower:
        score += 6

    return min(score, 100)


def level_from_score(score):
    if score >= 75:
        return "high"
    if score >= 45:
        return "medium"
    if score >= 20:
        return "low"
    return "minimal"


def extract_features(geojson_data):
    if not isinstance(geojson_data, dict):
        return []

    features = geojson_data.get("features", [])

    if isinstance(features, list):
        return features

    return []


def build_country_overlay(country_id, all_features, summary_bullets):
    matched_features = []

    for feature in all_features:
        text = text_of_feature(feature)

        if text_matches_country(text, country_id):
            matched_features.append(feature)

    country_text = " ".join(text_of_feature(f) for f in matched_features)
    bullet_text = " ".join(
        bullet for bullet in summary_bullets
        if text_matches_country(bullet, country_id)
    )

    combined_text = f"{country_text} {bullet_text}"

    score = security_score_from_text(combined_text)

    if not matched_features and not bullet_text:
        score = 0

    top_items = []

    for feature in matched_features[:5]:
        props = feature.get("properties", {})
        top_items.append({
            "title": (
                props.get("title")
                or props.get("name")
                or props.get("event")
                or "Security-related item"
            ),
            "source": props.get("source", "cee-security-map"),
            "category": props.get("category", "security"),
            "url": props.get("url", "")
        })

    top_bullets = [
        bullet for bullet in summary_bullets
        if text_matches_country(bullet, country_id)
    ][:3]

    return {
        "country_id": country_id,
        "security_score": score,
        "security_level": level_from_score(score),
        "event_count": len(matched_features),
        "source": "cee-security-map",
        "main_security_narrative": (
            "Security-linked events detected from CEE Security Map."
            if score > 0
            else "No country-specific security event detected from CEE Security Map."
        ),
        "top_security_items": top_items,
        "summary_bullets": top_bullets
    }


def build_overlay():
    daily_osint = fetch_json("daily_osint.geojson", {"features": []})
    direct_news = fetch_json("direct_news.geojson", {"features": []})
    gdelt = fetch_json("gdelt.geojson", {"features": []})
    early = fetch_json("early.json", {})
    summary = fetch_json("summary.json", {})

    all_features = []
    all_features.extend(extract_features(daily_osint))
    all_features.extend(extract_features(direct_news))
    all_features.extend(extract_features(gdelt))

    summary_bullets = summary.get("bullets", [])
    if not isinstance(summary_bullets, list):
        summary_bullets = []

    countries = {}

    for country_id in COUNTRY_ALIASES:
        countries[country_id] = build_country_overlay(
            country_id,
            all_features,
            summary_bullets
        )

    overlay = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source_repo": "mikloshetzer-sketch/cee-security-map",
        "source_files": [
            "daily_osint.geojson",
            "direct_news.geojson",
            "gdelt.geojson",
            "early.json",
            "summary.json"
        ],
        "summary": {
            "headline": summary.get(
                "headline",
                "CEE Security Map background signal"
            ),
            "generated_utc": summary.get("generated_utc", ""),
            "bullet_count": len(summary_bullets),
            "early_signal_available": bool(early)
        },
        "countries": countries
    }

    return overlay


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def main():
    ensure_dirs()
    overlay = build_overlay()
    save_json(OUTPUT_PATH, overlay)

    print(f"[OK] Security overlay saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
