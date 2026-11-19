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
]
BRANDS.sort(key=len, reverse=True)
BRAND_ALIASES = {"s&w": "Smith & Wesson", "sig": "Sig Sauer", "hk": "Heckler & Koch",
                 "hi point": "Hi-Point", "ati": "ATI", "cz": "CZ", "fn": "FN", "fnh": "FN",
                 "iwi": "IWI", "sccy": "SCCY", "heckler and koch": "Heckler & Koch",
                 "smith and wesson": "Smith & Wesson", "dpms": "DPMS", "altor corp": "Altor Corp"}

SITE_CONFIGS = {
    "Guns.com": {
        "card_selector": "li.product-card, .productCard, div[class*='productCard']",
        "url_prefix": "https://www.guns.com",
        "render_js": True,
        "urls": ["https://www.guns.com/firearms/handguns?condition=used"],
    },
    "Classic Firearms": {
        "card_selector": "div.product-card, .product-item",
        "url_prefix": "https://www.classicfirearms.com",
        "render_js": False,
        "urls": [
            "https://www.classicfirearms.com/firearms/handguns/",
            "https://www.classicfirearms.com/firearms/handguns/?p=2",
            "https://www.classicfirearms.com/firearms/handguns/?p=3",
        ],
    },
}

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


def table_valuation(title: str):
    t_lower = normalize_for_match(title)
    is_pre = any(trig in t_lower for trig in PRE_BAN_TRIGGERS)
    for key, vals in MULTI_SOURCE_VALUATIONS.items():
        if re.search(r"\b" + re.escape(key) + r"\b", t_lower):
            return vals, round(sum(vals.values()) / 3.0, 2), is_pre
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
        lot["compliance_badge"] = "Pre-Ban Grandfathered" if is_pre else ("Roster Model" if basis == "table" else "Peer comp")
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
        "total_landed_cost": landed,
        "listing_url": url,
    }
    vals, avg, is_pre = table_valuation(f"{make} {model} {title}")
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


def model_key(lot: dict) -> str:
    make = re.sub(r"[^a-z0-9]", "", str(lot.get("make", "")).lower())
    mtxt = re.sub(r"\bgen\.?\s?\d\b", " ", str(lot.get("model", "")).lower())
    toks = re.findall(r"[a-z0-9][a-z0-9\-\.&/]*", mtxt)
    toks = [t for t in toks if t not in ("unknown", "model")][:3]
    if not make or not toks:
        return ""
    return make + "|" + " ".join(toks) + "|" + caliber_key(lot.get("caliber", ""))


def apply_peer_comps(lots):
    """Value unvalued listings with the median price of OTHER listings of the same make and model."""
    groups = {}
    for l in lots:
        k = model_key(l)
        price = l.get("buy_now") or (0 if l.get("is_auction") else l.get("current_bid", 0))
        if k and price and price >= 50:
            groups.setdefault(k, []).append((l["listing_url"], price))
    valued = 0
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
    print(f"Peer comps applied to {valued} listings.")


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
def fetch_html(target_url: str, render_js: bool) -> str:
    if not SCRAPER_API_KEY:
        print("No SCRAPER_API_KEY set.")
        return ""
    try:
        payload = {
            "api_key": SCRAPER_API_KEY,
            "url": target_url,
            "render": "true" if render_js else "false",
        }
        if render_js:
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


PARSERS = {"Guns.com": parse_gunscom, "Classic Firearms": parse_classic}


def scrape_target(site_name, task_url):
    lots = []
    config = SITE_CONFIGS[site_name]
    print(f"Executing task for {site_name}: {task_url}")
    html = fetch_html(task_url, render_js=config["render_js"])
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
        lots.append(build_lot(site_name, item["title"], item["make"], item["model"], item["price"],
                              item["url"], item["caliber"], item["is_auction"], item["buy_now"]))
    print(f"[{site_name}] {task_url} -> cards={len(cards)} kept={len(lots)} dropped={dropped}")
    return lots


def main():
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Starting multi-platform scrape...")
    lots = []
    per_source = {}

    gb = fetch_gunbroker_api()
    lots.extend(gb)
    per_source["GunBroker"] = len(gb)

    tasks = []
    for site, cfg in SITE_CONFIGS.items():
        for u in cfg["urls"]:
            tasks.append({"site": site, "url": u})

    with ThreadPoolExecutor(max_workers=3) as executor:
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
