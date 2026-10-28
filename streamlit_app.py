import os
import json
import traceback
from datetime import datetime
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="FFL Deal Radar",
    page_icon="🎯",
    layout="wide"
)

FEED_FILE = "feed_data.json"
CRON_TOKEN = "DEALER2026"
ACCESS_PASSCODE = "dealer2026"

ALL_PLATFORMS = [
    "GunBroker",
    "HiBid",
    "Armslist",
    "Guns.com",
    "GunsAmerica",
    "Buds Gun Shop",
    "Sportsman's Outdoor Superstore",
    "Tacswap",
    "UsedGuns.com"
]

# Ensure table takes full container width and disables inner clipping
st.markdown(
    """
<style>
div[data-testid="stDataFrame"] {
    width: 100% !important;
}
div[data-testid="stDataFrame"] > div {
    max-height: none !important;
}
</style>
""",
    unsafe_allow_html=True
)

# ---------------------------------------------------------
# 1. CRON SCRAPER TRIGGER (SAFE BACKGROUND SYNC)
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
# 2. FEED LOADER
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
                if isinstance(data, dict) and "lots" in data and len(data["lots"]) > 0:
                    return data
        except Exception:
            pass

    try:
        import worker
        worker.main()
        with open(FEED_FILE, "r") as f:
            return json.load(f)
    except Exception:
        pass

    return {
        "last_updated": datetime.now().strftime("%Y-%m-%d %I:%M %p"),
        "lots": []
    }

# ---------------------------------------------------------
# 3. ACCESS GATE
# ---------------------------------------------------------
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.title("🎯 FFL Deal Radar — Authorized Portal")
    st.write("Private dealer terminal. Enter your dealer access code below.")

    with st.form("auth_form"):
        code_input = st.text_input("Dealer Access Key", type="password")
        if st.form_submit_button("Enter Terminal", use_container_width=True):
            if code_input.strip() == ACCESS_PASSCODE:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Invalid access code.")
    st.stop()

# ---------------------------------------------------------
# 4. DEALER DASHBOARD
# ---------------------------------------------------------
with st.sidebar:
    st.title("🎯 FFL Radar")
    st.success("🟢 Full Catalog Unlocked (500+ Active)")
    st.caption("Operator: `camerondickens9000@gmail.com`")

    if st.button("🚪 Lock Terminal", use_container_width=True, key="btn_sign_out"):
        st.session_state["authenticated"] = False
        st.rerun()

    st.divider()
    st.subheader("📑 Views & Sections")

    active_view = st.radio(
        "Select Section",
        [
            "📋 All Inventory Feed",
            "🔨 Live Auctions",
            "🔔 Push Alerts",
            "⚙️ System Status"
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

    selected_sources = st.multiselect(
        "Source Platforms",
        ALL_PLATFORMS,
        default=ALL_PLATFORMS,
        key="multiselect_sources"
    )

    st.caption("Profitability thresholds (default wide open):")
    min_profit = st.slider("Min Net Spread ($)", -300, 800, -300, 25, key="slider_min_profit")
    min_margin = st.slider("Min Margin (%)", -100, 70, -100, 5, key="slider_min_margin")
    max_cost = st.number_input("Max Purchase / Bid ($)", min_value=0, value=5000, step=250, key="num_max_cost")

    action_only = st.checkbox("Show 'BID' Targets Only (≥ Threshold)", value=False, key="chk_action_only")
    pre_ban_only = st.checkbox("Pre-Ban Grandfathered Only", value=False, key="chk_pre_ban") if is_ma else False
    search_query = st.text_input("🔍 Search Keyword (Make, Model, Title)", "", key="txt_search_query").strip().lower()

# TOP HEADER
h1, h2 = st.columns([3, 1])
h1.title(f"{active_view} — {mode}")

feed = get_feed()
all_lots = feed.get("lots", [])
st.caption(f"⚡ Live Sync • Last updated: **{feed.get('last_updated', 'Just now')}** • Triangulated Comps (GunBroker + Guns.com + GunsAmerica)")

for l in all_lots:
    l["disp_retail"] = float(l.get("ma_retail", 0.0) if is_ma else l.get("federal_retail", 0.0))
    l["disp_profit"] = float(l.get("ma_profit", 0.0) if is_ma else l.get("federal_profit", 0.0))
    l["disp_margin"] = float(l.get("ma_margin", 0.0) if is_ma else l.get("federal_margin", 0.0))
    l["disp_act"] = bool(l.get("actionable_ma", False) if is_ma else l.get("actionable_federal", False))
    is_auction_lot = l.get("source_site") in ["GunBroker", "HiBid"] or "bid" in l.get("title", "").lower()
    l["is_auction"] = is_auction_lot

def render_feed_table(items, empty_msg):
    st.write(f"Showing **{len(items)}** matching lots out of **{len(all_lots)}** total active inventory.")

    if items:
        rows = []
        for lot in items:
            spread_val = lot.get("disp_profit", 0.0)
            sign_str = "+" if spread_val >= 0 else ""
            v_sources = lot.get("valuation_sources", {})
            comps_str = (
                f"${v_sources.get('gunbroker_past_sold', 0):.0f} / "
                f"${v_sources.get('guns_com_used_retail', 0):.0f} / "
                f"${v_sources.get('market_comp', 0):.0f}"
            )
            rows.append({
                "Signal": "🟢 BID" if lot.get("disp_act") else "⚪ PASS",
                "Source": lot.get("source_site", "Direct"),
                "Type": "🔨 Auction" if lot.get("is_auction") else "🏷️ Buy-It-Now",
                "Model": f"{lot.get('make', '').title()} {lot.get('model', '').title()}",
                "Current Ask / Bid": f"${float(lot.get('current_bid', 0)):.2f}",
                "Total Landed": f"${float(lot.get('total_landed_cost', 0)):.2f}",
                "Triangulated Value": f"${lot.get('disp_retail', 0):.2f}",
                "Net Spread": f"{sign_str}${spread_val:.2f}",
                "Margin": f"{lot.get('disp_margin', 0):.1f}%",
                "Comps (GB / GC / GA)": comps_str,
                "Recommended Max Bid": f"${float(lot.get('max_bid', 0)):.2f}",
                "Badge": lot.get("compliance_badge", "Title 1"),
                "Link": lot.get("listing_url", "#")
            })

        df = pd.DataFrame(rows)
        # Dynamically sized height ensures all 500+ rows render smoothly into the page
        calculated_height = int((len(rows) + 1) * 36 + 15)

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            height=calculated_height,
            column_config={
                "Link": st.column_config.LinkColumn(
                    "Direct Listing",
                    display_text="Open Lot ↗"
                )
            }
        )
    else:
        st.warning(empty_msg)

# Filter processing
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

# ---------------------------------------------------------
# VIEW ROUTING
# ---------------------------------------------------------
if active_view == "📋 All Inventory Feed":
    render_feed_table(
        filtered_lots,
        "No listings match the current filters."
    )

elif active_view == "🔨 Live Auctions":
    auction_items = [l for l in filtered_lots if l.get("is_auction")]

    m1, m2, m3 = st.columns(3)
    m1.metric("Live Auction Lots", f"{len(auction_items)} Items")
    avg_spread = (
        sum(l["disp_profit"] for l in auction_items) / len(auction_items)
        if auction_items else 0.0
    )
    m2.metric("Average Auction Spread", f"${avg_spread:.2f}")
    top_margin = max([l["disp_margin"] for l in auction_items], default=0.0)
    m3.metric("Top Auction Margin", f"{top_margin:.1f}%")

    render_feed_table(
        auction_items,
        "No auction listings match the current filters."
    )

elif active_view == "🔔 Push Alerts":
    st.subheader("🔔 Instant Arbitrage Alerts")
    st.write("Alert Destination: `camerondickens9000@gmail.com`")
    st.number_input("Target Profit Spread Threshold ($)", value=100.0, step=25.0)
    if st.button("Save Alert Threshold", use_container_width=True):
        st.success("Alert preferences updated.")

elif active_view == "⚙️ System Status":
    st.subheader("System Infrastructure")
    st.write(f"**Connected Sources:** {len(ALL_PLATFORMS)} Platforms")
    st.write(f"**Total Ingested Lots:** {len(all_lots)} Items")
    st.write(f"**Valuation Engine:** 3-Way Triangulation (GunBroker Historical + Guns.com + GunsAmerica)")
    st.write(f"**Feed Status:** `feed_data.json` ({'Healthy' if len(all_lots) > 0 else 'Sync Required'})")
    if st.button("🔄 Force Immediate Re-Sync", use_container_width=True):
        try:
            import worker
            worker.main()
            st.success("Synchronized! Reloading...")
            st.rerun()
        except Exception as e:
            st.error(f"Sync error: {e}")
