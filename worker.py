import os
import re
import json
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import requests
from bs4 import BeautifulSoup

FEED_FILE = "feed_data.json"
USERS_FILE = "users.json"
SEEN_FILE = "seen_lots.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# ---------------------------------------------------------------------------
# 500+ MODEL TAXONOMY ACROSS 30+ TOP BRANDS
# ---------------------------------------------------------------------------
BRAND_CATALOG = {
    "glock": [
        "19x", "19", "17l", "17", "43x", "48", "45", "44", "43", "42", "41", "40",
        "36", "35", "34", "33", "32", "31", "30s", "30", "29", "27", "26", "23",
        "22", "21", "20", "47"
    ],
    "smith & wesson": [
        # Revolvers
        "model 10", "model 12", "model 13", "model 14", "model 15", "model 17",
        "model 19", "model 27", "model 28", "model 29", "model 36", "model 49",
        "model 60", "model 63", "model 64", "model 65", "model 66", "model 67",
        "model 617", "model 627", "model 629", "model 686", "model 586", "model 642",
        "model 442", "model 340pd", "model 500", "model 460", "governor",
        # Semi-Autos
        "shield plus", "shield ez", "shield", "m&p 2.0", "m&p 9", "m&p 40",
        "m&p 45", "m&p 10mm", "m&p 22", "bodyguard 2.0", "bodyguard 380", "bodyguard",
        "csx", "equalizer", "sd9 ve", "sd40 ve", "sd9", "sw1911", "victory",
        "3913", "5906", "4006", "4506", "6906",
        # Long Guns
        "m&p 15-22", "m&p 15", "fpc", "response", "model 1854"
    ],
    "sig sauer": [
        "p365-xmacro", "p365 xmacro", "p365xl", "p365x", "p365 fuse", "p365 sas", "p365",
        "p320 x-five", "p320 axg", "p320 spectre", "p320 x-carry", "p320 compact", "p320",
        "m17", "m18", "p226 legion", "p226 mk25", "p226", "p229 legion", "p229",
        "p220 hunter", "p220", "p225", "p228", "p238", "p938", "p210", "sp2022",
        "mcx virtus", "mcx spear", "mcx", "mpx", "cross", "m400 tread", "m400"
    ],
    "colt": [
        "python", "anaconda", "king cobra", "cobra", "diamondback", "detective special",
        "police positive", "official police", "single action army",
        "gold cup national match", "gold cup trophy", "gold cup", "delta elite",
        "combat elite", "combat commander", "commander", "officer's acp", "officer",
        "defender", "government model", "1911",
        "sporter match hbar", "sporter target", "sporter lightweight", "sporter",
        "ar-15 a2", "ar-15", "le6920", "cr6920"
    ],
    "ruger": [
        "10/22 takedown", "10/22 carbine", "10/22", "mark iv 22/45", "mark iv", "mark iii",
        "mark ii", "sr22", "lcp max", "lcp ii", "lcp", "security-9", "security-380",
        "ec9s", "lc9s", "max-9", "sr1911", "57",
        "gp100", "sp101", "redhawk", "super redhawk", "blackhawk", "super blackhawk",
        "vaquero", "single-six", "wrangler", "super wrangler", "lcrx", "lcr",
        "american predator", "american ranch", "american rifle", "precision rifle",
        "precision rimfire", "gunsite scout", "scout", "mini-14", "mini-30",
        "pc carbine", "pc charger", "sfar", "ar-556", "hawkeye", "m77"
    ],
    "beretta": [
        "92fs brigadier", "92fs", "92x rdo", "92x", "92xi", "m9a4", "m9a3", "m9a1", "m9",
        "96a1", "96", "80x cheetah", "84fs cheetah", "84 cheetah", "85 cheetah", "81 cheetah",
        "apx a1", "apx", "px4 storm", "21a bobcat", "3032 tomcat", "950 jetfire",
        "1301 tactical", "1301 comp", "a300 ultima patrol", "a300 ultima", "a300",
        "a400 xcel", "a400 lite", "a400", "686 silver pigeon", "687", "694", "dt11"
    ],
    "benelli": [
        "m4 tactical", "m4", "m2 tactical", "m2 field", "m2", "m1 super 90", "m3 super 90",
        "super black eagle 3", "super black eagle ii", "super black eagle", "sbe3",
        "montefeltro", "supernova tactical", "supernova", "nova", "ethos", "vinci", "lupo"
    ],
    "remington": [
        "870 wingmaster", "870 police magnum", "870 express magnum", "870 express", "870 tactical", "870",
        "1100 sporting", "1100", "11-87 premier", "11-87 police", "11-87", "v3 tac-13", "v3",
        "versamax", "700 sendero", "700 police", "700 pcr", "700 sps", "700 bdl", "700 cdl", "700",
        "model seven", "7600", "7400", "783", "597"
    ],
    "mossberg": [
        "590a1 retrograde", "590a1", "590 shockwave", "590 retrograde", "590",
        "500 retrograde", "500 field", "500 hunting", "500", "835 ulti-mag", "535",
        "940 pro tactical", "940 pro jm", "940 pro", "930 spx", "930", "maverick 88",
        "patriot predator", "patriot", "mvp scout", "mvp patrol", "mvp predator", "mvp",
        "702 plinkster"
    ],
    "winchester": [
        "model 94 pre-64", "model 94", "model 70 featherweight", "model 70 super grade", "model 70",
        "model 1873", "model 1892", "model 1886", "model 1895", "model 1894",
        "model 12", "model 97", "model 1200", "model 1300 defender", "model 1300",
        "sxp defender", "sxp", "sx4 hybrid", "sx4", "sx3", "xpr", "wildcat"
    ],
    "springfield": [
        "hellcat pro rdp", "hellcat pro", "hellcat rdp", "hellcat", "echelon",
        "1911 ds prodigy", "prodigy", "1911 operator", "1911 trp", "1911 ronin",
        "1911 garrison", "1911 loaded", "1911 mil-spec", "sa-35",
        "xd-m elite", "xd-m", "xd-s mod.2", "xd-s", "xd mod.2", "xd",
        "m1a socom 16", "m1a scout squad", "m1a loaded", "m1a standard", "m1a",
        "saint victor", "saint edge", "saint"
    ],
    "cz": [
        "shadow 2 orange", "shadow 2 compact", "shadow 2", "ts 2", "tactical sport",
        "75 sp-01 tactical", "75 sp-01", "75 bd", "75b omega", "75b", "75 compact",
        "p-01 omega", "p-01", "pcr", "97b", "85 combat", "85b",
        "p-10 f", "p-10 c", "p-10 s", "p-10 m", "p-07", "p-09",
        "cz 457 varmint", "cz 457 american", "cz 457", "cz 455", "cz 527", "cz 557", "cz 600",
        "bren 2 ms", "scorpion evo 3 s1", "scorpion"
    ],
    "walther": [
        "pdp steel frame", "pdp pro sd", "pdp f-series", "pdp compact", "pdp full size", "pdp",
        "ppq m2", "ppq", "p99 as", "p99", "ppk/s", "ppk", "pps m2", "pps", "ccp m2", "ccp", "wmp"
    ],
    "fn": [
        "509 tactical", "509 midsize", "509 compact", "509", "five-seven mk3", "five-seven",
        "fnx-45 tactical", "fnx-45", "fnx-9", "fns-9c", "fns-9", "reflex mrd", "reflex",
        "high power", "scar 20s", "scar 17s", "scar 16s", "ps90"
    ],
    "hk": [
        "vp9 match", "vp9 tactical", "vp9l", "vp9sk", "vp9", "p30l", "p30sk", "p30",
        "hk45 tactical", "hk45 compact", "hk45c", "hk45", "usp tactical", "usp expert",
        "usp compact", "usp", "p2000sk", "p2000", "mark 23", "sp5k-pdw", "sp5", "mr556a1", "mr762"
    ],
    "marlin": [
        "1895 sbl", "1895 trapper", "1895 guide gun", "1895gbl", "1895", "336 classic",
        "336 trapper", "336 dark", "336", "1894 classic", "1894 csbl", "1894",
        "model 60", "model 795", "model 39a"
    ],
    "henry": [
        "big boy all-weather", "big boy brass", "big boy x", "big boy steel", "big boy",
        "golden boy", "classic lever action .22", "long ranger", "homesteader 9mm", "single shot"
    ],
    "tikka": [
        "t3x tac a1", "t3x superlite", "t3x ctr", "t3x roughtech", "t3x lite", "t3x varmint", "t3x", "t1x"
    ],
    "savage": [
        "110 tactical", "110 ultralite", "110 hunter", "110 high country", "110 precision", "110 storm", "110",
        "axis ii precision", "axis ii xp", "axis ii", "axis", "10 fcp-sr", "12 bvss", "mark ii fv-sr", "mark ii", "b22"
    ],
    "browning": [
        "citori 725 pro", "citori 725", "citori cx", "citori cxs", "citori", "cynergy",
        "a5 sweet sixteen", "a5 wicked wing", "a5 hunter", "a5", "maxus ii", "silver field", "bps",
        "x-bolt pro", "x-bolt speed", "x-bolt hell's canyon", "x-bolt hunter", "x-bolt",
        "a-bolt iii", "a-bolt", "bar mk3", "bar", "buck mark hunter", "buck mark plus", "buck mark"
    ],
    "taurus": [
        "g3c", "g3", "g2c", "gx4 carry", "gx4", "tx22 competition", "tx22",
        "judge public defender", "judge magnum", "judge", "tracker 627", "tracker 44",
        "raging hunter", "model 856", "model 605", "model 66", "1911"
    ],
    "canik": [
        "tti combat", "rival-s", "sfx rival", "mete mc9", "mete sft pro", "mete sft",
        "mete sf", "tp9 elite sc", "tp9sfx", "tp9sf", "tp9sa"
    ],
    "staccato": [
        "staccato xc", "staccato xl", "staccato p", "staccato c2", "staccato cs", "staccato c"
    ],
    "kimber": [
        "custom ii", "pro carry ii", "ultra carry ii", "stainless ii", "rapide",
        "khx", "micro 9", "micro 380", "r7 mako", "k6s dasa", "k6s"
    ],
    "dan wesson": [
        "dwx compact", "dwx", "specialist", "valor", "tcp", "ecp", "pointman 7", "kodiak"
    ],
    "kel-tec": [
        "sub-2000 gen 3", "sub-2000 gen 2", "sub-2000", "ksg", "ks7", "cp33", "pmr-30", "cmr-30", "p17", "rdb", "rfb"
    ],
    "bergara": [
        "b-14 hmr", "b-14 hunter", "b-14 ridge", "b-14 wilderness", "b-14 timber", "bmr"
    ],
    "daniel defense": [
        "ddm4 v7 pro", "ddm4 v7", "ddm4 v9", "ddm4 pdw", "mk18", "dd5 v4", "delta 5 pro"
    ],
    "norinco": [
        "mak-90 sporter", "mak-90", "nhm-91", "type 56s", "type 84s", "sks sporter", "sks", "tt-33", "1911 a1"
    ],
    "military surplus": [
        "m1 garand", "m1 carbine", "1903 springfield", "1903a3", "mosin nagant 91/30", "mosin nagant m44",
        "sks yugo 59/66", "sks russian", "mauser k98k", "mauser gewehr 98", "lee-enfield no. 4 mk 1",
        "lee-enfield smle no. 1", "swiss k31", "swiss k11", "makarov pm", "walther p38", "luger p08",
        "webley mk iv", "cz 82", "cz 52", "tokarev tt-33"
    ]
}

# ---------------------------------------------------------------------------
# CATEGORICAL BASELINE WHOLESALE/RETAIL VALUATION RULES
# ---------------------------------------------------------------------------
CATEGORY_VALUATIONS = {
    # 2011 & High-End Handguns
    "staccato": {"base": 2100.0, "min_margin": 250.0},
    "dan wesson": {"base": 1400.0, "min_margin": 200.0},
    # Luxury Shotguns & Double Guns
    "benelli m4": {"base": 1850.0, "min_margin": 250.0},
    "benelli super black eagle": {"base": 1600.0, "min_margin": 220.0},
    "beretta 1301": {"base": 1350.0, "min_margin": 200.0},
    "browning citori": {"base": 1750.0, "min_margin": 250.0},
    "beretta 686": {"base": 1800.0, "min_margin": 250.0},
    # Revolvers
    "colt python": {"base": 1250.0, "min_margin": 180.0},
    "colt anaconda": {"base": 1300.0, "min_margin": 180.0},
    "smith & wesson model 686": {"base": 820.0, "min_margin": 140.0},
    "smith & wesson model 29": {"base": 950.0, "min_margin": 150.0},
    "ruger gp100": {"base": 680.0, "min_margin": 120.0},
    # Lever Action
    "marlin 1895": {"base": 1050.0, "min_margin": 160.0},
    "henry big boy": {"base": 820.0, "min_margin": 130.0},
    # Premium Rifles
    "daniel defense": {"base": 1650.0, "min_margin": 220.0},
    "tikka t3x": {"base": 780.0, "min_margin": 130.0},
    "bergara b-14": {"base": 850.0, "min_margin": 140.0},
    # Classic Bolt Actions & Pump Shotguns
    "remington 700": {"base": 680.0, "min_margin": 120.0},
    "remington 870 wingmaster": {"base": 580.0, "min_margin": 120.0},
    "remington 870": {"base": 380.0, "min_margin": 80.0},
    "mossberg 590a1": {"base": 560.0, "min_margin": 100.0},
    "mossberg 500": {"base": 340.0, "min_margin": 80.0},
    # Duty Handguns
    "hk usp": {"base": 850.0, "min_margin": 140.0},
    "sig sauer p226": {"base": 850.0, "min_margin": 140.0},
    "cz shadow 2": {"base": 1150.0, "min_margin": 160.0},
    "glock": {"base": 480.0, "min_margin": 90.0},
    "smith & wesson shield": {"base": 360.0, "min_margin": 80.0},
    "ruger 10/22": {"base": 260.0, "min_margin": 60.0}
}

# ---------------------------------------------------------------------------
# MARKETPLACE SCRAPERS (EXPANDED BROAD HARVESTING)
# ---------------------------------------------------------------------------
def parse_price(val):
    if not val:
        return 0.0
    cleaned = str(val).replace(",", "").replace("$", "")
    m = re.search(r"(\d+\.?\d*)", cleaned)
    return float(m.group(1)) if m else 0.0

def scrape_gunbroker():
    lots = []
    # Broad firehose queries covering modern pistols, revolvers, shotguns, rifles, and surplus
    queries = [
        "https://www.gunbroker.com/All/search?Keywords=firearms&PageSize=48&Sort=13",
        "https://www.gunbroker.com/Pistols/search?PageSize=48&Sort=13",
        "https://www.gunbroker.com/Rifles/search?PageSize=48&Sort=13",
        "https://www.gunbroker.com/Shotguns/search?PageSize=48&Sort=13"
    ]
    for url in queries:
        try:
            r = requests.get(url, headers=HEADERS, timeout=8)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                for item in soup.select("div.tile"):
                    t_el = item.select_one("a.title")
                    p_el = item.select_one("span.price")
                    if t_el and p_el:
                        title = t_el.get_text(strip=True)
                        price = parse_price(p_el.get_text(strip=True))
                        href = t_el.get("href", "")
                        link = href if href.startswith("http") else f"https://www.gunbroker.com{href}"
                        lots.append({
                            "lot_id": f"GB-{abs(hash(link)) % 100000}",
                            "source_site": "GunBroker",
                            "title": title,
                            "current_bid": price,
                            "listing_url": link
                        })
        except Exception:
            pass
    return lots

def scrape_hibid():
    lots = []
    queries = [
        "https://hibid.com/lots?q=firearms",
        "https://hibid.com/lots?q=pistol+revolver",
        "https://hibid.com/lots?q=shotgun+rifle"
    ]
    for url in queries:
        try:
            r = requests.get(url, headers=HEADERS, timeout=8)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                for item in soup.select("div.lot-tile, tr.lot-row"):
                    t_el = item.select_one("a.lot-title, h2.lot-title a")
                    p_el = item.select_one(".lot-bid-current, .price-text")
                    if t_el:
                        title = t_el.get_text(strip=True)
                        price = parse_price(p_el.get_text(strip=True)) if p_el else 100.0
                        href = t_el.get("href", "")
                        link = href if href.startswith("http") else f"https://hibid.com{href}"
                        lots.append({
                            "lot_id": f"HB-{abs(hash(link)) % 100000}",
                            "source_site": "HiBid",
                            "title": title,
                            "current_bid": price,
                            "listing_url": link
                        })
        except Exception:
            pass
    return lots

def scrape_armslist():
    lots = []
    try:
        url = "https://www.armslist.com/classifieds/massachusetts/guns"
        r = requests.get(url, headers=HEADERS, timeout=8)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            for item in soup.select("div.classified-item, .post-item"):
                link_el = item.select_one("a")
                t_el = item.select_one(".title, h3")
                p_el = item.select_one(".price")
                if link_el and t_el:
                    title = t_el.get_text(strip=True)
                    price = parse_price(p_el.get_text(strip=True)) if p_el else 250.0
                    href = link_el.get("href", "")
                    link = href if href.startswith("http") else f"https://www.armslist.com{href}"
                    lots.append({
                        "lot_id": f"AL-{abs(hash(link)) % 100000}",
                        "source_site": "Armslist",
                        "title": title,
                        "current_bid": price,
                        "listing_url": link
                    })
    except Exception:
        pass
    return lots

# ---------------------------------------------------------------------------
# BRAND & 500-MODEL IDENTIFICATION ENGINE
# ---------------------------------------------------------------------------
def match_brand_and_model(title: str):
    t = title.lower()
    matched_brand = "Universal"
    matched_model = "Firearm"

    # 1. Identify Brand
    for brand, models in BRAND_CATALOG.items():
        # Check alias synonyms
        aliases = [brand]
        if brand == "smith & wesson":
            aliases.extend(["s&w", "smith and wesson", "smith &amp; wesson"])
        elif brand == "sig sauer":
            aliases.extend(["sig"])
        elif brand == "hk":
            aliases.extend(["heckler & koch", "heckler and koch"])
        elif brand == "springfield":
            aliases.extend(["springfield armory"])
        elif brand == "fn":
            aliases.extend(["fn herstal", "fnh"])
        elif brand == "cz":
            aliases.extend(["ceska zbrojovka"])

        if any(re.search(rf"\b{re.escape(a)}\b", t) for a in aliases):
            matched_brand = brand
            # 2. Check 500+ Model Catalog for that brand
            for mod in models:
                if re.search(rf"\b{re.escape(mod)}\b", t):
                    matched_model = mod
                    break
            break

    # If brand wasn't found first, check if a unique model reveals the brand
    if matched_brand == "Universal":
        for brand, models in BRAND_CATALOG.items():
            for mod in models:
                if len(mod) >= 4 and re.search(rf"\b{re.escape(mod)}\b", t):
                    matched_brand = brand
                    matched_model = mod
                    break
            if matched_brand != "Universal":
                break

    return matched_brand, matched_model

# ---------------------------------------------------------------------------
# VALUATION & SPREAD ANALYSIS ENGINE
# ---------------------------------------------------------------------------
def analyze_lot(raw):
    title = raw.get("title", "")
    t_lower = title.lower()
    bid = float(raw.get("current_bid", 0.0))
    source = raw.get("source_site", "Direct")

    # Landed Cost Calculation
    premium = 0.18 if source == "HiBid" else 0.05
    shipping = 40.0
    transfer_fee = 25.0
    landed = round((bid * (1.0 + premium)) + shipping + transfer_fee, 2)

    brand, model = match_brand_and_model(title)
    pair_key = f"{brand} {model}".strip()

    # Pre-Ban Multiplier Detection (Included, not exclusive)
    pre_ban_terms = ["preban", "pre-ban", "pre ban", "sporter match", "blue label", "pre-94", "1989", "1990", "1991", "1992", "1993"]
    is_pre_ban = any(term in t_lower for term in pre_ban_terms)

    # Curio & Relic Detection (50-Year Rule)
    cr_terms = ["c&r", "curio", "relic", "194", "195", "196", "1970", "1971", "1972", "1973", "1974", "1975"]
    is_cr = any(term in t_lower for term in cr_terms) or brand == "military surplus"

    # Base Retail Valuation Lookup
    base_retail = None
    for k, v in CATEGORY_VALUATIONS.items():
        if k in pair_key or k in brand:
            base_retail = v["base"]
            break

    if not base_retail:
        # Dynamic market multiplier fallback based on ask/bid
        base_retail = max(bid * 1.35, landed + 115.0)

    # Compliance-Adjusted Pricing
    # MA Grandfathered pre-bans command 1.65x, C&Rs command 1.20x, standard commercial runs 1.10x
    ma_mult = 1.65 if is_pre_ban else (1.20 if is_cr else 1.10)
    fed_retail = round(base_retail, 2)
    ma_retail = round(base_retail * ma_mult, 2)

    fed_profit = round(fed_retail - landed, 2)
    ma_profit = round(ma_retail - landed, 2)
    fed_margin = round((fed_profit / fed_retail) * 100, 1) if fed_retail > 0 else 0.0
    ma_margin = round((ma_profit / ma_retail) * 100, 1) if ma_retail > 0 else 0.0

    # Badge Categorization
    if is_pre_ban:
        badge = "🔥 Pre-Ban Grandfathered"
    elif is_cr:
        badge = "🏛️ C&R 50-Year Exempt"
    elif brand == "glock" and any(g in t_lower for g in ["gen 4", "gen 5", "gen4", "gen5"]):
        badge = "⚠️ Frame Transfer Only"
    else:
        badge = "Federal Title 1 / Commercial"

    return {
        "lot_id": raw.get("lot_id"),
        "source_site": source,
        "title": title,
        "make": brand,
        "model": model,
        "current_bid": bid,
        "total_landed_cost": landed,
        "federal_retail": fed_retail,
        "federal_profit": fed_profit,
        "federal_margin": fed_margin,
        "actionable_federal": bool(fed_profit >= 110.0 and fed_margin >= 18.0),
        "ma_retail": ma_retail,
        "ma_profit": ma_profit,
        "ma_margin": ma_margin,
        "actionable_ma": bool(ma_profit >= 130.0 and ma_margin >= 20.0),
        "max_bid": round(ma_retail * 0.70, 2),
        "is_pre_ban": is_pre_ban,
        "compliance_badge": badge,
        "listing_url": raw.get("listing_url")
    }

# ---------------------------------------------------------------------------
# EMAIL ALERT DISPATCH
# ---------------------------------------------------------------------------
def dispatch_alerts(analyzed_lots):
    if not os.path.exists(USERS_FILE):
        return
    try:
        with open(USERS_FILE, "r") as f:
            users = json.load(f)
    except Exception:
        return

    seen = set()
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, "r") as f:
                seen = set(json.load(f))
        except Exception:
            pass

    u = os.environ.get("SMTP_USER", "")
    p = os.environ.get("SMTP_PASSWORD", "")
    s = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", 587))
    newly_seen = set()

    for email, profile in users.items():
        if not profile.get("email_alerts"):
            continue
        min_thresh = float(profile.get("min_profit", 150.0))
        is_pro = (profile.get("plan") == "pro")
        alert_count = 0

        for lot in analyzed_lots:
            lot_id = lot.get("lot_id")
            if lot_id in seen:
                continue

            profit = lot.get("ma_profit", 0.0)
            if lot.get("actionable_ma") and profit >= min_thresh:
                if not is_pro and alert_count >= 2:
                    break

                if u and p:
                    try:
                        msg = MIMEMultipart("alternative")
                        msg["Subject"] = f"🎯 RADAR SIGNAL: {lot.get('title')} (+${profit:.2f})"
                        msg["From"] = u
                        msg["To"] = email
                        body = f"""
                        <h3>FFL Radar Arbitrage Opportunity</h3>
                        <p><strong>Brand / Model:</strong> {lot.get('make','').title()} {lot.get('model','').title()}</p>
                        <p><strong>Item:</strong> {lot.get('title')}</p>
                        <p><strong>Platform:</strong> {lot.get('source_site')}</p>
                        <p><strong>Current Price:</strong> ${lot.get('current_bid',0):.2f}</p>
                        <p><strong>Landed Cost:</strong> ${lot.get('total_landed_cost',0):.2f}</p>
                        <p><strong>Projected Resale:</strong> ${lot.get('ma_retail',0):.2f}</p>
                        <p><strong>Net Spread:</strong> <span style="color:green;font-weight:bold;">+${profit:.2f}</span> ({lot.get('ma_margin',0)}%)</p>
                        <p><strong>Classification:</strong> {lot.get('compliance_badge')}</p>
                        <p><a href="{lot.get('listing_url')}" style="padding:10px 18px;background:#10B981;color:#fff;text-decoration:none;border-radius:4px;">Open Listing Directly</a></p>
                        """
                        msg.attach(MIMEText(body, "html"))
                        with smtplib.SMTP(s, port) as server:
                            server.starttls()
                            server.login(u, p)
                            server.sendmail(u, email, msg.as_string())
                        alert_count += 1
                        newly_seen.add(lot_id)
                    except Exception:
                        pass

    if newly_seen:
        seen.update(newly_seen)
        with open(SEEN_FILE, "w") as f:
            json.dump(list(seen), f)

# ---------------------------------------------------------------------------
# MAIN WORKER RUNNER
# ---------------------------------------------------------------------------
def main():
    scraped = []
    scraped.extend(scrape_gunbroker())
    scraped.extend(scrape_hibid())
    scraped.extend(scrape_armslist())

    analyzed = [analyze_lot(lot) for lot in scraped] if scraped else []

    if not analyzed and os.path.exists(FEED_FILE):
        try:
            with open(FEED_FILE, "r") as f:
                analyzed = json.load(f).get("lots", [])
        except Exception:
            pass

    feed_packet = {
        "last_updated": datetime.now().strftime("%Y-%m-%d %I:%M %p"),
        "lots": analyzed
    }
    with open(FEED_FILE, "w") as f:
        json.dump(feed_packet, f, indent=2)

    dispatch_alerts(analyzed)
    print(f"WORKER_SUCCESS: Catalog matching across 500+ models. Ingested {len(analyzed)} lots.")

if __name__ == "__main__":
    main()
