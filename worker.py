import os
import re
import json
import urllib.parse
from datetime import datetime
import requests
from bs4 import BeautifulSoup

FEED_FILE = "feed_data.json"
# Requires SCRAPER_API_KEY environment variable set in Render
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
    "colt king cobra": {"gb_sold": 820.0, "gc_retail": 890.0, "ga_comp": 850.0},
    "colt 1911": {"gb_sold": 1050.0, "gc_retail": 1150.0, "ga_comp": 1100.0},
    "colt ar-15": {"gb_sold": 1350.0, "gc_retail": 1450.0, "ga_comp": 1400.0},
    "glock 19": {"gb_sold": 510.0, "gc_retail": 550.0, "ga_comp": 530.0},
    "glock 17": {"gb_sold": 495.0, "gc_retail": 535.0, "ga_comp": 515.0},
    "glock 43": {"gb_sold": 435.0, "gc_retail": 475.0, "ga_comp": 450.0},
    "glock 22": {"gb_sold": 340.0, "gc_retail": 380.0, "ga_comp": 360.0},
    "glock": {"gb_sold": 470.0, "gc_retail": 510.0, "ga_comp": 490.0},
    "smith & wesson 686": {"gb_sold": 850.0, "gc_retail": 910.0, "ga_comp": 880.0},
    "smith & wesson 629": {"gb_sold": 940.0, "gc_retail": 1020.0, "ga_comp": 980.0},
    "smith & wesson shield": {"gb_sold": 395.0, "gc_retail": 440.0, "ga_comp": 415.0},
    "smith & wesson m&p": {"gb_sold": 440.0, "gc_retail": 495.0, "ga_comp": 465.0},
    "smith & wesson": {"gb_sold": 590.0, "gc_retail": 650.0, "ga_comp": 620.0},
    "sig sauer p226": {"gb_sold": 890.0, "gc_retail": 960.0, "ga_comp": 925.0},
    "sig sauer p365": {"gb_sold": 520.0, "gc_retail": 570.0, "ga_comp": 545.0},
    "sig sauer p320": {"gb_sold": 500.0, "gc_retail": 555.0, "ga_comp": 530.0},
    "sig sauer": {"gb_sold": 650.0, "gc_retail": 710.0, "ga_comp": 680.0},
    "ruger 10/22": {"gb_sold": 275.0, "gc_retail": 310.0, "ga_comp": 290.0},
    "ruger gp100": {"gb_sold": 690.0, "gc_retail": 750.0, "ga_comp": 720.0},
    "ruger": {"gb_sold": 450.0, "gc_retail": 510.0, "ga_comp": 480.0},
    "remington 870": {"gb_sold": 420.0, "gc_retail": 475.0, "ga_comp": 445.0},
    "mossberg 500": {"gb_sold": 350.0, "gc_retail": 400.0, "ga_comp": 380.0},
    "mossberg 590": {"gb_sold": 510.0, "gc_retail": 565.0, "ga_comp": 535.0},
    "beretta 92": {"gb_sold": 590.0, "gc_retail": 650.0, "ga_comp": 620.0},
    "cz 75": {"gb_sold": 680.0, "gc_retail": 750.0, "ga_comp": 715.0},
    "browning citori": {"gb_sold": 1580.0, "gc_retail": 1720.0, "ga_comp": 1650.0},
    "winchester 94": {"gb_sold": 740.0, "gc_retail": 820.0, "ga_comp": 780.0},
    "marlin 1895": {"gb_sold": 1050.0, "gc_retail": 1160.0, "ga_comp": 1100.0},
    "springfield 1911": {"gb_sold": 790.0, "gc_retail": 860.0, "ga_comp": 820.0}
}

PRE_BAN_TRIGGERS = ["pre-ban", "pre ban", "pre-94", "pre 94", "sporter match", "green label", "blue label sporter", "mak-90"]

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
    matched_model = "Firearm"
    v_dict = {"gb_sold": 520.0, "gc_retail": 580.0, "ga_comp": 550.0}

    for key, val_sources in MULTI_SOURCE_VALUATIONS.items():
        if key in t_lower:
            parts = key.split(" ", 1)
            matched_make = parts[0]
            matched_model = parts[1] if len(parts) > 1 else "Various"
            v_dict = val_sources
            break

    if matched_make == "General":
        for m in ["colt", "glock", "smith & wesson", "s&w", "sig sauer", "ruger", "remington", "mossberg", "beretta", "browning", "cz", "springfield"]:
            if m in t_lower:
                matched_make = m
                matched_model = re.sub(r'[^a-zA-Z0-9\s]', '', t_lower.replace(m, "")).strip()[:15]
                v_dict = {"gb_sold": 550.0, "gc_retail": 610.0, "ga_comp": 580.0}
                break

    val_average = round((v_dict["gb_sold"] + v_dict["gc_retail"] + v_dict["ga_comp"]) / 3.0, 2)
    badge = "🔥 Pre-Ban Grandfathered" if is_pre else "Commercial Roster"
    return matched_make, matched_model, v_dict, val_average, is_pre, badge

def calculate_margins(src, title, ask_price, url, status_text="Active"):
    url_lower = url.lower()
    valid_signatures = {
        "GunBroker": "/item/",
        "HiBid": "/lot/",
        "Buds Gun Shop": "products_id",
        "Sportsman's Outdoor Superstore": "/products.cfm/id/",
        "Guns.com": "/item/",
        "GunsAmerica": "/listing/",
        "Armslist": "/posts/",
        "Tacswap": "/post/",
        "UsedGuns.com": "/listing/"
    }
    
    sig = valid_signatures.get(src)
    if sig and sig not in url_lower:
        return None
    if is_sold_or_ended(title) or is_sold_or_ended(status_text) or is_sold_or_ended(url_lower):
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

def fetch_html(target_url: str, render_js: bool = False) -> str:
    """Routes requests directly through ScraperAPI proxy gateway to bypass Cloudflare/Akamai."""
    try:
        if not SCRAPER_API_KEY:
            print("WARNING: SCRAPER_API_KEY environment variable is not set. Requests may be blocked.")
            return ""
        
        payload = {
            "api_key": SCRAPER_API_KEY,
            "url": target_url,
            "render": "true" if render_js else "false"
        }
        proxy_url = f"http://api.scraperapi.com?{urllib.parse.urlencode(payload)}"
        resp = requests.get(proxy_url, timeout=25)
        if resp.status_code == 200:
            return resp.text
    except Exception as e:
        print(f"Proxy fetch error for {target_url}: {e}")
    return ""

def live_scrape_all_platforms():
    """Extracts listings using ScraperAPI proxy routing across key firearm searches."""
    lots = []
    keywords = ["glock", "colt", "smith+wesson", "sig+sauer", "ruger", "remington", "mossberg", "beretta", "cz", "springfield", "winchester", "marlin"]

    print("Fetching GunBroker via ScraperAPI proxy...")
    for kw in keywords:
        html = fetch_html(f"https://www.gunbroker.com/All/search?Keywords={kw}&Sort=1&PageSize=48&Tab=1")
        if html:
            soup = BeautifulSoup(html, "html.parser")
            for card in soup.select(".listing, .tile, .item-tile, .row.item-row"):
                txt = card.get_text()
                title_node = card.select_one(".title a, .item-title, h3 a")
                price_node = card.select_one(".price, .bid-price, .current-bid")
                if title_node and price_node:
                    href = title_node.get("href", "")
                    link = f"https://www.gunbroker.com{href}" if href.startswith("/") else href
                    match = re.search(r'\$?([\d,]+\.?\d*)', price_node.get_text())
                    if match:
                        lot = calculate_margins("GunBroker", title_node.get_text(strip=True), float(match.group(1).replace(",", "")), link, txt)
                        if lot: lots.append(lot)

    print("Fetching Guns.com via ScraperAPI (JS render enabled)...")
    for cat in ["handguns", "rifles", "shotguns"]:
        html = fetch_html(f"https://www.guns.com/firearms/{cat}?condition=used&inStock=true", render_js=True)
        if html:
            soup = BeautifulSoup(html, "html.parser")
            for card in soup.select(".productCard, .product-card, .productItem"):
                txt = card.get_text()
                title_node = card.select_one(".productCard__title a, a.product-title, h3 a")
                price_node = card.select_one(".productCard__price, .price")
                if title_node and price_node:
                    href = title_node.get("href", "")
                    link = f"https://www.guns.com{href}" if href.startswith("/") else href
                    match = re.search(r'\$?([\d,]+\.?\d*)', price_node.get_text())
                    if match:
                        lot = calculate_margins("Guns.com", title_node.get_text(strip=True), float(match.group(1).replace(",", "")), link, txt)
                        if lot: lots.append(lot)

    print("Fetching GunsAmerica via ScraperAPI proxy...")
    for kw in keywords[:5]:
        html = fetch_html(f"https://www.gunsamerica.com/Search.aspx?T={kw}")
        if html:
            soup = BeautifulSoup(html, "html.parser")
            for row in soup.select(".listing-item, .search-result-item, .item-container"):
                txt = row.get_text()
                title_node = row.select_one(".title a, h2 a, a.listing-title")
                price_node = row.select_one(".price, .price-field, .amount")
                if title_node and price_node:
                    href = title_node.get("href", "")
                    link = f"https://www.gunsamerica.com{href}" if href.startswith("/") else href
                    match = re.search(r'\$?([\d,]+\.?\d*)', price_node.get_text())
                    if match:
                        lot = calculate_margins("GunsAmerica", title_node.get_text(strip=True), float(match.group(1).replace(",", "")), link, txt)
                        if lot: lots.append(lot)

    return lots

def main():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Commencing ScraperAPI-backed organic scrape...")
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

    print(f"SUCCESS: Extracted {len(valid_lots)} listings through ScraperAPI gateway.")

if __name__ == "__main__":
    main()
