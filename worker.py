import os
import json
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from twilio.rest import Client

# -----------------------------------------------------------------------------
# 1. SETTINGS & DUAL-MODE CONFIGURATION
# -----------------------------------------------------------------------------
FEED_OUTPUT_FILE = "feed_data.json"
CACHE_SEEN_FILE = "seen_lots.json"
DEALER_DB_FILE = "registered_dealers.json"

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER", "")

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

# Universal Manufacturer Directory for Dynamic Extraction
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

# Baseline Valuation Index (Expands dynamically)
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
# 2. UNIVERSAL PARSER & VALUATION ENGINE
# -----------------------------------------------------------------------------
def parse_firearm_details(title: str):
    clean_title = title.lower()
    detected_make = "Unknown"
    for m in MAJOR_MANUFACTURERS:
        if re.search(rf"\b{re.escape(m)}\b", clean_title):
            detected_make = m
            break

    detected_model = "Firearm"
    benchmark_val = 400.0  # Base fallback estimate if unique/unindexed

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
    
    # 50-Year C&R Rule
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
# 3. LIVE SCRAPERS (GUNBROKER, HIBID, ARMSLIST)
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
                link = href if href.startswith("http") else f"https://www.gunbroker.com{href}"
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
            cards = soup.select(".lot-tile, .lot-list-item, div[id*='lot-']")
            for c in cards:
                t_el = c.select_one(".lot-title a, h2 a, a[href*='/lot/']")
                b_el = c.select_one(".current-bid-amount, .lead.price")
                if not t_el or not b_el:
                    continue
                title = t_el.get_text(strip=True)
                href = t_el.get("href", "")
                link = href if href.startswith("http") else f"https://hibid.com{href}"
                raw_bid = re.sub(r"[^\d.]", "", b_el.get_text(strip=True))
                bid = float(raw_bid) if raw_bid else 0.0
                if bid > 10.0:
                    id_match = re.search(r"/lot/(\d+)", link)
                    lot_id = f"HB-{id_match.group(1)}" if id_match else f"HB-{abs(hash(link)) % 100000}"
                    lots.append({"lot_id": lot_id, "source": "HiBid", "title": title, "bid": bid, "bp": 0.18, "url": link})
    except Exception as e:
        print(f"[HiBid Scrape Error] {e}")
    return lots

def scrape_armslist() -> list[dict]:
    lots = []
    # Query Armslist categorized feeds
    url = "https://www.armslist.com/classifieds/search?category=guns&posttype=7"
    try:
        r = requests.get(url, headers=SESSION_HEADERS, timeout=10)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            posts = soup.select(".classified-list-item, .post-container, .post-item")
            for p in posts:
                t_el = p.select_one("a[href*='/posts/']")
                b_el = p.select_one(".price, .post-price")
                if not t_el or not b_el:
                    continue
                title = t_el.get_text(strip=True)
                href = t_el.get("href", "")
                link = href if href.startswith("http") else f"https://www.armslist.com{href}"
                raw_bid = re.sub(r"[^\d.]", "", b_el.get_text(strip=True))
                bid = float(raw_bid) if raw_bid else 0.0
                if bid > 10.0:
                    id_match = re.search(r"/posts/(\d+)", link)
                    lot_id = f"AL-{id_match.group(1)}" if id_match else f"AL-{abs(hash(link)) % 100000}"
                    lots.append({"lot_id": lot_id, "source": "Armslist", "title": title, "bid": bid, "bp": 0.0, "url": link})
    except Exception as e:
        print(f"[Armslist Scrape Error] {e}")
    return lots

# -----------------------------------------------------------------------------
# 4. DISPATCHERS (SMS VIA TWILIO & EMAIL VIA SMTP)
# -----------------------------------------------------------------------------
def send_sms_alert(to_phone: str, deal: dict, mode: str):
    if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_PHONE_NUMBER):
        return
    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        retail_val = deal["ma_retail"] if mode == "MA" else deal["federal_retail"]
        profit_val = deal["ma_profit"] if mode == "MA" else deal["federal_profit"]
        margin_val = deal["ma_margin"] if mode == "MA" else deal["federal_margin"]

        body_text = (
            f"🎯 FFL RADAR ALERT [{mode} MODE]\n"
            f"{deal['title']}\n"
            f"Current: ${deal['current_bid']:.2f} | Landed: ${deal['total_landed_cost']:.2f}\n"
            f"Est. Resale: ${retail_val:.2f} | Spread: +${profit_val:.2f} ({margin_val:.1f}%)\n"
            f"Max Bid: ${deal['max_bid']:.2f}\n"
            f"Link: {deal['listing_url']}"
        )
        client.messages.create(body=body_text, from_=TWILIO_PHONE_NUMBER, to=to_phone)
        print(f"[SMS Sent] To {to_phone} for lot {deal['lot_id']}")
    except Exception as e:
        print(f"[Twilio SMS Error] {e}")

def send_email_alert(to_email: str, deal: dict, mode: str):
    if not (SMTP_USER and SMTP_PASSWORD):
        return
    try:
        retail_val = deal["ma_retail"] if mode == "MA" else deal["federal_retail"]
        profit_val = deal["ma_profit"] if mode == "MA" else deal["federal_profit"]
        margin_val = deal["ma_margin"] if mode == "MA" else deal["federal_margin"]

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"🎯 Buy Signal: {deal['make'].title()} {deal['model'].title()} (+${profit_val:.0f})"
        msg["From"] = f"FFL Deal Radar <{SMTP_USER}>"
        msg["To"] = to_email

        html = f"""
        <div style="font-family: Arial, sans-serif; background-color: #0d1117; color: #c9d1d9; padding: 20px; border-radius: 8px;">
            <h2 style="color: #58a6ff; margin-top: 0;">🎯 FFL Buy Signal Detected ({mode} Mode)</h2>
            <h3 style="color: #f0f6fc;">{deal['title']}</h3>
            <p><strong>Platform:</strong> {deal['source_site']} &nbsp;|&nbsp; <strong>Classification:</strong> {deal['compliance_badge']}</p>
            <div style="background-color: #161b22; padding: 15px; border-radius: 6px; margin: 15px 0;">
                <p><strong>Current Price:</strong> ${deal['current_bid']:.2f}</p>
                <p><strong>Total Landed Cost:</strong> ${deal['total_landed_cost']:.2f}</p>
                <p><strong>Target Valuation:</strong> ${retail_val:.2f}</p>
                <p style="font-size: 1.1rem; color: #3fb950;"><strong>Net Profit Spread:</strong> +${profit_val:.2f} ({margin_val:.1f}%)</p>
                <p><strong>Max Walk-Away Bid:</strong> ${deal['max_bid']:.2f}</p>
            </div>
            <a href="{deal['listing_url']}" style="background-color: #238636; color: white; padding: 10px 18px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">Open Listing Page ↗</a>
        </div>
        """
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, to_email, msg.as_string())
        print(f"[Email Sent] To {to_email} for lot {deal['lot_id']}")
    except Exception as e:
        print(f"[SMTP Email Error] {e}")

# -----------------------------------------------------------------------------
# 5. EXECUTION & PERSISTENCE
# -----------------------------------------------------------------------------
def run_cycle():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Hunting GunBroker, HiBid, and Armslist...")
    raw_lots = scrape_gunbroker() + scrape_hibid() + scrape_armslist()
    print(f"Ingested {len(raw_lots)} total raw firearm lots.")

    dealers = []
    if os.path.exists(DEALER_DB_FILE):
        try:
            with open(DEALER_DB_FILE, "r") as f:
                dealers = json.load(f)
        except Exception:
            dealers = []

    seen = {}
    if os.path.exists(CACHE_SEEN_FILE):
        try:
            with open(CACHE_SEEN_FILE, "r") as f:
                seen = json.load(f)
        except Exception:
            seen = {}

    processed = []

    for item in raw_lots:
        make, model, nat_val, is_handgun = parse_firearm_details(item["title"])
        shipping = CONFIG["SHIPPING_HANDGUN"] if is_handgun else CONFIG["SHIPPING_LONGGUN"]
        overhead = shipping + CONFIG["CLEANING_RECONDITIONING"]
        landed = item["bid"] + (item["bid"] * item["bp"]) + overhead

        # 1. Federal Standard Evaluation
        fed_retail = nat_val
        fed_profit = fed_retail - landed
        fed_margin = (fed_profit / fed_retail * 100) if fed_retail > 0 else 0.0

        # 2. Massachusetts Evaluation
        pre_ban, cr, roster = check_ma_compliance(make, model, item["title"])
        ma_retail = nat_val * CONFIG["MA_PRE_BAN_MULTIPLIER"] if pre_ban else (
            nat_val + CONFIG["MA_OFF_ROSTER_PREMIUM"] if not roster and is_handgun else nat_val
        )
        ma_profit = ma_retail - landed
        ma_margin = (ma_profit / ma_retail * 100) if ma_retail > 0 else 0.0

        # Ceiling calculation
        max_bid = max(0.0, (ma_retail - 150.0 - overhead) / (1 + item["bp"]))
        actionable_fed = (fed_profit >= 100.0 and fed_margin >= 20.0)
        actionable_ma = (ma_profit >= 150.0 and ma_margin >= 30.0)

        badge_parts = []
        if pre_ban: badge_parts.append("🔥 Pre-Ban")
        if cr: badge_parts.append("🏛️ C&R Exempt")
        if roster and not pre_ban and not cr: badge_parts.append("✅ MA Roster")
        if not roster and is_handgun: badge_parts.append("⚠️ Frame Transfer Only")

        record = {
            "lot_id": item["lot_id"],
            "source_site": item["source"],
            "title": item["title"],
            "make": make,
            "model": model,
            "current_bid": round(item["bid"], 2),
            "total_landed_cost": round(landed, 2),
            "federal_retail": round(fed_retail, 2),
            "federal_profit": round(fed_profit, 2),
            "federal_margin": round(fed_margin, 1),
            "actionable_federal": actionable_fed,
            "ma_retail": round(ma_retail, 2),
            "ma_profit": round(ma_profit, 2),
            "ma_margin": round(ma_margin, 1),
            "actionable_ma": actionable_ma,
            "max_bid": round(max_bid, 2),
            "is_pre_ban": pre_ban,
            "is_curio_relic": cr,
            "ma_roster_compliant": roster,
            "compliance_badge": " • ".join(badge_parts) if badge_parts else "Federal Title 1 Standard",
            "listing_url": item["url"],
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        processed.append(record)

        # Dispatch alerts to registered dealers if newly discovered
        if item["lot_id"] not in seen or seen[item["lot_id"]] > item["bid"]:
            for d in dealers:
                dealer_mode = d.get("operating_mode", "Federal")
                threshold = float(d.get("min_profit_threshold", 150.0))
                
                is_eligible = (record["ma_profit"] >= threshold and record["actionable_ma"]) if dealer_mode == "Massachusetts" else (
                    record["federal_profit"] >= threshold and record["actionable_federal"]
                )

                if is_eligible:
                    if d.get("enable_sms") and d.get("phone"):
                        send_sms_alert(d["phone"], record, dealer_mode)
                    if d.get("enable_email") and d.get("email"):
                        send_email_alert(d["email"], record, dealer_mode)

            seen[item["lot_id"]] = item["bid"]

    if processed:
        out = {
            "last_updated": datetime.now().strftime("%Y-%m-%d %I:%M:%S %p"),
            "lots": processed
        }
        with open(FEED_OUTPUT_FILE, "w") as f:
            json.dump(out, f, indent=2)
        with open(CACHE_SEEN_FILE, "w") as f:
            json.dump(seen, f, indent=2)
        print(f"Cycle finished. Processed {len(processed)} lots.")

if __name__ == "__main__":
    run_cycle()
