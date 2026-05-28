import json
import os
from datetime import datetime, timezone


RAW_NEWS_PATH = "docs/data/raw_news.json"
LATEST_STATUS_PATH = "docs/data/latest_status.json"
SECURITY_OVERLAY_PATH = "docs/data/security_overlay.json"
SOCIAL_OVERLAY_PATH = "docs/data/social_overlay.json"
COUNTRY_HISTORY_PATH = "docs/data/history/country_history.json"
OUTPUT_PATH = "docs/data/dashboard_layers.json"


MAIN_NARRATIVE_RULES = {
    "NATO keleti szárny és katonai elrettentés": [
        "nato", "eastern flank", "deterrence", "troops", "military",
        "defence", "defense", "army", "exercise", "air policing",
        "katonai", "hadsereg", "védelem", "wojsko", "bezpieczeństwo",
        "bezpečnosť", "securitate", "julgeolek", "drošība", "saugumas"
    ],
    "Ukrajna támogatása és orosz–ukrán háború": [
        "ukraine", "ukrainian", "kyiv", "russia", "russian", "war",
        "sanctions", "frontline", "ukrajna", "ukraina", "ucraina",
        "oroszország", "rosja", "rusko", "rusia", "venemaa",
        "krievija", "rusija", "háború", "wojna", "vojna", "válka"
    ],
    "EU-politika, jogállamiság és uniós források": [
        "european union", "eu", "brussels", "commission", "council",
        "rule of law", "eu funds", "cohesion funds", "democracy",
        "európai unió", "brüsszel", "bizottság", "jogállamiság",
        "praworządność", "statul de drept"
    ],
    "Belpolitikai feszültség és választási dinamika": [
        "government", "parliament", "opposition", "election", "coalition",
        "resignation", "prime minister", "president", "party", "cabinet",
        "protest", "corruption", "court", "media freedom",
        "kormány", "parlament", "ellenzék", "választás", "koalíció",
        "tüntetés", "korrupció", "bíróság", "rząd", "opozycja",
        "wybory", "vláda", "opozícia", "voľby", "guvern", "alegeri"
    ],
    "Kiberbiztonság és dezinformáció": [
        "cyber", "cyberattack", "ransomware", "hack", "disinformation",
        "propaganda", "hybrid", "information warfare", "kiber",
        "kibertámadás", "dezinformáció", "kybernetický", "dezinformace",
        "atac cibernetic", "küberrünnak", "kiberuzbrukums"
    ],
    "Energiabiztonság, gazdaság és infrastruktúra": [
        "energy", "gas", "oil", "pipeline", "electricity", "nuclear",
        "lng", "inflation", "economy", "infrastructure", "energia",
        "gáz", "olaj", "vezeték", "infláció", "gazdaság", "plyn",
        "ropa", "infrastruktura"
    ],
    "Belarusz, Kalinyingrád és határbiztonság": [
        "belarus", "belarusian", "kaliningrad", "border security",
        "border pressure", "suwalki", "suwałki", "białoruś",
        "baltarusija", "kaliningradas", "határ", "granica",
        "robeža", "siena"
    ],
    "Fekete-tengeri biztonság és Moldova": [
        "black sea", "moldova", "transnistria", "danube", "constanta",
        "marea neagră", "dunărea", "romania nato", "black sea security"
    ],
    "Külső befolyás és hibrid műveletek": [
        "russian influence", "china", "chinese", "foreign influence",
        "hybrid operation", "espionage", "spy", "sabotage",
        "orosz befolyás", "kína", "kínai", "külső befolyás",
        "rosyjski wpływ", "chiny", "szpieg", "influență rusă"
    ],
    "Migráció és határnyomás": [
        "migration", "migrant", "refugee", "asylum", "border pressure",
        "migráció", "menekült", "menedékjog", "migracja",
        "uchodźcy", "azyl", "migrácia", "migrație", "refugiat"
    ],
    "V4 együttműködés és regionális törésvonalak": [
        "visegrad", "v4", "central europe", "regional cooperation",
        "visegrád", "közép-európa", "współpraca regionalna"
    ]
}


SUB_NARRATIVE_RULES = {
    "NATO keleti szárny és katonai elrettentés": {
        "keleti szárny megerősítése": [
            "eastern flank", "forward presence", "nato presence",
            "keleti szárny", "előretolt jelenlét"
        ],
        "hadgyakorlatok és katonai készültség": [
            "exercise", "military drill", "training", "readiness",
            "hadgyakorlat", "készültség", "gyakorlat"
        ],
        "légtérellenőrzés és légvédelem": [
            "air policing", "air defence", "airspace", "fighter jets",
            "légtér", "légvédelem", "vadászgép"
        ],
        "védelmi kiadások és fegyverbeszerzés": [
            "defence spending", "defense spending", "arms procurement",
            "weapons", "missile", "drone", "védelmi kiadás",
            "fegyverbeszerzés", "rakéta", "drón"
        ],
        "balti elrettentés": [
            "baltic defence", "baltic security", "estonia", "latvia",
            "lithuania", "balti", "baltic states"
        ]
    },
    "Ukrajna támogatása és orosz–ukrán háború": {
        "katonai támogatás Ukrajnának": [
            "military aid", "weapons for ukraine", "ammunition",
            "ukraine support", "katonai támogatás", "lőszer"
        ],
        "szankciós politika": [
            "sanctions", "sanction package", "russian assets",
            "szankció", "befagyasztott vagyon"
        ],
        "háborús fáradtság és politikai vita": [
            "war fatigue", "support fatigue", "domestic debate",
            "háborús fáradtság", "politikai vita"
        ],
        "orosz diplomáciai nyomás": [
            "russian pressure", "moscow", "kremlin", "diplomatic pressure",
            "orosz nyomás", "moszkva", "kreml"
        ],
        "menekültügy és humanitárius terhek": [
            "refugees from ukraine", "ukrainian refugees", "humanitarian",
            "ukrán menekültek", "humanitárius"
        ]
    },
    "EU-politika, jogállamiság és uniós források": {
        "uniós források és kohéziós pénzek": [
            "eu funds", "cohesion funds", "recovery funds",
            "uniós forrás", "helyreállítási alap", "kohéziós"
        ],
        "jogállamisági eljárás": [
            "rule of law", "article 7", "conditionality",
            "jogállamiság", "feltételességi eljárás"
        ],
        "korrupció és intézményi bizalom": [
            "corruption", "anti-corruption", "fraud", "scandal",
            "korrupció", "csalás", "botrány"
        ],
        "igazságszolgáltatási reform": [
            "judiciary", "court reform", "justice reform",
            "bíróság", "igazságszolgáltatás"
        ],
        "EU-s döntéshozatali konfliktus": [
            "brussels", "commission", "council", "veto", "eu decision",
            "brüsszel", "bizottság", "vétó"
        ]
    },
    "Belpolitikai feszültség és választási dinamika": {
        "kormány–ellenzék konfliktus": [
            "government", "opposition", "ruling party", "ellenzék",
            "kormány", "rząd", "opozycja", "vláda", "opozícia",
            "opozice", "guvern"
        ],
        "választási kampány és politikai verseny": [
            "election", "campaign", "vote", "poll", "választás",
            "kampány", "wybory", "voľby", "volby", "alegeri"
        ],
        "korrupciós ügyek": [
            "corruption", "fraud", "bribery", "scandal", "korrupció",
            "korupcja", "korupcia", "korupce", "corupție"
        ],
        "tüntetések és utcai mobilizáció": [
            "protest", "demonstration", "strike", "riot", "tüntetés",
            "tiltakozás", "protesty", "štrajk", "manifestace", "proteste"
        ],
        "parlamenti válság vagy kormányválság": [
            "parliament", "coalition", "government crisis", "resignation",
            "cabinet", "parlament", "koalíció", "lemondás",
            "dissolution"
        ],
        "igazságszolgáltatási vita": [
            "court", "judiciary", "justice", "constitutional court",
            "bíróság", "igazságszolgáltatás", "trybunał", "sąd",
            "soud", "justiție"
        ],
        "médiaszabadság és civil szféra": [
            "media freedom", "press freedom", "ngo", "civil society",
            "média", "sajtószabadság", "civil", "organizacja pozarządowa"
        ],
        "polarizáció és radikalizáció": [
            "polarization", "radical", "extremist", "far-right",
            "far left", "polarizáció", "radikalizáció", "szélsőjobb",
            "populist"
        ],
        "kisebbségi vagy etnikai belpolitikai vita": [
            "minority", "ethnic", "language law", "roma",
            "russian minority", "kisebbség", "etnikai", "nyelvtörvény"
        ],
        "helyi önkormányzati konfliktus": [
            "mayor", "municipality", "local government", "city council",
            "polgármester", "önkormányzat", "rada miasta", "primar"
        ]
    },
    "Kiberbiztonság és dezinformáció": {
        "kibertámadás": [
            "cyberattack", "cyber attack", "hack", "ransomware",
            "kibertámadás", "kiber"
        ],
        "dezinformációs kampány": [
            "disinformation", "propaganda", "fake news",
            "dezinformáció", "propaganda"
        ],
        "választási befolyásolás": [
            "election interference", "foreign interference",
            "választási befolyásolás"
        ],
        "kritikus infrastruktúra elleni kiberkockázat": [
            "critical infrastructure", "infrastructure attack",
            "kritikus infrastruktúra"
        ]
    },
    "Energiabiztonság, gazdaság és infrastruktúra": {
        "gázfüggőség és energiaellátás": [
            "gas supply", "energy dependence", "pipeline", "gázellátás",
            "energiafüggőség", "vezeték"
        ],
        "nukleáris energia": [
            "nuclear", "nuclear power", "atomenergia", "paksi", "paks"
        ],
        "infláció és gazdasági nyomás": [
            "inflation", "prices", "cost of living", "infláció",
            "megélhetési költségek"
        ],
        "kritikus infrastruktúra": [
            "infrastructure", "rail", "port", "grid", "critical infrastructure",
            "infrastruktúra", "hálózat"
        ],
        "LNG és energiaútvonalak": [
            "lng", "energy routes", "terminal", "interconnector",
            "energiaútvonal", "terminál"
        ]
    },
    "Belarusz, Kalinyingrád és határbiztonság": {
        "Belarusz-határ nyomása": [
            "belarus border", "border pressure", "białoruś", "baltarusija",
            "belarusz-határ"
        ],
        "Kalinyingrád és Suwałki-folyosó": [
            "kaliningrad", "suwalki", "suwałki", "kaliningradas"
        ],
        "migrációs határnyomás": [
            "migrant", "migration", "asylum", "migráció", "menekült"
        ],
        "határincidensek és légtérsértés": [
            "border incident", "airspace violation", "határincidens",
            "légtérsértés"
        ]
    },
    "Fekete-tengeri biztonság és Moldova": {
        "Fekete-tengeri NATO-jelenlét": [
            "black sea security", "nato black sea", "marea neagră"
        ],
        "Moldova és Transznisztria": [
            "moldova", "transnistria", "transnistria"
        ],
        "Duna és kikötői infrastruktúra": [
            "danube", "constanta", "port", "dunărea", "kikötő"
        ]
    },
    "Külső befolyás és hibrid műveletek": {
        "orosz befolyás": [
            "russian influence", "kremlin", "moscow", "orosz befolyás",
            "kreml", "moszkva"
        ],
        "kínai gazdasági vagy politikai jelenlét": [
            "china", "chinese investment", "belt and road", "kína",
            "kínai beruházás"
        ],
        "kémkedés és szabotázs": [
            "spy", "espionage", "sabotage", "kémkedés", "szabotázs"
        ],
        "hibrid műveletek": [
            "hybrid operation", "hybrid threat", "hibrid művelet",
            "hibrid fenyegetés"
        ]
    }
}
def load_json(path, default=None):
    if default is None:
        default = {}

    if not os.path.exists(path):
        return default

    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)

    except Exception:
        return default


def normalize_text(text):
    if not text:
        return ""

    return str(text).lower().strip()


def article_text(article):
    return normalize_text(
        f"{article.get('title', '')} "
        f"{article.get('description', '')} "
        f"{article.get('source', '')} "
        f"{article.get('url', '')}"
    )


def score_main_narratives(articles):
    scores = {}

    for article in articles:
        text = article_text(article)

        for narrative, keywords in MAIN_NARRATIVE_RULES.items():

            for keyword in keywords:

                if keyword.lower() in text:
                    scores[narrative] = scores.get(narrative, 0) + 1

    return sorted(
        scores.items(),
        key=lambda item: item[1],
        reverse=True
    )


def score_sub_narratives(main_narrative, articles):

    sub_rules = SUB_NARRATIVE_RULES.get(main_narrative, {})

    scores = {}

    for sub_name, keywords in sub_rules.items():

        scores[sub_name] = 0

        for article in articles:

            text = article_text(article)

            for keyword in keywords:

                if keyword.lower() in text:
                    scores[sub_name] += 1

    filtered = {
        key: value
        for key, value in scores.items()
        if value > 0
    }

    return sorted(
        filtered.items(),
        key=lambda item: item[1],
        reverse=True
    )


def top_narrative_drivers(articles, limit=5):

    scored = []

    for article in articles:

        text = article_text(article)

        score = 0

        for keywords in MAIN_NARRATIVE_RULES.values():

            for keyword in keywords:

                if keyword.lower() in text:
                    score += 1

        if any(
            word in text
            for word in [
                "war", "security", "nato", "protest", "corruption",
                "cyber", "hybrid", "sanctions", "military",
                "háború", "biztonság", "korrupció",
                "kiber", "tüntetés"
            ]
        ):
            score += 3

        scored.append((score, article))

    scored = sorted(
        scored,
        key=lambda item: item[0],
        reverse=True
    )

    result = []

    for score, article in scored[:limit]:

        result.append({
            "title": article.get("title", ""),
            "source": article.get("source", ""),
            "url": article.get("url", ""),
            "score": score
        })

    return result


def build_narrative_summary(main_narrative, sub_narratives):

    if not main_narrative:
        return "Nem azonosítható domináns stratégiai narratíva."

    top_subs = [item[0] for item in sub_narratives[:3]]

    if not top_subs:
        return (
            f"A domináns stratégiai narratíva jelenleg: "
            f"{main_narrative}."
        )

    return (
        f"A domináns stratégiai narratíva jelenleg: "
        f"{main_narrative}. "
        f"A legerősebb alnarratívák: "
        f"{', '.join(top_subs)}."
    )


def build_security_layer(country, security_overlay):

    security_data = security_overlay.get(
        "countries",
        {}
    ).get(
        country["id"],
        {}
    )

    return {
        "security_risk_score": security_data.get(
            "risk_score",
            country.get("risk_score", 0)
        ),
        "security_status": security_data.get(
            "risk_level",
            country.get("risk_level", "UNKNOWN")
        ),
        "security_events": security_data.get(
            "security_hits",
            0
        ),
        "security_trend": security_data.get(
            "security_trend",
            country.get("security_trend", "STABLE")
        )
    }


def build_social_layer(country, social_overlay):

    social_data = social_overlay.get(
        "countries",
        {}
    ).get(
        country["id"],
        {}
    )

    return {
        "social_index": social_data.get("index", 0),
        "social_mentions": social_data.get("mentions", 0),
        "x_mentions": social_data.get("x_mentions", 0),
        "reddit_mentions": social_data.get("reddit_mentions", 0),
        "mastodon_mentions": social_data.get("mastodon_mentions", 0),
        "social_topic": social_data.get(
            "main_social_topic",
            ""
        ),
        "social_topics": social_data.get(
            "topics",
            []
        )
    }


def build_combined_history(country_id, country_history):

    rows = country_history.get(
        "countries",
        {}
    ).get(
        country_id,
        []
    )

    combined = []

    for row in rows[-30:]:

        combined.append({
            "date": row.get("date"),
            "risk_score": row.get("risk_score", 0),
            "social_signal": row.get("social_signal", 0),
            "article_count": row.get("article_count", 0)
        })

    return combined


def build_country_dashboard_layer(
    country,
    articles,
    security_overlay,
    social_overlay,
    country_history
):

    narrative_scores = score_main_narratives(articles)

    dominant_narratives = []

    for narrative_name, score in narrative_scores[:4]:

        sub_scores = score_sub_narratives(
            narrative_name,
            articles
        )

        dominant_narratives.append({
            "name": narrative_name,
            "score": score,
            "sub_narratives": [
                {
                    "name": item[0],
                    "score": item[1]
                }
                for item in sub_scores[:6]
            ]
        })

    main_narrative = (
        dominant_narratives[0]["name"]
        if dominant_narratives
        else ""
    )

    main_sub_narratives = []

    if dominant_narratives:
        main_sub_narratives = [
            (
                item["name"],
                item["score"]
            )
            for item in dominant_narratives[0].get(
                "sub_narratives",
                []
            )
        ]

    security_layer = build_security_layer(
        country,
        security_overlay
    )

    social_layer = build_social_layer(
        country,
        social_overlay
    )

    history = build_combined_history(
        country["id"],
        country_history
    )

    return {
        "id": country["id"],
        "country": country.get("country"),
        "country_local": country.get("country_local"),
        "risk_level": country.get("risk_level"),
        "risk_score": country.get("risk_score"),
        "political_mood": country.get("political_mood"),
        "security_trend": country.get("security_trend"),
        "main_topic": country.get("main_topic"),
        "article_count": country.get("article_count", 0),

        "dominant_narratives": dominant_narratives,

        "narrative_summary": build_narrative_summary(
            main_narrative,
            main_sub_narratives
        ),

        "top_narrative_drivers": top_narrative_drivers(
            articles,
            limit=6
        ),

        "security_layer": security_layer,

        "social_layer": social_layer,

        "combined_history": history,

        "top_articles": country.get(
            "top_articles",
            []
        )
    }


def main():

    latest_status = load_json(
        LATEST_STATUS_PATH,
        {}
    )

    raw_news = load_json(
        RAW_NEWS_PATH,
        {}
    )

    security_overlay = load_json(
        SECURITY_OVERLAY_PATH,
        {}
    )

    social_overlay = load_json(
        SOCIAL_OVERLAY_PATH,
        {}
    )

    country_history = load_json(
        COUNTRY_HISTORY_PATH,
        {}
    )

    countries = latest_status.get(
        "countries",
        []
    )

    raw_items = raw_news.get(
        "items",
        {}
    )

    dashboard_layers = []

    for country in countries:

        country_id = country.get("id")

        articles = raw_items.get(
            country_id,
            []
        )

        layer = build_country_dashboard_layer(
            country,
            articles,
            security_overlay,
            social_overlay,
            country_history
        )

        dashboard_layers.append(layer)

    regional_risk = round(
        sum(
            item.get("risk_score", 0)
            for item in dashboard_layers
        ) / max(len(dashboard_layers), 1)
    )

    regional_social = round(
        sum(
            item.get(
                "social_layer",
                {}
            ).get(
                "social_index",
                0
            )
            for item in dashboard_layers
        ) / max(len(dashboard_layers), 1)
    )

    top_regional_narratives = {}

    for layer in dashboard_layers:

        for narrative in layer.get(
            "dominant_narratives",
            []
        ):

            name = narrative["name"]

            top_regional_narratives[name] = (
                top_regional_narratives.get(name, 0)
                + narrative["score"]
            )

    regional_narratives = sorted(
        top_regional_narratives.items(),
        key=lambda item: item[1],
        reverse=True
    )

    output = {
        "last_update": datetime.now(
            timezone.utc
        ).isoformat(),

        "source": (
            "latest_status.json + raw_news.json + "
            "security_overlay.json + social_overlay.json"
        ),

        "regional_summary": {
            "regional_risk_score": regional_risk,
            "regional_social_score": regional_social,
            "top_regional_narratives": [
                {
                    "name": item[0],
                    "score": item[1]
                }
                for item in regional_narratives[:8]
            ]
        },

        "countries": dashboard_layers
    }

    os.makedirs(
        os.path.dirname(OUTPUT_PATH),
        exist_ok=True
    )

    with open(
        OUTPUT_PATH,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            output,
            file,
            ensure_ascii=False,
            indent=2
        )

    print(
        f"Dashboard layers frissítve: {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()
