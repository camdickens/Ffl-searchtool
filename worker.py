import os
import re
import json
import hashlib
import urllib.parse
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FEED_FILE = os.path.join(BASE_DIR, "feed_data.json")
SCRAPER_API_KEY = os.environ.get("SCRAPER_API_KEY", "").strip()
GB_KEY = os.environ.get("GUNBROKER_DEV_KEY", "").strip()

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

SITE_CONFIGS = {
    "Guns.com": {
        "card_selector": ".productCard, .product-card, div[class*='productCard']",
        "link_filter": "/firearms/",
        "url_prefix": "https://www.guns.com",
        "render_js": True,
    },
    "Classic Firearms": {
        "card_selector": ".product-item, .product-card, div[class*='product-item']",
        "link_filter": "/firearms/",
        "url_prefix": "https://www.classicfirearms.com",
        "render_js": False,
    },
}


def clean_title(raw_title: str) -> str:
    cleaned = re.sub(r'^(Recently Added.*?\d+\s+days\s+ago|SHOWCASE|NEW)', '',
                     raw_title, flags=re.IGNORECASE)
    cleaned = re.sub(r'[^\w\s\-\.\#\/\(\)&]', ' ', cleaned)
    cleaned = re.sub(r'([a-zA-Z])([0-9])', r'\1 \2', cleaned)
    cleaned = re.sub(r'([0-9])([a-zA-Z])', r'\1 \2', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned if len(cleaned) > 4 else raw_title


def normalize_for_match(title: str) -> str:
    t = title.lower()
    t = re.sub(r'\bs\s?&\s?w\b', 'smith & wesson', t)
    t = re.sub(r'\bsig\b(?!\s*sauer)', 'sig sauer', t)
    t = re.sub(r'\bh&k\b|\bheckler\s*&?\s*koch\b', 'hk', t)
    return t


def extract_multi_source_valuation(title: str):
    t_lower = normalize_for_match(title)
    is_pre = any(trig in t_lower for trig in PRE_BAN_TRIGGERS)
    matched_make, matched_model = "General", "Unknown"
    v_dict = None

    for key, val_sources in MULTI_SOURCE_VALUATIONS.items():
        # word-boundary match so "glock 19" doesn't match "glock 19x"
        if re.search(r'\b' + re.escape(key) + r'\b', t_lower):
            parts = key.split(" ", 1)
            matched_make = parts[0]
            matched_model = parts[1] if len(parts) > 1 else "Various"
            v_dict = val_sources
            break

    if v_dict is None:
        return matched_make, matched_model, None, 0.0, is_pre, "Unvalued"

    val_average = round(sum(v_dict.values()) / 3.0, 2)
    badge = "🔥 Pre-Ban Grandfathered" if is_pre else "Commercial Roster"
    return matched_make, matched_model, v_dict, val_average, is_pre, badge


def calculate_margins(src, title, ask_price, url):
    make, model, val_sources, fed_avg, is_pre, badge = extract_multi_source_valuation(title)

    prem_pct = 0.035 if src == "GunBroker" else 0.0
    shipping_ffl = 45.0 if src == "GunBroker" else 30.0
    landed = round((ask_price * (1.0 + prem_pct)) + shipping_ffl, 2)

    if val_sources is None:
        ma_avg, ma_profit, ma_margin, fed_profit = 0.0, 0.0, 0.0, 0.0
    else:
        ma_multiplier = 1.65 if is_pre else 1.15
        ma_avg = round(fed_avg * ma_multiplier, 2)
        ma_profit = round(ma_avg - landed, 2)
        ma_margin = round((ma_profit / ma_avg) * 100, 1) if ma_avg > 0 else 0.0
        fed_profit = round(fed_avg - landed, 2)

    lid = f"{src[:2].upper()}-{hashlib.md5(url.encode()).hexdigest()[:8]}"

    return {
        "lot_id": lid,
        "source_site": src,
        "title": title.strip(),
        "make": make,
        "model": model,
        "current_bid": ask_price,
        "total_landed_cost": landed,
        "valuation_sources": {"triangulated_avg": fed_avg},
        "federal_retail": fed_avg,
        "federal_profit": fed_profit,
        "ma_retail": ma_avg,
        "ma_profit": ma_profit,
        "ma_margin": ma_margin,
        "is_pre_ban": is_pre,
        "compliance_badge": badge,
        "listing_url": url,
    }


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
        if price < 50.0 or len(title) < 5:
            continue
        link = f"https://www.gunbroker.com/item/{it.get('itemID')}"
        lots.append(calculate_margins("GunBroker", clean_title(title), price, link))
    print(f"[GunBroker] Extracted {len(lots)} listings from API.")
    return lots


# ---------- ScraperAPI for the other sites ----------
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
        resp = requests.get(proxy_url, timeout=60)
        print(f"ScraperAPI {resp.status_code} for {target_url}")
        if resp.status_code == 200:
            return resp.text
    except Exception as e:
        print(f"Fetch error for {target_url}: {e}")
    return ""


def scrape_target(site_name, task_url):
    lots = []
    print(f"Executing task for {site_name}...")
    config = SITE_CONFIGS[site_name]
    html = fetch_html(task_url, render_js=config["render_js"])

    if html:
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select(config["card_selector"])
        print(f"[{site_name}] Found {len(cards)} item cards/rows.")

        for card in cards:
            txt = card.get_text(separator=" ", strip=True)
            if len(txt) < 15:
                continue

            target_a = None
            for a in card.find_all("a", href=True):
                if config["link_filter"] in a["href"]:
                    target_a = a
                    break
            if not target_a:
                target_a = card.select_one("a[href]")
            if not target_a:
                continue

            href = target_a.get("href", "")
            raw_title = target_a.get_text(strip=True)

            if len(raw_title) < 5:
                h_tag = card.select_one("h2, h3, h4, h5, span")
                if h_tag:
                    raw_title = h_tag.get_text(strip=True)
            if len(raw_title) < 5:
                continue

            title_str = clean_title(raw_title)

            price_val = 0.0
            match = re.search(r'\$\s?([0-9,]+(?:\.[0-9]{1,2})?)', txt)
            if match:
                try:
                    price_val = float(match.group(1).replace(",", ""))
                except ValueError:
                    pass
            if price_val < 50.0:
                continue

            if href.startswith("http"):
                link = href
            elif href.startswith("/"):
                link = f"{config['url_prefix']}{href}"
            else:
                link = f"{config['url_prefix']}/{href}"

            lots.append(calculate_margins(site_name, title_str, price_val, link))

        print(f"[{site_name}] Extracted {len(lots)} listings.")
    return lots


def main():
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Starting multi-platform scrape...")
    lots = []

    lots.extend(fetch_gunbroker_api())

    tasks = [
        {"site": "Guns.com", "url": "https://www.guns.com/firearms/handguns?condition=used"},
        {"site": "Classic Firearms", "url": "https://www.classicfirearms.com/firearms/handguns/"},
    ]

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_to_task = {executor.submit(scrape_target, t["site"], t["url"]): t["site"] for t in tasks}
        for future in as_completed(future_to_task):
            try:
                res = future.result()
                if res:
                    lots.extend(res)
            except Exception as e:
                print(f"Exception in worker thread: {e}")

    unique_map = {}
    for item in lots:
        url = item.get("listing_url", "")
        if url and url not in unique_map:
            unique_map[url] = item

    valid_lots = list(unique_map.values())
    valid_lots.sort(key=lambda x: (x["ma_profit"], x["ma_margin"]), reverse=True)

    if not valid_lots:
        print("No listings retrieved; keeping existing feed_data.json untouched.")
        return

    feed_payload = {
        "last_updated": datetime.now().strftime("%Y-%m-%d %I:%M %p"),
        "total_scraped": len(valid_lots),
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
