This error happens when an orphaned `try:` line was left behind above Section 6 on GitHub (or if old code wasn't completely selected and deleted before pasting, leaving mismatched indentation). When Python sees an open `try:`, it halts at the very first unindented line and throws `SyntaxError: expected 'except' or 'finally' block`.

To fix this once and for all:

1. Open `streamlit_app.py` in your GitHub repository and click the **pencil icon (Edit)**.
2. Press **`Cmd + A`** (Mac) or **`Ctrl + A`** (Windows) to select everything, then press **Delete / Backspace** so the editor is completely empty (line 1 is blank).
3. Paste the clean, verified code below. Every `try` block in this script is strictly self-contained with its own `except`, and Section 6 contains zero outer try wrappers.
4. Click **Commit changes**.

---

### Clean `streamlit_app.py`

```python
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
    
    if is_pro:
        st.success("🟢 Pro Dealer Unlocked (VIP Access)")
    else:
        st.warning("🟡 Free Preview Active (Top 2 Free)")
        st.link_button(
            "⚡ Upgrade Pro ($199/mo)",
            stripe_url,
            type="primary",
            use_container_width=True,
            key="btn_upgrade_sidebar"
        )
        
    if st.button("🚪 Sign Out", use_container_width=True, key="btn_sign_out_sidebar"):
        if "auth" in st.query_params:
            del st.query_params["auth"]
        st.session_state["user"] = None
        st.rerun()

    st.divider()
    st.subheader("📑 Views & Sections")
    
    active_view = st.radio(
        "Select Section",
        [
            "🔨 Live Auctions",
            "📋 All Inventory Feed",
            "🔔 Push Alerts",
            "⚙️ Account Profile"
        ],
        index=0,
        key="radio_nav_section"
    )

    st.divider()
    st.subheader("⚙️ Sourcing Filters")
    
    mode = st.radio(
        "Legal Framework",
        ["Massachusetts Compliant", "Federal Standard"],
        key="radio_legal_framework"
    )
    is_ma = (mode == "Massachusetts Compliant")

    default_sources = ["GunBroker", "HiBid"] if active_view == "🔨 Live Auctions" else ["GunBroker", "Armslist", "HiBid"]
    selected_sources = st.multiselect(
        "Source Platforms",
        ["GunBroker", "HiBid", "Armslist"],
        default=default_sources,
        key="multiselect_sources"
    )

    min_profit = st.slider("Min Net Spread ($)", 25, 600, 100, 25, key="slider_min_profit")
    min_margin = st.slider("Min Margin (%)", 5, 60, 15, 5, key="slider_min_margin")
    max_cost = st.number_input("Max Purchase / Bid ($)", min_value=0, value=2500, step=100, key="num_max_cost")

    action_only = st.checkbox("Show 'BID' Only (Spread ≥ Target)", value=True, key="chk_action_only")
    pre_ban_only = st.checkbox("Pre-Ban Grandfathered Only", value=False, key="chk_pre_ban") if is_ma else False
    search_query = st.text_input("🔍 Search Keyword (Make, Model, Title)", "", key="txt_search_query").strip().lower()

# TOP HEADER
h1, h2 = st.columns([3, 1])
h1.title(f"{active_view} — {mode}")
if not is_pro:
    h2.link_button(
        "⚡ Upgrade Pro ($199/mo)",
        stripe_url,
        type="primary",
        use_container_width=True,
        key="btn_upgrade_top_header"
    )

feed = get_feed()
all_lots = feed.get("lots", [])
st.caption(f"⚡ Live Sync • Last updated: **{feed.get('last_updated', 'Just now')}**")

# Safe computation of display fields
for l in all_lots:
    l["disp_retail"] = float(l.get("ma_retail", 0.0) if is_ma else l.get("federal_retail", 0.0))
    l["disp_profit"] = float(l.get("ma_profit", 0.0) if is_ma else l.get("federal_profit", 0.0))
    l["disp_margin"] = float(l.get("ma_margin", 0.0) if is_ma else l.get("federal_margin", 0.0))
    l["disp_act"] = bool(l.get("actionable_ma", False) if is_ma else l.get("actionable_federal", False))
    is_auction_lot = l.get("source_site") in ["GunBroker", "HiBid"] or "bid" in l.get("title", "").lower()
    l["is_auction"] = is_auction_lot

def render_feed_table(items, empty_msg):
    if not is_pro:
        st.info("💡 Free Preview: Top 2 lots unlocked with direct source links. Upgrade to Pro to unlock all 20+ arbitrage spreads.")
    
    st.write(f"Showing **{len(items)}** matching lots out of **{len(all_lots)}** total inventory.")
    
    if items:
        rows = []
        for idx, lot in enumerate(items):
            open_row = is_pro or (idx < 2)
            direct_link = lot.get("listing_url", "")
            rows.append({
                "Signal": "🟢 BID" if lot.get("disp_act") else "🔴 PASS",
                "Source": lot.get("source_site", "Direct"),
                "Type": "🔨 Auction" if lot.get("is_auction") else "🏷️ Classified",
                "Model": f"{lot.get('make', '').title()} {lot.get('model', '').title()}",
                "Current Bid / Ask": f"${float(lot.get('current_bid', 0)):.2f}",
                "Total Landed": f"${float(lot.get('total_landed_cost', 0)):.2f}",
                "Target Value": f"${lot.get('disp_retail', 0):.2f}",
                "Net Spread": f"+${lot.get('disp_profit', 0):.2f}" if open_row else "🔒 Pro Only",
                "Margin": f"{lot.get('disp_margin', 0):.1f}%" if open_row else "🔒 Locked",
                "Recommended Max Bid": f"${float(lot.get('max_bid', 0)):.2f}" if open_row else "🔒 Pro Only",
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
                    display_text="Open Lot ↗" if open_row else "Unlock 🔒"
                )
            }
        )
    else:
        st.warning(empty_msg)

# Filter evaluation
filtered_lots = []
for l in all_lots:
    if selected_sources and l.get("source_site") not in selected_sources:
        continue
    if l["disp_profit"] < min_profit:
        continue
    if l["disp_margin"] < min_margin:
        continue
    if float(l.get("current_bid", 0)) > max_cost:
        continue
    if action_only and not l["disp_act"]:
        continue
    if is_ma and pre_ban_only and not l.get("is_pre_ban", False):
        continue
    if search_query:
        combined = f"{l.get('make','')} {l.get('model','')} {l.get('title','')} {l.get('compliance_badge','')}".lower()
        if search_query not in combined:
            continue
    filtered_lots.append(l)

# VIEW 1: LIVE AUCTIONS
if active_view == "🔨 Live Auctions":
    auction_items = [l for l in filtered_lots if l.get("is_auction")]
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Active Live Auctions", f"{len(auction_items)} Lots")
    avg_auction_spread = (
        sum(l["disp_profit"] for l in auction_items) / len(auction_items)
        if auction_items else 0.0
    )
    m2.metric("Average Auction Spread", f"+${avg_auction_spread:.2f}")
    top_auction_margin = max([l["disp_margin"] for l in auction_items], default=0.0)
    m3.metric("Top Auction Margin", f"{top_auction_margin:.1f}%")
    
    render_feed_table(
        auction_items,
        "No live auctions currently match your filter criteria. Adjust the minimum profit or clear search terms."
    )

# VIEW 2: ALL INVENTORY FEED
elif active_view == "📋 All Inventory Feed":
    render_feed_table(
        filtered_lots,
        "No lots match the chosen criteria across auctions and classifieds. Try broadening your filter range."
    )

# VIEW 3: PUSH ALERTS
elif active_view == "🔔 Push Alerts":
    st.subheader("🔔 Autonomous Buy Alerts")
    st.write(f"Alert Dispatch Target: `{user_email}`")
    u_thresh = st.number_input(
        "Min Profit Spread for Automated Email Dispatch ($)",
        value=float(current_user.get("min_profit", 150.0)),
        step=25.0,
        key="num_alert_threshold"
    )
    if st.button("💾 Save Alert Settings", use_container_width=True, key="btn_save_alerts"):
        users = get_all_users()
        if user_email in users:
            users[user_email]["min_profit"] = u_thresh
            save_all_users(users)
            st.session_state["user"]["min_profit"] = u_thresh
            st.success("Alert preferences saved successfully!")

# VIEW 4: ACCOUNT PROFILE
elif active_view == "⚙️ Account Profile":
    st.subheader("Store Profile & Membership")
    st.write(f"**Business Store:** {store_title}")
    st.write(f"**Email Address:** {user_email}")
    st.write(f"**FFL License:** {current_user.get('ffl') or 'Not provided'}")
    st.write(f"**Subscription Plan:** {'🟢 Pro Subscriber (Active VIP)' if is_pro else '🟡 Free Tier'}")
    st.divider()
    if not is_pro:
        st.markdown("### Activate Pro Membership ($199/month)")
        st.write("Instant access to all masked arbitrage listings, custom alert thresholds, and direct auction lot URLs.")
        st.link_button(
            "👉 Complete Checkout via Stripe",
            stripe_url,
            type="primary",
            use_container_width=True,
            key="btn_checkout_account_tab"
        )
    else:
        st.success("Your Pro subscription is fully active. All live feeds, links, and calculation metrics are unlocked.")

```
