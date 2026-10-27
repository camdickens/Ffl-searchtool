import streamlit as st
import pandas as pd
import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# -----------------------------------------------------------------------------
# 1. APPLICATION SETUP & CONSTANTS
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="FFL Deal Radar | Sourcing & Arbitrage Engine",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

FEED_DATA_FILE = "feed_data.json"
DEALER_DB_FILE = "registered_dealers.json"
STRIPE_PRO_TIER_URL = "https://buy.stripe.com/test_replace_with_your_link"
SUBSCRIBER_ACCESS_KEY = "DEALER2026"

# -----------------------------------------------------------------------------
# 2. DATA PERSISTENCE & EMAIL DISPATCH
# -----------------------------------------------------------------------------
def load_live_feed():
    if os.path.exists(FEED_DATA_FILE):
        try:
            with open(FEED_DATA_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "last_updated": datetime.now().strftime("%Y-%m-%d %I:%M:%S %p"),
        "lots": [
            {
                "lot_id": "GB-1049281",
                "source_site": "GunBroker",
                "title": "Colt AR-15 Sporter Match HBAR 5.56 (Pre-1994)",
                "make": "colt",
                "model": "ar-15",
                "current_bid": 720.0,
                "total_landed_cost": 806.60,
                "federal_retail": 1150.0,
                "federal_profit": 343.40,
                "federal_margin": 29.9,
                "actionable_federal": True,
                "ma_retail": 1897.50,
                "ma_profit": 1090.90,
                "ma_margin": 57.5,
                "actionable_ma": True,
                "max_bid": 1400.0,
                "is_pre_ban": True,
                "is_curio_relic": False,
                "ma_roster_compliant": True,
                "compliance_badge": "🔥 Pre-Ban Grandfathered",
                "listing_url": "https://www.gunbroker.com/item/1049281982"
            },
            {
                "lot_id": "HB-982348",
                "source_site": "HiBid",
                "title": "Smith & Wesson Model 19-3 .357 Mag Revolver (1974 C&R)",
                "make": "smith & wesson",
                "model": "model 19",
                "current_bid": 340.0,
                "total_landed_cost": 456.20,
                "federal_retail": 850.0,
