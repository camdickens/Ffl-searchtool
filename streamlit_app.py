import streamlit as st
import pandas as pd
from models import RawAuctionLot
from margin_engine import evaluate_opportunity

# Page Setup
st.set_page_config(page_title="FFL Inventory Sourcing Engine", layout="wide")
st.title("🎯 FFL Sourcing & Arbitrage Dashboard")
st.caption("Automated auction scraping, landed cost calculation, and MA compliance filtering")

# --- SIDEBAR CONTROLS ---
with st.sidebar:
    st.header("Sourcing Filters")
    min_profit = st.slider("Minimum Net Profit ($)", min_value=50, max_value=500, value=150, step=25)
    min_margin = st.slider("Minimum Margin (%)", min_value=10, max_value=50, value=30, step=5)
    
    st.divider()
    filter_actionable = st.checkbox("Show Only Buy/Bid Opportunities", value=True)
    filter_pre_ban = st.checkbox("Pre-Ban Grandfathered Only", value=False)
    filter_ma_roster = st.checkbox("MA Roster / Compliant Only", value=False)
    
    st.divider()
    run_scrape = st.button("🔄 Check Auctions Now", type="primary")

# --- DATA / ENGINE INTEGRATION ---
# Mock TGV Reference Cache (Model -> National Baseline Retail)
MOCK_TGV_CACHE = {
    ("smith & wesson", "model 19"): 850.0,
    ("colt", "ar-15 sporter"): 1100.0,
    ("glock", "19 gen 5"): 520.0,
    ("ruger", "security 9"): 340.0,
}

def resolve_entity(title: str):
    t = title.lower()
    if "model 19" in t or "s&w 19" in t:
        return "smith & wesson", "model 19", MOCK_TGV_CACHE[("smith & wesson", "model 19")]
    elif "colt" in t and "ar-15" in t:
        return "colt", "ar-15 sporter", MOCK_TGV_CACHE[("colt", "ar-15 sporter")]
    elif "glock" in t and "19" in t:
        return "glock", "19 gen 5", MOCK_TGV_CACHE[("glock", "19 gen 5")]
    elif "security 9" in t:
        return "ruger", "security 9", MOCK_TGV_CACHE[("ruger", "security 9")]
    return "Unknown", "Unknown", 0.0

# Sample Auction Feed
sample_lots = [
    RawAuctionLot(
        lot_id="LOT-401",
        source_site="estate-auctions.com",
        title="Smith & Wesson Model 19-3 .357 Mag Pinned & Recessed, 1974 Mfg w/ Box",
        current_bid=340.0,
        listing_url="https://auction.example.com/lot/401",
        is_handgun=True
    ),
    RawAuctionLot(
        lot_id="LOT-402",
        source_site="regional-bid.com",
        title="Pre-Ban Colt AR-15 Sporter Match HBAR 5.56 Rifle",
        current_bid=720.0,
        listing_url="https://auction.example.com/lot/402",
        is_handgun=False
    ),
    RawAuctionLot(
        lot_id="LOT-403",
        source_site="liquidations.com",
        title="Glock 19 Gen 5 9mm (Used, 2 Mags)",
        current_bid=410.0,
        listing_url="https://auction.example.com/lot/403",
        is_handgun=True
    ),
    RawAuctionLot(
        lot_id="LOT-404",
        source_site="midwest-firearms.com",
        title="Ruger Security 9 9mm Pistol",
        current_bid=280.0,
        listing_url="https://auction.example.com/lot/404",
        is_handgun=True
    ),
]

# Run Analysis
evaluated = []
for lot in sample_lots:
    make, model, tgv_price = resolve_entity(lot.title)
    if tgv_price > 0:
        res = evaluate_opportunity(lot, make, model, tgv_price)
        
        # Override dynamic sidebar criteria
        res.actionable_deal = (
            res.projected_net_profit >= min_profit and 
            res.projected_margin_pct >= min_margin and 
            res.current_bid <= res.recommended_max_bid
        )
        evaluated.append(res)

# Apply UI Filters
filtered = evaluated
if filter_actionable:
    filtered = [x for x in filtered if x.actionable_deal]
if filter_pre_ban:
    filtered = [x for x in filtered if x.is_pre_ban]
if filter_ma_roster:
    filtered = [x for x in filtered if x.ma_roster_compliant]

# --- METRIC CARDS ---
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Opportunities", len(evaluated))
col2.metric("Actionable Deals", len([x for x in evaluated if x.actionable_deal]))
col3.metric("Pre-Ban Matches", len([x for x in evaluated if x.is_pre_ban]))
col4.metric("Avg Projected Profit", f"${sum(x.projected_net_profit for x in evaluated)/len(evaluated):.2f}" if evaluated else "$0")

st.divider()

# --- TABLE DISPLAY ---
if filtered:
    table_data = []
    for x in filtered:
        status = "🟢 BID / BUY" if x.actionable_deal else "🔴 PASS"
        flags = []
        if x.is_pre_ban: flags.append("Pre-Ban")
        if x.is_curio_relic: flags.append("C&R (50+yr)")
        if x.ma_roster_compliant and not x.is_pre_ban and not x.is_curio_relic: flags.append("MA Roster")
        if not x.ma_roster_compliant: flags.append("Off-Roster")

        table_data.append({
            "Status": status,
            "Lot ID": x.lot_id,
            "Model": f"{x.normalized_make.title()} {x.normalized_model.title()}",
            "Current Bid": f"${x.current_bid:.2f}",
            "Landed Cost": f"${x.total_landed_cost:.2f}",
            "MA Retail": f"${x.adjusted_local_retail:.2f}",
            "Net Profit": f"${x.projected_net_profit:.2f}",
            "Margin %": f"{x.projected_margin_pct:.1f}%",
            "Max Bid": f"${x.recommended_max_bid:.2f}",
            "Compliance Flags": ", ".join(flags),
            "Auction Link": x.source_url
        })
    
    st.dataframe(pd.DataFrame(table_data), use_container_width=True, hide_index=True)
else:
    st.info("No lots match the selected margin and compliance criteria.")
