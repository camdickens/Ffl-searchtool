import os
import json
import hashlib
import smtplib
import subprocess
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="FFL Deal Radar",
    page_icon="🎯",
    layout="wide"
)

USERS_FILE = "users.json"
FEED_FILE = "feed_data.json"
STRIPE_BASE_URL = "https://buy.stripe.com/test_replace"
CRON_TOKEN = "DEALER2026"

# ---------------------------------------------------------
# 1. AUTONOMOUS CRON SCRAPER TRIGGER
# ---------------------------------------------------------
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

# ---------------------------------------------------------
# 2. USER DATABASE & HELPERS
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

def register_user(email, password, store, ffl):
    users = get_all_users()
    e = email.strip().lower()
    if e in users:
        return False, "Account already exists."
    users[e] = {
        "store_name": store.strip(),
        "ffl": ffl.strip(),
        "password_hash": hash_pw(password),
        "plan": "free",
        "created_at": datetime.now().strftime("%Y-%m-%d"),
        "min_profit": 150.0,
        "email_alerts": True
    }
    save_all_users(users)
    return True, "Account created."

def authenticate_user(email, password):
    users = get_all_users()
    e = email.strip().lower()
    user = users.get(e)
    if user and user.get("password_hash") == hash_pw(password):
        user["email"] = e
        return user
    return None

def upgrade_user_to_pro(email: str):
    users = get_all_users()
    e = email.strip().lower()
    if e in users:
        users[e]["plan"] = "pro"
        save_all_users(users)
        return True
    return False

# ---------------------------------------------------------
# 3. AUTOMATED STRIPE RETURN HANDLER (METHOD B)
# ---------------------------------------------------------
if "session_id" in params:
    sess_id = params.get("session_id")
    s_key = os.environ.get("STRIPE_SECRET_KEY") or st.secrets.get(
        "STRIPE_SECRET_KEY", ""
    )
    if s_key:
        try:
            resp = requests.get(
                f"https://api.stripe.com/v1/checkout/sessions/{sess_id}",
                auth=(s_key, ""),
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("payment_status") == "paid":
                    c_email = (
                        data.get("customer_details", {}).get("email")
                        or data.get("customer_email")
                    )
                    if c_email:
                        upgrade_user_to_pro(c_email)
                        st.success(
                            f"🎉 Payment Verified! Account '{c_email}' "
                            f"upgraded to Pro."
                        )
                        users = get_all_users()
                        if c_email.lower() in users:
                            st.session_state["user"] = users[c_email.lower()]
                            st.session_state["user"]["email"] = c_email.lower()
        except Exception:
            pass

# ---------------------------------------------------------
# 4. FEED LOADER
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
        "lots": []
    }

# ---------------------------------------------------------
# 5. AUTHENTICATION GATEWAY
# ---------------------------------------------------------
if "user" not in st.session_state:
    st.session_state["user"] = None

if st.session_state["user"] is None:
    st.title("🎯 FFL Deal Radar — Dealer Portal")
    st.write("Sign in or create an account to view autonomous sourcing feeds.")
    
    t_login, t_signup = st.tabs(["🔐 Sign In", "📝 Create Dealer Account"])
    with t_login:
        with st.form("login_form"):
            l_email = st.text_input("Business Email")
            l_pw = st.text_input("Password", type="password")
            if st.form_submit_button("Sign In", use_container_width=True):
                user = authenticate_user(l_email, l_pw)
                if user:
                    st.session_state["user"] = user
                    st.rerun()
                else:
                    st.error("Invalid credentials.")
    with t_signup:
        with st.form("signup_form"):
            s_name = st.text_input("Store Name *")
            s_ffl = st.text_input("FFL Number (Optional)")
            s_email = st.text_input("Account Email *")
            s_pw = st.text_input("Password *", type="password")
            if st.form_submit_button("Create Account", use_container_width=True):
                if s_name and s_email and s_pw:
                    ok, msg = register_user(s_email, s_pw, s_name, s_ffl)
                    if ok:
                        st.success(f"{msg} You can now log in.")
                    else:
                        st.error(msg)
                else:
                    st.error("Fill in all required fields.")
    st.stop()

# ---------------------------------------------------------
# 6. AUTHENTICATED DASHBOARD
# ---------------------------------------------------------
current_user = st.session_state["user"]
is_pro = current_user.get("plan") == "pro"
user_email = current_user.get("email")
stripe_url = f"{STRIPE_BASE_URL}?prefilled_email={user_email}"

with st.sidebar:
    st.title("🎯 FFL Radar")
    st.write(f"Store: **{current_user.get('store_name')}**")
    st.caption(f"Account: `{user_email}`")
    
    if is_pro:
        st.success("🟢 Pro Dealer Unlocked")
    else:
        st.warning("🟡 Free Preview Active (Top 2 Free)")
        st.link_button(
            "⚡ Upgrade Pro ($199/mo)",
            stripe_url,
            type="primary",
            use_container_width=True
        )
    if st.button("🚪 Sign Out", use_container_width=True):
        st.session_state["user"] = None
        st.rerun()

    st.divider()
    mode = st.radio(
        "Framework",
        ["Massachusetts Compliant", "Federal Standard"]
    )
    is_ma = (mode == "Massachusetts Compliant")
    min_profit = st.slider("Min Profit ($)", 50, 500, 150, 25)
    action_only = st.checkbox("Show 'BID' Only", value=True)
    pre_ban_only = st.checkbox("Pre-Ban Only", value=False) if is_ma else False

h1, h2 = st.columns([3, 1])
h1.title(f"FFL Sourcing Radar — {mode}")
if not is_pro:
    h2.link_button(
        "⚡ Upgrade Pro ($199/mo)",
        stripe_url,
        type="primary",
        use_container_width=True
    )

feed = get_feed()
all_lots = feed.get("lots", [])
st.caption(
    f"⚡ Live Sync • Last updated: **{feed.get('last_updated')}**"
)

for l in all_lots:
    l["disp_retail"] = (
        l.get("ma_retail", 0.0) if is_ma
        else l.get("federal_retail", 0.0)
    )
    l["disp_profit"] = (
        l.get("ma_profit", 0.0) if is_ma
        else l.get("federal_profit", 0.0)
    )
    l["disp_margin"] = (
        l.get("ma_margin", 0.0) if is_ma
        else l.get("federal_margin", 0.0)
    )
    l["disp_act"] = (
        l.get("actionable_ma", False) if is_ma
        else l.get("actionable_federal", False)
    )

displayed = all_lots
if action_only:
    displayed = [l for l in displayed if l["disp_act"]]
if is_ma and pre_ban_only:
    displayed = [l for l in displayed if l.get("is_pre_ban")]

t_feed, t_alerts, t_account = st.tabs(
    ["📋 Sourcing Feed", "🔔 Alerts", "⚙️ Account"]
)

with t_feed:
    if not is_pro:
        st.warning(
            "🔒 Free Preview: First 2 rows open. "
            "Remaining lots locked for Pro subscribers."
        )
    if displayed:
        rows = []
        for idx, lot in enumerate(displayed):
            open_row = is_pro or (idx < 2)
            direct_link = lot.get("listing_url", "")
            rows.append({
                "Signal": "🟢 BID" if lot["disp_act"] else "🔴 PASS",
                "Source": lot.get("source_site"),
                "Model": f"{lot.get('make','').title()} {lot.get('model','').title()}",
                "Ask": f"${lot.get('current_bid',0):.2f}",
                "Landed": f"${lot.get('total_landed_cost',0):.2f}",
                "Target": f"${lot['disp_retail']:.2f}",
                "Net Spread": (
                    f"+${lot['disp_profit']:.2f}"
                    if open_row else "🔒 Pro Only"
                ),
                "Margin": (
                    f"{lot['disp_margin']:.1f}%"
                    if open_row else "🔒 Locked"
                ),
                "Max Bid": (
                    f"${lot.get('max_bid',0):.2f}"
                    if open_row else "🔒 Pro Only"
                ),
                "Badge": lot.get("compliance_badge", "Title 1"),
                "Link": direct_link if open_row else stripe_url
            })
        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Link": st.column_config.LinkColumn(
                    "Direct Listing",
                    display_text="Open Lot ↗" if is_pro else "Unlock 🔒"
                )
            }
        )
    else:
        st.info("No lots match the current criteria.")

with t_alerts:
    st.subheader("🔔 Instant Push Alerts")
    st.write(f"Recipient: `{user_email}`")
    u_thresh = st.number_input(
        "Min Profit Spread ($)",
        value=float(current_user.get("min_profit", 150.0)),
        step=25.0
    )
    if st.button("💾 Save Alert Settings", use_container_width=True):
        users = get_all_users()
        if user_email in users:
            users[user_email]["min_profit"] = u_thresh
            save_all_users(users)
            current_user["min_profit"] = u_thresh
            st.success("Alert preferences saved!")

with t_account:
    st.subheader("Store Profile")
    st.write(f"**Business:** {current_user.get('store_name')}")
    st.write(f"**Email:** {user_email}")
    st.write(f"**FFL:** {current_user.get('ffl') or 'Not provided'}")
    st.write(f"**Tier:** {'🟢 Pro Subscriber' if is_pro else '🟡 Free Tier'}")
    st.divider()
    if not is_pro:
        st.markdown("### Activate Pro Membership ($199/month)")
        st.write("Instant access to all masked arbitrage listings and 24/7 buy alerts.")
        st.link_button(
            "👉 Complete Checkout via Stripe",
            stripe_url,
            type="primary",
            use_container_width=True
        )
    else:
        st.success("Your Pro subscription is fully active.")

