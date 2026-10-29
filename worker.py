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
    # COLT
    "colt python": {"gb_sold": 1420.0, "gc_retail": 1495.0, "ga_comp": 1450.0},
    "colt anaconda": {"gb_sold": 1350.0, "gc_retail": 1425.0, "ga_comp": 1380.0},
    "colt king cobra": {"gb_sold": 820.0, "gc_retail": 890.0, "ga_comp": 850.0},
    "colt 1911": {"gb_sold": 1050.0, "gc_retail": 1150.0, "ga_comp": 1100.0},
    "colt ar-15": {"gb_sold": 1350.0, "gc_retail": 1450.0, "ga_comp": 1400.0},
    "colt": {"gb_sold": 920.0, "gc_retail": 980.0, "ga_comp": 950.0},
    
    # GLOCK
    "glock 17": {"gb_sold": 495.0, "gc_retail": 535.0, "ga_comp": 515.0},
    "glock 19": {"gb_sold": 510.0, "gc_retail": 550.0, "ga_comp": 530.0},
    "glock 20": {"gb_sold": 560.0, "gc_retail": 615.0, "ga_comp": 585.0},
    "glock 43": {"gb_sold": 435.0, "gc_retail": 475.0, "ga_comp": 450.0},
    "glock 47": {"gb_sold": 550.0, "gc_retail": 600.0, "ga_comp": 575.0},
    "glock": {"gb_sold": 470.0, "gc_retail": 510.0, "ga_comp": 490.0},
    
    # SMITH & WESSON
    "smith & wesson 686": {"gb_sold": 850.0, "gc_retail": 910.0, "ga_comp": 880.0},
    "smith & wesson 629": {"gb_sold": 940.0, "gc_retail": 1020.0, "ga_comp": 980.0},
    "smith & wesson shield": {"gb_sold": 395.0, "gc_retail": 440.0, "ga_comp": 415.0},
    "smith & wesson m&p": {"gb_sold": 440.0, "gc_retail": 495.0, "ga_comp": 465.0},
    "smith & wesson": {"gb_sold": 590.0, "gc_retail": 650.0, "ga_comp": 620.0},
    
    # SIG SAUER
    "sig sauer p226": {"gb_sold": 890.0, "gc_retail": 960.0, "ga_comp": 925.0},
    "sig sauer p365": {"gb_sold": 520.0, "gc_retail": 570.0, "ga_comp": 545.0},
    "sig sauer p320": {"gb_sold": 500.0, "gc_retail": 555.0, "ga_comp": 530.0},
    "sig sauer": {"gb_sold": 650.0, "gc_retail": 710.0, "ga_comp": 680.0},
    
    # RUGER
    "ruger 10/22": {"gb_sold": 275.0, "gc_retail": 310.0, "ga_comp": 290.0},
    "ruger gp100": {"gb_sold": 690.0, "gc_retail": 750.0, "ga_comp": 720.0},
    "ruger": {"gb_sold": 450.0, "gc_retail": 510.0, "ga_comp": 480.0},

    # TAURUS, CANIK, KIMBER
    "taurus g2c": {"gb_sold": 190.0, "gc_retail": 240.0, "ga_comp": 210.0},
    "taurus judge": {"gb_sold": 410.0, "gc_retail": 480.0, "ga_comp": 445.0},
    "canik mete": {"gb_sold": 410.0, "gc_retail": 470.0, "ga_comp": 440.0},
    "kimber 1911": {"gb_sold": 780.0, "gc_retail": 890.0, "ga_comp": 835.0},

    # HECKLER & KOCH (HK)
    "hk mp5": {"gb_sold": 2800.0, "gc_retail": 3100.0, "ga_comp": 2950.0},
    "hk vp9": {"gb_sold": 590.0, "gc_retail": 650.0, "ga_comp": 620.0},
    
    # RIFLES & SHOTGUNS
    "tikka t3x": {"gb_sold": 720.0, "gc_retail": 810.0, "ga_comp": 765.0},
    "daniel defense ddm4": {"gb_sold": 1550.0, "gc_retail": 1750.0, "ga_comp": 1650.0},
    "psa pa-15": {"gb_sold": 410.0, "gc_retail": 490.0, "ga_comp": 450.0},
    "remington 870": {"gb_sold": 420.0, "gc_retail": 475.0, "ga_comp": 445.0},
    "mossberg 500": {"gb_sold": 350.0, "gc_retail": 400.0, "ga_comp": 380.0},
    "beretta 92": {"gb_sold": 590.0, "gc_retail": 650.0, "ga_comp": 620.0},
    "winchester 94": {"gb_sold": 740.0, "gc_retail": 820.0, "ga_comp": 780.0},
    "marlin 1895": {"gb_sold": 1050.0, "gc_retail": 1160.0, "ga_comp": 1100.0},
    "staccato p": {"gb_sold": 2250.0, "gc_retail": 2450.0, "ga_comp": 2350.0},
    "fn scar": {"gb_sold": 2950.0, "gc_retail": 3250.0, "ga_comp": 3100.0}
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
    v_dict = {"gb_sold": 0.0, "gc_retail": 0.0, "ga_comp": 0.0}

    for key, val_sources in MULTI_SOURCE_VALUATIONS.items():
        if key in t_lower:
            parts = key.split(" ", 1)
            matched_make = parts[0]
            matched_model = parts[1] if len(parts) > 1 else "Various"
            v_dict = val_sources
            break

    if matched_make == "General":
        brand_list = [
            "colt", "glock", "smith & wesson", "s&w", "sig sauer", "ruger", 
            "remington", "mossberg", "beretta", "browning", "cz", 
            "springfield", "hk", "taurus", "canik", "kimber", "staccato", "fn"
        ]
        for m in brand_list:
            if m in t_lower:
                matched_make = m
                matched_model = re.sub(r'[^a-zA-Z0-9\s]', '', t_lower.replace(m, "")).strip()[:15]
                v_dict = {"gb_sold": 550.0, "gc_retail": 610.0, "ga_comp": 580.0}
                break

    val_average = round((v_dict["gb_sold"] + v_dict["gc_retail"] + v_dict["ga_comp"]) / 3.0, 2)
    badge = "🔥 Pre-Ban Grandfathered" if is_pre else "Commercial Roster"
    return matched_make, matched_model, v_dict, val_average, is_pre, badge

def calculate_margins(src, title, ask_price, url, status_text="Active"):
    if is_sold_or_ended(title) or is_sold_or_ended(status_text) or is_sold_or_ended(url):
        return None

    make, model, val_sources, fed_avg, is_pre, badge = extract_multi_source_valuation(title)
    
    # STRICT INTERNAL FILTER: Discard if brand is completely unrecognized
    if make == "General":
        return None

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
            "gunbroker_past_sold": val_sources["gb_sold"],
            "guns_com_used_retail": val_sources["gc_retail"],
            "market_comp": val_sources["ga_comp"],
            "triangulated_avg": fed_avg
        },
        "federal_retail": fed_avg,
        "federal_profit": round(fed_avg - landed, 2),
        "federal_margin": round(((fed_avg - landed) / fed_avg) * 100, 1) if fed_avg > 0 else 0.0,
        "actionable_federal": bool((fed_avg - landed) >= 75.0),
        "ma_retail": ma_avg,
        "ma_profit": ma_profit,
        "ma_margin": ma_margin,
        "actionable_ma": bool(ma_profit >= 100.0),
        "max_bid": round(ma_avg * 0.70, 2),
        "is_pre_ban": is_pre,
        "compliance_badge": badge,
        "listing_url": url
    }

def fetch_html(target_url: str, render_js: bool, use_premium: bool = True) -> str:
    """Universal Fetcher routing via ScraperAPI."""
    try:
        if not SCRAPER_API_KEY:
            print("Missing API Key")
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
        else:
            print(f"ScraperAPI returned status {resp.status_code} for {target_url}")
    except Exception as e:
        print(f"Request timeout or error: {e}")
        
    return ""

def scrape_target(site_name, task_url, render_js):
    """Universal parser that applies the correct HTML extraction rules based on the site."""
    lots = []
    print(f"Executing parallel task for {site_name}...")
    html = fetch_html(task_url, render_js=render_js, use_premium=True)
    
    if html:
        print(f"\n--- HTML SNIPPET FOR {site_name} ---")
        print(html[:200])
        
        soup = BeautifulSoup(html, "html.parser")
        config = SITE_CONFIGS[site_name]
        
        cards = soup.select(config["card_selector"])
        print(f"Found {len(cards)} item cards on {site_name}")
        
        for card in cards:
            txt = card.get_text(separator=" ", strip=True)
            
            # Universal Title Extraction
            title_node = None
            if site_name == "TacSwap":
                title_node = card  # Tacswap links are the cards themselves
            else:
                title_node = card.select_one(config["title_selector"])
                
            # Universal Price Extraction (Regex fallback for sites that hide price classes)
            price_val = 0.0
            price_node = card.select_one(config["price_selector"])
            if price_node:
                match = re.search(r'\$?([\d,]+\.?\d*)', price_node.get_text())
                if match: price_val = float(match.group(1).replace(",", ""))
            else:
                # Fallback: scan the whole card text for the first dollar amount
                match = re.search(r'\$\s?([\d,]+\.?\d*)', txt)
                if match: price_val = float(match.group(1).replace(",", ""))

            if title_node and price_val > 0:
                href = title_node.get("href", "")
                link = f"{config['url_prefix']}{href}" if href.startswith("/") else href
                title_str = title_node.get_text(strip=True) if site_name != "TacSwap" else txt[:50]
                
                lot = calculate_margins(site_name, title_str, price_val, link, txt)
                if lot: 
                    lots.append(lot)
                    
        print(f"Filtered {site_name} down to {len(lots)} recognized firearms.\n")
    return lots

def live_scrape_all_platforms():
    lots = []
    
    # Master Dispatch List: Defines what to scrape and whether it requires JS rendering
    tasks = [
        {"site": "GunBroker", "url": "https://www.gunbroker.com/Pistols/search?Sort=13&PageSize=48", "js": False},
        {"site": "Guns.com", "url": "https://www.guns.com/firearms/handguns?condition=used", "js": True},
        {"site": "Armslist", "url": "https://www.armslist.com/classifieds/search?category=handguns", "js": False},
        {"site": "HiBid", "url": "https://hibid.com/lots?words=pistol", "js": True},
        {"site": "TacSwap", "url": "https://www.tacswap.com/category/pistols", "js": True}
    ]
    
    print("Launching Omni-Platform Scraper via ScraperAPI PREMIUM...")
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_task = {executor.submit(scrape_target, t["site"], t["url"], t["js"]): t["site"] for t in tasks}
        for future in as_completed(future_to_task):
            try:
                result_lots = future.result()
                if result_lots:
                    lots.extend(result_lots)
            except Exception as e:
                print(f"Parallel fetch generated an exception: {e}")
                
    return lots

def main():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Running Omni-Platform Sync (LIVE DATA ONLY)...")
    
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

    print(f"SUCCESS: Feed populated with {len(valid_lots)} recognized, cross-platform listings.")

if __name__ == "__main__":
    main()
