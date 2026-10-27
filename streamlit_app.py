import os
import json
import hashlib
import smtplib
import traceback
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
# 1. AUTONOMOUS CRON SCRAPER TRIGGER (DIRECT IMPORT)
# ---------------------------------------------------------
params = st.query_params
if (
    params.get("task") == "scrape"
    and params.get("token") == CRON_TOKEN
):
    try:
        import worker
        worker.main()
        st.write("CRON_OK: worker.main() executed successfully.")
    except Exception as e:
        st.write(f"CRON_ERROR: {str(e)}")
        st.code(traceback.format_exc())
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
