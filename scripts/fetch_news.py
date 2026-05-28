import json
import os
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime


LATEST_STATUS_PATH = "docs/data/latest_status.json"
RAW_NEWS_PATH = "docs/data/raw_news.json"
REGIONAL_HISTORY_PATH = "docs/data/history/regional_history.json"
COUNTRY_HISTORY_PATH = "docs/data/history/country_history.json"

MAX_ARTICLES_PER_COUNTRY = 90
GDELT_MAX_RECORDS = 50
GDELT_TIMESPAN = "7d"


RSS_FEEDS = [
    # International / regional
    {"name": "Reuters Europe", "url": "https://feeds.reuters.com/reuters/worldNews", "weight": 10},
    {"name": "Politico Europe", "url": "https://www.politico.eu/feed/", "weight": 9},
    {"name": "Euractiv", "url": "https://www.euractiv.com/feed/", "weight": 8},
    {"name": "Euronews", "url": "https://www.euronews.com/rss?level=theme&name=news", "weight": 7},
    {"name": "RFE/RL Europe", "url": "https://www.rferl.org/api/zrqiteuuir", "weight": 8},
    {"name": "NATO News", "url": "https://www.nato.int/cps/en/natohq/rss.xml", "weight": 9},

    # Hungary
    {"name": "Telex", "url": "https://telex.hu/rss", "weight": 8},
    {"name": "HVG", "url": "https://hvg.hu/rss", "weight": 7},
    {"name": "444", "url": "https://444.hu/feed", "weight": 7},
    {"name": "Index", "url": "https://index.hu/24ora/rss/", "weight": 6},
    {"name": "Portfolio Global", "url": "https://www.portfolio.hu/rss/global.xml", "weight": 8},
    {"name": "Portfolio Economy", "url": "https://www.portfolio.hu/rss/gazdasag.xml", "weight": 8},

    # Poland
    {"name": "Notes from Poland", "url": "https://notesfrompoland.com/feed/", "weight": 8},
    {"name": "TVN24 Poland", "url": "https://tvn24.pl/najnowsze.xml", "weight": 8},
    {"name": "Polskie Radio", "url": "https://www.polskieradio.pl/395/rss", "weight": 7},
    {"name": "Rzeczpospolita", "url": "https://www.rp.pl/rss/1010-kraj.xml", "weight": 7},
    {"name": "Wyborcza", "url": "https://wyborcza.pl/pub/rss/wyborcza_kraj.xml", "weight": 7},

    # Slovakia
    {"name": "Aktuality Slovakia", "url": "https://www.aktuality.sk/rss/", "weight": 7},
    {"name": "SME Slovakia", "url": "https://www.sme.sk/rss-title", "weight": 7},
    {"name": "Pravda Slovakia", "url": "https://spravy.pravda.sk/rss/xml/", "weight": 6},
    {"name": "Dennik N Slovakia", "url": "https://dennikn.sk/feed/", "weight": 7},

    # Czechia
    {"name": "iRozhlas", "url": "https://www.irozhlas.cz/rss", "weight": 8},
    {"name": "Novinky Czechia", "url": "https://www.novinky.cz/rss", "weight": 7},
    {"name": "iDNES Czechia", "url": "https://www.idnes.cz/rss.aspx", "weight": 7},
    {"name": "CT24 Czechia", "url": "https://ct24.ceskatelevize.cz/rss/hlavni-zpravy", "weight": 8},

    # Romania
    {"name": "Digi24 Romania", "url": "https://www.digi24.ro/rss", "weight": 8},
    {"name": "HotNews Romania", "url": "https://hotnews.ro/rss", "weight": 7},
    {"name": "G4Media Romania", "url": "https://www.g4media.ro/feed", "weight": 8},
    {"name": "Romania Insider", "url": "https://www.romania-insider.com/rss.xml", "weight": 7},
    {"name": "Europa Libera Romania", "url": "https://romania.europalibera.org/api/zrqiteuuir", "weight": 8},

    # Estonia
    {"name": "ERR Estonia", "url": "https://news.err.ee/rss", "weight": 8},
    {"name": "Postimees Estonia", "url": "https://www.postimees.ee/rss", "weight": 7},
    {"name": "Delfi Estonia", "url": "https://www.delfi.ee/rss", "weight": 7},

    # Latvia
    {"name": "LSM Latvia", "url": "https://eng.lsm.lv/rss/", "weight": 8},
    {"name": "Delfi Latvia", "url": "https://www.delfi.lv/rss/", "weight": 7},
    {"name": "Latvijas Avize", "url": "https://www.la.lv/feed", "weight": 6},

    # Lithuania
    {"name": "LRT Lithuania", "url": "https://www.lrt.lt/rss/news", "weight": 8},
    {"name": "Delfi Lithuania", "url": "https://www.delfi.lt/rss/feeds/news.xml", "weight": 7},
    {"name": "15min Lithuania", "url": "https://www.15min.lt/rss", "weight": 7}
]


COUNTRIES = [
    {
        "id": "hungary",
        "country": "Hungary",
        "country_local": "Magyarország",
        "coordinates": [47.4979, 19.0402],
        "queries": [
            "Hungary politics EU NATO Ukraine",
            "Hungary government Russia Ukraine policy",
            "Hungary rule of law EU funds"
        ],
        "keywords": [
            "hungary", "hungarian", "budapest", "orban", "orbán", "fidesz",
            "magyarország", "magyar", "magyar kormány", "kormány",
            "parlament", "ellenzék", "tüntetés", "jogállamiság",
            "ukrajna", "oroszország", "nato", "eu", "brüsszel"
        ]
    },
    {
        "id": "poland",
        "country": "Poland",
        "country_local": "Polska",
        "coordinates": [52.2297, 21.0122],
        "queries": [
            "Poland politics NATO eastern flank Ukraine",
            "Poland government EU rule of law",
            "Poland Belarus border security"
        ],
        "keywords": [
            "poland", "polish", "warsaw", "warszawa", "polska",
            "polski rząd", "rząd", "opozycja", "wybory", "tusk",
            "duda", "pis", "nato", "ukraina", "rosja", "białoruś",
            "bezpieczeństwo", "granica"
        ]
    },
    {
        "id": "slovakia",
        "country": "Slovakia",
        "country_local": "Slovensko",
        "coordinates": [48.1486, 17.1077],
        "queries": [
            "Slovakia politics Fico Ukraine Russia",
            "Slovakia government NATO EU",
            "Slovakia domestic political crisis"
        ],
        "keywords": [
            "slovakia", "slovak", "bratislava", "fico", "slovensko",
            "slovenská vláda", "vláda", "opozícia", "voľby", "nato",
            "ukrajina", "rusko", "bezpečnosť", "protest"
        ]
    },
    {
        "id": "czechia",
        "country": "Czechia",
        "country_local": "Česko",
        "coordinates": [50.0755, 14.4378],
        "queries": [
            "Czechia politics NATO Ukraine",
            "Czech Republic government EU security",
            "Czechia Russia influence disinformation"
        ],
        "keywords": [
            "czechia", "czech republic", "czech", "prague", "praha",
            "česko", "česká republika", "česká vláda", "vláda",
            "opozice", "volby", "nato", "ukrajina", "rusko",
            "bezpečnost", "dezinformace"
        ]
    },
    {
        "id": "romania",
        "country": "Romania",
        "country_local": "România",
        "coordinates": [44.4268, 26.1025],
        "queries": [
            "Romania politics NATO Black Sea Ukraine",
            "Romania government Moldova security",
            "Romania election EU Russia influence"
        ],
        "keywords": [
            "romania", "romanian", "bucharest", "bucuresti", "bucurești",
            "românia", "guvernul român", "guvern", "alegeri",
            "nato", "ucraina", "rusia", "moldova", "marea neagră",
            "securitate", "corupție"
        ]
    },
    {
        "id": "estonia",
        "country": "Estonia",
        "country_local": "Eesti",
        "coordinates": [59.437, 24.7536],
        "queries": [
            "Estonia NATO Russia cyber security",
            "Estonia government Ukraine Baltic defence",
            "Estonia Russian influence disinformation"
        ],
        "keywords": [
            "estonia", "estonian", "tallinn", "eesti", "eesti valitsus",
            "valitsus", "nato", "ukraina", "venemaa", "julgeolek",
            "küberrünnak", "küberjulgeolek", "balti julgeolek"
        ]
    },
    {
        "id": "latvia",
        "country": "Latvia",
        "country_local": "Latvija",
        "coordinates": [56.9496, 24.1052],
        "queries": [
            "Latvia NATO Russia security",
            "Latvia government Ukraine Baltic defence",
            "Latvia border security disinformation"
        ],
        "keywords": [
            "latvia", "latvian", "riga", "rīga", "latvija",
            "latvijas valdība", "valdība", "nato", "ukraina",
            "krievija", "drošība", "robeža", "kiberuzbrukums",
            "dezinformācija"
        ]
    },
    {
        "id": "lithuania",
        "country": "Lithuania",
        "country_local": "Lietuva",
        "coordinates": [54.6872, 25.2797],
        "queries": [
            "Lithuania NATO Kaliningrad Belarus security",
            "Lithuania government Ukraine Russia sanctions",
            "Lithuania border security Belarus"
        ],
        "keywords": [
            "lithuania", "lithuanian", "vilnius", "lietuva",
            "lietuvos vyriausybė", "vyriausybė", "nato", "ukraina",
            "rusija", "baltarusija", "kaliningrad", "kaliningradas",
            "saugumas", "kibernetinė ataka"
        ]
    }
]


NEGATIVE_WORDS = [
    "protest", "protests", "crisis", "corruption", "violence", "conflict",
    "tension", "tensions", "sanction", "sanctions", "arrest", "attack",
    "war", "unrest", "fraud", "dispute", "scandal", "threat",
    "instability", "clash", "clashes", "riot", "boycott", "polarization",
    "propaganda", "blocked", "deadlock", "resignation", "investigation",
    "charges", "convicted", "hybrid", "sabotage", "espionage", "spy",
    "háború", "válság", "korrupció", "támadás", "tüntetés",
    "fenyegetés", "feszültség", "szankció", "dezinformáció",
    "wojna", "kryzys", "korupcja", "atak", "protest",
    "vojna", "korupcia", "útok", "kríza",
    "válka", "korupce", "útok", "krize",
    "război", "criză", "corupție", "atac",
    "karš", "krīze", "korupcija", "uzbrukums",
    "sõda", "kriis", "korruptsioon", "rünnak",
    "karas", "krizė", "korupcija", "ataka"
]


POSITIVE_WORDS = [
    "agreement", "reform", "growth", "cooperation", "investment",
    "stability", "dialogue", "progress", "development", "support",
    "partnership", "coordination", "resilience", "aid package",
    "defence cooperation", "eu funds", "nato support",
    "megállapodás", "reform", "együttműködés", "támogatás",
    "stabilitás", "beruházás", "fejlődés",
    "porozumienie", "współpraca", "stabilność",
    "dohoda", "spolupráca", "stabilita",
    "acord", "cooperare", "stabilitate",
    "kokkulepe", "koostöö", "stabiilsus",
    "vienošanās", "sadarbība", "stabilitāte",
    "susitarimas", "bendradarbiavimas", "stabilumas"
]
TOPIC_RULES = [
    {
        "label": "NATO keleti szárny és katonai elrettentés",
        "keywords": [
            "nato", "eastern flank", "deterrence", "troops", "military",
            "defence", "defense", "army", "exercise", "air policing",
            "forward presence", "katonai", "hadsereg", "védelem",
            "wojsko", "bezpieczeństwo", "armia", "vojaci", "bezpečnosť",
            "bezpečnost", "securitate", "julgeolek", "drošība", "saugumas"
        ],
        "weight": 8
    },
    {
        "label": "Ukrajna támogatása és orosz–ukrán háború",
        "keywords": [
            "ukraine", "ukrainian", "kyiv", "russia", "russian", "war",
            "sanctions", "frontline", "ukrajna", "ukraina", "ucraina",
            "oroszország", "rosja", "rusko", "rusia", "venemaa",
            "krievija", "rusija", "háború", "wojna", "vojna", "válka",
            "război", "karš", "karas"
        ],
        "weight": 8
    },
    {
        "label": "EU-politika, jogállamiság és uniós források",
        "keywords": [
            "european union", "eu", "brussels", "commission", "council",
            "rule of law", "eu funds", "cohesion funds", "democracy",
            "európai unió", "brüsszel", "bizottság", "jogállamiság",
            "unijne fundusze", "praworządność", "eurofondy",
            "vláda zákona", "statul de drept"
        ],
        "weight": 7
    },
    {
        "label": "Belpolitikai feszültség és választási dinamika",
        "keywords": [
            "government", "parliament", "opposition", "election", "coalition",
            "resignation", "prime minister", "president", "party", "cabinet",
            "kormány", "parlament", "ellenzék", "választás", "koalíció",
            "rząd", "opozycja", "wybory", "vláda", "opozícia", "voľby",
            "opozice", "volby", "guvern", "alegeri"
        ],
        "weight": 6
    },
    {
        "label": "Tüntetések, társadalmi nyomás és polarizáció",
        "keywords": [
            "protest", "protests", "demonstration", "strike", "riot",
            "unrest", "boycott", "polarization", "tüntetés", "tiltakozás",
            "sztrájk", "protesty", "demonstracja", "protest", "manifestace",
            "protesty", "proteste", "polarizare"
        ],
        "weight": 6
    },
    {
        "label": "Kiberbiztonság és dezinformáció",
        "keywords": [
            "cyber", "cyberattack", "ransomware", "hack", "disinformation",
            "propaganda", "hybrid", "information warfare", "kiber",
            "kibertámadás", "dezinformáció", "dezinformacja",
            "kybernetický", "kybernetické", "dezinformace",
            "atac cibernetic", "küberrünnak", "kiberuzbrukums",
            "kibernetinė ataka"
        ],
        "weight": 7
    },
    {
        "label": "Energiabiztonság, gazdaság és infrastruktúra",
        "keywords": [
            "energy", "gas", "oil", "pipeline", "electricity", "nuclear",
            "lng", "inflation", "economy", "infrastructure",
            "energia", "gáz", "olaj", "vezeték", "infláció", "gazdaság",
            "energia", "gaz", "ropa", "inflacja", "gospodarka",
            "energie", "plyn", "ropa", "infrastruktura",
            "energie", "gaz", "petrol", "economie"
        ],
        "weight": 5
    },
    {
        "label": "Belarusz, Kalinyingrád és határbiztonság",
        "keywords": [
            "belarus", "belarusian", "kaliningrad", "border security",
            "border pressure", "suwałki", "suwalki", "białoruś",
            "baltarusija", "kaliningradas", "határ", "granica",
            "hranica", "frontier", "robeža", "siena"
        ],
        "weight": 8
    },
    {
        "label": "Fekete-tengeri biztonság és Moldova",
        "keywords": [
            "black sea", "moldova", "transnistria", "danube", "constanta",
            "marea neagră", "moldova", "transnistria", "dunărea",
            "romania nato", "black sea security"
        ],
        "weight": 8
    },
    {
        "label": "Külső befolyás: Oroszország, Kína és hibrid műveletek",
        "keywords": [
            "russian influence", "china", "chinese", "foreign influence",
            "hybrid operation", "espionage", "spy", "sabotage",
            "orosz befolyás", "kína", "kínai", "külső befolyás",
            "rosyjski wpływ", "chiny", "szpieg", "špionáž",
            "influență rusă", "china"
        ],
        "weight": 7
    },
    {
        "label": "Migráció és határnyomás",
        "keywords": [
            "migration", "migrant", "refugee", "asylum", "border pressure",
            "migráció", "menekült", "menedékjog", "migracja",
            "uchodźcy", "azyl", "migrácia", "uprchlík",
            "migrație", "refugiat"
        ],
        "weight": 5
    },
    {
        "label": "V4 együttműködés és regionális törésvonalak",
        "keywords": [
            "visegrad", "v4", "central europe", "regional cooperation",
            "visegrád", "v4", "közép-európa", "współpraca regionalna",
            "visegrádská", "visegrád"
        ],
        "weight": 6
    }
]


def ensure_dirs():
    os.makedirs("docs/data", exist_ok=True)
    os.makedirs("docs/data/history", exist_ok=True)


def clean_text(text):
    if not text:
        return ""

    text = re.sub(r"<[^>]+>", " ", str(text))
    text = text.replace("\n", " ")
    text = text.replace("\r", " ")
    text = text.replace("&nbsp;", " ")
    text = text.replace("&amp;", "&")
    text = text.replace("&quot;", '"')
    text = text.replace("&#39;", "'")

    return " ".join(text.split()).strip()


def normalize_url(url):
    return clean_text(url).split("?")[0].strip()


def fetch_url(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 CEE-Strategic-Monitor/1.0"
        }
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def parse_date(value):
    if not value:
        return ""

    try:
        parsed = parsedate_to_datetime(value)

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed.astimezone(timezone.utc).isoformat()

    except Exception:
        return clean_text(value)


def fetch_gdelt_articles(query):
    base_url = "https://api.gdeltproject.org/api/v2/doc/doc"

    params = {
        "query": query,
        "mode": "artlist",
        "format": "json",
        "maxrecords": GDELT_MAX_RECORDS,
        "sort": "datedesc",
        "timespan": GDELT_TIMESPAN
    }

    url = base_url + "?" + urllib.parse.urlencode(params)

    try:
        raw_data = fetch_url(url).decode("utf-8")
        data = json.loads(raw_data)

        articles = []

        for item in data.get("articles", []):
            title = clean_text(item.get("title", ""))
            article_url = normalize_url(item.get("url", ""))

            if not title or not article_url:
                continue

            articles.append({
                "title": title,
                "url": article_url,
                "source": item.get("domain", "GDELT"),
                "source_weight": 5,
                "seen_date": item.get("seendate", ""),
                "description": "",
                "origin": "GDELT"
            })

        return articles

    except Exception as error:
        print(f"GDELT hiba: {query}")
        print(error)
        return []


def fetch_rss_articles(feed):
    articles = []

    try:
        raw_xml = fetch_url(feed["url"])
        root = ET.fromstring(raw_xml)

        # RSS 2.0
        for item in root.findall(".//item"):
            title = clean_text(item.findtext("title", ""))
            link = normalize_url(item.findtext("link", ""))
            pub_date = clean_text(item.findtext("pubDate", ""))
            description = clean_text(item.findtext("description", ""))

            if not title or not link:
                continue

            articles.append({
                "title": title,
                "url": link,
                "source": feed["name"],
                "source_weight": feed.get("weight", 5),
                "seen_date": parse_date(pub_date),
                "description": description,
                "origin": "RSS"
            })

        # Atom fallback
        if not articles:
            ns = {"atom": "http://www.w3.org/2005/Atom"}

            for entry in root.findall(".//atom:entry", ns):
                title = clean_text(entry.findtext("atom:title", "", ns))
                link_node = entry.find("atom:link", ns)
                link = ""

                if link_node is not None:
                    link = normalize_url(link_node.attrib.get("href", ""))

                updated = clean_text(entry.findtext("atom:updated", "", ns))
                summary = clean_text(entry.findtext("atom:summary", "", ns))

                if not title or not link:
                    continue

                articles.append({
                    "title": title,
                    "url": link,
                    "source": feed["name"],
                    "source_weight": feed.get("weight", 5),
                    "seen_date": parse_date(updated),
                    "description": summary,
                    "origin": "RSS"
                })

        print(f"RSS találatok: {feed['name']} - {len(articles)}")

    except Exception as error:
        print(f"RSS hiba: {feed['name']}")
        print(error)

    return articles


def fetch_all_rss_articles():
    all_articles = []

    for feed in RSS_FEEDS:
        all_articles.extend(fetch_rss_articles(feed))
        time.sleep(0.3)

    return all_articles


def article_text(article):
    return (
        f"{article.get('title', '')} "
        f"{article.get('description', '')} "
        f"{article.get('source', '')} "
        f"{article.get('url', '')}"
    ).lower()


def is_relevant(article, keywords):
    text = article_text(article)

    for keyword in keywords:
        if keyword.lower() in text:
            return True

    return False


def collect_articles(country, rss_articles):
    all_articles = []
    seen_urls = set()

    for query in country["queries"]:
        gdelt_articles = fetch_gdelt_articles(query)

        for article in gdelt_articles:
            url = article.get("url", "")

            if not url:
                continue

            if url in seen_urls:
                continue

            if not is_relevant(article, country["keywords"]):
                continue

            seen_urls.add(url)
            all_articles.append(article)

        time.sleep(0.5)

    for article in rss_articles:
        url = article.get("url", "")

        if not url:
            continue

        if url in seen_urls:
            continue

        if not is_relevant(article, country["keywords"]):
            continue

        seen_urls.add(url)
        all_articles.append(article)

    return all_articles[:MAX_ARTICLES_PER_COUNTRY]


def classify_topics(articles):
    topic_scores = {}

    for article in articles:
        text = article_text(article)

        for rule in TOPIC_RULES:
            label = rule["label"]
            weight = rule.get("weight", 1)

            for keyword in rule["keywords"]:
                if keyword.lower() in text:
                    topic_scores[label] = topic_scores.get(label, 0) + weight
                    break

    sorted_topics = sorted(
        topic_scores.items(),
        key=lambda item: item[1],
        reverse=True
    )

    return {
        "main_topic": (
            sorted_topics[0][0]
            if sorted_topics
            else "nincs kiemelkedő téma"
        ),
        "topic_scores": dict(sorted_topics[:6])
    }


def analyze_articles(articles):
    negative_hits = 0
    positive_hits = 0
    source_weight_total = 0
    security_hits = 0

    for article in articles:
        text = article_text(article)

        source_weight_total += int(article.get("source_weight", 5))

        if any(word.lower() in text for word in NEGATIVE_WORDS):
            negative_hits += 1

        if any(word.lower() in text for word in POSITIVE_WORDS):
            positive_hits += 1

        if any(
            word in text
            for word in [
                "nato", "military", "defence", "defense", "security",
                "border", "cyber", "hybrid", "sabotage", "war",
                "katonai", "biztonság", "határ", "kiber"
            ]
        ):
            security_hits += 1

    risk_score = (
        len(articles) * 1.2
        + negative_hits * 4
        + security_hits * 3
        + min(source_weight_total / 10, 20)
        - positive_hits * 1.5
    )

    risk_score = max(15, min(round(risk_score), 90))

    sentiment_score = (positive_hits * 4) - (negative_hits * 4)
    sentiment_score = max(min(sentiment_score, 30), -30)

    return {
        "risk_score": risk_score,
        "sentiment_score": sentiment_score,
        "negative_hits": negative_hits,
        "positive_hits": positive_hits,
        "security_hits": security_hits
    }


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


def get_top_articles(articles):
    scored = []

    for article in articles:
        text = article_text(article)
        topic_result = classify_topics([article])
        priority = int(article.get("source_weight", 5))

        if any(word.lower() in text for word in NEGATIVE_WORDS):
            priority += 4

        if any(word.lower() in text for word in POSITIVE_WORDS):
            priority += 1

        if topic_result["main_topic"] != "nincs kiemelkedő téma":
            priority += 3

        scored.append((priority, article))

    scored = sorted(scored, key=lambda item: item[0], reverse=True)

    top_articles = []

    for _, article in scored[:8]:
        top_articles.append({
            "title": article.get("title", ""),
            "url": article.get("url", ""),
            "source": article.get("source", ""),
            "seen_date": article.get("seen_date", ""),
            "origin": article.get("origin", "")
        })

    return top_articles


def build_country_output(country, articles):
    analysis = analyze_articles(articles)
    topic_result = classify_topics(articles)

    return {
        "id": country["id"],
        "country": country["country"],
        "country_local": country["country_local"],
        "coordinates": country["coordinates"],
        "risk_level": risk_level(analysis["risk_score"]),
        "risk_score": analysis["risk_score"],
        "political_mood": political_mood(analysis["risk_score"]),
        "social_signal": 0,
        "security_trend": security_trend(analysis["risk_score"]),
        "top_narrative": (
            f"Domináns téma: {topic_result['main_topic']}."
            if topic_result["main_topic"] != "nincs kiemelkedő téma"
            else "Nem azonosítható erős domináns narratíva."
        ),
        "main_topic": topic_result["main_topic"],
        "topic_scores": topic_result["topic_scores"],
        "article_count": len(articles),
        "negative_hits": analysis["negative_hits"],
        "positive_hits": analysis["positive_hits"],
        "security_hits": analysis["security_hits"],
        "latest_event": (
            articles[0]["title"]
            if articles
            else "No fresh article available."
        ),
        "top_articles": get_top_articles(articles)
    }


def update_history(latest_status):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    regional_history = {
        "project": "Central & Eastern Europe Strategic Monitor",
        "history": []
    }

    if os.path.exists(REGIONAL_HISTORY_PATH):
        with open(REGIONAL_HISTORY_PATH, "r", encoding="utf-8") as file:
            regional_history = json.load(file)

    summary = latest_status.get("regional_summary", {})

    regional_history["history"] = [
        row for row in regional_history.get("history", [])
        if row.get("date") != today
    ]

    regional_history["history"].append({
        "date": today,
        "regional_stability_score": summary.get("regional_stability_score", 0),
        "regional_risk_score": summary.get("regional_risk_score", 0),
        "overall_risk": summary.get("overall_risk", "UNKNOWN"),
        "main_trend": summary.get("main_trend", "")
    })

    regional_history["history"] = regional_history["history"][-90:]
    regional_history["last_update"] = datetime.now(timezone.utc).isoformat()

    with open(REGIONAL_HISTORY_PATH, "w", encoding="utf-8") as file:
        json.dump(regional_history, file, ensure_ascii=False, indent=2)

    country_history = {
        "project": "Central & Eastern Europe Strategic Monitor",
        "countries": {}
    }

    if os.path.exists(COUNTRY_HISTORY_PATH):
        with open(COUNTRY_HISTORY_PATH, "r", encoding="utf-8") as file:
            country_history = json.load(file)

    for country in latest_status.get("countries", []):
        country_id = country.get("id")

        rows = country_history.get("countries", {}).get(country_id, [])

        rows = [
            row for row in rows
            if row.get("date") != today
        ]

        rows.append({
            "date": today,
            "risk_score": country.get("risk_score", 0),
            "risk_level": country.get("risk_level", ""),
            "political_mood": country.get("political_mood", ""),
            "social_signal": country.get("social_signal", 0),
            "security_trend": country.get("security_trend", ""),
            "article_count": country.get("article_count", 0),
            "main_topic": country.get("main_topic", "")
        })

        rows = rows[-90:]
        country_history.setdefault("countries", {})[country_id] = rows

    country_history["last_update"] = datetime.now(timezone.utc).isoformat()

    with open(COUNTRY_HISTORY_PATH, "w", encoding="utf-8") as file:
        json.dump(country_history, file, ensure_ascii=False, indent=2)


def main():
    ensure_dirs()

    print("RSS források lekérése...")
    rss_articles = fetch_all_rss_articles()

    countries_output = []
    raw_news = {}

    for country in COUNTRIES:
        print(f"Adatgyűjtés: {country['country']}")

        articles = collect_articles(country, rss_articles)

        print(f"Szűrt cikkek száma: {len(articles)}")

        raw_news[country["id"]] = articles

        countries_output.append(
            build_country_output(country, articles)
        )

    avg_risk = round(
        sum(country["risk_score"] for country in countries_output)
        / len(countries_output)
    )

    regional_stability = max(
        0,
        min(100, 100 - avg_risk)
    )

    topic_counter = {}

    for country in countries_output:
        topic = country.get("main_topic", "")

        if topic:
            topic_counter[topic] = topic_counter.get(topic, 0) + 1

    top_topics = sorted(
        topic_counter,
        key=topic_counter.get,
        reverse=True
    )[:6]

    latest_status = {
        "last_update": datetime.now(timezone.utc).isoformat(),
        "source": "GDELT + regional RSS + local-language keyword filtering",
        "method_note": (
            "Kulcsszavas, híralapú stratégiai monitoring. "
            "Nem közvélemény-kutatás. "
            "A rendszer GDELT, regionális RSS és országonkénti saját nyelvű kulcsszavak alapján dolgozik."
        ),
        "regional_summary": {
            "overall_risk": risk_level(avg_risk),
            "regional_stability_score": regional_stability,
            "regional_risk_score": avg_risk,
            "main_trend": (
                "A régiós összkép a híráramlás, biztonsági témák, "
                "EU/NATO narratívák és helyi politikai feszültségek alapján készül."
            ),
            "top_topics": top_topics
        },
        "countries": countries_output
    }

    with open(LATEST_STATUS_PATH, "w", encoding="utf-8") as file:
        json.dump(latest_status, file, ensure_ascii=False, indent=2)

    with open(RAW_NEWS_PATH, "w", encoding="utf-8") as file:
        json.dump({
            "last_update": datetime.now(timezone.utc).isoformat(),
            "items": raw_news
        }, file, ensure_ascii=False, indent=2)

    update_history(latest_status)

    print("latest_status.json, raw_news.json és history frissítve")


if __name__ == "__main__":
    main()
