import os
import json
import subprocess
import threading
from datetime import datetime
import streamlit as st

@@ -36,15 +37,18 @@
st.session_state.authenticated = False
st.rerun()

# --- BACKGROUND TRIGGER HANDLING ---
# --- NON-BLOCKING BACKGROUND TRIGGER HANDLING ---
query_params = st.query_params
if query_params.get("task") == "scrape" and query_params.get("token") == "DEALER2026":
    st.sidebar.info("Triggering background sync...")
    try:
        subprocess.run(["python", "worker.py"], check=True)
        st.sidebar.success("Sync completed successfully!")
    except Exception as e:
        st.sidebar.error(f"Sync failed: {e}")
    def run_async_worker():
        try:
            subprocess.run(["python", "worker.py"], check=True)
        except Exception as e:
            print(f"Async worker error: {e}")

    # Fire off worker asynchronously so cron-job.org gets an instant 200 OK without timeout
    threading.Thread(target=run_async_worker, daemon=True).start()
    st.sidebar.info("Background sync task initiated asynchronously.")

# --- LOAD FEED DATA ---
def load_feed():
@@ -105,23 +109,18 @@ def load_feed():
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
