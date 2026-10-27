import os
import json
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import requests
from bs4 import BeautifulSoup

# -----------------------------------------------------------------------------
# 1. SETTINGS & CONFIGURATION
# -----------------------------------------------------------------------------
FEED_OUTPUT_FILE = "feed_data.json"
CACHE_SEEN_FILE = "seen_lots.json"
DEALER_DB_FILE = "registered_dealers.json"

SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")

CONFIG = {
    "DEFAULT_BUYERS_PREMIUM": 0.18,
    "SHIPPING_HANDGUN": 35.0,
    "SHIPPING_LONGGUN": 45.0,
    "CLEANING_RECONDITIONING": 20.0,
    "MA_PRE_BAN_MULTIPLIER": 1.65,
    "MA_OFF_ROSTER_PREMIUM": 175.0,
}

MAJOR_MANUFACTURERS = [
    "smith & wesson", "s&w", "colt", "glock", "ruger", "sig sauer", "sig",
    "beretta", "browning", "remington", "winchester", "mossberg", "springfield armory",
    "springfield", "cz", "heckler & koch", "h&k", "walther", "fn", "fn herstal",
    "marlin", "savage", "henry", "taurus", "canik", "kimber", "kel-tec", "dan wesson"
]

MA_ROSTER_WHITELIST = {
    "ruger": ["mark iv", "mark iii", "lcp", "security 9", "sp101", "gp100", "10/22"],
    "smith & wesson": ["m&p", "model 19", "model 686", "shield", "model 10", "model 66", "model 642", "model 29", "model 36", "bodyguard"],
    "sig sauer": ["p365", "p320", "p226", "p229"],
    "beretta": ["92fs", "80x", "tomcat", "bobcat"],
    "colt": ["python", "king cobra", "1911", "detective special"],
    "glock": [],  # Frame transfers required in MA
}

PRE_BAN_PATTERNS = [
    r"pre[\s\-_]?ban",
    r"pre[\s\-_]?1994",
    r"manufactured\s+19[0-8][0-9]",
    r"colt\s+ar-15",
    r"norinco",
    r"polytech",
    r"daewoo",
]

TGV_BENCHMARK_CACHE = {
    ("smith & wesson", "model 19"): 850.0,
    ("smith & wesson", "model 686"): 825.0,
    ("smith & wesson", "model 10"): 450.0,
    ("smith & wesson", "shield"): 420.0,
    ("smith & wesson", "m&p"): 480.0,
    ("colt", "ar-15"): 1150.0,
    ("colt", "python"): 1350.0,
    ("colt", "1911"): 950.0,
    ("glock", "19"): 520.0,
    ("glock", "17"): 520.0,
    ("glock", "43x"): 460.0,
    ("ruger", "security 9"): 340.0,
    ("ruger", "mark iv"): 450.0,
    ("ruger", "10/22"): 280.0,
    ("ruger", "gp100"): 650.0,
    ("sig sauer", "p365"): 450.0,
    ("sig sauer", "p320"): 480.0,
    ("beretta", "92fs"): 525.0,
    ("remington", "870"): 375.0,
    ("mossberg", "500"): 340.0,
    ("winchester", "model 94"): 750.0,
    ("browning", "buck mark"): 380.0,
    ("springfield armory", "1911"): 720.0,
}

SESSION_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/",
}

# -----------------------------------------------------------------------------
# 2. PARSING & COMPLIANCE LOGIC
# -----------------------------------------------------------------------------
def parse_firearm_details(title: str):
    clean_title = title.lower()
    detected_make = "Unknown"
    for m in MAJOR_MANUFACTURERS:
        if re.search(rf"\b{re.escape(m)}\b", clean_title):
            detected_make = m
            break

    detected_model = "Firearm"
    benchmark_val = 400.0

    for (make, model), baseline in TGV_BENCHMARK_CACHE.items():
        if (detected_make == make or detected_make in make) and model in clean_title:
            detected_model = model
            benchmark_val = baseline
            break

    is_handgun = not any(w in clean_title for w in ["rifle", "shotgun", "carbine", "12ga", "20ga", "hbar", "bolt", "lever"])
    return detected_make, detected_model, benchmark_val, is_handgun

def check_ma_compliance(make: str, model: str, title: str) -> tuple[bool, bool, bool]:
    text = f"{make} {model} {title}".lower()
    is_pre_ban = any(re.search(p, text) for p in PRE_BAN_PATTERNS)
    
    match = re.search(r"\b(19[0-7][0-9]|18[0-9]{2})\b", text)
    is_cr = bool(match and (datetime.now().year - int(match.group(1)) >= 50))

    ma_roster = False
    make_clean = make.lower()
    if make_clean in MA_ROSTER_WHITELIST:
        if any(appr in model.lower() for appr in MA_ROSTER_WHITELIST[make_clean]):
            ma_roster = True
    if is_pre_ban or is_cr:
        ma_roster = True
    return is_pre_ban, is_cr, ma_roster

# -----------------------------------------------------------------------------
# 3. LIVE SCRAPERS WITH ABSOLUTE DIRECT URL NORMALIZATION
# -----------------------------------------------------------------------------
def scrape_gunbroker() -> list[dict]:
    lots = []
    url = "https://www.gunbroker.com/All/search?Keywords=firearms&Sort=1&PageSize=48"
    try:
        r = requests.get(url, headers=SESSION_HEADERS, timeout=10)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            items = soup.select(".tile.tile--item, .item-tile, .gl-item")
            for it in items:
                t_el = it.select_one(".gl-item-title a, .title a, a[href*='/item/']")
                b_el = it.select_one(".gl-item-bid, .price, .bid-amount")
                if not t_el or not b_el:
                    continue
                title = t_el.get_text(strip=True)
                href = t_el.get("href", "")
                
                # Assemble direct lot link
                if href.startswith("http"):
                    link = href
                elif href.startswith("/"):
                    link = f"https://www.gunbroker.com{href}"
                else:
                    link = f"https://www.gunbroker.com/{href}"

                raw_bid = re.sub(r"[^\d.]", "", b_el.get_text(strip=True))
                bid = float(raw_bid) if raw_bid else 0.0
                if bid > 10.0:
                    id_match = re.search(r"/item/(\d+)", link)
                    lot_id = f"GB-{id_match.group(1)}" if id_match else f"GB-{abs(hash(link)) % 100000}"
                    lots.append({"lot_id": lot_id, "source": "GunBroker", "title": title, "bid": bid, "bp": 0.03, "url": link})
    except Exception as e:
        print(f"[GunBroker Scrape Error] {e}")
    return lots

def scrape_hibid() -> list[dict]:
    lots = []
    url = "https://hibid.com/lots?q=firearms"
    try:
        r = requests.get(url, headers=SESSION_HEADERS, timeout=10)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            cards = soup.select(".lot-tile, .lot-list-
