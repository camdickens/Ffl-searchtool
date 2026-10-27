import streamlit as st
import pandas as pd
import json
import os
import re
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import requests
from bs4 import BeautifulSoup

st.set_page_config(page_title="FFL Deal Radar", page_icon="🎯", layout="wide")

FEED_FILE = "feed_data.json"
DEALER_FILE = "registered_dealers.json"
SEEN_FILE = "seen_lots.json"
STRIPE_URL = "https://buy.stripe.com/test_replace_with_your_link"
PRO_KEY = "DEALER2026"
CRON_TOKEN = "DEALER2026"

def get_feed():
    if os.path.exists(FEED_FILE):
        try:
            with open(FEED_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "last_updated": datetime.now().strftime("%Y-%m-%d %I:%M %p"),
        "lots": [
            {
                "lot_id": "GB-101",
                "source_site": "GunBroker",
                "title": "Colt AR-15 Sporter Match HBAR 5.56 (Pre-1994)",
                "make": "colt",
                "model": "ar-15",
                "current_bid": 720.0,
                "total_landed_cost": 806.6,
                "federal_retail": 1150.0,
                "federal_profit": 343.4,
                "federal_margin": 29.9,
                "actionable_federal": True,
                "ma_retail": 1897.5,
                "ma_profit": 1090.9,
                "ma_margin": 57.5,
                "actionable_ma": True,
                "max_bid": 1400.0,
                "is_pre_ban": True,
                "compliance_badge": "🔥 Pre-Ban Grandfathered",
                "listing_url": "https://www.gunbroker.com"
            },
            {
                "lot_id": "HB-202",
                "source_site": "HiBid",
                "title": "Smith & Wesson Model 19-3 .357 (1974 C&R)",
                "make": "smith & wesson",
                "model": "model 19",
                "current_bid": 340.0,
                "total_landed_cost": 456.2,
                "federal_retail": 850.0,
                "federal_profit": 393.8,
                "federal_margin": 46.3,
                "actionable_federal": True,
                "ma_retail": 850.0,
                "ma_profit": 393.8,
                "ma_margin": 46.3,
                "actionable_ma": True,
                "max_bid": 546.6,
                "is_pre_ban": False,
                "compliance_badge": "🏛️ C&R 50-Year Exempt",
                "listing_url": "https://hibid.com"
            },
            {
                "lot_id": "AL-303",
                "source_site": "Armslist",
                "title": "Remington 870 Wingmaster 12 Gauge",
                "make": "remington",
                "model": "870",
                "current_bid": 180.0,
                "total_landed_cost": 245.0,
                "federal_retail": 375.0,
                "federal_profit": 130.0,
                "federal_margin": 34.7,
                "actionable_federal": True,
                "ma_retail": 375.0,
                "ma_profit": 130.0,
                "ma_margin": 34.7,
                "actionable_ma": True,
                "max_bid": 210.0,
                "is_pre_ban": False,
                "compliance_badge": "Federal Title 1",
                "listing_url": "https://www.armslist.com"
            },
            {
                "lot_id": "GB-404",
                "source_site": "GunBroker",
                "title": "Glock 19 Gen 5 9mm (Used)",
                "make": "glock",
                "model": "19",
                "current_bid": 410.0,
                "total_landed_cost": 477.3,
                "federal_retail": 520.0,
                "federal_profit": 42.7,
                "federal_margin": 8.2,
                "actionable_federal": False,
                "ma_retail": 695.0,
                "ma_profit": 217.7,
                "ma_margin": 31.3,
                "actionable_ma": True,
                "max_bid": 415.2,
                "is_pre_ban": False,
                "compliance_badge": "⚠️ Frame Transfer Only",
                "listing_url": "https://www.gunbroker.com"
            }
        ]
    }

def save_feed(data):
    with open(FEED_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_dealers():
    if os.path.exists(DEALER_FILE):
        try:
            with open(DEALER_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return []

def save_dealer(profile):
    dealers = get_dealers()
    for i, d in enumerate(dealers):
        if d.get("email") == profile.get("email"):
            dealers[i] = profile
            with open(DEALER_FILE, "w") as f:
                json.dump(dealers, f, indent=2)
            return
    dealers.append(profile)
    with open(DEALER_FILE, "w") as f:
        json.dump(dealers, f, indent=2)

def get_seen_lots():
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, "r") as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()

def save_seen_lots(seen_set):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen_set), f)

def get_smtp_config():
    u = os.environ.get("SMTP_USER") or st.secrets.get("SMTP_USER", "")
    p = os.environ.get("SMTP_PASSWORD") or st.secrets.get("SMTP_PASSWORD", "")
    s = os.environ.get("SMTP_SERVER") or st.secrets.get("SMTP_SERVER", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT") or st.secrets.get("SMTP_PORT", 587))
    return u, p, s, port

def send_email_alert(to_email, subject, html_content):
    user, pw, server, port = get_smtp_config()
    if not (user and pw):
        return False, "SMTP credentials missing from secrets."
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = user
        msg["To"] = to_email
        msg.attach(MIMEText(html_content, "html"))
        with smtplib.SMTP(server, port) as s:
            s.starttls()
            s.login(user, pw)
            s.sendmail(user, to_email, msg.as_string())
        return True, "Email sent successfully."
    except Exception as e:
        return False, str(e)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

def parse_price(text):
    if not text:
        return 0.0
    match = re.search(r"\$([\d,]+\.?\d*)", str(text))
    if match:
        return float(match.group(1).replace(",", ""))
    return 0.0

def scrape_gunbroker_live():
    lots = []
    try:
        url = "https://www.gunbroker.com/All/search?Keywords=firearms&PageSize=48&Sort=13"
        res = requests.get(url, headers=HEADERS, timeout=8)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            for item in soup.select("div.tile"):
                t_elem = item.select_one("a.title")
                p_elem = item.select_one("span.price")
                if t_elem and p_elem:
                    t = t_elem.get_text(strip=True)
                    p = parse_price(p_elem.get_text(strip=True))
                    href = t_elem.get("href", "")
                    link = href if href.startswith("http") else f"https://www.gunbroker.com{href}"
                    l_id = f"GB-{abs(hash(link)) % 100000}"
                    lots.append({
                        "lot_id": l_id,
                        "source_site": "GunBroker",
                        "title": t,
                        "current_bid": p,
                        "listing_url": link
                    })
    except Exception:
        pass
    return lots

def scrape_hibid_live():
    lots = []
    try:
        url = "https://hibid.com/lots?q=firearms"
        res = requests.get(url, headers=HEADERS, timeout=8)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            for item in soup.select("div.lot-tile, tr.lot-row"):
                t_elem = item.select_one("a.lot-title, h2.lot-title a")
                p_elem = item.select_one(".lot-bid-current, .price-text")
                if t_elem:
                    t = t_elem.get_text(strip=True)
                    p = parse_price(p_elem.get_text(strip=True)) if p_elem else 100.0
                    href = t_elem.get("href", "")
                    link = href if href.startswith("http") else f"https://hibid.com{href}"
                    l_id = f"HB-{abs(hash(link)) % 100000}"
                    lots.append({
                        "lot_id": l_id,
                        "source_site": "HiBid",
                        "title": t,
                        "current_bid": p,
                        "listing_url": link
                    })
    except Exception:
        pass
    return lots

def scrape_armslist_live():
    lots = []
    try:
        url = "https://www.armslist.com/classifieds/massachusetts/guns"
        res = requests.get(url, headers=HEADERS, timeout=8)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            for post in soup.select("div.classified-item, .post-item"):
                link_elem = post.select_one("a")
                t_elem = post.select_one(".title, h3")
                p_elem = post.select_one(".price")
                if link_elem and t_elem:
                    t = t_elem.get_text(strip=True)
                    p = parse_price(p_elem.get_text(strip=True)) if p_elem else 250.0
                    href = link_elem.get("href", "")
                    link = href if href.startswith("http") else f"https://www.armslist.com{href}"
                    l_id = f"AL-{abs(hash(link)) % 100000}"
                    lots.append({
                        "lot_id": l_id,
                        "source_site": "Armslist",
                        "title": t,
                        "current_bid": p,
                        "listing_url": link
                    })
    except Exception:
        pass
    return lots

def analyze_lot(raw):
    title = raw.get("title", "")
    t_lower = title.lower()
    bid = float(raw.get("current_bid", 0.0))
    source = raw.get("source_site", "Direct")

    premium = 0.18 if source == "HiBid" else 0.05
    shipping = 40.0
    transfer_fee = 25.0
    landed = round((bid * (1.0 + premium)) + shipping + transfer_fee, 2)

    pre_ban_terms = ["preban", "pre-ban", "pre ban", "sporter match", "blue label", "1993", "1992", "1990", "1989"]
    is_pre_ban = any(w in t_lower for w in pre_ban_terms)
    cr_terms = ["c&r", "curio", "relic", "194", "195", "196", "1970", "1971", "1972", "1973", "1974", "1975"]
    is_cr = any(w in t_lower for w in cr_terms)

    fed_est = max(bid * 1.35, landed + 100.0)
    ma_mult = 1.65 if is_pre_ban else (1.20 if is_cr else 1.15)
    ma_est = fed_est * ma_mult

    fed_profit = round(fed_est - landed, 2)
    ma_profit = round(ma_est - landed, 2)
    fed_margin = round((fed_profit / fed_est) * 100, 1) if fed_est > 0 else 0.0
    ma_margin = round((ma_profit / ma_est))
