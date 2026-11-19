import os
import re
import json
import hashlib
import statistics
import urllib.parse
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FEED_FILE = os.path.join(BASE_DIR, "feed_data.json")
SCRAPER_API_KEY = os.environ.get("SCRAPER_API_KEY", "").strip()
GB_KEY = os.environ.get("GUNBROKER_DEV_KEY", "").strip()

# Hand-entered reference values. Peer comps (below) cover everything else.
MULTI_SOURCE_VALUATIONS = {
    "colt python": {"gb_sold": 1420.0, "gc_retail": 1495.0, "ga_comp": 1450.0},
    "colt anaconda": {"gb_sold": 1350.0, "gc_retail": 1425.0, "ga_comp": 1380.0},
    "glock 19": {"gb_sold": 510.0, "gc_retail": 550.0, "ga_comp": 530.0},
    "glock 43": {"gb_sold": 435.0, "gc_retail": 475.0, "ga_comp": 450.0},
    "smith & wesson 686": {"gb_sold": 850.0, "gc_retail": 910.0, "ga_comp": 880.0},
    "sig sauer p365": {"gb_sold": 520.0, "gc_retail": 570.0, "ga_comp": 545.0},
    "ruger 10/22": {"gb_sold": 275.0, "gc_retail": 310.0, "ga_comp": 290.0},
    "hk mp5": {"gb_sold": 2800.0, "gc_retail": 3100.0, "ga_comp": 2950.0},
    "staccato p": {"gb_sold": 2250.0, "gc_retail": 2450.0, "ga_comp": 2350.0},
}

PRE_BAN_TRIGGERS = ["pre-ban", "pre ban", "pre-94", "pre 94", "sporter match",
                    "green label", "blue label sporter", "mak-90"]

# Longest names first so "smith & wesson" wins over "smith".
BRANDS = [
    "Smith & Wesson", "Sig Sauer", "Heckler & Koch", "Springfield Armory", "Palmetto State Armory",
    "Daniel Defense", "Wilson Combat", "Dan Wesson", "Rock Island", "Century Arms", "Pioneer Arms",
    "Panzer Arms", "Magnum Research", "Charter Arms", "Standard Manufacturing", "American Tactical",
    "Anderson Manufacturing", "Diamondback", "Kel-Tec", "Hi-Point", "Hi Point", "Gforce Arms",
    "Heritage Mfg", "Heritage", "Simson And Company", "Remington", "Mossberg", "Savage", "Henry",
    "Winchester", "Marlin", "Browning", "Beretta", "Taurus", "Kimber", "Glock", "Ruger", "Colt", "CZ",
    "Walther", "Canik", "Staccato", "Kahr", "Girsan", "Mauser", "Zastava", "Pietta", "Armscor",
    "Tisas", "Bersa", "Steyr", "Nighthawk", "Ithaca", "Benelli", "Stoeger", "Weatherby", "Tikka",
    "Bergara", "Sako", "Radical Firearms", "Springfield", "FN", "FNH", "IWI", "Sccy", "Ati", "HK",
    "Auto-Ordnance", "Uberti", "Cimarron", "Taylor's", "Chiappa", "Franchi", "Rossi", "Lorcin",
    "Jennings", "Bryco", "Davis", "Phoenix Arms", "Iver Johnson", "High Standard", "Llama", "Astra",
    "Star", "Makarov", "Tokarev", "Luger", "Sig", "S&W",
    "Heckler and Koch", "Smith and Wesson", "Radom", "Altor Corp", "Altor", "Derya", "DPMS", "Zenith Firearms",
    "Polish", "Sar Arms", "SAR", "Girsan", "Mkm", "Hungarian", "Romanian", "Glock Inc",
    "Shadow Systems", "Archon Firearms", "Springfield Armory", "Ruger", "FN America", "Bul Armory", "Tanfoglio", "EAA", "Excel Arms", "Walther Arms", "Savage Arms",
]
BRANDS.sort(key=len, reverse=True)
BRAND_ALIASES = {"s&w": "Smith & Wesson", "sig": "Sig Sauer", "hk": "Heckler & Koch",
                 "hi point": "Hi-Point", "ati": "ATI", "cz": "CZ", "fn": "FN", "fnh": "FN",
                 "iwi": "IWI", "sccy": "SCCY", "heckler and koch": "Heckler & Koch",
                 "smith and wesson": "Smith & Wesson", "dpms": "DPMS", "altor corp": "Altor Corp"}

def paged(base, pages, joiner="?"):
    return [base] + [f"{base}{joiner}page={i}" for i in range(2, pages + 1)]


# Rough ScraperAPI cost per run: Guns.com 3 premium pages (~75), Bud's 3 + UsedGuns 4 + GunsAmerica 1 + HiBid 1
# + Tacswap 1 rendered pages (~10 each), the rest plain fetches (~1 each). About 210 credits per run.
SITE_CONFIGS = {
    "Guns.com": {
        "card_selector": "li.product-card, .productCard, div[class*='productCard']",
        "url_prefix": "https://www.guns.com",
        "render_js": True, "premium": True,
        "urls": [
            "https://www.guns.com/firearms/handguns?condition=used",
            "https://www.guns.com/firearms/rifles?condition=used",
            "https://www.guns.com/firearms/shotguns?condition=used",
        ],
    },
    "Classic Firearms": {
        "card_selector": "div.product-card, .product-item",
        "url_prefix": "https://www.classicfirearms.com",
        "render_js": False,
        "urls": (["https://www.classicfirearms.com/firearms/handguns/"]
                 + [f"https://www.classicfirearms.com/firearms/handguns/?p={i}" for i in range(2, 9)]
                 + ["https://www.classicfirearms.com/firearms/rifles/"]
                 + [f"https://www.classicfirearms.com/firearms/rifles/?p={i}" for i in range(2, 9)]
                 + ["https://www.classicfirearms.com/firearms/shotguns/"]
                 + [f"https://www.classicfirearms.com/firearms/shotguns/?p={i}" for i in range(2, 5)]),
    },
    "Buds Gun Shop": {
        "card_selector": "a[href*='/products/']",
        "url_prefix": "https://www.budsgunshop.com",
        "render_js": True,
        "urls": paged("https://www.budsgunshop.com/categories/firearms/used", 3),
    },
    "Sportsman's Outdoor Superstore": {
        "card_selector": "div.box-outline",
        "url_prefix": "https://www.sportsmansoutdoorsuperstore.com",
        "render_js": False,
        "urls": ["https://www.sportsmansoutdoorsuperstore.com/category.cfm/sportsman/used-firearms"]
                + [f"https://www.sportsmansoutdoorsuperstore.com/category.cfm/CurrentPage/{i}/sportsman/used-firearms/dept/Firearms"
                   for i in range(2, 7)],
    },
    "UsedGuns.com": {
        "card_selector": "div.product-card",
        "url_prefix": "https://www.usedguns.com",
        "render_js": True,
        "urls": [
            "https://www.usedguns.com/Subcategory/Pistol/8423042?filter=1&sort=7&images=false&freeShipping=false&shipping=false",
            "https://www.usedguns.com/Subcategory/Revolver/16811650?filter=1&sort=7&images=false&freeShipping=false&shipping=false",
            "https://www.usedguns.com/Subcategory/Rifle/33588866?filter=1&sort=7&images=false&freeShipping=false&shipping=false",
            "https://www.usedguns.com/Subcategory/Firearms/34434?filter=1&sort=7&images=false&freeShipping=false&shipping=false",
        ],
    },
    "GunsAmerica": {
        "card_selector": "h2 a[href*='/firearms/']",
        "url_prefix": "https://gunsamerica.com",
        "render_js": True,
        "urls": ["https://gunsamerica.com/firearms/handguns?sort=listingStartDate"],
    },
    "Armslist": {
        "card_selector": "li.pdl_item",
        "url_prefix": "https://www.armslist.com",
        "render_js": False,
        "urls": [f"https://www.armslist.com/search?category={c}&posttype=7&ships=true" + (f"&page={p}" if p > 1 else "")
                 for c in ("handguns", "rifles", "shotguns") for p in (1, 2)],
    },
    "HiBid": {
        "card_selector": "div.lot-tile",
        "url_prefix": "https://hibid.com",
        "render_js": True, "strict": True,
        "urls": ["https://hibid.com/lots?q=firearm&status=Open&category=Firearms"],
    },
    "Tacswap": {
        "card_selector": "a[href*='/post/']",
        "url_prefix": "https://tacswap.com",
        "render_js": True, "strict": True,
        "urls": ["https://tacswap.com/firearm"],
    },
}

NON_GUN_RE = re.compile(
    r"\b(holsters?|magazines?|cases?|optics?|scopes?|sights?|ammo|ammunition|uppers?|lowers?|suppressors?|"
    r"silencers?|barrels?|grips?|stocks?|triggers?|lights?|lasers?|knife|knives|slings?|mounts?|bipods?|safes?|cleaning|builds?)\b",
    re.IGNORECASE)
GUN_WORD_RE = re.compile(r"\b(pistol|revolver|rifle|shotgun|carbine|handgun|derringer)\b", re.IGNORECASE)


def looks_like_gun(title: str) -> bool:
    if NON_GUN_RE.search(title or ""):
        return False
    if GUN_WORD_RE.search(title or ""):
        return True
    low = (title or "").lower()
    return any(re.search(r"\b" + re.escape(b.lower()) + r"\b", low) for b in BRANDS if len(b) > 2)


CALIBER_RE = re.compile(
    r"((?<![\d.])\.\d{2,3}\s?(?:acp|auto|lr|wmr|mag(?:num)?|spl|special|s&w|win|colt|nato)?"
    r"|\b\d{1,2}(?:\.\d+)?\s?mm(?:\s?(?:luger|nato|makarov|x\s?\d+))?|\b5\.56\b|\b7\.62(?:\s?x\s?\d+)?|\b9\s?mm\b)",
    re.IGNORECASE)
MODEL_CUT_RE = re.compile(
    r"(\s[-–—]\s|,|\(|\b(?:semi|pistol|revolver|rifle|shotgun|used|surplus|blem|bundle|"
    r"new|stainless|black|blued|compact|barrel|bbl)\b|\s\.\d{2,3}\b|\b\d{1,2}(?:\.\d+)?\s?(?:mm|\"|in\b|rd\b|round)|\bacp\b)",
    re.IGNORECASE)


PARTS_FOR_RE = re.compile(
    r"\bfor\s+(?:the\s+)?(?:glock|sig|smith|s&w|ruger|1911|beretta|cz\b|springfield|hk\b|walther|taurus|ar-?15|ak-?47)",
    re.IGNORECASE)
PARTS_MAKERS = ("sct manufacturing", "magpul", "midwest industries", "hogue", "pearce grip", "crimson trace",
                "ghost inc", "apex tactical", "zev technologies parts")


def is_gun_listing(title: str) -> bool:
    low = (title or "").lower()
    if any(low.startswith(p) for p in PARTS_MAKERS):
        return False
    if PARTS_FOR_RE.search(low):
        return False
    return True


def squash(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def clean_title(raw_title: str) -> str:
    t = re.sub(r"^(Recently Added.*?\d+\s+days\s+ago|SHOWCASE|NEW)", "", raw_title or "", flags=re.IGNORECASE)
    t = squash(t)
    return t if len(t) > 4 else squash(raw_title)


def pretty_brand(brand: str) -> str:
    b = squash(brand)
    low = b.lower()
    if low in BRAND_ALIASES:
        return BRAND_ALIASES[low]
    return b.title() if b.isupper() or b.islower() else b


def split_make_model(title: str, make_hint: str = "", model_hint: str = ""):
    """Return (make, model). Uses site-provided hints when present, else brand matching on the title."""
    title = squash(title)
    if make_hint:
        make = pretty_brand(make_hint)
        model = squash(model_hint)
        parts = [re.escape(p) for p in re.split(r"\s*&\s*|\s+and\s+", make_hint, flags=re.IGNORECASE)]
        pat = r"^" + r"\s*(?:&|and)\s*".join(parts)
        if not model:
            model = title
        model = re.sub(pat, "", model, flags=re.IGNORECASE).strip(" -:,")
        model = re.sub(r"^(?:and\s+koch|and\s+wesson)\b", "", model, flags=re.IGNORECASE).strip(" -:,")
        return make, trim_model(model)

    low = title.lower()
    for brand in BRANDS:
        if re.match(r"^" + re.escape(brand.lower()) + r"\b", low):
            rest = title[len(brand):].strip(" -:,")
            return pretty_brand(brand), trim_model(rest)
    # brand not at start: look anywhere in the title
    for brand in BRANDS:
        m = re.search(r"\b" + re.escape(brand.lower()) + r"\b", low)
        if m and len(brand) > 3:
            rest = (title[:m.start()] + " " + title[m.end():]).strip(" -:,")
            return pretty_brand(brand), trim_model(rest)
    words = title.split()
    return (words[0].title() if words else "Unknown"), trim_model(" ".join(words[1:]))


def trim_model(text: str) -> str:
    text = squash(text)
    m = MODEL_CUT_RE.search(text)
    if m and m.start() > 0:
        text = text[:m.start()]
    words = text.split()[:4]
    out = " ".join(words).strip(" -:,/")
    return out if out else "Unknown"


def find_caliber(text: str) -> str:
    m = CALIBER_RE.search(text or "")
    return squash(m.group(1)).upper() if m else ""


def normalize_for_match(title: str) -> str:
    t = title.lower()
    t = re.sub(r"\bs\s?&\s?w\b", "smith & wesson", t)
    t = re.sub(r"\bsig\b(?!\s*sauer)", "sig sauer", t)
    t = re.sub(r"\bh&k\b|\bheckler\s*&?\s*koch\b", "hk", t)
    return t


USED_RE = re.compile(r"\b(used|pre-owned|preowned|police trade|trade-in|surplus|very good|excellent|like new|refurb|consignment|fair condition|good condition)\b", re.IGNORECASE)
NEW_RE = re.compile(r"\b(new|nib|brand new|unfired)\b", re.IGNORECASE)
NEW_SOURCES = {"Classic Firearms"}
USED_ONLY_SOURCES = {"Guns.com", "Buds Gun Shop", "Sportsman's Outdoor Superstore"}


def detect_condition(src: str, title: str) -> str:
    """Return 'used' or 'new'. Used and new listings are only ever valued against their own kind."""
    if src in USED_ONLY_SOURCES:
        return "used"
    if USED_RE.search(title or ""):
        return "used"
    if NEW_RE.search(title or ""):
        return "new"
    return "new" if src in NEW_SOURCES else "used"


def table_valuation(title: str, condition: str = "used"):
    """Hand-entered references: used guns use the sold price, new guns use the retail price."""
    t_lower = normalize_for_match(title)
    is_pre = any(trig in t_lower for trig in PRE_BAN_TRIGGERS)
    for key, vals in MULTI_SOURCE_VALUATIONS.items():
        if re.search(r"\b" + re.escape(key) + r"\b", t_lower):
            ref = vals["gc_retail"] if condition == "new" else vals["gb_sold"]
            return vals, round(float(ref), 2), is_pre
    return None, 0.0, is_pre


def finalize_lot(lot: dict, fed_avg: float, basis: str, is_pre: bool, val_sources=None):
    """Fill valuation and profit fields on a lot."""
    landed = lot["total_landed_cost"]
    lot["valuation_sources"] = val_sources or {"triangulated_avg": fed_avg}
    lot["valuation_basis"] = basis
    lot["is_pre_ban"] = is_pre
    lot["federal_retail"] = fed_avg
    if fed_avg > 0:
        mult = 1.65 if is_pre else 1.15
        ma_avg = round(fed_avg * mult, 2)
        ma_profit = round(ma_avg - landed, 2)
        lot["ma_retail"] = ma_avg
        lot["ma_profit"] = ma_profit
        lot["ma_margin"] = round((ma_profit / ma_avg) * 100, 1) if ma_avg > 0 else 0.0
        lot["federal_profit"] = round(fed_avg - landed, 2)
        lot["compliance_badge"] = "Pre-Ban Grandfathered" if is_pre else ("70% of new" if basis == "newfallback" else (("Retail ref" if lot.get("condition") == "new" else "Sold comps") if basis == "table" else ("New comps" if lot.get("condition") == "new" else "Used comps")))
    else:
        lot["ma_retail"] = lot["ma_profit"] = lot["ma_margin"] = lot["federal_profit"] = 0.0
        lot["compliance_badge"] = "Unvalued"
    return lot


def build_lot(src, title, make, model, ask_price, url, caliber="", is_auction=False, buy_now=0.0):
    prem_pct = 0.035 if src == "GunBroker" else 0.0
    shipping_ffl = 45.0 if src == "GunBroker" else 30.0
    landed = round((ask_price * (1.0 + prem_pct)) + shipping_ffl, 2)
    lid = f"{src[:2].upper()}-{hashlib.md5(url.encode()).hexdigest()[:8]}"
    lot = {
        "lot_id": lid,
        "source_site": src,
        "title": squash(title),
        "make": make,
        "model": model,
        "caliber": caliber,
        "current_bid": ask_price,
        "buy_now": buy_now,
        "is_auction": bool(is_auction),
        "condition": detect_condition(src, title),
        "total_landed_cost": landed,
        "listing_url": url,
    }
    vals, avg, is_pre = table_valuation(f"{make} {model} {title}", lot["condition"])
    if vals:
        finalize_lot(lot, avg, "table", is_pre, val_sources=vals)
    else:
        finalize_lot(lot, 0.0, "none", is_pre)
    return lot


def caliber_key(cal: str) -> str:
    m = re.search(r"\d+(?:\.\d+)?", cal or "")
    if not m:
        return ""
    base = m.group(0).replace(".", "")
    return base + ("mm" if "mm" in (cal or "").lower() else "")


def model_key(lot: dict, cond: str = "") -> str:
    make = re.sub(r"[^a-z0-9]", "", str(lot.get("make", "")).lower())
    mtxt = re.sub(r"\bgen\.?\s?\d\b", " ", str(lot.get("model", "")).lower())
    toks = re.findall(r"[a-z0-9][a-z0-9\-\.&/]*", mtxt)
    toks = [t for t in toks if t not in ("unknown", "model")][:3]
    if not make or not toks:
        return ""
    return make + "|" + " ".join(toks) + "|" + caliber_key(lot.get("caliber", "")) + "|" + (cond or str(lot.get("condition", "used")))


USED_FROM_NEW_FACTOR = 0.70


def apply_peer_comps(lots):
    """Value unvalued listings from other listings of the same make and model.

    Used guns are compared with other used guns. If no used comps exist, fall back to 70% of the median
    price of the same model sold new. New guns are only compared with new guns.
    """
    groups = {}
    for l in lots:
        k = model_key(l)
        price = l.get("buy_now") or (0 if l.get("is_auction") else l.get("current_bid", 0))
        if k and price and price >= 50:
            groups.setdefault(k, []).append((l["listing_url"], price))
    valued = 0
    fallback = 0
    for l in lots:
        if l.get("federal_retail", 0) > 0:
            continue
        k = model_key(l)
        peers = [p for (u, p) in groups.get(k, []) if u != l["listing_url"]]
        if len(peers) >= 2:
            comp = round(statistics.median(peers), 2)
            finalize_lot(l, comp, "peer", l.get("is_pre_ban", False),
                         val_sources={"peer_median": comp, "peer_count": len(peers)})
            valued += 1
            continue
        if l.get("condition") == "used":
            new_peers = [p for (u, p) in groups.get(model_key(l, "new"), []) if u != l["listing_url"]]
            if new_peers:
                new_med = round(statistics.median(new_peers), 2)
                finalize_lot(l, round(new_med * USED_FROM_NEW_FACTOR, 2), "newfallback", l.get("is_pre_ban", False),
                             val_sources={"new_median": new_med, "factor": USED_FROM_NEW_FACTOR, "peer_count": len(new_peers)})
                fallback += 1
    print(f"Peer comps applied to {valued} listings; 70%-of-new fallback on {fallback}.")


# ---------- GunBroker official API ----------
def fetch_gunbroker_api(keywords="pistol", page_size=48):
    if not GB_KEY:
        print("GunBroker: no GUNBROKER_DEV_KEY set, skipping.")
        return []
    try:
        resp = requests.get(
            "https://api.gunbroker.com/v1/Items",
            headers={"X-DevKey": GB_KEY},
            params={"Keywords": keywords, "PageSize": page_size, "Sort": 13},
            timeout=30,
        )
        print(f"GunBroker API status: {resp.status_code}")
        if resp.status_code != 200:
            print(resp.text[:300])
            return []
        results = resp.json().get("results", [])
    except Exception as e:
        print(f"GunBroker API error: {e}")
        return []

    lots = []
    for it in results:
        price = it.get("currentBid") or it.get("buyPrice") or it.get("fixedPrice") or 0
        try:
            price = float(price)
        except (TypeError, ValueError):
            continue
        title = it.get("title", "")
        if price < 50.0 or len(title) < 5 or not is_gun_listing(title):
            continue
        link = f"https://www.gunbroker.com/item/{it.get('itemID')}"
        t = clean_title(title)
        make, model = split_make_model(t)
        lots.append(build_lot("GunBroker", t, make, model, price, link, find_caliber(t), is_auction=True))
    print(f"[GunBroker] Extracted {len(lots)} listings from API.")
    return lots


# ---------- ScraperAPI ----------
def fetch_html(target_url: str, render_js: bool, premium: bool = False) -> str:
    if not SCRAPER_API_KEY:
        print("No SCRAPER_API_KEY set.")
        return ""
    try:
        payload = {
            "api_key": SCRAPER_API_KEY,
            "url": target_url,
            "render": "true" if render_js else "false",
        }
        if render_js and premium:
            payload["premium"] = "true"
        proxy_url = f"http://api.scraperapi.com?{urllib.parse.urlencode(payload)}"
        resp = requests.get(proxy_url, timeout=70)
        print(f"ScraperAPI {resp.status_code} for {target_url}")
        if resp.status_code == 200:
            return resp.text
    except Exception as e:
        print(f"Fetch error for {target_url}: {e}")
    return ""


def money(text: str):
    """All dollar amounts in text. Handles '$349 99' (cents in a separate element) and '$1,299.99'."""
    out = []
    for m in re.finditer(r"\$\s?([0-9][0-9,]*)(?:\.(\d{2})|\s+(\d{2})\b)?", text or ""):
        whole = float(m.group(1).replace(",", ""))
        cents = m.group(2) or m.group(3)
        out.append(whole + (int(cents) / 100.0 if cents else 0.0))
    return out


def absolute_url(config, href):
    if href.startswith("http"):
        return href
    if href.startswith("/"):
        return f"{config['url_prefix']}{href}"
    return f"{config['url_prefix']}/{href}"


def parse_gunscom(card, config):
    a = card.select_one("a[href]")
    if not a:
        return None
    title = squash(a.get("title") or "")
    brand_el = card.select_one(".manufacturer")
    brand = squash(brand_el.get_text(" ", strip=True)) if brand_el else ""
    if not title:
        title = squash(card.get_text(" ", strip=True))[:80]
    model_hint = title
    if brand and title.lower().startswith(brand.lower()):
        model_hint = title[len(brand):].strip()
    make, model = split_make_model(title, make_hint=brand, model_hint=model_hint) if brand else split_make_model(title)
    specs = [squash(s.get_text(" ", strip=True)) for s in card.select(".spec")]
    caliber = specs[0] if specs and CALIBER_RE.search(specs[0]) else find_caliber(" ".join(specs) + " " + title)

    price_box = card.select_one(".price-container") or card
    ptxt = price_box.get_text(" ", strip=True)
    amounts = money(ptxt)
    if not amounts:
        amounts = money(card.get_text(" ", strip=True))
    if not amounts:
        return None
    full = card.get_text(" ", strip=True).upper()
    is_auction = "AUCTION" in full or "STARTING BID" in full or "BID / BUY" in full
    buy_now = amounts[1] if (is_auction and len(amounts) > 1) else 0.0
    return dict(title=title, make=make, model=model, price=amounts[0], url=absolute_url(config, a.get("href", "")),
                caliber=caliber, is_auction=is_auction, buy_now=buy_now)


def parse_classic(card, config):
    name = card.select_one("h2.product-name a, .product-name a")
    if not name:
        return None
    title = squash(name.get("title") or name.get_text(" ", strip=True))
    if len(title) < 5:
        return None
    price_el = card.select_one(".special-price .price") or card.select_one(".product-price .price") or card.select_one(".price")
    amounts = money(price_el.get_text(" ", strip=True)) if price_el else money(card.get_text(" ", strip=True))
    if not amounts:
        return None
    make, model = split_make_model(title)
    return dict(title=title, make=make, model=model, price=amounts[0], url=absolute_url(config, name.get("href", "")),
                caliber=find_caliber(title), is_auction=False, buy_now=0.0)


def strip_condition(title: str) -> str:
    return squash(re.sub(r"^(?:used|like new|new)\s+", "", title or "", flags=re.IGNORECASE))


def first_price(text):
    amounts = money(text)
    return amounts[0] if amounts else 0.0


def parse_buds(a, config):
    title = squash(a.get_text(" ", strip=True))
    if len(title) < 8:
        return None
    price_el = None
    for parent in a.parents:
        price_el = parent.select_one("[id^=card-pricing-display]")
        if price_el:
            break
        if parent.name == "body":
            return None
    if not price_el:
        return None
    price = first_price(price_el.get_text(" ", strip=True))
    if not price:
        return None
    title = strip_condition(title)
    make, model = split_make_model(title)
    return dict(title=title, make=make, model=model, price=price, url=absolute_url(config, a.get("href", "")),
                caliber=find_caliber(title), is_auction=False, buy_now=0.0)


def parse_sportsmans(card, config):
    a = card.select_one(".prd-info h2 a")
    if not a:
        return None
    title = strip_condition(squash(a.get_text(" ", strip=True)))
    price_el = card.select_one("span.price")
    price = first_price(price_el.get_text(" ", strip=True)) if price_el else 0.0
    if not price:
        return None
    brand_el = card.select_one("[itemprop=brand] [itemprop=name], [itemprop=brand]")
    brand = squash(brand_el.get_text(" ", strip=True)) if brand_el else ""
    if brand:
        hint = title[len(brand):].strip() if title.lower().startswith(brand.lower()) else title
        make, model = split_make_model(title, make_hint=brand, model_hint=hint)
    else:
        make, model = split_make_model(title)
    return dict(title=title, make=make, model=model, price=price, url=absolute_url(config, a.get("href", "")),
                caliber=find_caliber(title), is_auction=False, buy_now=0.0)


def parse_usedguns(card, config):
    a = card.select_one("a[href*='/Item/Details/']")
    if not a:
        return None
    title = squash(a.get_text(" ", strip=True))
    if not title:
        info = card.select_one(".item-info")
        title = squash(info.get_text(" ", strip=True).split("$")[0]) if info else ""
    if len(title) < 4:
        return None
    price = first_price(card.get_text(" ", strip=True))
    if not price:
        return None
    make, model = split_make_model(title)
    return dict(title=title, make=make, model=model, price=price, url=absolute_url(config, a.get("href", "")),
                caliber=find_caliber(title), is_auction=False, buy_now=0.0)


def parse_gunsamerica(a, config):
    title = squash(a.get_text(" ", strip=True))
    href = a.get("href", "")
    path = href.split("?")[0].strip("/").split("/")
    if title.endswith("...") or title.endswith("\u2026"):
        if len(path) >= 2:
            title = squash(title.rstrip(".\u2026") + " " + path[-1].replace("-", " "))
    if len(title) < 4:
        return None
    card = a
    for parent in a.parents:
        if first_price(parent.get_text(" ", strip=True)) and len(parent.find_all("h2")) == 1:
            card = parent
            break
    price = first_price(card.get_text(" ", strip=True))
    if not price:
        return None
    make, model = split_make_model(title)
    return dict(title=title, make=make, model=model, price=price, url=absolute_url(config, href),
                caliber=find_caliber(title), is_auction=False, buy_now=0.0)


def parse_armslist(card, config):
    a = card.select_one("h3 a, a.search-link")
    if not a:
        return None
    title = squash(a.get("title") or a.get_text(" ", strip=True))
    if len(title) < 4:
        return None
    price_el = card.select_one(".ci-price")
    price = first_price(price_el.get_text(" ", strip=True)) if price_el else 0.0
    if not price:
        return None
    make, model = split_make_model(title)
    return dict(title=title, make=make, model=model, price=price, url=absolute_url(config, a.get("href", "")),
                caliber=find_caliber(title), is_auction=False, buy_now=0.0)


def parse_hibid(card, config):
    a = None
    for cand in card.select(".app-auction-lot-card__body a[href*='/lot/'], a[href*='/lot/']"):
        if len(squash(cand.get_text(" ", strip=True))) > 6 and not re.match(r"^lot\s*\d+$", squash(cand.get_text(" ", strip=True)), re.I):
            a = cand
            break
    if not a:
        return None
    full = squash(card.get_text(" ", strip=True))
    if "local pickup only" in full.lower():
        return None
    price = first_price(full)
    if not price:
        return None
    title = squash(a.get_text(" ", strip=True))
    make, model = split_make_model(title)
    return dict(title=title, make=make, model=model, price=price, url=absolute_url(config, a.get("href", "")),
                caliber=find_caliber(title), is_auction=True, buy_now=0.0)


def parse_tacswap(a, config):
    title = squash(a.get_text(" ", strip=True))
    if len(title) < 4:
        return None
    card = a
    for parent in a.parents:
        txt = squash(parent.get_text(" ", strip=True))
        if "$" in txt and len(txt) < 400:
            card = parent
            break
    txt = squash(card.get_text(" ", strip=True))
    if "want to trade" in txt.lower():
        return None
    price = first_price(txt)
    if not price:
        return None
    make, model = split_make_model(title)
    return dict(title=title, make=make, model=model, price=price, url=absolute_url(config, a.get("href", "")),
                caliber=find_caliber(title), is_auction=False, buy_now=0.0)


PARSERS = {"Guns.com": parse_gunscom, "Classic Firearms": parse_classic, "Buds Gun Shop": parse_buds,
           "Sportsman's Outdoor Superstore": parse_sportsmans, "UsedGuns.com": parse_usedguns,
           "GunsAmerica": parse_gunsamerica, "Armslist": parse_armslist, "HiBid": parse_hibid,
           "Tacswap": parse_tacswap}


def scrape_target(site_name, task_url):
    lots = []
    config = SITE_CONFIGS[site_name]
    print(f"Executing task for {site_name}: {task_url}")
    html = fetch_html(task_url, render_js=config["render_js"], premium=config.get("premium", False))
    if not html:
        return lots
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select(config["card_selector"])
    parser = PARSERS[site_name]
    dropped = 0
    for card in cards:
        try:
            item = parser(card, config)
        except Exception as e:
            print(f"[{site_name}] parse error: {e}")
            item = None
        if not item or item["price"] < 50.0 or not is_gun_listing(item["title"]):
            dropped += 1
            continue
        if config.get("strict") and not looks_like_gun(item["title"]):
            dropped += 1
            continue
        lots.append(build_lot(site_name, item["title"], item["make"], item["model"], item["price"],
                              item["url"], item["caliber"], item["is_auction"], item["buy_now"]))
    print(f"[{site_name}] {task_url} -> cards={len(cards)} kept={len(lots)} dropped={dropped}")
    return lots


def main():
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Starting multi-platform scrape...")
    lots = []
    per_source = {}

    gb = []
    for kw in ("pistol", "revolver", "rifle", "shotgun"):
        gb.extend(fetch_gunbroker_api(keywords=kw))
    lots.extend(gb)
    per_source["GunBroker"] = len(gb)

    tasks = []
    for site, cfg in SITE_CONFIGS.items():
        for u in cfg["urls"]:
            tasks.append({"site": site, "url": u})

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(scrape_target, t["site"], t["url"]): t["site"] for t in tasks}
        for future in as_completed(futures):
            site = futures[future]
            try:
                res = future.result()
                if res:
                    lots.extend(res)
                    per_source[site] = per_source.get(site, 0) + len(res)
            except Exception as e:
                print(f"Exception in worker thread: {e}")

    unique_map = {}
    for item in lots:
        url = item.get("listing_url", "")
        if url and url not in unique_map:
            unique_map[url] = item
    valid_lots = list(unique_map.values())

    apply_peer_comps(valid_lots)
    valid_lots.sort(key=lambda x: (x["ma_profit"], x["ma_margin"]), reverse=True)

    if not valid_lots:
        print("No listings retrieved; keeping existing feed_data.json untouched.")
        return

    valued = sum(1 for l in valid_lots if l.get("federal_retail", 0) > 0)
    print(f"Per source: {per_source}; valued {valued}/{len(valid_lots)}")

    feed_payload = {
        "last_updated": datetime.now().strftime("%Y-%m-%d %I:%M %p"),
        "total_scraped": len(valid_lots),
        "per_source": per_source,
        "lots": valid_lots,
    }

    try:
        tmp = FEED_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(feed_payload, f, indent=2)
        os.replace(tmp, FEED_FILE)
        print(f"SUCCESS: feed updated with {len(valid_lots)} listings.\n")
    except Exception as e:
        print(f"Failed to write feed file: {e}")


if __name__ == "__main__":
    main()
