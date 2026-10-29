import os
import re
import json
import urllib.parse
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

FEED_FILE = "feed_data.json"
SCRAPER_API_KEY = os.environ.get("SCRAPER_API_KEY", "").strip()

# Master Triangulated Valuation Matrix
MULTI_SOURCE_VALUATIONS = {
    "colt python": {"gb_sold": 1420.0, "gc_retail": 1495.0, "ga_comp": 1450.0},
    "colt anaconda": {"gb_sold": 1350.0, "gc_retail": 1425.0, "ga_comp": 1380.0},
    "glock 19": {"gb_sold": 510.0, "gc_retail": 550.0, "ga_comp": 530.0},
    "glock 43": {"gb_sold": 435.0, "gc_retail": 475.0, "ga_comp": 450.0},
    "smith & wesson 686": {"gb_sold": 850.0, "gc_retail": 910.0, "ga_comp": 880.0},
    "sig sauer p365": {"gb_sold": 520.0, "gc_retail": 570.0, "ga_comp": 545.0},
    "ruger 10/22": {"gb_sold": 275.0, "gc_retail": 310.0, "ga_comp": 290.0},
    "hk mp5": {"gb_sold": 2800.0, "gc_retail": 3100.0, "ga_comp": 2950.0},
    "staccato p": {"gb_sold": 2250.0, "gc_retail": 2450.0, "ga_comp": 2350.0}
}

PRE_BAN_TRIGGERS = ["pre-ban", "pre ban", "pre-94", "pre 94", "sporter match", "green label", "blue label sporter", "mak-90"]

SITE_CONFIGS = {
    "GunBroker": {
        "card_selector": "div[data-item-id], .item-row, .tile, .listing, article, tr",
        "link_filter": "/item/",
        "url_prefix": "https://www.gunbroker.com",
        "render_js": True
    },
    "Guns.com": {
        "card_selector": ".productCard, .product-card, div[class*='productCard']",
        "link_filter": "/firearms/",
        "url_prefix": "https://www.guns.com",
        "render_js": True
    },
    "Classic Firearms": {
        "card_selector": ".product-item, .product-card, div[class*='product-item']",
        "link_filter": "/firearms/",
        "url_prefix": "https://www.classicfirearms.com",
        "render_js": False
    }
}

def clean_title(raw_title: str) -> str:
    cleaned = re.sub(r'^(Recently Added.*?\d+\s+days\s+ago|SHOWCASE|NEW)', '', raw_title, flags=re.IGNORECASE)
    cleaned = re.sub(r'[^\w\s\-\.\#\/\(\)]', ' ', cleaned)
    cleaned = re.sub(r'([a-zA-Z])([0-9])', r'\1 \2', cleaned)
    cleaned = re.sub(r'([0-9])([a-zA-Z])', r'\1 \2', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned if len(cleaned) > 4 else raw_title

def extract_multi_source_valuation(title: str):
    t_lower = title.lower()
    is_pre = any(trig in t_lower for trig in PRE_BAN_TRIGGERS)
    matched_make = "General"
    matched_model = "Unknown"
    
    v_dict = {"gb_sold": 550.0, "gc_retail": 610.0, "ga_comp": 580.0}

    for key, val_sources in MULTI_SOURCE_VALUATIONS.items():
        if key in t_lower:
            parts = key.split(" ", 1)
            matched_make = parts[0]
            matched_model = parts[1] if len(parts) > 1 else "Various"
            v_dict = val_sources
            break

    val_average = round((v_dict["gb_sold"] + v_dict["gc_retail"] + v_dict["ga_comp"]) / 3.0, 2)
    badge = "🔥 Pre-Ban Grandfathered" if is_pre else "Commercial Roster"
    return matched_make, matched_model, v_dict, val_average, is_pre, badge

def calculate_margins(src, title, ask_price, url):
    make, model, val_sources, fed_avg, is_pre, badge = extract_multi_source_valuation(title)

    prem_pct = 0.035 if src == "GunBroker" else 0.0
    shipping_ffl = 45.0 if src == "GunBroker" else 30.0

    landed = round((ask_price * (1.0 + prem_pct)) + shipping_ffl, 2)
    ma_multiplier = 1.65 if is_pre else 1.15
    ma_avg = round(fed_avg * ma_multiplier, 2)

    ma_profit = round(ma_avg - landed, 2)
    ma_margin = round((ma_profit / ma_avg) * 100, 1) if ma_avg > 0 else 0.0
    
    lid = f"{src[:2].upper()}-{abs(hash(url)) % 10000000}"

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
        "federal_profit": round(fed_avg - landed, 2),
        "ma_retail": ma_avg,
        "ma_profit": ma_profit,
        "ma_margin": ma_margin,
        "is_pre_ban": is_pre,
        "compliance_badge": badge,
        "listing_url": url
    }

def fetch_html(target_url: str, render_js: bool) -> str:
    try:
        if not SCRAPER_API_KEY:
            return ""
        payload = {
            "api_key": SCRAPER_API_KEY,
            "url": target_url,
            "render": "true" if render_js else "false",
            "premium": "true"
        }
        proxy_url = f"http://api.scraperapi.com?{urllib.parse.urlencode(payload)}"
        resp = requests.get(proxy_url, timeout=50)
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
            
            lot = calculate_margins(site_name, title_str, price_val, link)
            if lot: 
                print(f"  -> KEPT [{site_name}]: {title_str[:35]}... | ${price_val}")
                lots.append(lot)
                
        print(f"[{site_name}] Successfully extracted {len(lots)} clean listings.")
    return lots

def main():
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Starting Expanded Multi-Platform Scrape...")
    lots = []
    
    tasks = [
        {"site": "GunBroker", "url": "https://www.gunbroker.com/All/search?Keywords=pistol&Sort=13&PageSize=48"},
        {"site": "Guns.com", "url": "https://www.guns.com/firearms/handguns?condition=used"},
        {"site": "Classic Firearms", "url": "https://www.classicfirearms.com/firearms/handguns/"}
    ]
    
    with ThreadPoolExecutor(max_workers=3) as executor:
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

    feed_payload = {
        "last_updated": datetime.now().strftime("%Y-%m-%d %I:%M %p"),
        "total_scraped": len(valid_lots),
        "lots": valid_lots
    }

    try:
        with open(FEED_FILE, "w") as f:
            json.dump(feed_payload, f, indent=2)
        print(f"SUCCESS: feed_data.json updated with {len(valid_lots)} verified multi-platform listings.\n")
    except Exception as e:
        print(f"Failed to write feed file: {e}")

if __name__ == "__main__":
    main()
