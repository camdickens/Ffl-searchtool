import streamlit as st
import pandas as pd
import json
import os
import subprocess
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

st.set_page_config(page_title="FFL Deal Radar", page_icon="🎯", layout="wide")

FEED_FILE = "feed_data.json"
DEALER_FILE = "registered_dealers.json"
STRIPE_URL = "https://buy.stripe.com/test_replace_with_your_link"
PRO_KEY = "DEALER2026"
CRON_TOKEN = "DEALER2026"

# 1. HEADLESS BACKGROUND HOOK (OPTION 3)
params = st.query_params
if params.get("task") == "scrape" and params.get("token") == CRON_TOKEN:
    proc = subprocess.run(["python", "worker.py"], capture_output=True, text=True)
    st.write(f"CRON_OK: Worker executed. Output: {proc.stdout} Errors: {proc.stderr}")
    st.stop()

# 2. DATA LOADERS
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
            {"lot_id": "GB-101", "source_site": "GunBroker", "title": "Colt AR-15 Sporter Match HBAR 5.56 (Pre-1994)", "make": "colt", "model": "ar-15", "current_bid": 720.0, "total_landed_cost": 806.6, "federal_retail": 1150.0, "federal_profit": 343.4, "federal_margin": 29.9, "actionable_federal": True, "ma_retail": 1897.5, "ma_profit": 1090.9, "ma_margin": 57.5, "actionable_ma": True, "max_bid": 1400.0, "is_pre_ban": True, "compliance_badge": "🔥 Pre-Ban Grandfathered", "listing_url": "https://www.gunbroker.com"},
            {"lot_id": "HB-202", "source_site": "HiBid", "title": "Smith & Wesson Model 19-3 .357 (1974 C&R)", "make": "smith & wesson", "model": "model 19", "current_bid": 340.0, "total_landed_cost": 456.2, "federal_retail": 850.0, "federal_profit": 393.8, "federal_margin": 46.3, "actionable_federal": True, "ma_retail": 850.0, "ma_profit": 393.8, "ma_margin": 46.3, "actionable_ma": True, "max_bid": 546.6, "is_pre_ban": False, "compliance_badge": "🏛️ C&R 50-Year Exempt", "listing_url": "https://hibid.com"},
            {"lot_id": "AL-303", "source_site": "Armslist", "title": "Remington 870 Wingmaster 12 Gauge", "make": "remington", "model": "870", "current_bid": 180.0, "total_landed_cost": 245.0, "federal_retail": 375.0, "federal_profit": 130.0, "federal_margin": 34.7, "actionable_federal": True, "ma_retail": 375.0, "ma_profit": 130.0, "ma_margin": 3
