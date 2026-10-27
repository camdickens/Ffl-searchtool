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

# ---------------------------------------------------------
# PERSISTENCE & DATA HELPERS
# ---------------------------------------------------------
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
                "listing_url": "https://www.gunbroker.com/item/1049281982"
            },
            {
                "lot_id": "HB-202",
                "source_site": "HiBid",
                "title": "Smith & Wesson Model 19-3 .357 Mag Revolver (1974 C&R)",
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
                "listing_url": "
