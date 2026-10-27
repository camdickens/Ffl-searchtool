import os
import json
import hashlib
import smtplib
import subprocess
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pandas as pd
import streamlit as st

st.set_page_config(page_title="FFL Deal Radar", page_icon="🎯", layout="wide")

USERS_FILE = "users.json"
FEED_FILE = "feed_data.json"
STRIPE_BASE_URL = "https://buy.stripe.com/test_replace"
CRON_TOKEN = "DEALER2026"

# ---------------------------------------------------------
# 1. AUTONOMOUS BACKGROUND SCRAPER HOOK
# ---------------------------------------------------------
params = st.query_params
if params.get("task") == "scrape" and params.get("token") == CRON_TOKEN:
    proc = subprocess.run(["python", "worker.py"], capture_output=True, text=True)
    st.write(f"CRON_OK: {proc.stdout}")
    st.stop()

# ---------------------------------------------------------
# 2. USER AUTHENTICATION & DATABASE (users.json)
# ---------------------------------------------------------
def hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

def get_all_users() -> dict:
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_all_users(users: dict):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

def register_user(email: str, password: str, store_name: str, ffl_num: str):
    users = get_all_users()
    e = email.strip().lower()
    if e in users:
        return False, "An account with this email already exists."
    users[e] = {
        "store_name": store_name.strip(),
        "ffl": ffl_num.strip(),
        "password_hash": hash_pw(password),
        "plan": "free",
        "created_at": datetime.now().strftime("%Y-%m-%d"),
        "min_profit": 150.0,
        "email_alerts": True
    }
    save_all_users(users)
    return True, "Account registered successfully."

def authenticate_user(email: str, password: str):
    users = get_all_users()
    e = email.strip().lower()
    user = users.get(e)
    if not user:
        return None
    if user.get("password_hash") == hash_pw(password):
        user["email"] = e
        return user
    return None

def update_user_settings(email: str, updates: dict):
    users = get_all_users()
    e = email.strip().lower()
    if e in users:
        users[e].update(updates)
        save_all_users(users)

# ---------------------------------------------------------
# 3. FEED DATA LOADER
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
                "compliance_badge": "🔥 Pre-Ban Grandfathered",
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
                "federal_margin": 46.3,
                "actionable_federal": True,
                "ma_retail": 850.0,
                "ma_profit": 393.8,
                "ma_margin": 46.3,
                "actionable_ma": True,
                "max_bid": 546.6,
                "is_pre_ban": False,
                "compliance_badge": "🏛️ C&R Exempt",
                "listing_url": "https://hibid.com"
            },
            {
                "lot_id": "AL-303",
                "source_site": "Armslist",
                "title": "Remington 870 Wingmaster 12G",
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
                "compliance_badge": "⚠️ Frame Only",
                "listing_url": "https://www.gunbroker.com"
            }
        ]
    }

# ---------------------------------------------------------
# 4. SESSION STATE AUTH INITIALIZATION
# ---------------------------------------------------------
if "user" not in st.session_state:
    st.session_state["user"] = None

# If user is not logged in, show Auth Gate
if st.session_state["user"] is None:
    st.title("🎯 FFL Deal Radar — Dealer Portal")
    st.write("Sign in or create an account to access autonomous market arbitrage feeds.")
    
    t_login, t_signup = st.tabs(["🔐 Sign In", "📝 Create Dealer Account"])
    
    with t_login:
        with st.form("login_form"):
            login_email = st.text_input("Email Address")
            login_pw = st.text_input("Password", type="password")
            submit_login = st.form_submit_button("Sign In", use_container_width=True)
            if submit_login:
                user = authenticate_user(login_email, login_pw)
                if user:
                    st.session_state["user"] = user
                    st.rerun()
                else:
                    st.error("Invalid email or password.")
                    
    with t_signup:
        with st.form("signup_form"):
            new_store = st.text_input("Dealership / Store Name *")
            new_ffl = st.text_input("FFL License Number (Optional)")
            new_email = st.text_input("Business Email *")
            new_pw = st.text_input("Create Password *", type="password")
            submit_reg = st.form_submit_button("Create Account", use_container_width=True)
            if submit_reg:
                if new_store and new_email and new_pw:
                    ok, msg = register_user(new_email, new_pw, new_store, new_ffl)
                    if ok:
                        st.success(f"{msg} You can now log in above.")
                    else:
                        st.error(msg)
                else:
                    st.error("Please fill in all required fields (*).")
    st.stop()

# ---------------------------------------------------------
# 5. AUTHENTICATED DASHBOARD (USER LOGGED IN)
# ---------------------------------------------------------
current_user = st.session_state["user"]
is_pro = current_user.get("plan") == "pro"
user_email = current_user.get("email")

# Dynamic Stripe link passing dealer's email
stripe_checkout_url = f"{STRIPE_BASE_URL}?prefilled_email={user_email}"

with st.sidebar:
    st.title("🎯 FFL Radar")
    st.write(f"Logged in as: **{current_user.get('store_name')}**")
    st.caption(f"Email: `{user_email}`")
    
    if is_pro:
        st.success("🟢 Tier: Pro Subscriber")
    else:
        st.warning("🟡 Tier: Free Preview (Top 2 Free)")
        st.link_button("⚡ Upgrade to Pro ($199/mo)", stripe_checkout_url, type="primary", use_container_width=True)
        
    if st.button("🚪 Sign Out", use_container_width=True):
        st.session_state["user"] = None
        st.rerun()
        
    st.divider()
    mode = st.radio("Compliance Framework", ["Massachusetts Compliant", "Federal Standard"])
    is_ma = (mode == "Massachusetts Compliant")
    min_profit = st.slider("Min Net Profit ($)", 50, 500, 150, 25)
    action_only = st.checkbox("Show 'BID' Signals Only", value=True)
    pre_ban_only = st.checkbox("Pre-Ban Grandfathered Only", value=False) if is_ma else False

h1, h2 = st.columns([3, 1])
h1.title(f"FFL Sourcing Radar — {mode}")
if not is_pro:
    h2.link_button("⚡ Upgrade to Pro ($199/mo)", stripe_checkout_url, type="primary", use_container_width=True)

feed = get_feed()
all_lots = feed.get("lots", [])
st.caption(f"⚡ Live Sync • Last updated: **{feed.get('last_updated')}**")

for l in all_lots:
    l["disp_retail"] = l.get("ma_retail", 0.0) if is_ma else l.get("federal_retail", 0.0)
    l["disp_profit"] = l.get("ma_profit", 0.0) if is_ma else l.get("federal_profit", 0.0)
    l["disp_margin"] = l.get("ma_margin", 0.0) if is_ma else l.get("federal_margin", 0.0)
    l["disp_act"] = l.get("actionable_ma", False) if is_ma else l.get("actionable_federal", False)

displayed = all_lots
if action_only:
    displayed = [l for l in displayed if l["disp_act"]]
if is_ma and pre_ban_only:
    displayed = [l for l in displayed if l.get("is_pre_ban")]

t_feed, t_alerts, t_account = st.tabs(["📋 Sourcing Feed", "🔔 Email Alerts", "⚙️ Account & Billing"])

with t_feed:
    if not is_pro:
        st.warning("🔒 Free Preview: First 2 listings open. Remaining lots masked for Pro Subscribers.")
    if displayed:
        rows = []
        for idx, lot in enumerate(displayed):
            open_row = is_pro or (idx < 2)
            rows.append({
                "Signal": "🟢 BID" if lot["disp_act"] else "🔴 PASS",
                "Source": lot.get("source_site"),
                "Model": f"{lot.get('make','').title()} {lot.get('model','').title()}",
                "Ask": f"${lot.get('current_bid',0):.2f}",
                "Landed": f"${lot.get('total_landed_cost',0):.2f}",
                "Target": f"${lot['disp_retail']:.2f}",
                "Net Spread": f"+${lot['disp_profit']:.2f}" if open_row else "🔒 Pro Only",
                "Margin": f"{lot['disp_margin']:.1f}%" if open_row else "🔒 Locked",
                "Max Bid": f"${lot.get('max_bid',0):.2f}" if open_row else "🔒 Pro Only",
                "Badge": lot.get("compliance_badge", "Title 1"),
                "Link": lot.get("listing_url") if open_row else stripe_checkout_url
            })
        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
            column_config={"Link": st.column_config.LinkColumn("Listing", display_text="Open ↗" if is_pro else "Unlock 🔒")}
        )
    else:
        st.info("No lots match the current criteria.")

with t_alerts:
    st.subheader("🔔 Dealer Push Alerts")
    st.write(f"Alerts configured for: `{user_email}`")
    user_thresh = st.number_input("Minimum Profit Spread to Trigger Alert ($)", value=float(current_user.get("min_profit", 150.0)), step=25.0)
    user_enable = st.checkbox("Enable 24/7 background alerts", value=current_user.get("email_alerts", True))
    if st.button("💾 Save Alert Preferences", use_container_width=True):
        update_user_settings(user_email, {"min_profit": user_thresh, "email_alerts": user_enable})
        current_user["min_profit"] = user_thresh
        current_user["email_alerts"] = user_enable
        st.success("Alert preferences saved!")

with t_account:
    st.subheader("Store Profile")
    st.write(f"**Business:** {current_user.get('store_name')}")
    st.write(f"**Email:** {user_email}")
    st.write(f"**FFL:** {current_user.get('ffl') or 'Not specified'}")
    st.write(f"**Current Status:** {'🟢 Pro Subscriber' if is_pro else '🟡 Free Tier'}")
    st.divider()
    if not is_pro:
        st.markdown("### Upgrade to Pro Tier ($199/month)")
        st.write("Unlock unrestricted access to all nationwide sourcing arbitrage listings and instant alerts.")
        st.link_button("👉 Subscribe via Stripe Checkout", stripe_checkout_url, type="primary", use_container_width=True)
    else:
        st.success("Your Pro subscription is active. All listings and instant email alerts are unlocked.")
