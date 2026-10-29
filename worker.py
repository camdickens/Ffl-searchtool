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

SOLD_REJECT_TERMS = [
    "sold", "sold out", "out of stock", "bidding closed", "auction ended",
    "listing ended", "ended", "closed", "winning bid", "final bid",
    "sale pending", "pending sale", "spf", "reserve met", "reserve not met",
    "backorder", "notify me", "notify when in stock", "expired", "inactive",
    "won", "completed", "archive", "archived", "time left: 0", "item ended"
]

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
        "card_selector": ".listing, .tile, .item-tile",
        "title_selector": ".title a, .item-title, h3 a",
        "price_selector": ".price, .bid-price",
        "url_prefix": "https://www.gunbroker.com"
    },
    "Guns.com": {
        "card_selector": ".productCard, .product-card, .productItem",
        "title_selector": ".productCard__title a, a.product-title, h3 a",
        "price_selector": ".productCard__price, .price",
        "url_prefix": "https://www.guns.com"
    },
    "Armslist": {
        "card_selector": ".card, .listing-card, .row.category-item",
        "title_selector": ".title a, h2 a, h4 a",
        "price_selector": ".price, .listing-price",
        "url_prefix": "https://www.armslist.com"
    },
    "HiBid": {
        "card_selector": ".lot-item, .lot-card, .lot-box",
        "title_selector": ".lot-title, .lot-name",
        "price_selector": ".lot-high-bid, .current-bid, .price",
        "url_prefix": "https://hibid.com"
    },
    "TacSwap": {
        "card_selector": "a[href^='/post/']",
        "title_selector": "h6, h5, .post-title, p",
        "price_selector": "p, span", 
        "url_prefix": "https://www.tacswap.com"
    }
}

def is_sold_or_ended(text: str) -> bool:
    t_clean = text.lower()
    for term in SOLD_REJECT_TERMS:
        if re.search(r'\b' + re.escape(term) + r'\b', t_clean) or f"[{term}]" in t_clean or f"({term})" in t_clean:
            return True
    return False

def extract_multi_source_valuation(title: str):
    t_lower = title.lower()
    is_pre = any(trig in t_lower for trig in PRE_BAN_TRIGGERS)
    matched_make = "General"
    matched_model = "Unknown"
    
    # Baseline for items not found in our matrix
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

def calculate_margins(src, title, ask_price, url, status_text="Active"):
    if is_sold_or_ended(title) or is_sold_or_ended(status_text) or is_sold_or_ended(url):
        return None

    make, model, val_sources, fed_avg, is_pre, badge = extract_multi_source_valuation(title)

    prem_pct = 0.18 if src == "HiBid" else (0.035 if src == "GunBroker" else 0.0)
    shipping_ffl = 45.0 if src in ["HiBid", "GunBroker"] else 30.0

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
        "valuation_sources": {
            "triangulated_avg": fed_avg
        },
        "federal_retail": fed_avg,
        "federal_profit": round(fed_avg - landed, 2),
        "ma_retail": ma_avg,
        "ma_profit": ma_profit,
        "ma_margin": ma_margin,
        "is_pre_ban": is_pre,
        "compliance_badge": badge,
        "listing_url": url
    }

def fetch_html(target_url: str, render_js: bool, use_premium: bool = True) -> str:
    try:
        if not SCRAPER_API_KEY:
            return ""
        payload = {
            "api_key": SCRAPER_API_KEY,
            "url": target_url,
            "render": "true" if render_js else "false",
            "premium": "true" if use_premium else "false"
        }
        proxy_url = f"http://api.scraperapi.com?{urllib.parse.urlencode(payload)}"
        resp = requests.get(proxy_url, timeout=45)
        if resp.status_code == 200:
            return resp.text
    except Exception:
        pass
    return ""

def scrape_target(site_name, task_url, render_js):
    lots = []
    print(f"Executing task for {site_name}...")
    html = fetch_html(task_url, render_js=render_js, use_premium=True)
    
    if html:
        soup = BeautifulSoup(html, "html.parser")
        config = SITE_CONFIGS[site_name]
        cards = soup.select(config["card_selector"])
        print(f"[{site_name}] Found {len(cards)} raw HTML item cards.")
        
        dropped_noprice = 0
        dropped_sold = 0
        dropped_notitle = 0
        
        for card in cards:
            # Bulletproof cleanup to handle weird web formatting spaces
            txt = card.get_text(separator=" ", strip=True)
            txt_clean = re.sub(r'\s+', ' ', txt)
            
            title_node = card if site_name == "TacSwap" else card.select_one(config["title_selector"])
            if not title_node:
                dropped_notitle += 1
                continue
                
            price_val = 0.0
            
            # Aggressive Price Regex: Looks for a dollar sign, ignores spaces, and captures the numbers/decimals
            price_node = card.select_one(config["price_selector"])
            search_text = price_node.get_text(separator=" ", strip=True) if price_node else txt_clean
            
            match = re.search(r'\$\s?([0-9,]+(?:\.[0-9]{1,2})?)', search_text)
            if match:
                price_val = float(match.group(1).replace(",", ""))
                
            if price_val <= 0.0:
                dropped_noprice += 1
                continue
                
            href = title_node.get("href", "")
            link = f"{config['url_prefix']}{href}" if href.startswith("/") else href
            
            # Prevent empty titles if TacSwap card was just a picture
            title_str = title_node.get_text(strip=True) if site_name != "TacSwap" else txt_clean[:60]
            if not title_str:
                title_str = "Unknown Listing"
            
            lot = calculate_margins(site_name, title_str, price_val, link, txt_clean)
            if lot: 
                lots.append(lot)
            else:
                dropped_sold += 1
                
        print(f"[{site_name}] Results: Kept {len(lots)} | Dropped (No Price): {dropped_noprice} | Dropped (Sold/Ended): {dropped_sold} | Dropped (No Title): {dropped_notitle}")
    return lots

def live_scrape_all_platforms():
    lots = []
    tasks = [
        {"site": "GunBroker", "url": "https://www.gunbroker.com/Pistols/search?Sort=13&PageSize=48", "js": False},
        {"site": "Guns.com", "url": "https://www.guns.com/firearms/handguns?condition=used", "js": True},
        {"site": "Armslist", "url": "https://www.armslist.com/classifieds/search?category=handguns", "js": False}
    ]
    
    with ThreadPoolExecutor(max_workers=3) as executor:
        future_to_task = {executor.submit(scrape_target, t["site"], t["url"], t["js"]): t["site"] for t in tasks}
        for future in as_completed(future_to_task):
            try:
                result_lots = future.result()
                if result_lots:
                    lots.extend(result_lots)
            except Exception as e:
                print(f"Exception: {e}")
                
    return lots

def main():
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Starting Strict Live Scrape...")
    live_items = live_scrape_all_platforms()

    unique_map = {}
    for item in live_items:
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

    with open(FEED_FILE, "w") as f:
        json.dump(feed_payload, f, indent=2)

    print(f"SUCCESS: feed_data.json updated with {len(valid_lots)} listings.\n")

if __name__ == "__main__":
    main()
