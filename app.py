import streamlit as st
import pandas as pd
import json
import os
import urllib.request
from datetime import datetime

# ---------------------------------------------------------
# 1. PAGE SETUP & CONFIGURATION
# ---------------------------------------------------------
st.set_page_config(
    page_title="FFL Deal Radar | Sourcing Engine",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

FEED_DATA_FILE = "feed_data.json"
DEALER_DB_FILE = "registered_dealers.json"
ALERT_DISPATCH_CACHE = "app_alerted_lots.json"

# Replace with your actual Stripe Checkout link
STRIPE_PRO_TIER_URL = "https://buy.stripe.com/test_replace_with_your_link"

# Secret subscriber key to unlock paywalled data
SUBSCRIBER_ACCESS_KEY = "DEALER2026"

# ---------------------------------------------------------
# 2. DATA PERSISTENCE & ALERT DISPATCH
# ---------------------------------------------------------
def load_live_feed():
    """Loads latest scraped catalog from worker output."""
    if os.path.exists(FEED_DATA_FILE):
        try:
            with open(FEED_DATA_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"last_updated": datetime.now().strftime("%Y-%m-%d %I:%M:%S %p"), "lots": []}

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
    # Update existing dealer if email matches, otherwise append
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

def dispatch_refresh_alert(webhook_url: str, deal: dict):
    """Sends a rich Discord notification when a new lot populates on refresh."""
    payload = {
        "username": "FFL Deal Radar (Live Sync)",
        "avatar_url": "https://cdn-icons-png.flaticon.com/512/1041/1041888.png",
        "embeds": [{
            "title": f"⚡ NEW LISTING ON REFRESH: {deal.get('make', '').title()} {deal.get('model', '').title()}",
            "description": f"**Item:** {deal.get('title', '')}\n**Source:** {deal.get('source_site', 'Auction')}\n**Link:** [Open Live Lot]({deal.get('listing_url', '#')})",
            "color": 3066993,
            "fields": [
                {"name": "Current Bid", "value": f"${deal.get('current_bid', 0):.2f}", "inline": True},
                {"name": "Total Landed Cost", "value": f"${deal.get('total_landed_cost', 0):.2f}", "inline": True},
                {"name": "Est. MA Retail", "value": f"${deal.get('ma_retail', 0):.2f}", "inline": True},
                {"name": "Projected Profit", "value": f"**+${deal.get('net_profit', 0):.2f}**", "inline": True},
                {"name": "Margin", "value": f"{deal.get('margin_pct', 0):.1f}%", "inline": True},
                {"name": "Max Walk-Away Bid", "value": f"${deal.get('max_bid', 0):.2f}", "inline": True},
                {"name": "Compliance", "value": deal.get("compliance_badge", "Standard"), "inline": False}
            ],
            "footer": {"text": "Auto-dispatched on feed sync"}
        }]
    }
    req = urllib.request.Request(
        webhook_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "FFL-LiveAlert"}
    )
    try:
        urllib.request.urlopen(req)
    except Exception as e:
        print(f"Failed to send refresh alert: {e}")

# ---------------------------------------------------------
# 3. SIDEBAR: SUBSCRIBER LOGIN & FILTERS
# ---------------------------------------------------------
with st.sidebar:
    st.title("🎯 FFL Radar")

    st.markdown("### 🔑 Dealer Access")
    entered_key = st.text_input("Subscriber License Key", type="password", placeholder="Enter key from welcome email...")
    is_pro_member = (entered_key == SUBSCRIBER_ACCESS_KEY)

    if is_pro_member:
        st.success("🟢 Pro Dealer Unlocked")
    else:
        st.info("🔒 Preview Mode Active (Top 2 Lots Free)")

    st.divider()
    st.subheader("Filter Inventory")
    min_profit = st.slider("Min Net Profit ($)", min_value=50, max_value=500, value=150, step=25)
    min_margin = st.slider("Min Margin (%)", min_value=10, max_value=50, value=30, step=5)
    
    filter_actionable = st.checkbox("Show 'BID / BUY' Only", value=True)
    filter_pre_ban = st.checkbox("Pre-Ban Grandfathered Only", value=False)
    filter_ma_roster = st.checkbox("MA Roster / Compliant Only", value=False)

    st.divider()
    st.caption("Auto-refresh active: checks every 30s")

# ---------------------------------------------------------
# 4. MAIN INTERFACE & ONBOARDING TABS
# ---------------------------------------------------------
header_col1, header_col2 = st.columns([3, 1])
with header_col1:
    st.title("FFL Inventory Sourcing Radar")
    st.write("Autonomous auction monitoring, landed acquisition calculations, and Massachusetts compliance filtering.")
with header_col2:
    st.write("")
    if not is_pro_member:
        st.link_button("⚡ Create Profile / Upgrade", "#tabs-b2b-membership", type="primary", use_container_width=True)

# ---------------------------------------------------------
# 5. LIVE AUTO-REFRESH CATALOG FRAGMENT (30s POLLING)
# ---------------------------------------------------------
@st.fragment(run_every="30s")
def render_live_catalog():
    feed = load_live_feed()
    all_lots = feed.get("lots", [])
    last_sync = feed.get("last_updated", "Just now")

    st.caption(f"⚡ Live Catalog Feed • Auto-refresh active (30s) • Last synchronized: **{last_sync}**")

    # Load seen alert cache to trigger notifications on newly ingested listings
    seen_alerts = []
    if os.path.exists(ALERT_DISPATCH_CACHE):
        try:
            with open(ALERT_DISPATCH_CACHE, "r") as f:
                seen_alerts = json.load(f)
        except Exception:
            seen_alerts = []

    # Check registered dealers who opted in to refresh alerts
    dealers = load_registered_dealers()
    for lot in all_lots:
        if lot.get("actionable_deal") and lot.get("lot_id") not in seen_alerts:
            for d in dealers:
                if d.get("alert_on_refresh") and d.get("discord_webhook"):
                    dispatch_refresh_alert(d.get("discord_webhook"), lot)
            seen_alerts.append(lot.get("lot_id"))

    # Update alert cache
    with open(ALERT_DISPATCH_CACHE, "w") as f:
        json.dump(seen_alerts, f)

    # Top KPI Cards
    c1, c2, c3, c4 = st.columns(4)
    actionable_deals = [l for l in all_lots if l.get("actionable_deal", False)]
    pre_bans = [l for l in all_lots if l.get("is_pre_ban", False)]
    c1.metric("Catalog Lots Monitored", len(all_lots))
    c2.metric("Actionable Buy Signals", len(actionable_deals))
    c3.metric("Pre-Ban Matches", len(pre_bans))
    c4.metric("Engine Surveillance", "Active 24/7", delta="Background Worker")

    st.divider()

    # Apply sidebar filters
    displayed = all_lots
    if filter_actionable:
        displayed = [l for l in displayed if l.get("actionable_deal", False)]
    if filter_pre_ban:
        displayed = [l for l in displayed if l.get("is_pre_ban", False)]
    if filter_ma_roster:
        displayed = [l for l in displayed if l.get("ma_roster_compliant", False)]

    tab_table, tab_cards, tab_calc, tab_onboarding = st.tabs([
        "📋 Live Auction Table", 
        "🗂️ Opportunity Cards", 
        "🧮 Deal Screener", 
        "🏬 Create Profile & Subscribe"
    ])

    # --- TAB 1: AUCTION TABLE (PAYWALLED) ---
    with tab_table:
        if not is_pro_member:
            st.warning("🔒 **Free Preview Active:** Unrestricted details on top 2 preview lots. Remaining deals, max bids, and direct auction links are reserved for Pro Subscribers.")

        if displayed:
            table_rows = []
            for idx, lot in enumerate(displayed):
                is_unmasked = is_pro_member or (idx < 2)

                signal = "🟢 BID" if lot.get("actionable_deal") else "🔴 PASS"
                model_name = f"{lot.get('make', '').title()} {lot.get('model', '').title()}"
                bid_str = f"${lot.get('current_bid', 0):.2f}"
                landed_str = f"${lot.get('total_landed_cost', 0):.2f}"
                retail_str = f"${lot.get('ma_retail', 0):.2f}"

                profit_str = f"+${lot.get('net_profit', 0):.2f}" if is_unmasked else "🔒 Pro Only"
                margin_str = f"{lot.get('margin_pct', 0):.1f}%" if is_unmasked else "🔒 Locked"
                max_bid_str = f"${lot.get('max_bid', 0):.2f}" if is_unmasked else "🔒 Pro Only"
                auction_link = lot.get("listing_url") if is_unmasked else STRIPE_PRO_TIER_URL

                table_rows.append({
                    "Signal": signal,
                    "Source": lot.get("source_site", "Auction"),
                    "Model": model_name,
                    "Current Bid": bid_str,
                    "Landed Cost": landed_str,
                    "Est. MA Retail": retail_str,
                    "Net Spread": profit_str,
                    "Margin": margin_str,
                    "Max Walk-Away Bid": max_bid_str,
                    "Compliance": lot.get("compliance_badge", "Standard"),
                    "Auction Link": auction_link
                })

            st.dataframe(
                pd.DataFrame(table_rows),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Auction Link": st.column_config.LinkColumn(
                        "Auction Source",
                        display_text="Open Lot ↗" if is_pro_member else "Unlock Link 🔒"
                    )
                }
            )
        else:
            st.info("No auction listings currently match your selected margin and compliance criteria.")

    # --- TAB 2: RICH OPPORTUNITY CARDS ---
    with tab_cards:
        if displayed:
            for idx, deal in enumerate(displayed):
                is_unmasked = is_pro_member or (idx < 2)

                with st.container():
                    c_card1, c_card2, c_card3 = st.columns([3, 2, 1])

                    with c_card1:
                        st.markdown(f"### {deal.get('make', '').title()} {deal.get('model', '').title()} &nbsp; `[{deal.get('source_site', 'Auction')}]`")
                        st.caption(deal.get("title", ""))
                        st.write(deal.get("compliance_badge", "Standard"))

                    with c_card2:
                        st.write(f"**Current Bid:** ${deal.get('current_bid', 0):.2f} | **Landed:** ${deal.get('total_landed_cost', 0):.2f}")
                        if is_unmasked:
                            st.write(f"**Est MA Retail:** ${deal.get('ma_retail', 0):.2f} | **Max Walk-Away:** ${deal.get('max_bid', 0):.2f}")
                            st.success(f"+${deal.get('net_profit', 0):.2f} Net Profit ({deal.get('margin_pct', 0):.1f}%)")
                        else:
                            st.write("**Est MA Retail:** Hidden | **Max Walk-Away:** `🔒 Locked`")
                            st.info("🔒 Subscribe to reveal target spread & max bid")

                    with c_card3:
                        st.write("")
                        if is_unmasked:
                            st.link_button("Open Lot Page ↗", deal.get("listing_url", "#"), use_container_width=True)
                        else:
                            st.link_button("Unlock Lot Link 🔒", STRIPE_PRO_TIER_URL, type="primary", use_container_width=True)

                    st.divider()
        else:
            st.info("No lots match the active filter criteria.")

    # --- TAB 3: DEAL SCREENER ---
    with tab_calc:
        st.subheader("Manual Deal Sizing Calculator")
        st.caption("Screen counter walk-ins, private collections, or estate catalogs:")

        sc_col1, sc_col2 = st.columns(2)
        with sc_col1:
            scr_title = st.text_input("Firearm Description", value="Smith & Wesson Model 19-4 .357 Mag 4-inch")
            scr_bid = st.number_input("Asking Price / Current Bid ($)", value=375.0, step=25.0)
            scr_bp = st.number_input("Buyer's Premium Rate (%)", value=18.0, step=1.0) / 100.0
            scr_category = st.radio("Classification", ["Handgun", "Long Gun"], horizontal=True)

        with sc_col2:
            scr_retail = st.number_input("National Used Comp (True Gun Value)", value=825.0, step=25.0)
            scr_preban = st.checkbox("Pre-September 1994 Manufacture? (+65% Local Demand)", value=False)
            scr_roster = st.checkbox("Massachusetts Target/Approved Roster Compliant?", value=True)

            shipping = 35.0 if scr_category == "Handgun" else 45.0
            landed = scr_bid + (scr_bid * scr_bp) + shipping + 20.0
            resale = scr_retail * 1.65 if scr_preban else scr_retail
            profit = resale - landed
            margin = (profit / resale * 100) if resale > 0 else 0.0
            max_bid = max(0.0, (resale - 150.0 - shipping - 20.0) / (1 + scr_bp))

        st.write("---")
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Landed Cost", f"${landed:.2f}")
        r2.metric("Projected Resale", f"${resale:.2f}")
        r3.metric("Projected Spread", f"${profit:.2f}", delta=f"{margin:.1f}% Margin")
        r4.metric("Walk-Away Ceiling", f"${max_bid:.2f}")

        if scr_bid <= max_bid and profit >= min_profit:
            st.success(f"✅ HIGH-MARGIN DEAL: Offer/bid up to ${max_bid:.2f} while retaining your ${min_profit:.0f} target profit.")
        else:
            st.error(f"❌ OVERPRICED: Maximum allowable bid is ${max_bid:.2f} to protect your ${min_profit:.0f} margin floor.")

    # --- TAB 4: TWO-STEP DEALER ONBOARDING & PAYMENT ---
    with tab_onboarding:
        st.subheader("Step 1: Create Dealer Profile")
        st.markdown("Set up your store details and notification preferences before activating your subscription.")

        form_col, info_col = st.columns([3, 2])

        with form_col:
            with st.form("dealer_profile_onboarding_form"):
                st.markdown("##### 🏢 Store & License Credentials")
                f_store_name = st.text_input("Store / FFL Legal Trade Name *", placeholder="e.g. Apex Defense & Sporting Goods")
                f_contact_name = st.text_input("Primary Contact / Licensee Name *", placeholder="e.g. John Miller")
                f_ffl = st.text_input("Federal Firearms License (FFL)", placeholder="e.g. 1-04-XXXXX (Optional for preview)")
                f_state = st.selectbox("Operating State Roster", ["MA", "NH", "PA", "RI", "CT", "Other"])

                st.markdown("##### 🔔 Alert & Refresh Notification Settings")
                f_email = st.text_input("Account Email (For Billing & Keys) *", placeholder="owner@store.com")
                f_phone = st.text_input("Mobile Phone Number (For Instant SMS) *", placeholder="508-555-0199")
                
                f_alert_on_refresh = st.checkbox("⚡ Send instant notifications as soon as new lots populate on refresh", value=True)
                f_discord_webhook = st.text_input("Discord Webhook URL (For Real-Time Push Alerts)", placeholder="https://discord.com/api/webhooks/...")

                submit_profile = st.form_submit_button("Save Profile & Unlock Subscription Step", use_container_width=True)

            if submit_profile:
                if f_store_name and f_contact_name and f_email and f_phone:
                    profile_payload = {
                        "timestamp": datetime.now().isoformat(),
                        "store_name": f_store_name,
                        "contact_name": f_contact_name,
                        "ffl_number": f_ffl,
                        "state": f_state,
                        "email": f_email,
                        "phone": f_phone,
                        "alert_on_refresh": f_alert_on_refresh,
                        "discord_webhook": f_discord_webhook,
                        "profile_completed": True
                    }
                    save_dealer_profile(profile_payload)
                    st.session_state["profile_submitted"] = True
                    st.session_state["saved_dealer_name"] = f_store_name
                    st.success("✅ Profile registered! Proceed to Step 2 below to complete subscription.")
                else:
                    st.error("Please complete all required fields (*).")

        with info_col:
            st.markdown("""
            <div style="background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 1.25rem;">
                <h4 style="color: #58a6ff; margin-top: 0;">What you get with Pro:</h4>
                <ul style="color: #c9d1d9; font-size: 0.9rem; line-height: 1.8;">
                    <li><strong>Real-time push alerts</strong> dispatched automatically when auctions refresh</li>
                    <li><strong>Direct auction links</strong> on GunBroker, HiBid, and Proxibid</li>
                    <li><strong>Pre-Ban & C&R exemption matching</strong> for Massachusetts & restricted states</li>
                    <li><strong>Walk-away max bid ceiling</strong> calculated on every firearm</li>
                    <li>Dedicated customer onboarding & roster updates</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)

        st.divider()

        # STEP 2: SUBSCRIPTION CHECKOUT (GATED UNTIL PROFILE SUBMITTED)
        st.subheader("Step 2: Activate Sourcing Subscription")
        profile_ready = st.session_state.get("profile_submitted", False)

        if profile_ready:
            st.success(f"Profile verified for **{st.session_state.get('saved_dealer_name', 'Your Store')}**.")
            p_col1, p_col2 = st.columns([2, 3])
            with p_col1:
                st.markdown("### $199 / month\n*Billed monthly. Cancel anytime.*")
                st.link_button("👉 Proceed to Stripe Secure Checkout", STRIPE_PRO_TIER_URL, type="primary", use_container_width=True)
            with p_col2:
                st.info("💡 **Instant Activation:** Once Stripe payment confirms, your Subscriber Key will be dispatched to your account email, and your Discord/SMS alert preferences will activate automatically.")
        else:
            st.warning("⚠️ **Step 2 Locked:** Please fill out and submit the store profile above in Step 1 to generate your account before subscribing.")

# Execute live auto-refreshing dashboard
render_live_catalog()
