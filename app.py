import os
import json
import subprocess
from datetime import datetime
import streamlit as st

FEED_FILE = "feed_data.json"
PASSCODE = "dealer2026"

st.set_page_config(
    page_title="FFL Arbitrage & Sourcing Terminal",
    page_icon="🔥",
    layout="wide"
)

# --- AUTHENTICATION & SESSION PERSISTENCE ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

st.sidebar.header("🔐 Dealer Authentication")
remember_me = st.sidebar.checkbox("Remember Me (Stay Logged In)", value=True)

if not st.session_state.authenticated:
    user_pass = st.sidebar.text_input("Enter Passcode", type="password")
    if user_pass == PASSCODE:
        st.session_state.authenticated = True
        st.rerun()
    elif user_pass != "":
        st.sidebar.error("Incorrect passcode.")
        st.stop()
    else:
        st.warning("Please enter the authorized dealer passcode to access live inventory feeds.")
        st.stop()
else:
    if st.sidebar.button("🔒 Lock Terminal"):
        st.session_state.authenticated = False
        st.rerun()

# --- BACKGROUND TRIGGER HANDLING ---
query_params = st.query_params
if query_params.get("task") == "scrape" and query_params.get("token") == "DEALER2026":
    st.sidebar.info("Triggering background sync...")
    try:
        subprocess.run(["python", "worker.py"], check=True)
        st.sidebar.success("Sync completed successfully!")
    except Exception as e:
        st.sidebar.error(f"Sync failed: {e}")

# --- LOAD FEED DATA ---
def load_feed():
    if os.path.exists(FEED_FILE):
        try:
            with open(FEED_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {"last_updated": "Never", "total_scraped": 0, "lots": []}
    return {"last_updated": "Never", "total_scraped": 0, "lots": []}

feed_data = load_feed()
lots = feed_data.get("lots", [])

# --- HEADER & METRICS ---
st.title("🔥 FFL Multi-Platform Arbitrage & Compliance Terminal")
st.markdown(f"**Last Synchronized:** {feed_data.get('last_updated', 'Unknown')} | **Active Verified Lots:** {len(lots)}")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total Scraped Feed", len(lots))
with col2:
    pre_ban_count = sum(1 for l in lots if l.get("is_pre_ban", False))
    st.metric("Pre-Ban / Grandfathered", pre_ban_count)
with col3:
    actionable_count = sum(1 for l in lots if l.get("federal_profit", 0) >= 75)
    st.metric("Actionable Spreads ($75+)", actionable_count)
with col4:
    if st.button("🔄 Run Manual Sync Now", width='stretch'):
        with st.spinner("Executing multi-platform live scrape..."):
            try:
                subprocess.run(["python", "worker.py"], check=True)
                st.success("Sync complete! Refreshing feed...")
                st.rerun()
            except Exception as e:
                st.error(f"Error running worker: {e}")

st.markdown("---")

# --- ADVANCED FILTER CONTROLS (SIDEBAR) ---
st.sidebar.header("🔍 Inventory Filters")

market_mode = st.sidebar.radio("Compliance & Pricing Mode", ["MA FFL Roster & Arbitrage", "Federal / Nationwide Market"])

search_query = st.sidebar.text_input("Search Make / Model", "").strip().lower()
selected_source = st.sidebar.selectbox("Source Platform", ["All", "GunBroker", "Guns.com", "Classic Firearms"])

if market_mode == "MA FFL Roster & Arbitrage":
    min_profit = st.sidebar.slider("Minimum MA Profit ($)", min_value=-200, max_value=500, value=0, step=25)
    pre_ban_only = st.sidebar.checkbox("Show Pre-Ban / Grandfathered Only", value=False)
else:
    min_profit = st.sidebar.slider("Minimum Federal Profit ($)", min_value=-200, max_value=500, value=0, step=25)
    pre_ban_only = False

max_landed = st.sidebar.slider("Max Landed Cost ($)", min_value=100, max_value=4000, value=4000, step=100)
max_ask = st.sidebar.slider("Max Ask Price ($)", min_value=100, max_value=4000, value=4000, step=100)

# --- APPLY FILTERS ---
filtered_lots = []
for lot in lots:
    # Source filter
    if selected_source != "All" and lot.get("source_site") != selected_source:
        continue
    # Pre-ban filter
    if pre_ban_only and not lot.get("is_pre_ban", False):
        continue
    # Search query filter
    if search_query:
        combined_text = f"{lot.get('make', '')} {lot.get('model', '')} {lot.get('title', '')}".lower()
        if search_query not in combined_text:
            continue
    # Price limits
    if lot.get("total_landed_cost", 0) > max_landed:
        continue
    if lot.get("current_bid", 0) > max_ask:
        continue
    # Profit threshold based on mode
    if market_mode == "MA FFL Roster & Arbitrage":
        if lot.get("ma_profit", 0) < min_profit:
            continue
    else:
        if lot.get("federal_profit", 0) < min_profit:
            continue
            
    filtered_lots.append(lot)

st.subheader(f"Filtered Opportunities ({len(filtered_lots)} results) — [{market_mode}]")

if not filtered_lots:
    st.info("No active listings match your current filter parameters. Try expanding your profit threshold or price range.")
else:
    display_data = []
    for lot in filtered_lots:
        if market_mode == "MA FFL Roster & Arbitrage":
            display_data.append({
                "Source": lot.get("source_site"),
                "Title": lot.get("title"),
                "Make": lot.get("make"),
                "Model": lot.get("model"),
                "Ask ($)": lot.get("current_bid"),
                "Landed ($)": lot.get("total_landed_cost"),
                "MA Retail ($)": lot.get("ma_retail"),
                "MA Profit ($)": lot.get("ma_profit"),
                "Margin (%)": lot.get("ma_margin"),
                "Badge": lot.get("compliance_badge"),
                "URL": lot.get("listing_url")
            })
        else:
            display_data.append({
                "Source": lot.get("source_site"),
                "Title": lot.get("title"),
                "Make": lot.get("make"),
                "Model": lot.get("model"),
                "Ask ($)": lot.get("current_bid"),
                "Landed ($)": lot.get("total_landed_cost"),
                "Fed Retail ($)": lot.get("federal_retail"),
                "Fed Profit ($)": lot.get("federal_profit"),
                "Badge": lot.get("compliance_badge"),
                "URL": lot.get("listing_url")
            })

    st.dataframe(
        display_data,
        width='stretch',
        column_config={
            "URL": st.column_config.LinkColumn("Direct Link"),
            "MA Profit ($)": st.column_config.NumberColumn(format="$%.2f"),
            "Fed Profit ($)": st.column_config.NumberColumn(format="$%.2f"),
            "Ask ($)": st.column_config.NumberColumn(format="$%.2f"),
            "Landed ($)": st.column_config.NumberColumn(format="$%.2f"),
            "MA Retail ($)": st.column_config.NumberColumn(format="$%.2f"),
            "Fed Retail ($)": st.column_config.NumberColumn(format="$%.2f"),
        },
        hide_index=True
    )
