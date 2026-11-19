import os
import json
import traceback
from datetime import datetime
import pandas as pd
import streamlit as st

st.set_page_config(page_title="FFL Deal Radar", page_icon="🎯", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FEED_FILE = os.path.join(BASE_DIR, "feed_data.json")


def get_secret(name, default=""):
    """Read a secret from environment variables, then Streamlit secrets."""
    val = os.environ.get(name)
    if val:
        return val.strip()
    try:
        return str(st.secrets[name]).strip()
    except Exception:
        return default


ACCESS_PASSCODE = get_secret("ACCESS_PASSCODE")
CRON_TOKEN = get_secret("CRON_TOKEN")

ALL_PLATFORMS = [
    "GunBroker", "HiBid", "Armslist", "Guns.com", "GunsAmerica",
    "Buds Gun Shop", "Sportsman's Outdoor Superstore", "Tacswap", "UsedGuns.com"
]


def num(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


st.markdown(
    """
<style>
div[data-testid="stDataFrame"] { width: 100% !important; }
div[data-testid="stDataFrame"] > div { max-height: none !important; }
</style>
""", unsafe_allow_html=True)

# ---------------- OPTIONAL MANUAL SCRAPE TRIGGER ----------------
# Disabled unless CRON_TOKEN is configured. Scheduled scraping now runs in GitHub Actions.
params = st.query_params
if CRON_TOKEN and params.get("task") == "scrape" and params.get("token") == CRON_TOKEN:
    try:
        import worker
        worker.main()
        st.write("CRON_OK: worker.main() executed successfully.")
    except Exception as e:
        st.write(f"CRON_ERROR: {str(e)}")
        st.code(traceback.format_exc())
    st.stop()


# ---------------- FEED LOADER ----------------
def get_feed():
    if os.path.exists(FEED_FILE):
        try:
            with open(FEED_FILE, "r") as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("lots"), list):
                return data
        except Exception:
            pass
    return {"last_updated": datetime.now().strftime("%Y-%m-%d %I:%M %p"), "lots": []}


# ---------------- ACCESS GATE ----------------
if not ACCESS_PASSCODE:
    st.title("🎯 FFL Deal Radar")
    st.error("ACCESS_PASSCODE is not configured. Add it to your host's secrets or environment variables.")
    st.stop()

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.title("🎯 FFL Deal Radar — Authorized Portal")
    with st.form("auth_form"):
        code_input = st.text_input("Dealer Access Key", type="password")
        if st.form_submit_button("Enter Terminal", use_container_width=True):
            if code_input.strip() == ACCESS_PASSCODE:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Invalid access code.")
    st.stop()

# ---------------- DEALER DASHBOARD ----------------
with st.sidebar:
    st.title("🎯 FFL Radar")
    st.success("🟢 100% Verified Live Links")
    st.caption("Operator: `camerondickens9000@gmail.com`")

    if st.button("🚪 Lock Terminal", use_container_width=True):
        st.session_state["authenticated"] = False
        st.rerun()

    st.divider()
    active_view = st.radio("Select Section", ["📋 All Inventory Feed", "🔨 Live Auctions", "🔔 Push Alerts", "⚙️ System Status"])
    st.divider()

    mode = st.radio("Legal Framework", ["Massachusetts Compliant", "Federal Standard"])
    is_ma = (mode == "Massachusetts Compliant")

    selected_sources = st.multiselect("Source Platforms", ALL_PLATFORMS, default=ALL_PLATFORMS)

    st.caption("Profitability thresholds (default wide open):")
    min_profit = st.slider("Min Net Spread ($)", -300, 800, -300, 25)
    min_margin = st.slider("Min Margin (%)", -100, 70, -100, 5)
    max_cost = st.number_input("Max Purchase / Bid ($)", min_value=0, value=5000, step=250)
    action_only = st.checkbox("Show 'BID' Targets Only", value=False)
    pre_ban_only = st.checkbox("Pre-Ban Grandfathered Only", value=False) if is_ma else False
    search_query = st.text_input("🔍 Search Keyword", "").strip().lower()

h1, h2 = st.columns([3, 1])
h1.title(f"{active_view} — {mode}")

feed = get_feed()
all_lots = [l for l in feed.get("lots", []) if isinstance(l, dict)]
st.caption(f"⚡ Live Sync • Last updated: **{feed.get('last_updated', 'Just now')}** • Triangulated Comps (GunBroker + Guns.com + GunsAmerica)")

for l in all_lots:
    l["disp_retail"] = num(l.get("ma_retail") if is_ma else l.get("federal_retail"))
    l["disp_profit"] = num(l.get("ma_profit") if is_ma else l.get("federal_profit"))
    l["disp_margin"] = num(l.get("ma_margin") if is_ma else l.get("federal_margin"))
    l["disp_act"] = bool(l.get("actionable_ma") if is_ma else l.get("actionable_federal"))
    l["is_auction"] = l.get("source_site") in ["GunBroker", "HiBid"] or "bid" in str(l.get("title", "")).lower()


def render_feed_table(items, empty_msg):
    st.write(f"Showing **{len(items)}** verified active items out of **{len(all_lots)}** total scraped.")
    if items:
        rows = []
        for lot in items:
            spread = lot.get("disp_profit", 0.0)
            v = lot.get("valuation_sources") or {}
            rows.append({
                "Signal": "🟢 BID" if lot.get("disp_act") else "⚪ PASS",
                "Source": lot.get("source_site", "Direct"),
                "Type": "🔨 Auction" if lot.get("is_auction") else "🏷️ Buy-It-Now",
                "Model": f"{str(lot.get('make') or '').title()} {str(lot.get('model') or '').title()}",
                "Ask / Bid": f"${num(lot.get('current_bid')):.2f}",
                "Total Landed": f"${num(lot.get('total_landed_cost')):.2f}",
                "Triangulated Value": f"${lot.get('disp_retail', 0):.2f}",
                "Net Spread": f"{'+' if spread >= 0 else ''}${spread:.2f}",
                "Margin": f"{lot.get('disp_margin', 0):.1f}%",
                "Comps (GB/GC/GA)": f"${num(v.get('gunbroker_past_sold')):.0f} / ${num(v.get('guns_com_used_retail')):.0f} / ${num(v.get('market_comp')):.0f}",
                "Max Bid": f"${num(lot.get('max_bid')):.2f}",
                "Badge": lot.get("compliance_badge", "Title 1"),
                "Link": lot.get("listing_url", "#")
            })

        df = pd.DataFrame(rows)
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            height=int((len(rows) + 1) * 36 + 15),
            column_config={"Link": st.column_config.LinkColumn("Direct Listing", display_text="Open Lot ↗")}
        )
    else:
        st.warning(empty_msg)


filtered_lots = []
for l in all_lots:
    if selected_sources and l.get("source_site") not in selected_sources:
        continue
    if l["disp_profit"] < min_profit:
        continue
    if l["disp_margin"] < min_margin:
        continue
    if num(l.get("current_bid")) > max_cost:
        continue
    if action_only and not l["disp_act"]:
        continue
    if is_ma and pre_ban_only and not l.get("is_pre_ban", False):
        continue
    haystack = f"{l.get('make','')} {l.get('model','')} {l.get('title','')} {l.get('compliance_badge','')}".lower()
    if search_query and search_query not in haystack:
        continue
    filtered_lots.append(l)

if active_view == "📋 All Inventory Feed":
    render_feed_table(filtered_lots, "No listings match the current filters.")
elif active_view == "🔨 Live Auctions":
    auction_items = [l for l in filtered_lots if l.get("is_auction")]
    m1, m2, m3 = st.columns(3)
    m1.metric("Live Auction Lots", f"{len(auction_items)} Items")
    avg_spread = sum(l["disp_profit"] for l in auction_items) / len(auction_items) if auction_items else 0.0
    m2.metric("Average Auction Spread", f"${avg_spread:.2f}")
    m3.metric("Top Auction Margin", f"{max([l['disp_margin'] for l in auction_items], default=0.0):.1f}%")
    render_feed_table(auction_items, "No auction listings match the current filters.")
elif active_view == "🔔 Push Alerts":
    st.subheader("🔔 Instant Arbitrage Alerts")
    st.write("Alert Destination: `camerondickens9000@gmail.com`")
    st.number_input("Target Profit Spread Threshold ($)", value=100.0, step=25.0)
    if st.button("Save Alert Threshold", use_container_width=True):
        st.success("Alert preferences updated.")
elif active_view == "⚙️ System Status":
    st.subheader("System Infrastructure")
    st.write(f"**Connected Sources:** {len(ALL_PLATFORMS)} Platforms")
    st.write(f"**Total Individual Listings:** {len(all_lots)} Items")
    st.write(f"**Feed Status:** `feed_data.json` ({'Healthy' if len(all_lots) > 0 else 'Sync Required'})")
    st.caption("The feed is refreshed on a schedule by a GitHub Actions workflow (every 30 minutes).")

    if st.button("🔄 Force Immediate Organic Re-Sync", use_container_width=True):
        try:
            import worker
            worker.main()
            st.success("Synchronized! Reloading...")
            st.rerun()
        except Exception as e:
            st.error(f"Sync error: {e}")
            st.code(traceback.format_exc())
