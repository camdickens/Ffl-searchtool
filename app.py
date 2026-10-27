import streamlit as st
import pandas as pd
import re
from dataclasses import dataclass
from typing import Optional

# ---------------------------------------------------------
# 1. CONFIGURATION & CONSTANTS
# ---------------------------------------------------------
CONFIG = {
    "DEFAULT_BUYERS_PREMIUM": 0.18,      # 18% standard auction house premium
    "ESTIMATED_SHIPPING_HANDGUN": 35.0,  # 2-day insured
    "ESTIMATED_SHIPPING_LONGGUN": 45.0,  # Ground insured
    "INBOUND_TRANSFER_COST": 0.0,        # $0 if dealer's own license
    "CLEANING_RECONDITIONING": 20.0,     # Labor/cleaning supplies
    "MA_PRE_BAN_MULTIPLIER": 1.65,       # ~65% premium over national median for pre-1994
    "MA_OFF_ROSTER_PREMIUM": 175.0,      # Frame transfer / target exemption local premium
}

# Massachusetts Approved / Target Roster Reference Whitelist
MA_ROSTER_WHITELIST = {
    "ruger": ["mark iv", "mark iii", "lcp", "security 9", "sp101", "gp100"],
    "smith & wesson": ["m&p 2.0", "model 19", "model 686", "shield plus", "model 10", "model 66", "model 642"],
    "sig sauer": ["p365", "p320", "p226", "p229"],
    "beretta": ["92fs", "80x cheetah", "tomcat"],
    "colt": ["python", "king cobra", "1911 standard government"],
    "glock": [],  # Off-roster; requires frame transfer
}

PRE_BAN_PATTERNS = [
    r"pre[\s\-_]?ban",
    r"pre[\s\-_]?1994",
    r"manufactured\s+19[0-8][0-9]",
    r"colt\s+ar-15\s+sporter",
    r"norinco\s+56s",
    r"polytech\s+legend",
    r"daewoo\s+k2",
]

# Baseline valuation benchmark cache (National Used Median Comps)
TGV_BENCHMARK_CACHE = {
    ("smith & wesson", "model 19"): 850.0,
    ("colt", "ar-15 sporter"): 1100.0,
    ("glock", "19 gen 5"): 520.0,
    ("ruger", "security 9"): 340.0,
    ("sig sauer", "p365"): 450.0,
    ("beretta", "92fs"): 525.0,
}

# ---------------------------------------------------------
# 2. DATA MODELS
# ---------------------------------------------------------
@dataclass
class AuctionLot:
    lot_id: str
    source_site: str
    title: str
    current_bid: float
    listing_url: str
    is_handgun: bool = True
    buyers_premium_pct: float = 0.18

@dataclass
class EvaluationResult:
    lot_id: str
    title: str
    make: str
    model: str
    current_bid: float
    total_landed_cost: float
    national_retail: float
    ma_retail: float
    net_profit: float
    margin_pct: float
    max_bid: float
    is_pre_ban: bool
    is_curio_relic: bool
    ma_roster_compliant: bool
    actionable_deal: bool
    listing_url: str

# ---------------------------------------------------------
# 3. COMPLIANCE & MARGIN ENGINE
# ---------------------------------------------------------
def check_curio_relic(text: str) -> bool:
    """True if firearm is >= 50 years old (1976 or older)."""
    current_year = 2026
    match = re.search(r"\b(19[0-7][0-9]|18[0-9]{2})\b", text)
    if match:
        year = int(match.group(1))
        return (current_year - year) >= 50
    return False

def evaluate_compliance(make: str, model: str, title: str) -> tuple[bool, bool, bool]:
    text = f"{make} {model} {title}".lower()
    is_pre_ban = any(re.search(p, text) for p in PRE_BAN_PATTERNS)
    is_cr = check_curio_relic(text)
    
    make_clean = make.lower()
    model_clean = model.lower()
    ma_roster = False
    if make_clean in MA_ROSTER_WHITELIST:
        if any(appr in model_clean for appr in MA_ROSTER_WHITELIST[make_clean]):
            ma_roster = True
            
    if is_pre_ban or is_cr:
        ma_roster = True

    return is_pre_ban, is_cr, ma_roster

def resolve_entity(title: str) -> tuple[str, str, float]:
    t = title.lower()
    if "model 19" in t or "s&w 19" in t:
        return "smith & wesson", "model 19", TGV_BENCHMARK_CACHE[("smith & wesson", "model 19")]
    elif "colt" in t and "ar-15" in t:
        return "colt", "ar-15 sporter", TGV_BENCHMARK_CACHE[("colt", "ar-15 sporter")]
    elif "glock" in t and "19" in t:
        return "glock", "19 gen 5", TGV_BENCHMARK_CACHE[("glock", "19 gen 5")]
    elif "security 9" in t:
        return "ruger", "security 9", TGV_BENCHMARK_CACHE[("ruger", "security 9")]
    elif "p365" in t:
        return "sig sauer", "p365", TGV_BENCHMARK_CACHE[("sig sauer", "p365")]
    elif "92fs" in t:
        return "beretta", "92fs", TGV_BENCHMARK_CACHE[("beretta", "92fs")]
    return "Custom", "Firearm", 0.0

def evaluate_lot(lot: AuctionLot, make: str, model: str, national_retail: float, min_profit: float, min_margin: float) -> EvaluationResult:
    bp_cost = lot.current_bid * lot.buyers_premium_pct
    shipping = CONFIG["ESTIMATED_SHIPPING_HANDGUN"] if lot.is_handgun else CONFIG["ESTIMATED_SHIPPING_LONGGUN"]
    overhead = shipping + CONFIG["INBOUND_TRANSFER_COST"] + CONFIG["CLEANING_RECONDITIONING"]
    landed_cost = lot.current_bid + bp_cost + overhead

    is_pre_ban, is_cr, ma_roster = evaluate_compliance(make, model, lot.title)

    # MA Local Demand Multiplier
    ma_retail = national_retail
    if is_pre_ban:
        ma_retail = national_retail * CONFIG["MA_PRE_BAN_MULTIPLIER"]
    elif not ma_roster and lot.is_handgun:
        ma_retail = national_retail + CONFIG["MA_OFF_ROSTER_PREMIUM"]

    net_profit = ma_retail - landed_cost
    margin_pct = (net_profit / ma_retail * 100) if ma_retail > 0 else 0.0

    target_profit = max(min_profit, ma_retail * (min_margin / 100.0))
    allowable_landed = ma_retail - target_profit
    max_bid = max(0.0, (allowable_landed - overhead) / (1 + lot.buyers_premium_pct))

    is_actionable = (net_profit >= min_profit) and (margin_pct >= min_margin) and (lot.current_bid <= max_bid)

    return EvaluationResult(
        lot_id=lot.lot_id,
        title=lot.title,
        make=make,
        model=model,
        current_bid=lot.current_bid,
        total_landed_cost=round(landed_cost, 2),
        national_retail=round(national_retail, 2),
        ma_retail=round(ma_retail, 2),
        net_profit=round(net_profit, 2),
        margin_pct=round(margin_pct, 1),
        max_bid=round(max_bid, 2),
        is_pre_ban=is_pre_ban,
        is_curio_relic=is_cr,
        ma_roster_compliant=ma_roster,
        actionable_deal=is_actionable,
        listing_url=lot.listing_url
    )

# ---------------------------------------------------------
# 4. STREAMLIT USER INTERFACE
# ---------------------------------------------------------
st.set_page_config(page_title="FFL Inventory Sourcing", layout="wide")
st.title("🎯 FFL Sourcing & Arbitrage Dashboard")
st.caption("Live Auction Landed Costs, True Gun Value Comps & Massachusetts Compliance Engine")

# Sidebar Controls
with st.sidebar:
    st.header("Sourcing Parameters")
    min_profit = st.slider("Min Net Profit ($)", min_value=50, max_value=500, value=150, step=25)
    min_margin = st.slider("Min Margin (%)", min_value=10, max_value=50, value=30, step=5)
    
    st.divider()
    filter_actionable = st.checkbox("Show 'BID / BUY' Only", value=True)
    filter_pre_ban = st.checkbox("Pre-Ban Grandfathered Only", value=False)
    filter_ma_roster = st.checkbox("MA Compliant Only", value=False)

tab1, tab2 = st.tabs(["📊 Live Auction Lots", "🧮 Quick Deal Calculator"])

# --- TAB 1: AUCTION FEED ---
with tab1:
    sample_catalog = [
        AuctionLot("LOT-401", "estate-auctions.com", "Smith & Wesson Model 19-3 .357 Mag P&R 1974 w/ Box", 340.0, "https://auction.example.com/lot/401", True),
        AuctionLot("LOT-402", "regional-bid.com", "Pre-Ban Colt AR-15 Sporter Match HBAR 5.56", 720.0, "https://auction.example.com/lot/402", False),
        AuctionLot("LOT-403", "liquidations.com", "Glock 19 Gen 5 9mm (Used, 2 Mags)", 410.0, "https://auction.example.com/lot/403", True),
        AuctionLot("LOT-404", "midwest-firearms.com", "Ruger Security 9 9mm Pistol", 280.0, "https://auction.example.com/lot/404", True),
        AuctionLot("LOT-405", "proxibid.com", "Sig Sauer P365 9mm Nitron Micro-Compact", 290.0, "https://auction.example.com/lot/405", True),
    ]

    results = []
    for lot in sample_catalog:
        make, model, nat_val = resolve_entity(lot.title)
        if nat_val > 0:
            results.append(evaluate_lot(lot, make, model, nat_val, min_profit, min_margin))

    # Metric Row
    c1, c2, c3, c4 = st.columns(4)
    actionable_count = len([r for r in results if r.actionable_deal])
    avg_profit = sum(r.net_profit for r in results) / len(results) if results else 0
    c1.metric("Catalog Lots", len(results))
    c2.metric("Actionable Deals", actionable_count)
    c3.metric("Pre-Ban Matches", len([r for r in results if r.is_pre_ban]))
    c4.metric("Avg Projected Profit", f"${avg_profit:.2f}")

    # Filtering
    display_list = results
    if filter_actionable:
        display_list = [r for r in display_list if r.actionable_deal]
    if filter_pre_ban:
        display_list = [r for r in display_list if r.is_pre_ban]
    if filter_ma_roster:
        display_list = [r for r in display_list if r.ma_roster_compliant]

    st.write("")
    if display_list:
        rows = []
        for r in display_list:
            status = "🟢 BID / BUY" if r.actionable_deal else "🔴 PASS"
            flags = []
            if r.is_pre_ban: flags.append("Pre-Ban")
            if r.is_curio_relic: flags.append("C&R (50+yr)")
            if r.ma_roster_compliant and not r.is_pre_ban and not r.is_curio_relic: flags.append("MA Roster")
            if not r.ma_roster_compliant: flags.append("Off-Roster")

            rows.append({
                "Action": status,
                "Model": f"{r.make.title()} {r.model.title()}",
                "Bid": f"${r.current_bid:.2f}",
                "Landed Cost": f"${r.total_landed_cost:.2f}",
                "MA Retail": f"${r.ma_retail:.2f}",
                "Est. Profit": f"${r.net_profit:.2f}",
                "Margin": f"{r.margin_pct:.1f}%",
                "Max Walk-Away Bid": f"${r.max_bid:.2f}",
                "Flags": ", ".join(flags),
                "Auction URL": r.listing_url
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("No lots match the selected filters. Lower your minimum profit or margin sliders in the sidebar.")

# --- TAB 2: MANUAL DEAL EVALUATOR ---
with tab2:
    st.subheader("Evaluate Any Gun on the Fly")
    st.caption("Enter an auction lot manually from your phone to check landed costs and max bid:")

    col_a, col_b = st.columns(2)
    with col_a:
        calc_title = st.text_input("Firearm Description", value="Pre-Ban Colt AR-15 Sporter Match")
        calc_bid = st.number_input("Current Bid ($)", value=650.0, step=25.0)
        calc_bp = st.number_input("Buyer's Premium (%)", value=18.0, step=1.0) / 100.0
        calc_type = st.selectbox("Category", ["Handgun", "Rifle / Shotgun"])
    with col_b:
        calc_retail = st.number_input("National Retail Comp ($)", value=1050.0, step=25.0)
        calc_pre_ban = st.checkbox("Is Pre-September 1994 Grandfathered?", value=True)
        calc_roster = st.checkbox("Massachusetts Roster Compliant?", value=True)

    custom_lot = AuctionLot(
        lot_id="MANUAL-01",
        source_site="Manual",
        title=calc_title,
        current_bid=calc_bid,
        listing_url="N/A",
        is_handgun=(calc_type == "Handgun"),
        buyers_premium_pct=calc_bp
    )

    custom_eval = evaluate_lot(
        custom_lot,
        make="Custom",
        model="Lot",
        national_retail=calc_retail,
        min_profit=min_profit,
        min_margin=min_margin
    )
    # Manual overrides from checkboxes
    if calc_pre_ban:
        custom_eval.ma_retail = calc_retail * CONFIG["MA_PRE_BAN_MULTIPLIER"]
        custom_eval.is_pre_ban = True
    custom_eval.net_profit = custom_eval.ma_retail - custom_eval.total_landed_cost
    custom_eval.margin_pct = (custom_eval.net_profit / custom_eval.ma_retail * 100) if custom_eval.ma_retail > 0 else 0.0

    st.divider()
    res1, res2, res3, res4 = st.columns(4)
    res1.metric("Landed Cost", f"${custom_eval.total_landed_cost:.2f}")
    res2.metric("Projected MA Retail", f"${custom_eval.ma_retail:.2f}")
    res3.metric("Projected Profit", f"${custom_eval.net_profit:.2f}", delta=f"{custom_eval.margin_pct:.1f}% Margin")
    res4.metric("Recommended Max Bid", f"${custom_eval.max_bid:.2f}")

    if custom_eval.current_bid <= custom_eval.max_bid and custom_eval.net_profit >= min_profit:
        st.success(f"✅ PROFITABLE DEAL: Current bid (${custom_eval.current_bid:.2f}) is below your walk-away threshold (${custom_eval.max_bid:.2f}).")
    else:
        st.error(f"❌ OVERPRICED: Do not bid above ${custom_eval.max_bid:.2f} to protect your ${min_profit:.0f} target profit.")
