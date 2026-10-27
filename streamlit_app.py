import streamlit as st
import pandas as pd
import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

st.set_page_config(page_title="FFL Deal Radar", page_icon="🎯", layout="wide")

FEED_FILE = "feed_data.json"
DEALER_FILE = "registered_dealers.json"
STRIPE_URL = "https://buy.stripe.com/test_replace_with_your_link"
PRO_KEY = "DEALER2026"

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
                "listing_url": "https://hibid.com/lot/19823481/smith-and-wesson-model-19-3"
            },
            {
                "lot_id": "AL-303",
                "source_site": "Armslist",
                "title": "Remington 870 Wingmaster 12 Gauge",
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
                "listing_url": "https://www.armslist.com/posts/14982103/massachusetts-shotguns-for-sale--remington-870"
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
                "compliance_badge": "⚠️ Frame Transfer Only",
                "listing_url": "https://www.gunbroker.com/item/1049281989"
            }
        ]
    }

def get_dealers():
    if os.path.exists(DEALER_FILE):
        try:
            with open(DEALER_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return []

def save_dealer(profile):
    dealers = get_dealers()
    for i, d in enumerate(dealers):
        if d.get("email") == profile.get("email"):
            dealers[i] = profile
            with open(DEALER_FILE, "w") as f:
                json.dump(dealers, f, indent=2)
            return
    dealers.append(profile)
    with open(DEALER_FILE, "w") as f:
        json.dump(dealers, f, indent=2)

def send_test_email(to_email):
    user = os.environ.get("SMTP_USER") or st.secrets.get("SMTP_USER", "")
    pw = os.environ.get("SMTP_PASSWORD") or st.secrets.get("SMTP_PASSWORD", "")
    server = os.environ.get("SMTP_SERVER") or st.secrets.get("SMTP_SERVER", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT") or st.secrets.get("SMTP_PORT", 587))
    if not (user and pw):
        return False, "SMTP secrets not set. Add SMTP_USER and SMTP_PASSWORD to your Streamlit secrets."
    try:
        msg = MIMEMultipart()
        msg["Subject"] = "🎯 FFL Deal Radar Alert Test"
        msg["From"] = user
        msg["To"] = to_email
        msg.attach(MIMEText("<h3>FFL Deal Radar Connected!</h3><p>Live buy signals will arrive here.</p>", "html"))
        with smtplib.SMTP(server, port) as s:
            s.starttls()
            s.login(user, pw)
            s.sendmail(user, to_email, msg.as_string())
        return True, "Test email sent successfully!"
    except Exception as e:
        return False, str(e)

with st.sidebar:
    st.title("🎯 FFL Radar")
    mode = st.radio("Framework", ["Massachusetts Compliant", "Federally Legal (All 50 States)"])
    is_ma = (mode == "Massachusetts Compliant")
    st.divider()
    license_key = st.text_input("Subscriber License Key", type="password")
    is_pro = (license_key == PRO_KEY)
    if is_pro:
        st.success("🟢 Pro Dealer Unlocked")
    else:
        st.info("🔒 Free Preview Active (Top 2 Free)")
    st.divider()
    min_profit = st.slider("Min Net Profit ($)", 50, 500, 150, 25)
    action_only = st.checkbox("Show 'BID / BUY' Only", value=True)
    pre_ban_only = st.checkbox("Pre-Ban Only", value=False) if is_ma else False

h1, h2 = st.columns([3, 1])
h1.title(f"FFL Sourcing Radar — {mode}")
if not is_pro:
    h2.link_button("⚡ Upgrade to Pro ($199/mo)", STRIPE_URL, type="primary", use_container_width=True)

@st.fragment(run_every="30s")
def render():
    feed = get_feed()
    all_lots = feed.get("lots", [])
    st.caption(f"⚡ Live Sourcing Feed • Scrapes GunBroker + HiBid + Armslist • Auto-refresh 30s • Last sync: **{feed.get('last_updated')}**")

    for l in all_lots:
        l["disp_retail"] = l.get("ma_retail", 0.0) if is_ma else l.get("federal_retail", 0.0)
        l["disp_profit"] = l.get("ma_profit", 0.0) if is_ma else l.get("federal_profit", 0.0)
        l["disp_margin"] = l.get("ma_margin", 0.0) if is_ma else l.get("federal_margin", 0.0)
        l["disp_act"] = l.get("actionable_ma", False) if is_ma else l.get("actionable_federal", False)

    act_deals = [l for l in all_lots if l["disp_act"]]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Monitored Lots", len(all_lots))
    m2.metric("Buy Signals", len(act_deals))
    m3.metric("Pre-Ban Matches" if is_ma else "High-Margin Lots", len([l for l in all_lots if l.get("is_pre_ban")]) if is_ma else len([l for l in all_lots if l["disp_profit"] >= 200]))
    m4.metric("Active Mode", "Massachusetts" if is_ma else "Federal Title 1")
    st.divider()

    displayed = all_lots
    if action_only:
        displayed = [l for l in displayed if l["disp_act"]]
    if is_ma and pre_ban_only:
        displayed = [l for l in displayed if l.get("is_pre_ban")]

    t_table, t_cards, t_notif, t_sub = st.tabs(["📋 Sourcing Feed", "🗂️ Opportunity Cards", "🔔 Email Push Alerts", "🏬 Onboarding & Pro"])

    with t_table:
        if not is_pro:
            st.warning("🔒 Free Preview: First 2 listings open. Remaining lots masked for Pro Subscribers.")
        if displayed:
            rows = []
            for idx, lot in enumerate(displayed):
                open_row = is_pro or (idx < 2)
                rows.append({
                    "Signal": "🟢 BID" if lot["disp_act"] else "🔴 PASS",
                    "Source": lot.get("source_site"),
                    "Model": f"{lot.get('make', '').title()} {lot.get('model', '').title()}",
                    "Current Price": f"${lot.get('current_bid', 0):.2f}",
                    "Total Landed": f"${lot.get('total_landed_cost', 0):.2f}",
                    "Target Resale": f"${lot['disp_retail']:.2f}",
                    "Net Spread": f"+${lot['disp_profit']:.2f}" if open_row else "🔒 Pro Only",
                    "Margin": f"{lot['disp_margin']:.1f}%" if open_row else "🔒 Locked",
                    "Max Bid": f"${lot.get('max_bid', 0):.2f}" if open_row else "🔒 Pro Only",
                    "Compliance": lot.get("compliance_badge", "Title 1"),
                    "Link": lot.get("listing_url") if open_row else STRIPE_URL
                })
            st.dataframe(
                pd.DataFrame(rows),
                use_container_width=True,
                hide_index=True,
                column_config={"Link": st.column_config.LinkColumn("Source", display_text="Open Lot ↗" if is_pro else "Unlock 🔒")}
            )
        else:
            st.info("No lots currently match the selected criteria.")

    with t_cards:
        if displayed:
            for idx, d in enumerate(displayed):
                open_card = is_pro or (idx < 2)
                with st.container():
                    c1, c2, c3 = st.columns([3, 2, 1])
                    c1.markdown(f"### {d.get('make', '').title()} {d.get('model', '').title()} `[{d.get('source_site')}]`")
                    c1.caption(d.get("title"))
                    c1.write(f"**Classification:** {d.get('compliance_badge')}")
                    c2.write(f"**Current Ask:** ${d.get('current_bid', 0):.2f} | **Landed:** ${d.get('total_landed_cost', 0):.2f}")
                    if open_card:
                        c2.write(f"**Target Resale:** ${d['disp_retail']:.2f} | **Max Walk-Away:** ${d.get('max_bid', 0):.2f}")
                        c2.success(f"+${d['disp_profit']:.2f} Net Profit ({d['disp_margin']:.1f}%)")
                        c3.link_button("Open Listing ↗", d.get("listing_url"), use_container_width=True)
                    else:
                        c2.info("🔒 Spread and Max Bid locked")
                        c3.link_button("Unlock Deal 🔒", STRIPE_URL, type="primary", use_container_width=True)
                    st.divider()

    with t_notif:
        st.subheader("🔔 Instant Email Deal Alerts")
        nc1, nc2 = st.columns(2)
        with nc1:
            e_input = st.text_input("Dealer Alert Email", placeholder="owner@store.com")
            e_thresh = st.number_input("Min Profit to Trigger Alert ($)", value=150.0, step=25.0)
            if st.button("💾 Save Alert Settings", use_container_width=True):
                if e_input:
                    save_dealer({"email": e_input, "enable_email": True, "min_profit_threshold": e_thresh, "operating_mode": mode})
                    st.success(f"Saved! Alerts active for {e_input}")
                else:
                    st.error("Enter a valid email.")
        with nc2:
            st.markdown("#### 🧪 Test Alert")
            t_email = st.text_input("Destination for Test", value=e_input if 'e_input' in locals() else "")
            if st.button("✉️ Send Test Email", use_container_width=True):
                if t_email:
                    ok, msg = send_test_email(t_email)
                    st.success(msg) if ok else st.error(msg)

    with t_sub:
        st.subheader("Step 1: Store Registration")
        with st.form("reg_form"):
            s_name = st.text_input("Store Name *")
            s_contact = st.text_input("Licensee Name *")
            s_ffl = st.text_input("FFL Number (Optional)")
            s_email = st.text_input("Account Email *")
            if st.form_submit_button("Save Profile & Unlock Pro", use_container_width=True):
                if s_name and s_contact and s_email:
                    save_dealer({"store_name": s_name, "contact_name": s_contact, "ffl": s_ffl, "email": s_email, "operating_mode": mode})
                    st.session_state["registered"] = True
                    st.session_state["store_name"] = s_name
                    st.success("Profile saved! Proceed to Step 2 below.")
                else:
                    st.error("Fill in required fields (*).")

        st.subheader("Step 2: Activate Sourcing Subscription")
        if st.session_state.get("registered"):
            st.link_button("👉 Complete Stripe Checkout ($199/mo)", STRIPE_URL, type="primary", use_container_width=True)
        else:
            st.warning("⚠️ Step 2 Locked: Submit your profile above first.")

render()
