import os
import json
import math
import traceback
from datetime import datetime
import pandas as pd
import altair as alt
import streamlit as st
import ui_art

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


CRON_TOKEN = get_secret("CRON_TOKEN")

ALL_PLATFORMS = [
    "GunBroker", "HiBid", "Armslist", "Guns.com", "GunsAmerica",
    "Buds Gun Shop", "Sportsman's Outdoor Superstore", "Tacswap", "UsedGuns.com",
    "Classic Firearms",
]

GREEN = "#22c55e"
RED = "#ef4444"
BLUE = "#38bdf8"
AMBER = "#f59e0b"


def num(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# ---------------- STYLE: compact, dark, no page scroll ----------------
st.markdown(
    """
<style>
header[data-testid="stHeader"] { display: none; }
footer { visibility: hidden; }
.block-container { padding: 0.6rem 1.4rem 0 1.4rem !important; max-width: 100% !important; }
section[data-testid="stSidebar"] > div { padding-top: 0.6rem; }
div[data-testid="stVerticalBlock"] { gap: 0.45rem; }
.hero { display:flex; align-items:center; justify-content:space-between;
        background: linear-gradient(90deg,#0f172a 0%,#1e293b 60%,#0b3b2e 100%);
        border:1px solid #1f2a3c; border-radius:12px; padding:10px 18px; margin-bottom:4px; }
.hero h1 { font-size:1.35rem; margin:0; padding:0; color:#f1f5f9; letter-spacing:.3px; }
.hero .sub { color:#94a3b8; font-size:.78rem; }
.pill { display:inline-block; padding:2px 10px; border-radius:999px; font-size:.72rem;
        background:#14532d; color:#bbf7d0; margin-left:8px; }
.kpi { background:#111827; border:1px solid #1f2937; border-radius:12px; padding:8px 14px; }
.kpi .lbl { color:#94a3b8; font-size:.70rem; text-transform:uppercase; letter-spacing:.8px; }
.kpi .val { color:#f8fafc; font-size:1.45rem; font-weight:700; line-height:1.25; }
.kpi .val.good { color:#22c55e; }
.kpi .val.blue { color:#38bdf8; }
.kpi .val.amber { color:#f59e0b; }
.charttitle { color:#cbd5e1; font-size:.8rem; font-weight:600; margin:2px 0 -6px 2px; }
button[data-baseweb="tab"] { padding: 4px 14px !important; }
div[data-testid="stTabs"] { margin-top: -4px; }
div[data-testid="stDataFrame"] { border:1px solid #1f2937; border-radius:10px; }
</style>
""",
    unsafe_allow_html=True,
)

# ---------------- OPTIONAL MANUAL SCRAPE TRIGGER ----------------
# Disabled unless CRON_TOKEN is configured. Scheduled scraping runs in GitHub Actions.
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


# ---------------- ACCESS GATE (Google sign-in) ----------------
ALLOWED_EMAILS = {e.strip().lower() for e in get_secret("ALLOWED_EMAILS").split(",") if e.strip()}

if not hasattr(st, "login"):
    st.title("🎯 FFL Deal Radar")
    st.error("Google sign-in needs Streamlit 1.42 or newer. Update streamlit in requirements.txt.")
    st.stop()

try:
    auth_configured = "auth" in st.secrets
except Exception:
    auth_configured = False

if not auth_configured:
    st.title("🎯 FFL Deal Radar")
    st.error("Google sign-in is not configured yet. Add an [auth] section to the app secrets.")
    st.stop()

if not st.user.is_logged_in:
    ui_art.render_login()
    st.stop()

user_email = str(st.user.get("email") or "").lower()
email_verified = st.user.get("email_verified", True)
if not ALLOWED_EMAILS or user_email not in ALLOWED_EMAILS or not email_verified:
    ui_art.render_login(unauthorized_email=user_email)
    st.stop()

# ---------------- LOAD DATA ----------------
feed = get_feed()
all_lots = [l for l in feed.get("lots", []) if isinstance(l, dict)]

# ---------------- SIDEBAR FILTERS ----------------
with st.sidebar:
    st.markdown("### 🎯 FFL Radar")
    st.caption(f"Signed in as {user_email}")
    if st.button("🚪 Sign out", use_container_width=True):
        st.logout()

    mode = st.radio("Legal framework", ["Massachusetts Compliant", "Federal Standard"], horizontal=False)
    is_ma = (mode == "Massachusetts Compliant")

    present_sources = sorted({str(l.get("source_site")) for l in all_lots if l.get("source_site")})
    source_options = sorted(set(ALL_PLATFORMS) | set(present_sources))
    selected_sources = st.multiselect("Source platforms", source_options, default=present_sources or source_options)

    search_query = st.text_input("🔍 Search keyword", "").strip().lower()

    makes = sorted({str(l.get("make") or "").title() for l in all_lots if l.get("make")})
    selected_makes = st.multiselect("Brand / make", makes, default=[])

    listing_type = st.radio("Listing type", ["All", "Auctions", "Buy-It-Now"], horizontal=True)

    prices = [num(l.get("current_bid")) for l in all_lots]
    p_max = int(max(prices)) if prices else 5000
    p_max = max(100, int(math.ceil(p_max / 100.0) * 100))
    price_range = st.slider("Price range ($)", 0, p_max, (0, p_max), 25)

    min_profit = st.slider("Min net spread ($)", -300, 800, -300, 25)
    min_margin = st.slider("Min margin (%)", -100, 70, -100, 5)
    action_only = st.checkbox("Show 'BID' targets only", value=False)
    pre_ban_only = st.checkbox("Pre-ban grandfathered only", value=False) if is_ma else False

    sort_by = st.selectbox("Sort by", ["Best net spread", "Highest margin", "Lowest price", "Highest price", "Source A-Z"])

# ---------------- ENRICH ----------------
for l in all_lots:
    l["disp_retail"] = num(l.get("ma_retail") if is_ma else l.get("federal_retail"))
    l["disp_profit"] = num(l.get("ma_profit") if is_ma else l.get("federal_profit"))
    l["disp_margin"] = num(l.get("ma_margin") if is_ma else l.get("federal_margin"))
    l["disp_act"] = bool(l.get("actionable_ma") if is_ma else l.get("actionable_federal"))
    l["is_auction"] = l.get("source_site") in ["GunBroker", "HiBid"] or "bid" in str(l.get("title", "")).lower()

# ---------------- FILTER ----------------
filtered_lots = []
for l in all_lots:
    if selected_sources and l.get("source_site") not in selected_sources:
        continue
    if selected_makes and str(l.get("make") or "").title() not in selected_makes:
        continue
    if listing_type == "Auctions" and not l["is_auction"]:
        continue
    if listing_type == "Buy-It-Now" and l["is_auction"]:
        continue
    price = num(l.get("current_bid"))
    if price < price_range[0] or price > price_range[1]:
        continue
    if l["disp_profit"] < min_profit or l["disp_margin"] < min_margin:
        continue
    if action_only and not l["disp_act"]:
        continue
    if is_ma and pre_ban_only and not l.get("is_pre_ban", False):
        continue
    haystack = f"{l.get('make','')} {l.get('model','')} {l.get('title','')} {l.get('compliance_badge','')}".lower()
    if search_query and search_query not in haystack:
        continue
    filtered_lots.append(l)

sorters = {
    "Best net spread": (lambda l: l["disp_profit"], True),
    "Highest margin": (lambda l: l["disp_margin"], True),
    "Lowest price": (lambda l: num(l.get("current_bid")), False),
    "Highest price": (lambda l: num(l.get("current_bid")), True),
    "Source A-Z": (lambda l: str(l.get("source_site") or ""), False),
}
_key, _rev = sorters[sort_by]
filtered_lots.sort(key=_key, reverse=_rev)

# ---------------- HEADER ----------------
st.markdown(
    f"""
<div class="hero">
  <div><h1>{ui_art.CROSSHAIR_ICON}FFL Deal Radar<span class="pill">● LIVE</span></h1>
  <div class="sub">{mode} &nbsp;•&nbsp; Last updated {feed.get('last_updated', 'just now')} &nbsp;•&nbsp; refreshed hourly</div></div>
  <div class="sub">{len(filtered_lots)} of {len(all_lots)} listings shown</div>
</div>
""",
    unsafe_allow_html=True,
)


def kpi(col, label, value, cls=""):
    col.markdown(
        f'<div class="kpi"><div class="lbl">{label}</div><div class="val {cls}">{value}</div></div>',
        unsafe_allow_html=True,
    )


def render_dashboard(items, key, empty_msg):
    n = len(items)
    bids = sum(1 for l in items if l["disp_act"])
    best = max((l["disp_profit"] for l in items), default=0.0)
    avg_margin = (sum(l["disp_margin"] for l in items) / n) if n else 0.0
    auctions = sum(1 for l in items if l["is_auction"])

    k1, k2, k3, k4, k5 = st.columns(5)
    kpi(k1, "Listings", f"{n}", "blue")
    kpi(k2, "BID targets", f"{bids}", "good")
    kpi(k3, "Best net spread", f"${best:,.0f}", "good" if best > 0 else "")
    kpi(k4, "Avg margin", f"{avg_margin:.1f}%", "amber")
    kpi(k5, "Auctions", f"{auctions}", "")

    if not items:
        st.warning(empty_msg)
        return

    left, right = st.columns([2.3, 1])

    # ----- table (paginated so it always fits the screen) -----
    with left:
        c1, c2, c3 = st.columns([2.2, 1, 1])
        page_size = c2.selectbox("Rows", [8, 10, 12, 15, 20], index=1, key=f"ps_{key}", label_visibility="collapsed")
        pages = max(1, math.ceil(n / page_size))
        page = c3.number_input("Page", min_value=1, max_value=pages, value=1, step=1, key=f"pg_{key}", label_visibility="collapsed")
        start = (int(page) - 1) * page_size
        end = min(start + page_size, n)
        c1.caption(f"Showing {start + 1}-{end} of {n}  •  page {int(page)}/{pages}")

        rows = []
        for lot in items[start:end]:
            v = lot.get("valuation_sources") or {}
            rows.append({
                "Signal": "🟢 BID" if lot["disp_act"] else "⚪ PASS",
                "Source": lot.get("source_site", "Direct"),
                "Type": "🔨 Auction" if lot["is_auction"] else "🏷️ BIN",
                "Model": f"{str(lot.get('make') or '').title()} {str(lot.get('model') or '').title()}".strip(),
                "Ask / Bid": num(lot.get("current_bid")),
                "Landed": num(lot.get("total_landed_cost")),
                "Value": lot["disp_retail"],
                "Spread": lot["disp_profit"],
                "Margin %": lot["disp_margin"],
                "Max Bid": num(lot.get("max_bid")),
                "Badge": lot.get("compliance_badge", ""),
                "Link": lot.get("listing_url", "#"),
            })
        df = pd.DataFrame(rows)
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            height=int((len(rows) + 1) * 35 + 3),
            column_config={
                "Ask / Bid": st.column_config.NumberColumn(format="$%.0f"),
                "Landed": st.column_config.NumberColumn(format="$%.0f"),
                "Value": st.column_config.NumberColumn(format="$%.0f"),
                "Spread": st.column_config.NumberColumn(format="$%+.0f"),
                "Margin %": st.column_config.ProgressColumn(format="%.0f%%", min_value=-50, max_value=70),
                "Max Bid": st.column_config.NumberColumn(format="$%.0f"),
                "Link": st.column_config.LinkColumn("Listing", display_text="Open ↗"),
            },
        )

    # ----- charts -----
    with right:
        top = sorted(items, key=lambda l: l["disp_profit"], reverse=True)[:6]
        tdf = pd.DataFrame({
            "Deal": [f"{str(l.get('make') or '').title()} {str(l.get('model') or '').title()}".strip()[:22] or "Unknown" for l in top],
            "Spread": [l["disp_profit"] for l in top],
        })
        st.markdown('<div class="charttitle">💰 Top net spreads</div>', unsafe_allow_html=True)
        bar = (
            alt.Chart(tdf)
            .mark_bar(cornerRadiusEnd=4)
            .encode(
                x=alt.X("Spread:Q", title=None, axis=alt.Axis(format="$,.0f", labelColor="#94a3b8", grid=False)),
                y=alt.Y("Deal:N", sort="-x", title=None, axis=alt.Axis(labelColor="#cbd5e1", labelLimit=130)),
                color=alt.condition(alt.datum.Spread > 0, alt.value(GREEN), alt.value(RED)),
                tooltip=["Deal", alt.Tooltip("Spread:Q", format="$,.0f")],
            )
            .properties(height=175)
            .configure_view(strokeWidth=0)
        )
        st.altair_chart(bar, use_container_width=True, theme=None)

        src = pd.Series([str(l.get("source_site") or "Direct") for l in items]).value_counts().reset_index()
        src.columns = ["Source", "Count"]
        st.markdown('<div class="charttitle">🌐 Listings by source</div>', unsafe_allow_html=True)
        donut = (
            alt.Chart(src)
            .mark_arc(innerRadius=42, outerRadius=78)
            .encode(
                theta="Count:Q",
                color=alt.Color(
                    "Source:N",
                    scale=alt.Scale(range=[BLUE, GREEN, AMBER, "#a78bfa", "#f472b6", "#2dd4bf"]),
                    legend=alt.Legend(orient="right", labelColor="#cbd5e1", title=None, labelLimit=110),
                ),
                tooltip=["Source", "Count"],
            )
            .properties(height=175)
            .configure_view(strokeWidth=0)
        )
        st.altair_chart(donut, use_container_width=True, theme=None)


tab_all, tab_auc, tab_alert, tab_sys = st.tabs(["📋 Inventory", "🔨 Live Auctions", "🔔 Alerts", "⚙️ System"])

with tab_all:
    render_dashboard(filtered_lots, "all", "No listings match the current filters.")

with tab_auc:
    render_dashboard([l for l in filtered_lots if l["is_auction"]], "auc", "No auction listings match the current filters.")

with tab_alert:
    st.subheader("🔔 Instant arbitrage alerts")
    st.write(f"Alert destination: `{user_email}`")
    st.number_input("Target profit spread threshold ($)", value=100.0, step=25.0)
    if st.button("Save alert threshold"):
        st.success("Alert preferences updated.")

with tab_sys:
    st.subheader("System infrastructure")
    st.write(f"**Total listings:** {len(all_lots)}  •  **Feed status:** {'Healthy' if all_lots else 'Sync required'}")
    st.caption("The feed is refreshed hourly by a GitHub Actions workflow.")
    if st.button("🔄 Force immediate re-sync"):
        try:
            import worker
            worker.main()
            st.success("Synchronized! Reloading...")
            st.rerun()
        except Exception as e:
            st.error(f"Sync error: {e}")
            st.code(traceback.format_exc())
