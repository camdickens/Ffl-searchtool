import streamlit as st
import pandas as pd
import re
import json
import os
from dataclasses import dataclass
from datetime import datetime

# -----------------------------------------------------------------------------
# 1. PAGE SETUP & CONFIGURATION
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="FFL Deal Radar | Sourcing & Arbitrage Engine",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

STRIPE_PRO_TIER_URL = "https://buy.stripe.com/test_replace_with_your_link"
DEALER_DB_FILE = "registered_dealers.json"

CONFIG = {
    "DEFAULT_BUYERS_PREMIUM": 0.18,
    "ESTIMATED_SHIPPING_HANDGUN": 35.0,
    "ESTIMATED_SHIPPING_LONGGUN": 45.0,
    "INBOUND_TRANSFER_COST": 0.0,
    "CLEANING_RECONDITIONING": 20.0,
    "MA_PRE_BAN_MULTIPLIER": 1.65,
    "MA_OFF_ROSTER_PREMIUM": 175.0,
}

MA_ROSTER_WHITELIST = {
    "ruger": ["mark iv", "mark iii", "lcp", "security 9", "sp101", "gp100"],
    "smith & wesson": ["m&p 2.0", "model 19", "model 686", "shield plus", "model 10", "model 66", "model 642"],
    "sig sauer": ["p365", "p320", "p226", "p229"],
    "beretta": ["92fs", "80x cheetah", "tomcat"],
    "colt": ["python", "king cobra", "1911 standard government"],
    "glock": [],
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

TGV_BENCHMARK_CACHE = {
    ("smith & wesson", "model 19"): 850.0,
    ("colt", "ar-15 sporter"): 1100.0,
    ("glock", "19 gen 5"): 520.0,
    ("ruger", "security 9"): 340.0,
    ("sig sauer", "p365"): 450.0,
    ("beretta", "92fs"): 525.0,
}

# -----------------------------------------------------------------------------
# 2. INTERNAL DATA STRUCTURES & VALUATION ENGINE
# -----------------------------------------------------------------------------
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

def evaluate_compliance(make: str, model: str, title: str) -> tuple[bool, bool, bool]:
    text = f"{make} {model} {title}".lower()
    is_pre_ban = any(re.search(p, text) for p in PRE_BAN_PATTERNS)
    
    match = re.search(r"\b(19[0-7][0-9]|18[0-9]{2})\b", text)
    is_cr = bool(match and (2026 - int(match.group(1)) >= 50))
    
    make_clean, model_clean = make.lower(), model.lower()
    ma_roster = False
    if make_clean in MA_ROSTER_WHITELIST:
        if any(appr in model_clean for appr in MA_ROSTER_WHITELIST[make_clean]):
            ma_roster = True
    if is_pre_ban or is_cr:
        ma_roster = True
    return is_pre_ban, is_cr, ma_roster

def resolve_entity(title: str):
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

def save_dealer_lead(store_name, ffl_num, email, phone, state):
    dealers = []
    if os.path.exists(DEALER_DB_FILE):
        try:
            with open(DEALER_DB_FILE, "r") as f:
                dealers = json.load(f)
        except Exception:
            dealers = []
    dealers.append({
        "timestamp": datetime.now().isoformat(),
        "store_name": store_name,
        "ffl_num": ffl_num,
        "email": email,
        "phone": phone,
        "state": state
    })
    with open(DEALER_DB_FILE, "w") as f:
        json.dump(dealers, f, indent=2)

# -----------------------------------------------------------------------------
# 3. SIDEBAR CONTROLS
# -----------------------------------------------------------------------------
with st.sidebar:
    st.title("🎯 Sourcing Filters")
    min_profit = st.slider("Min Net Profit ($)", min_value=50, max_value=500, value=150, step=25)
    min_margin = st.slider("Min Margin (%)", min_value=10, max_value=50, value=30, step=5)

    st.divider()
    filter_actionable = st.checkbox("Show 'BID / BUY' Deals Only", value=True)
    filter_pre_ban = st.checkbox("Pre-Ban Grandfathered Only", value=False)
    filter_ma_roster = st.checkbox("MA Roster / Compliant Only", value=False)

# -----------------------------------------------------------------------------
# 4. MAIN INTERFACE
# -----------------------------------------------------------------------------
header_left, header_right = st.columns([3, 1])
with header_left:
    st.title("FFL Inventory Sourcing Radar")
    st.write("Autonomous auction monitoring, true landed acquisition cost calculation, and state compliance verification.")
with header_right:
    st.write("")
    st.link_button("⚡ Upgrade to Pro ($199/mo)", STRIPE_PRO_TIER_URL, type="primary", use_container_width=True)

sample_catalog = [
    AuctionLot("LOT-401", "estate-auctions.com", "Smith & Wesson Model 19-3 .357 Mag P&R 1974 w/ Box", 340.0, "https://auction.example.com/lot/401", True),
    AuctionLot("LOT-402", "regional-bid.com", "Pre-Ban Colt AR-15 Sporter Match HBAR 5.56", 720.0, "https://auction.example.com/lot/402", False),
    AuctionLot("LOT-403", "liquidations.com", "Glock 19 Gen 5 9mm (Used, 2 Mags)", 410.0, "https://auction.example.com/lot/403", True),
    AuctionLot("LOT-404", "midwest-firearms.com", "Ruger Security 9 9mm Pistol", 280.0, "https://auction.example.com/lot/404", True),
    AuctionLot("LOT-405", "proxibid.com", "Sig Sauer P365 9mm Nitron Micro-Compact", 290.0, "https://auction.example.com/lot/405", True),
]

all_evaluated = []
for lot in sample_catalog:
    make, model, nat_val = resolve_entity(lot.title)
    if nat_val > 0:
        all_evaluated.append(evaluate_lot(lot, make, model, nat_val, min_profit, min_margin))

m1, m2, m3, m4 = st.columns(4)
actionable_deals = [r for r in all_evaluated if r.actionable_deal]
m1.metric("Catalog Lots Monitored", len(all_evaluated))
m2.metric("Actionable Deals", len(actionable_deals), delta=f"{len(actionable_deals)} Buy Signals")
m3.metric("Pre-Ban Opportunities", len([r for r in all_evaluated if r.is_pre_ban]))
avg_spread = sum(r.net_profit for r in actionable_deals) / len(actionable_deals) if actionable_deals else 0
m4.metric("Avg Target Spread", f"${avg_spread:.2f}")

st.divider()

displayed_lots = all_evaluated
if filter_actionable:
    displayed_lots = [r for r in displayed_lots if r.actionable_deal]
if filter_pre_ban:
    displayed_lots = [r for r in displayed_lots if r.is_pre_ban]
if filter_ma_roster:
    displayed_lots = [r for r in displayed_lots if r.ma_roster_compliant]

tab_table, tab_cards, tab_calc, tab_register = st.tabs([
    "📋 Auction Table", 
    "🗂️ Opportunity Cards", 
    "🧮 Deal Screener", 
    "🏬 Dealer Membership & Billing"
])

# Tab 1: Interactive Table
with tab_table:
    search_query = st.text_input("🔍 Quick Search Catalog", placeholder="e.g. Colt, 19-3, Pre-Ban...")
    if search_query:
        displayed_lots = [l for l in displayed_lots if search_query.lower() in l.title.lower()]

    if displayed_lots:
        table_rows = []
        for r in displayed_lots:
            flags = []
            if r.is_pre_ban: flags.append("Pre-Ban")
            if r.is_curio_relic: flags.append("C&R")
            if r.ma_roster_compliant and not r.is_pre_ban and not r.is_curio_relic: flags.append("MA Roster")
            if not r.ma_roster_compliant: flags.append("Off-Roster")

            table_rows.append({
                "Signal": "🟢 BID" if r.actionable_deal else "🔴 PASS",
                "Model": f"{r.make.title()} {r.model.title()}",
                "Current Bid": f"${r.current_bid:.2f}",
                "Landed Cost": f"${r.total_landed_cost:.2f}",
                "Est MA Retail": f"${r.ma_retail:.2f}",
                "Net Profit": f"+${r.net_profit:.2f}",
                "Margin": f"{r.margin_pct:.1f}%",
                "Max Walk-Away Bid": f"${r.max_bid:.2f}",
                "Compliance": " • ".join(flags),
                "Auction URL": r.listing_url
            })
        
        st.dataframe(
            pd.DataFrame(table_rows),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Auction URL": st.column_config.LinkColumn("Listing Link", display_text="Open Lot ↗")
            }
        )
    else:
        st.info("No auction listings match your selected margin and compliance criteria.")

# Tab 2: Opportunity Cards
with tab_cards:
    if displayed_lots:
        for deal in displayed_lots:
            with st.container():
                c_card1, c_card2, c_card3 = st.columns([3, 2, 1])
                
                with c_card1:
                    st.markdown(f"### {deal.make.title()} {deal.model.title()}")
                    st.caption(deal.title)
                    flags = []
                    if deal.is_pre_ban: flags.append("🔥 Pre-Ban")
                    if deal.is_curio_relic: flags.append("🏛️ C&R Exempt")
                    if deal.ma_roster_compliant and not deal.is_pre_ban and not deal.is_curio_relic: flags.append("✅ MA Roster")
                    if not deal.ma_roster_compliant: flags.append("⚠️ Off-Roster")
                    st.write(" • ".join(flags))

                with c_card2:
                    st.write(f"**Current Bid:** ${deal.current_bid:.2f} | **Landed:** ${deal.total_landed_cost:.2f}")
                    st.write(f"**Est MA Retail:** ${deal.ma_retail:.2f} | **Max Bid:** ${deal.max_bid:.2f}")
                    st.success(f"+${deal.net_profit:.2f} Profit ({deal.margin_pct:.1f}%)")

                with c_card3:
                    st.write("")
                    st.link_button("View Auction ↗", deal.listing_url, use_container_width=True)
                
                st.divider()
    else:
        st.info("No lots match the active filter criteria.")

# Tab 3: Screener / Calculator
with tab_calc:
    st.subheader("Manual Deal & Estate Sizing Calculator")
    st.caption("Quickly evaluate counter trades, estate collections, or off-market lots:")

    sc_col1, sc_col2 = st.columns(2)
    with sc_col1:
        scr_title = st.text_input("Firearm Description", value="Smith & Wesson Model 19-4 .357 Mag 4-inch")
        scr_bid = st.number_input("Asking Price / Current Bid ($)", value=375.0, step=25.0)
        scr_bp = st.number_input("Buyer's Premium Rate (%)", value=18.0, step=1.0) / 100.0
        scr_category = st.radio("Classification", ["Handgun", "Long Gun"], horizontal=True)

    with sc_col2:
        scr_retail_national = st.number_input("National Used Comp (True Gun Value)", value=825.0, step=25.0)
        scr_preban = st.checkbox("Pre-September 1994 Manufacture? (+65% Local Demand)", value=False)
        scr_roster = st.checkbox("Massachusetts Target/Approved Roster Compliant?", value=True)
        
        scr_shipping = CONFIG["ESTIMATED_SHIPPING_HANDGUN"] if scr_category == "Handgun" else CONFIG["ESTIMATED_SHIPPING_LONGGUN"]
        scr_landed = scr_bid + (scr_bid * scr_bp) + scr_shipping + CONFIG["CLEANING_RECONDITIONING"]
        
        scr_ma_retail = scr_retail_national * CONFIG["MA_PRE_BAN_MULTIPLIER"] if scr_preban else (
            scr_retail_national + CONFIG["MA_OFF_ROSTER_PREMIUM"] if not scr_roster and scr_category == "Handgun" else scr_retail_national
        )
        scr_profit = scr_ma_retail - scr_landed
        scr_margin = (scr_profit / scr_ma_retail * 100) if scr_ma_retail > 0 else 0
        scr_max_bid = max(0.0, (scr_ma_retail - 150.0 - scr_shipping - CONFIG["CLEANING_RECONDITIONING"]) / (1 + scr_bp))

    st.write("---")
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Landed Cost", f"${scr_landed:.2f}")
    r2.metric("Projected Resale", f"${scr_ma_retail:.2f}")
    r3.metric("Projected Spread", f"${scr_profit:.2f}", delta=f"{scr_margin:.1f}% Margin")
    r4.metric("Walk-Away Ceiling", f"${scr_max_bid:.2f}")

    if scr_bid <= scr_max_bid and scr_profit >= min_profit:
        st.success(f"✅ HIGH-MARGIN DEAL: Offer/bid up to ${scr_max_bid:.2f} while retaining your ${min_profit:.0f} minimum profit target.")
    else:
        st.error(f"❌ OVERPRICED: Maximum allowable bid is ${scr_max_bid:.2f} to protect your ${min_profit:.0f} margin floor.")

# Tab 4: Dealer Registration & Billing
with tab_register:
    st.subheader("Dealer Subscription & Automated Alerting")
    plan_col, form_col = st.columns(2)

    with plan_col:
        st.info("### 🏬 Independent FFL Plan\n**$199 / month**\n\n* **Real-time alerts** for high-spread auction lots\n* **State compliance filtering** (Pre-Ban, C&R 50-year exemption, MA Roster)\n* **Automated landed cost calculation** (freight, transfer & fees)\n* **Calculated walk-away bids** on every incoming listing\n* Cancel anytime")
        st.link_button("👉 Subscribe with Stripe ($199/mo)", STRIPE_PRO_TIER_URL, type="primary", use_container_width=True)

    with form_col:
        st.markdown("### 📝 Link Store Credentials")
        st.caption("Register your store profile to connect your phone number and notifications to the engine:")
        with st.form("dealer_registration_form"):
            reg_store = st.text_input("Store / FFL Trade Name *")
            reg_ffl = st.text_input("FFL License Number", placeholder="e.g. 1-04-XXXXX")
            reg_email = st.text_input("Dealer Contact Email *")
            reg_phone = st.text_input("Mobile Number (For Immediate Deal Alerts) *")
            reg_state = st.selectbox("Licensed Operating State", ["MA", "NH", "PA", "RI", "CT", "Other"])
            
            submit_reg = st.form_submit_button("Submit Dealer Profile", use_container_width=True)
            if submit_reg:
                if reg_store and reg_email and reg_phone:
                    save_dealer_lead(reg_store, reg_ffl, reg_email, reg_phone, reg_state)
                    st.success("Store profile saved! Complete checkout on the left to link your live alert dispatch.")
                else:
                    st.error("Please fill in all required fields (*).")
