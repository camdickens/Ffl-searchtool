import os
import json
import smtplib
import subprocess
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="FFL Deal Radar",
    page_icon="🎯",
    layout="wide"
)

FEED_FILE = "feed_data.json"
DEALER_FILE = "registered_dealers.json"
STRIPE_URL = "https://buy.stripe.com/test_replace"
PRO_KEY = "DEALER2026"
CRON_TOKEN = "DEALER2026"

# 1. Background Webhook Trigger
params = st.query_params
if (
    params.get("task") == "scrape"
    and params.get("token") == CRON_TOKEN
):
    proc = subprocess.run(
        ["python", "worker.py"],
        capture_output=True,
        text=True
    )
    st.write(f"CRON_OK: {proc.stdout}")
    st.stop()

# 2. Data Loaders
def get_feed():
    if os.path.exists(FEED_FILE):
        try:
            with open(FEED_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "last_updated": datetime.now().strftime(
            "%Y-%m-%d %I:%M %p"
        ),
        "lots": [
            {
                "lot_id": "GB-101",
                "source_site": "GunBroker",
                "title": "Colt AR-15 Sporter Match 5.56",
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
                "compliance_badge": "🔥 Pre-Ban",
                "listing_url": "https://www.gunbroker.com"
            },
            {
                "lot_id": "HB-202",
                "source_site": "HiBid",
                "title": "S&W Model 19-3 .357 Mag (C&R)",
                "make": "smith & wesson",
                "model": "model 19",
                "current_bid": 340.0,
                "total_landed_cost": 456.2,
                "federal_retail": 850.0,
                "federal_profit": 393.8,
                "federal_margin
