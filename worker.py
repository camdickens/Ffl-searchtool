import os
import json
import subprocess
from datetime import datetime
import streamlit as st

FEED_FILE = "feed_data.json"
PASSCODE = "dealer2026"

st.set_page_config(
    page_title="MA FFL Arbitrage & Roster Finder",
    page_icon="🔥",
    layout="wide"
)

# --- AUTHENTICATION GATE ---
st.sidebar.header("🔐 Dealer Authentication")
user_pass = st.sidebar.text_input("Enter Passcode", type="password")

if user_pass != PASSCODE:
    st.warning("Please enter the authorized dealer passcode to access live inventory feeds.")
    st.stop()

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
st.title("🔥 MA FFL Live Arbitrage & Compliance Terminal")
st.markdown(f"**Last Synchronized:** {feed_data.get('last_updated', 'Unknown')} | **Active Verified Lots:** {len(lots)}")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total Scraped Feed", len(lots))
with col2:
    actionable_ma_count = sum(1 for l in lots if l.get("actionable_ma", False))
    st.metric("Actionable MA Spreads ($100+)", actionable_ma_count)
with col3:
    pre_ban_count = sum(1 for l in lots if l.get("is_pre_ban", False))
    st.metric("Pre-Ban Grandfathered", pre_ban_count)
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

# --- FILTER CONTROLS ---
st.sidebar.header("Filter Inventory")
min_profit = st.sidebar.slider("Minimum MA Profit ($)", min_value=0, max_value=500, value=75, step=25)
pre_ban_only = st.sidebar.checkbox("Show Pre-Ban / Grandfathered Only", value=False)
selected_source = st.sidebar.selectbox("Source Platform", ["All", "GunBroker", "Guns.com", "Armslist"])

filtered_lots = []
for lot in lots:
    if lot.get("ma_profit", 0) < min_profit:
        continue
    if pre_ban_only and not lot.get("is_pre_ban", False):
        continue
    if selected_source != "All" and lot.get("source_site") != selected_source:
        continue
    filtered_lots.append(lot)

st.subheader(f"Filtered Opportunities ({len(filtered_lots)} results)")

if not filtered_lots:
    st.info("No active listings match your current filter parameters. Try lowering the profit threshold or running a manual sync.")
else:
    # Prepare display table
    display_data = []
    for lot in filtered_lots:
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

    # Render table using current width parameter
    st.dataframe(
        display_data,
        width='stretch',
        column_config={
            "URL": st.column_config.LinkColumn("Direct Link"),
            "MA Profit ($)": st.column_config.NumberColumn(format="$%.2f"),
            "Ask ($)": st.column_config.NumberColumn(format="$%.2f"),
            "Landed ($)": st.column_config.NumberColumn(format="$%.2f"),
            "MA Retail ($)": st.column_config.NumberColumn(format="$%.2f"),
        },
        hide_index=True
    )
