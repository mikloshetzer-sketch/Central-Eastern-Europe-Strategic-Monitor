import json
import os
from datetime import datetime


LATEST_STATUS_PATH = "docs/data/latest_status.json"
REGIONAL_HISTORY_PATH = "docs/data/history/regional_history.json"
COUNTRY_HISTORY_PATH = "docs/data/history/country_history.json"


def ensure_history_dirs():
    os.makedirs("docs/data/history", exist_ok=True)


def load_json(path, fallback):
    if not os.path.exists(path):
        return fallback

    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def today_date():
    return datetime.utcnow().strftime("%Y-%m-%d")


def update_regional_history(latest_status):

    history_data = load_json(
        REGIONAL_HISTORY_PATH,
        {
            "project": "Central & Eastern Europe Strategic Monitor",
            "history": []
        }
    )

    today = today_date()

    regional_summary = latest_status.get("regional_summary", {})

    new_entry = {
        "date": today,
        "regional_stability_score":
            regional_summary.get("regional_stability_score", 0),

        "regional_risk_score":
            regional_summary.get("regional_risk_score", 0),

        "overall_risk":
            regional_summary.get("overall_risk", "UNKNOWN"),

        "main_trend":
            regional_summary.get("main_trend", "")
    }

    history = history_data.get("history", [])

    history = [h for h in history if h.get("date") != today]

    history.append(new_entry)

    history = sorted(history, key=lambda x: x["date"])

    history_data["last_update"] = datetime.utcnow().isoformat()
    history_data["history"] = history[-90:]

    save_json(REGIONAL_HISTORY_PATH, history_data)


def update_country_history(latest_status):

    history_data = load_json(
        COUNTRY_HISTORY_PATH,
        {
            "project": "Central & Eastern Europe Strategic Monitor",
            "countries": {}
        }
    )

    today = today_date()

    countries_history = history_data.get("countries", {})

    for country in latest_status.get("countries", []):

        country_id = country.get("id")

        if country_id not in countries_history:
            countries_history[country_id] = []

        entry = {
            "date": today,
            "risk_score": country.get("risk_score", 0),
            "risk_level": country.get("risk_level", ""),
            "political_mood": country.get("political_mood", ""),
            "social_signal": country.get("social_signal", 0),
            "security_trend": country.get("security_trend", ""),
            "article_count": country.get("article_count", 0),
            "main_topic": country.get("main_topic", "")
        }

        existing = countries_history[country_id]

        existing = [e for e in existing if e.get("date") != today]

        existing.append(entry)

        existing = sorted(existing, key=lambda x: x["date"])

        countries_history[country_id] = existing[-90:]

    history_data["last_update"] = datetime.utcnow().isoformat()
    history_data["countries"] = countries_history

    save_json(COUNTRY_HISTORY_PATH, history_data)


def main():

    ensure_history_dirs()

    latest_status = load_json(LATEST_STATUS_PATH, {})

    if not latest_status:
        print("[ERROR] latest_status.json not found or empty")
        return

    update_regional_history(latest_status)
    update_country_history(latest_status)

    print("[OK] History updated successfully")


if __name__ == "__main__":
    main()
