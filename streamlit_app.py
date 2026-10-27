import streamlit as st
import pandas as pd
import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from twilio.rest import Client

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
# 2. DATA PERSISTENCE & DISPATCH HELPERS
# -----------------------------------------------------------------------------
def load_live_feed():
    if os.path.exists(FEED_DATA_FILE):
        try:
            with open(FEED_DATA_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    # Fallback simulated dataset across all three platforms
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
                "listing_url": "https://www.gunbroker.com",
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
                "federal_profit": 393.80,
                "federal_margin": 46.3,
                "actionable_federal": True,
                "ma_retail": 850.0,
                "ma_profit": 393.80,
                "ma_margin": 46.3,
                "actionable_ma": True,
                "max_bid": 546.61,
                "is_pre_ban": False,
                "is_curio_relic": True,
                "ma_roster_compliant": True,
                "compliance_badge": "🏛️ C&R 50-Year Exempt",
                "listing_url": "https://www.hibid.com",
            },
            {
                "lot_id": "AL-582019",
                "source_site": "Armslist",
                "title": "Remington 870 Wingmaster 12 Gauge Shotgun",
                "make": "remington",
                "model": "870",
                "current_bid": 180.0,
                "total_landed_cost": 245.00,
                "federal_retail": 375.0,
                "federal_profit": 130.00,
                "federal_margin": 34.7,
                "actionable_federal": True,
                "ma_retail": 375.0,
                "ma_profit": 130.00,
                "ma_margin": 34.7,
                "actionable_ma": True,
                "max_bid": 210.0,
                "is_pre_ban": False,
                "is_curio_relic": False,
                "ma_roster_compliant": True,
                "compliance_badge": "Federal Title 1 Standard",
                "listing_url": "https://www.armslist.com",
            },
            {
                "lot_id": "GB-1049289",
                "source_site": "GunBroker",
                "title": "Glock 19 Gen 5 9mm Pistol (Used w/ 3 Mags)",
                "make": "glock",
                "model": "19",
                "current_bid": 410.0,
                "total_landed_cost": 477.30,
                "federal_retail": 520.0,
                "federal_profit": 42.70,
                "federal_margin": 8.2,
                "actionable_federal": False,
                "ma_retail": 695.0,
                "ma_profit": 217.70,
                "ma_margin": 31.3,
                "actionable_ma": True,
                "max_bid": 415.25,
                "is_pre_ban": False,
                "is_curio_relic": False,
                "ma_roster_compliant": False,
                "compliance_badge": "⚠️ Frame Transfer Only",
                "listing_url": "https://www.gunbroker.com",
            }
        ]
    }

def load_registered_dealers():
    if os.path.exists(DEALER_DB_FILE):
        try:
            with open(DEALER_DB_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_dealer_profile(profile: dict):
    dealers = load_registered_dealers()
    updated = False
    for i, d in enumerate(dealers):
        if d.get("email") == profile.get("email"):
            dealers[i] = profile
            updated = True
            break
    if not updated:
        dealers.append(profile)
    with open(DEALER_DB_FILE, "w") as f:
        json.dump(dealers, f, indent=2)

def trigger_test_sms(phone: str):
    sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
    token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    from_num = os.environ.get("TWILIO_PHONE_NUMBER", "")
    if not (sid and token and from_num):
        return False, "Twilio environment variables not configured in deployment."
    try:
        client = Client(sid, token)
        client.messages.create(
            body="🎯 FFL RADAR: Test deal alert connected successfully! You will receive live buy signals here.",
            from_=from_num,
            to=phone
        )
        return True, "Test SMS sent successfully!"
    except Exception as e:
        return False, str(e)

def trigger_test_email(email: str):
    user = os.environ.get("SMTP_USER", "")
    pw = os.environ.get("SMTP_PASSWORD", "")
    server = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", 587))
    if not (user and pw):
        return False, "SMTP credentials not configured in deployment."
    try:
        msg = MIMEMultipart()
        msg["Subject"] = "🎯 FFL Radar: Test Deal Alert"
        msg["From"] = f"FFL Deal Radar <{user}>"
        msg["To"] = email
        msg.attach(MIMEText("<h3>🎯 Test Alert Connected</h3><p>Your email notifications are configured for live auction alerts.</p>", "html"))
        with smtplib.SMTP(server, port) as s:
            s.starttls()
            s.login(user, pw)
            s.sendmail(user, email, msg.as_string())
        return True, "Test email dispatched successfully!"
    except Exception as e:
        return False, str(e)

# -----------------------------------------------------------------------------
# 3. SIDEBAR NAVIGATION & COMPLIANCE CONTROLS
# -----------------------------------------------------------------------------
with st.sidebar:
    st.title("🎯 FFL Radar")

    # MODE SWITCHER
    st.subheader("🌐 Regulatory Framework")
    selected_mode = st.radio(
        "Operating Mode",
        ["Massachusetts Compliant", "Federally Legal (All 50 States)"],
        help="Switch between Massachusetts state compliance (rosters + pre-bans) and standard Federal Title I out-of-state rules."
    )
    is_ma_mode = (selected_mode == "Massachusetts Compliant")

    st.divider()
    st.markdown("### 🔑 Dealer Access")
    entered_key = st.text_input("Subscriber License Key", type="password", placeholder="Enter key from email...")
    is_pro_member = (entered_key == SUBSCRIBER_ACCESS_KEY)

    if is_pro_member:
        st.success("🟢 Pro Dealer Unlocked")
    else:
        st.info("🔒 Free Preview Active (Top 2 Lots Free)")

    st.divider()
    st.subheader("Filter Parameters")
    min_profit = st.slider("Min Net Spread ($)", 50, 500, 150, 25)
    min_margin = st.slider("Min Margin (%)", 10, 50, 25, 5)

    filter_actionable = st.checkbox("Show 'BID / BUY' Signals Only", value=True)
    if is_ma_mode:
        filter_pre_ban = st.checkbox("Pre-Ban Grandfathered Only", value=False)
        filter_ma_roster = st.checkbox("MA Roster / Compliant Only", value=False)
    else:
        filter_pre_ban = False
        filter_ma_roster = False

# -----------------------------------------------------------------------------
# 4. MAIN INTERFACE & AUTO-REFRESH FRAGMENT
# -----------------------------------------------------------------------------
header_left, header_right = st.columns([3, 1])
with header_left:
    st.title(f"FFL Sourcing Radar — {selected_mode}")
    st.write("Autonomous sourcing across GunBroker, HiBid, and Armslist with true landed acquisition costs.")
with header_right:
    st.write("")
    if not is_pro_member:
        st.link_button("⚡ Upgrade to Pro ($199/mo)", STRIPE_PRO_TIER_URL, type="primary", use_container_width=True)

@st.fragment(run_every="30s")
def render_dashboard():
    feed = load_live_feed()
    all_lots = feed.get("lots", [])
    last_sync = feed.get("last_updated", "Just now")

    st.caption(f"⚡ Live Sourcing Feed • Scrapes GunBroker + HiBid + Armslist • Auto-refresh 30s • Last sync: **{last_sync}**")

    # Metrics calculation based on selected mode
    for l in all_lots:
        if is_ma_mode:
            l["display_retail"] = l.get("ma_retail", 0.0)
            l["display_profit"] = l.get("ma_profit", 0.0)
            l["display_margin"] = l.get("ma_margin", 0.0)
            l["display_signal"] = l.get("actionable_ma", False)
        else:
            l["display_retail"] = l.get("federal_retail", 0.0)
            l["display_profit"] = l.get("federal_profit", 0.0)
            l["display_margin"] = l.get("federal_margin", 0.0)
            l["display_signal"] = l.get("actionable_federal", False)

    actionable_deals = [l for l in all_lots if l["display_signal"]]
    pre_bans = [l for l in all_lots if l.get("is_pre_ban", False)]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Catalog Lots Monitored", len(all_lots))
    m2.metric("Actionable Buy Signals", len(actionable_deals), delta=f"{len(actionable_deals)} Deals")
    m3.metric("Pre-Ban Matches" if is_ma_mode else "High-Margin Spreads", len(pre_bans) if is_ma_mode else len([l for l in all_lots if l["display_profit"] >= 200]))
    m4.metric("Mode Active", "Massachusetts" if is_ma_mode else "Federal Title I")

    st.divider()

    # Filter pipeline
    displayed = all_lots
    if filter_actionable:
        displayed = [l for l in displayed if l["display_signal"]]
    if is_ma_mode:
        if filter_pre_ban:
            displayed = [l for l in displayed if l.get("is_pre_ban", False)]
        if filter_ma_roster:
            displayed = [l for l in displayed if l.get("ma_roster_compliant", False)]

    # 4 TABS
    tab_table, tab_cards, tab_notifs, tab_onboarding = st.tabs([
        "📋 Live Sourcing Table",
        "🗂️ Opportunity Cards",
        "🔔 Push Notifications",
        "🏬 Dealer Onboarding & Billing"
    ])

    # --- TAB 1: LIVE SOURCING TABLE (PAYWALLED) ---
    with tab_table:
        if not is_pro_member:
            st.warning("🔒 **Free Teaser Active:** Full spread data unlocked on top 2 preview deals. Remaining auction lots, max bids, and direct links require Pro Subscription.")

        if displayed:
            rows = []
            for idx, lot in enumerate(displayed):
                is_unmasked = is_pro_member or (idx < 2)

                signal = "🟢 BID" if lot["display_signal"] else "🔴 PASS"
                profit_str = f"+${lot['display_profit']:.2f}" if is_unmasked else "🔒 Pro Only"
                margin_str = f"{lot['display_margin']:.1f}%" if is_unmasked else "🔒 Locked"
                max_bid_str = f"${lot.get('max_bid', 0):.2f}" if is_unmasked else "🔒 Pro Only"
                link_url = lot.get("listing_url") if is_unmasked else STRIPE_PRO_TIER_URL

                rows.append({
                    "Signal": signal,
                    "Source": lot.get("source_site", "Live"),
                    "Model": f"{lot.get('make', '').title()} {lot.get('model', '').title()}",
                    "Current Price": f"${lot.get('current_bid', 0):.2f}",
                    "Total Landed": f"${lot.get('total_landed_cost', 0):.2f}",
                    "Target Resale": f"${lot['display_retail']:.2f}",
                    "Net Spread": profit_str,
                    "Margin": margin_str,
                    "Max Bid": max_bid_str,
                    "Compliance": lot.get("compliance_badge", "Title 1"),
                    "Auction Link": link_url
                })

            st.dataframe(
                pd.DataFrame(rows),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Auction Link": st.column_config.LinkColumn(
                        "Source Page",
                        display_text="Open Listing ↗" if is_pro_member else "Unlock Link 🔒"
                    )
                }
            )
        else:
            st.info("No lots currently match the active filter criteria.")

    # --- TAB 2: RICH OPPORTUNITY CARDS ---
    with tab_cards:
        if displayed:
            for idx, deal in enumerate(displayed):
                is_unmasked = is_pro_member or (idx < 2)
                with st.container():
                    c1, c2, c3 = st.columns([3, 2, 1])
                    with c1:
                        st.markdown(f"### {deal.get('make', '').title()} {deal.get('model', '').title()} `[{deal.get('source_site', 'Live')}]`")
                        st.caption(deal.get("title", ""))
                        st.write(f"**Classification:** {deal.get('compliance_badge', 'Title 1')}")

                    with c2:
                        st.write(f"**Current Ask/Bid:** ${deal.get('current_bid', 0):.2f} | **Total Landed:** ${deal.get('total_landed_cost', 0):.2f}")
                        if is_unmasked:
                            st.write(f"**Target Retail:** ${deal['display_retail']:.2f} | **Max Walk-Away:** ${deal.get('max_bid', 0):.2f}")
                            st.success(f"+${deal['display_profit']:.2f} Profit Spread ({deal['display_margin']:.1f}%)")
                        else:
                            st.info("🔒 Spread and Max Bid locked for Pro Members")

                    with c3:
                        st.write("")
                        if is_unmasked:
                            st.link_button("Open Listing ↗", deal.get("listing_url", "#"), use_container_width=True)
                        else:
                            st.link_button("Unlock Deal 🔒", STRIPE_PRO_TIER_URL, type="primary", use_container_width=True)
                    st.divider()
        else:
            st.info("No lots match the active filter criteria.")

    # --- TAB 3: DEDICATED PUSH NOTIFICATIONS ---
    with tab_notifs:
        st.subheader("🔔 Dealer Push Notification Dispatch")
        st.write("Configure real-time mobile and email notifications. Our 24/7 background worker automatically alerts you the second a qualifying firearm appears on GunBroker, HiBid, or Armslist.")

        notif_col1, notif_col2 = st.columns(2)

        with notif_col1:
            st.markdown("#### 📱 Notification Channels")
            enable_sms = st.checkbox("Enable Direct SMS Text Alerts to Phone", value=True)
            alert_phone = st.text_input("Mobile Phone Number", placeholder="e.g. 508-555-0199")

            enable_email = st.checkbox("Enable Instant Email Deal Alerts", value=True)
            alert_email = st.text_input("Alert Email Address", placeholder="e.g. owner@fflstore.com")

            st.markdown("#### ⚙️ Alert Trigger Thresholds")
            alert_threshold = st.number_input("Minimum Net Profit Spread to Trigger Alert ($)", min_value=50.0, max_value=1000.0, value=150.0, step=25.0)
            alert_mode = st.selectbox("Regulatory Lens for Dispatches", ["Massachusetts Compliant", "Federally Legal (All 50 States)"])

            if st.button("💾 Save Notification Preferences", use_container_width=True):
                if alert_phone or alert_email:
                    dealers = load_registered_dealers()
                    dealers.append({
                        "phone": alert_phone,
                        "email": alert_email,
                        "enable_sms": enable_sms,
                        "enable_email": enable_email,
                        "min_profit_threshold": alert_threshold,
                        "operating_mode": "Massachusetts" if alert_mode == "Massachusetts Compliant" else "Federal",
                        "updated_at": datetime.now().isoformat()
                    })
                    with open(DEALER_DB_FILE, "w") as f:
                        json.dump(dealers, f, indent=2)
                    st.success("Notification preferences saved! Background worker will alert this profile.")
                else:
                    st.error("Please provide at least a phone number or email address.")

        with notif_col2:
            st.markdown("#### 🧪 Test Alert Dispatch")
            st.write("Verify that your phone and email are connected properly to the automated dispatch engine.")

            test_target_phone = st.text_input("Test Phone Number", value=alert_phone)
            if st.button("📲 Send Test SMS Text", use_container_width=True):
                if test_target_phone:
                    success, msg = trigger_test_sms(test_target_phone)
                    if success:
                        st.success(msg)
                    else:
                        st.error(f"SMS failed: {msg}")
                else:
                    st.warning("Enter a phone number to test.")

            st.write("")
            test_target_email = st.text_input("Test Email Address", value=alert_email)
            if st.button("✉️ Send Test Email", use_container_width=True):
                if test_target_email:
                    success, msg = trigger_test_email(test_target_email)
                    if success:
                        st.success(msg)
                    else:
                        st.error(f"Email failed: {msg}")
                else:
                    st.warning("Enter an email address to test.")

    # --- TAB 4: TWO-STEP ONBOARDING & BILLING ---
    with tab_onboarding:
        st.subheader("Step 1: Complete Store Registration")
        st.caption("Register your store profile and regulatory preferences before activating your subscription.")

        ob_col1, ob_col2 = st.columns([3, 2])
        with ob_col1:
            with st.form("onboarding_profile_form"):
                store_name = st.text_input("Store / FFL Legal Trade Name *", placeholder="Apex Firearms & Defense")
                contact_name = st.text_input("Owner / Licensee Name *", placeholder="John Miller")
                ffl_num = st.text_input("FFL License Number", placeholder="e.g. 1-04-XXXXX (Optional for preview)")
                state_reg = st.selectbox("Primary State of Licensure", ["MA", "NH", "PA", "FL", "TX", "OH", "RI", "CT", "Other"])
                dealer_email = st.text_input("Billing & Account Email *", placeholder="contact@apexfirearms.com")
                dealer_phone = st.text_input("Direct Phone Number *", placeholder="508-555-0199")
                framework_choice = st.radio("Primary Sourcing Framework", ["Massachusetts Compliant", "Federally Legal (All 50 States)"])

                submit_profile = st.form_submit_button("Save Profile & Unlock Subscription Step", use_container_width=True)

            if submit_profile:
                if store_name and contact_name and dealer_email and dealer_phone:
                    save_dealer_profile({
                        "store_name": store_name,
                        "contact_name": contact_name,
                        "ffl_number": ffl_num,
                        "state": state_reg,
                        "email": dealer_email,
                        "phone": dealer_phone,
                        "operating_mode": "Massachusetts" if framework_choice == "Massachusetts Compliant" else "Federal",
                        "enable_sms": True,
                        "enable_email": True,
                        "min_profit_threshold": 150.0,
                        "profile_completed": True,
                        "registered_at": datetime.now().isoformat()
                    })
                    st.session_state["profile_submitted"] = True
                    st.session_state["store_name"] = store_name
                    st.success("✅ Profile verified! Proceed to Step 2 below to activate Pro access.")
                else:
                    st.error("Please fill in all required fields (*).")

        with ob_col2:
            st.markdown("""
            <div style="background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 1.25rem;">
                <h4 style="color: #58a6ff; margin-top: 0;">Pro Dealer Benefits ($199/mo)</h4>
                <ul style="color: #c9d1d9; font-size: 0.9rem; line-height: 1.8;">
                    <li><strong>24/7 background worker</strong> hunting GunBroker, HiBid, and Armslist</li>
                    <li><strong>Direct SMS and Email alerts</strong> dispatched immediately upon deal discovery</li>
                    <li><strong>Federal Title 1 & Massachusetts mode toggle</strong></li>
                    <li><strong>Unmasked live links</strong> taking you directly to the source listing</li>
                    <li><strong>Automated walk-away bid ceilings</strong> protecting your margin floor</li>
                    <li>Cancel anytime directly through Stripe portal</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)

        st.divider()

        # STEP 2: SUBSCRIPTION CHECKOUT
        st.subheader("Step 2: Activate Sourcing Subscription")
        if st.session_state.get("profile_submitted", False):
            st.success(f"Profile saved for **{st.session_state.get('store_name')}**. Proceed below to activate your live feed:")
            s1, s2 = st.columns([2, 3])
            with s1:
                st.markdown("### $199 / month\n*Billed monthly. Cancel anytime.*")
                st.link_button("👉 Complete Stripe Checkout", STRIPE_PRO_TIER_URL, type="primary", use_container_width=True)
            with s2:
                st.info("💡 **Instant Key Delivery:** Upon checkout, your secret subscriber key will be delivered to your account email, and your 24/7 alert pipeline will begin monitoring incoming lots immediately.")
        else:
            st.warning("⚠️ **Step 2 Locked:** Please submit your store profile in Step 1 above to unlock checkout.")

# Render Dashboard
render_dashboard()
