import os
import json
import smtplib
import subprocess
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pandas as pd
import streamlit as st

st.set_page_config(page_title="FFL Deal Radar", page_icon="🎯", layout="wide")

FEED_FILE = "feed_data.json"
DEALER_FILE = "registered_dealers.json"
STRIPE_URL = "https://buy.stripe.com/test_replace"
PRO_KEY = "DEALER2026"
CRON_TOKEN = "DEALER2026"

# 1. Autonomous Webhook Cron Ping
params = st.query_params
if params.get("task") == "scrape" and params.get("token") == CRON_TOKEN:
    proc = subprocess.run(["python", "worker.py"], capture_output=True, text=True)
    st.write(f"CRON_OK: {proc.stdout}")
    st.stop()

# 2. Feed Loader
def get_feed():
    if os.path.exists(FEED_FILE):
        try:
            with open(FEED_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"last_updated": datetime.now().strftime("%Y-%m-%d %I:%M %p"), "lots": []}

def save_dealer(profile):
    dealers = []
    if os.path.exists(DEALER_FILE):
        try:
            with open(DEALER_FILE, "r") as f:
                dealers = json.load(f)
        except Exception:
            pass
    dealers = [d for d in dealers if d.get("email") != profile.get("email")]
    dealers.append(profile)
    with open(DEALER_FILE, "w") as f:
        json.dump(dealers, f, indent=2)

def send_alert(to_email, subject, body):
    u = os.environ.get("SMTP_USER") or st.secrets.get("SMTP_USER", "")
    p = os.environ.get("SMTP_PASSWORD") or st.secrets.get("SMTP_PASSWORD", "")
    s = os.environ.get("SMTP_SERVER") or st.secrets.get("SMTP_SERVER", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT") or st.secrets.get("SMTP_PORT", 587))
    if not (u and p):
        return False, "Add SMTP credentials to Streamlit Secrets."
    try:
        msg = MIMEMultipart()
        msg["Subject"] = subject
        msg["From"] = u
        msg["To"] = to_email
        msg.attach(MIMEText(body, "html"))
        with smtplib.SMTP(s, port) as server:
            server.starttls()
            server.login(u, p)
            server.sendmail(u, to_email, msg.as_string())
        return True, "Email sent successfully!"
    except Exception as e:
        return False, str(e)

# 3. Sidebar Controls
with st.sidebar:
    st.title("🎯 FFL Radar")
    mode = st.radio("Framework", ["Massachusetts Compliant", "Federal Standard"])
    is_ma = (mode == "Massachusetts Compliant")
    license_key = st.text_input("Subscriber Key", type="password")
    is_pro = (license_key == PRO_KEY)
    st.success("🟢 Pro Active") if is_pro else st.info("🔒 Free Preview (Top 2 Free)")
    min_profit = st.slider("Min Profit ($)", 50, 500, 150, 25)
    action_only = st.checkbox("Show 'BID' Only", value=True)
    pre_ban_only = st.checkbox("Pre-Ban Only", value=False) if is_ma else False

# 4. Main App Interface
h1, h2 = st.columns([3, 1])
h1.title(f"FFL Sourcing Radar — {mode}")
if not is_pro:
    h2.link_button("⚡ Upgrade Pro ($199/mo)", STRIPE_URL, type="primary", use_container_width=True)

feed = get_feed()
all_lots = feed.get("lots", [])
st.caption(f"⚡ Live Feed • Last sync: **{feed.get('last_updated')}**")

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

t_feed, t_notif, t_sub = st.tabs(["📋 Sourcing Feed", "🔔 Email Alerts", "🏬 Onboarding"])

with t_feed:
    if not is_pro:
        st.warning("🔒 Free Preview: First 2 rows unlocked. Remainder masked for subscribers.")
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
                "Link": lot.get("listing_url") if open_row else STRIPE_URL
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, column_config={"Link": st.column_config.LinkColumn("Listing", display_text="Open ↗" if is_pro else "Unlock 🔒")})
    else:
        st.info("No lots found. Ping the webhook to trigger a live background cycle.")

with t_notif:
    st.subheader("🔔 Instant Email Alerts")
    nc1, nc2 = st.columns(2)
    with nc1:
        e_input = st.text_input("Dealer Alert Email", placeholder="dealer@store.com")
        e_thresh = st.number_input("Min Profit ($)", value=150.0, step=25.0)
        if st.button("💾 Save Alert Settings", use_container_width=True):
            if e_input:
                save_dealer({"email": e_input, "enable_email": True, "min_profit_threshold": e_thresh, "operating_mode": mode})
                st.success(f"Saved for {e_input}")
            else:
                st.error("Enter a valid email.")
    with nc2:
        t_email = st.text_input("Test Email Address")
        if st.button("✉️ Send Test Email", use_container_width=True):
            if t_email:
                ok, msg = send_alert(t_email, "🎯 Test Deal Alert", "<h3>Radar connected!</h3>")
                st.success(msg) if ok else st.error(msg)

with t_sub:
    st.subheader("Step 1: Dealer Registration")
    with st.form("reg"):
        s_name = st.text_input("Store Name *")
        s_ffl = st.text_input("FFL Number (Optional)")
        s_email = st.text_input("Contact Email *")
        if st.form_submit_button("Save & Proceed to Step 2", use_container_width=True):
            if s_name and s_email:
                save_dealer({"store_name": s_name, "ffl": s_ffl, "email": s_email, "operating_mode": mode})
                st.session_state["registered"] = True
                st.success("Registration saved! Complete checkout below.")
            else:
                st.error("Fill in required fields.")

    st.subheader("Step 2: Pro Tier Subscription")
    if st.session_state.get("registered"):
        st.link_button("👉 Checkout via Stripe ($199/mo)", STRIPE_URL, type="primary", use_container_width=True)
    else:
        st.warning("⚠️ Complete Step 1 above to unlock checkout.")
