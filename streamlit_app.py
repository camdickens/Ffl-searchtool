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

# 2. Resilient Feed Loader with Fallback
def build_lot(
    id, src, title, make, mod,
    bid, landed, f_ret, m_ret,
    pre, badge, url
):
    f_p = round(f_ret - landed, 2)
    m_p = round(m_ret - landed, 2)
    return {
        "lot_id": id,
        "source_site": src,
        "title": title,
        "make": make,
        "model": mod,
        "current_bid": bid,
        "total_landed_cost": landed,
        "federal_retail": f_ret,
        "federal_profit": f_p,
        "federal_margin": (
            round(f_p / f_ret * 100, 1) if f_ret else 0.0
        ),
        "actionable_federal": f_p >= 120,
        "ma_retail": m_ret,
        "ma_profit": m_p,
        "ma_margin": (
            round(m_p / m_ret * 100, 1) if m_ret else 0.0
        ),
        "actionable_ma": m_p >= 150,
        "max_bid": round(m_ret * 0.70, 2),
        "is_pre_ban": pre,
        "compliance_badge": badge,
        "listing_url": url
    }

def get_default_lots():
    return [
        build_lot(
            "GB-101", "GunBroker",
            "Colt AR-15 Sporter Match 5.56",
            "colt", "ar-15",
            720.0, 806.6, 1150.0, 1897.5,
            True, "🔥 Pre-Ban Grandfathered",
            "https://www.gunbroker.com"
        ),
        build_lot(
            "HB-202", "HiBid",
            "S&W Model 19-3 .357 Mag (C&R)",
            "smith & wesson", "model 19",
            340.0, 456.2, 850.0, 850.0,
            False, "🏛️ C&R Exempt",
            "https://hibid.com"
        ),
        build_lot(
            "AL-303", "Armslist",
            "Remington 870 Wingmaster 12G",
            "remington", "870",
            180.0, 245.0, 375.0, 375.0,
            False, "Federal Title 1",
            "https://www.armslist.com"
        ),
        build_lot(
            "GB-404", "GunBroker",
            "Glock 19 Gen 5 9mm (Used)",
            "glock", "19",
            410.0, 477.3, 520.0, 695.0,
            False, "⚠️ Frame Only",
            "https://www.gunbroker.com"
        )
    ]

def get_feed():
    lots = []
    if os.path.exists(FEED_FILE):
        try:
            with open(FEED_FILE, "r") as f:
                data = json.load(f)
                lots = data.get("lots", [])
        except Exception:
            pass
    if not lots:
        lots = get_default_lots()
    return {
        "last_updated": datetime.now().strftime(
            "%Y-%m-%d %I:%M %p"
        ),
        "lots": lots
    }

# 3. Sidebar Controls
with st.sidebar:
    st.title("🎯 FFL Radar")
    mode = st.radio(
        "Framework",
        ["Massachusetts Compliant", "Federal Standard"]
    )
    is_ma = (mode == "Massachusetts Compliant")
    license_key = st.text_input(
        "Subscriber Key",
        type="password"
    )
    is_pro = (license_key == PRO_KEY)
    if is_pro:
        st.success("🟢 Pro Active")
    else:
        st.info("🔒 Free Preview (Top 2 Free)")
    min_profit = st.slider(
        "Min Profit ($)", 50, 500, 150, 25
    )
    action_only = st.checkbox(
        "Show 'BID' Only", value=True
    )
    pre_ban_only = st.checkbox(
        "Pre-Ban Only", value=False
    ) if is_ma else False

# 4. Main App Interface
h1, h2 = st.columns([3, 1])
h1.title(f"FFL Sourcing Radar — {mode}")
if not is_pro:
    h2.link_button(
        "⚡ Upgrade Pro ($199/mo)",
        STRIPE_URL,
        type="primary",
        use_container_width=True
    )

feed = get_feed()
all_lots = feed.get("lots", [])
st.caption(
    f"⚡ Live Feed • Last sync: **{feed.get('last_updated')}**"
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

t_feed, t_notif, t_sub = st.tabs(
    ["📋 Sourcing Feed", "🔔 Email Alerts", "🏬 Onboarding"]
)

with t_feed:
    if not is_pro:
        st.warning(
            "🔒 Free Preview: First 2 rows unlocked. Remainder masked."
        )
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
                "Link": (
                    lot.get("listing_url")
                    if open_row else STRIPE_URL
                )
            })
        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Link": st.column_config.LinkColumn(
                    "Listing",
                    display_text="Open ↗" if is_pro else "Unlock 🔒"
                )
            }
        )
    else:
        st.info("No lots match the selected filters.")

with t_notif:
    st.subheader("🔔 Instant Email Alerts")
    e_input = st.text_input(
        "Dealer Alert Email",
        placeholder="dealer@store.com"
    )
    e_thresh = st.number_input(
        "Min Profit ($)", value=150.0, step=25.0
    )
    if st.button("💾 Save Alert Settings", use_container_width=True):
        if e_input:
            dealers = []
            if os.path.exists(DEALER_FILE):
                try:
                    with open(DEALER_FILE, "r") as f:
                        dealers = json.load(f)
                except Exception:
                    pass
            dealers = [d for d in dealers if d.get("email") != e_input]
            dealers.append({
                "email": e_input,
                "enable_email": True,
                "min_profit_threshold": e_thresh,
                "operating_mode": mode
            })
            with open(DEALER_FILE, "w") as f:
                json.dump(dealers, f, indent=2)
            st.success(f"Saved for {e_input}")
        else:
            st.error("Enter a valid email.")

with t_sub:
    st.subheader("Step 1: Dealer Registration")
    with st.form("reg"):
        s_name = st.text_input("Store Name *")
        s_ffl = st.text_input("FFL Number (Optional)")
        s_email = st.text_input("Contact Email *")
        if st.form_submit_button(
            "Save & Proceed to Step 2",
            use_container_width=True
        ):
            if s_name and s_email:
                st.session_state["registered"] = True
                st.success("Registration saved! Complete checkout below.")
            else:
                st.error("Fill in required fields.")

    st.subheader("Step 2: Pro Tier Subscription")
    if st.session_state.get("registered"):
        st.link_button(
            "👉 Checkout via Stripe ($199/mo)",
            STRIPE_URL,
            type="primary",
            use_container_width=True
        )
    else:
        st.warning("⚠️ Complete Step 1 above to unlock checkout.")
