import os
import json
import hashlib
import traceback
from datetime import datetime
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
SESSION_SALT = "FFL_RADAR_AUTH_SECRET_2026"

# ---------------------------------------------------------
# VIP / PRO BYPASS CONFIGURATION
# ---------------------------------------------------------
ADMIN_BYPASS_EMAILS = [
    "camerondickens9000@gmail.com",
    "admin@ffldealradar.com",
    "owner@dealfinder.com",
    "test@test.com"
]

def hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

def make_session_token(email: str) -> str:
    return hashlib.sha256((email.strip().lower() + SESSION_SALT).encode()).hexdigest()

# Permanent default accounts that survive container wipes
DEFAULT_SEEDED_USERS = {
    "camerondickens9000@gmail.com": {
        "store_name": "VIP Admin Store",
        "ffl": "01-ADMIN-BYPASS",
        "password_hash": hash_pw("admin123"),
        "plan": "pro",
        "created_at": "2026-01-01",
        "min_profit": 150.0,
        "email_alerts": True
    }
}

# ---------------------------------------------------------
# 1. AUTONOMOUS CRON SCRAPER TRIGGER
# ---------------------------------------------------------
params = st.query_params
if params.get("task") == "scrape" and params.get("token") == CRON_TOKEN:
    try:
        import worker
        worker.main()
        st.write("CRON_OK: worker.main() executed successfully.")
    except Exception as e:
        st.write(f"CRON_ERROR: {str(e)}")
        st.code(traceback.format_exc())
    st.stop()

# ---------------------------------------------------------
# 2. USER DATABASE & PERSISTENCE HELPERS
# ---------------------------------------------------------
def get_all_users() -> dict:
    users = dict(DEFAULT_SEEDED_USERS)
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    users.update(loaded)
        except Exception:
            pass
    return users

def save_all_users(users: dict):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

def register_user(email, password, store, ffl):
    users = get_all_users()
    e = email.strip().lower()
    if e in users and users[e].get("password_hash") != "":
        return False, "Account already exists."
    is_vip = e in [a.lower() for a in ADMIN_BYPASS_EMAILS]
    users[e] = {
        "store_name": store.strip(),
        "ffl": ffl.strip(),
        "password_hash": hash_pw(password),
        "plan": "pro" if is_vip else "free",
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
    if user:
        if (e in [a.lower() for a in ADMIN_BYPASS_EMAILS]) or (user.get("password_hash") == hash_pw(password)):
            user_copy = dict(user)
            user_copy["email"] = e
            if e in [a.lower() for a in ADMIN_BYPASS_EMAILS]:
                user_copy["plan"] = "pro"
            return user_copy
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
# 3. AUTOMATED STRIPE RETURN HANDLER
# ---------------------------------------------------------
if "session_id" in params:
    sess_id = params.get("session_id")
    s_key = os.environ.get("STRIPE_SECRET_KEY") or st.secrets.get("STRIPE_SECRET_KEY", "")
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
                        st.success(f"🎉 Payment Verified! Account '{c_email}' upgraded to Pro.")
                        users = get_all_users()
                        if c_email.lower() in users:
                            st.session_state["user"] = users[c_email.lower()]
                            st.session_state["user"]["email"] = c_email.lower()
                            st.query_params["auth"] = make_session_token(c_email.lower())
        except Exception:
            pass

# ---------------------------------------------------------
# 4. FEED LOADER
# ---------------------------------------------------------
def get_feed():
    if not os.path.exists(FEED_FILE):
        try:
            import worker
            worker.main()
        except Exception:
            pass

    if os.path.exists(FEED_FILE):
        try:
            with open(FEED_FILE, "r") as f:
                data = json.load(f)
                if isinstance(data, dict) and "lots" in data:
                    return data
        except Exception:
            pass

    return {
        "last_updated": datetime.now().strftime("%Y-%m-%d %I:%M %p"),
        "lots": []
    }

# ---------------------------------------------------------
# 5. AUTOMATIC PERSISTENT SESSION RESTORATION
# ---------------------------------------------------------
if "user" not in st.session_state:
    st.session_state["user"] = None

active_auth_token = st.query_params.get("auth")
if st.session_state["user"] is None and active_auth_token:
    all_known_users = get_all_users()
    for em, u_info in all_known_users.items():
        if make_session_token(em) == active_auth_token:
            restored = dict(u_info)
            restored["email"] = em
            if em in [a.lower() for a in ADMIN_BYPASS_EMAILS]:
                restored["plan"] = "pro"
            st.session_state["user"] = restored
            break

if st.session_state["user"] is None:
    st.title("🎯 FFL Deal Radar — Dealer Portal")
    st.write("Sign in or create an account to access live sourcing arbitrage feeds.")
    
    t_login, t_signup = st.tabs(["🔐 Sign In", "📝 Create Dealer Account"])
    with t_login:
        with st.form("login_form"):
            l_email = st.text_input("Business Email")
            l_pw = st.text_input("Password", type="password")
            remember_me = st.checkbox("Keep me signed in on this device", value=True)
            if st.form_submit_button("Sign In", use_container_width=True):
                user = authenticate_user(l_email, l_pw)
                if user:
                    st.session_state["user"] = user
                    if remember_me:
                        st.query_params["auth"] = make_session_token(user["email"])
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
try:
    current_user = st.session_state.get("user") or {}
    user_email = current_user.get("email", "").lower()
    is_pro = (current_user.get("plan") == "pro") or (user_email in [a.lower() for a in ADMIN_BYPASS_EMAILS])
    store_title = current_user.get("store_name", "Dealer")
    stripe_url = f"{STRIPE_BASE_URL}?prefilled_email={user_email}"

    if st.query_params.get("auth") != make_session_token(user_email):
        st.query_params["auth"] = make_session_token(user_email)

    with st.sidebar:
        st.title("🎯 FFL Radar")
        st.write(f"Store: **{store_title}**")
        st.caption(f"Account: `{user_email}`")
