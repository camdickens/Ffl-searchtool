import os
import html
import json
import math
import traceback
from datetime import datetime
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
SOURCE_COLORS = ["#38bdf8", "#22c55e", "#f59e0b", "#a78bfa", "#f472b6", "#2dd4bf", "#fb7185", "#facc15"]


def num(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def esc(x):
    return html.escape(str(x if x is not None else ""))


def usd(v):
    return "$" + f"{v:,.0f}"


def usd_signed(v):
    return ("+" if v >= 0 else "-") + "$" + f"{abs(v):,.0f}"


# Small original header illustration: pistol silhouette over target rings.
HERO_ART = (
    '<svg width="230" height="74" viewBox="0 0 330 105" xmlns="http://www.w3.org/2000/svg">'
    '<defs><linearGradient id="hm" x1="0" y1="0" x2="0" y2="1">'
    '<stop offset="0%" stop-color="#e2e8f0"/><stop offset="100%" stop-color="#64748b"/>'
    '</linearGradient></defs>'
    '<g fill="none" stroke="#22c55e" opacity="0.45" stroke-width="1.5">'
    '<circle cx="262" cy="52" r="46"/><circle cx="262" cy="52" r="30"/><circle cx="262" cy="52" r="14"/>'
    '<path d="M262 2V102M212 52H312" stroke-dasharray="4 5"/></g>'
    '<g transform="translate(18 14) scale(0.36)">'
    '<path d="M10 40 H250 Q268 40 268 58 V76 H150 L142 96 Q122 120 94 112 L82 112 L70 198 '
    'Q68 210 54 210 H18 Q4 210 6 196 L28 76 H10 Q0 76 0 66 V50 Q0 40 10 40 Z" fill="url(#hm)"/>'
    '<path d="M88 114 Q92 142 128 138 Q148 134 150 100" fill="none" stroke="#0f172a" stroke-width="7"/>'
    '<rect x="14" y="48" width="240" height="6" rx="3" fill="#0f172a" opacity="0.35"/>'
    '</g>'
    '<g transform="translate(118 62) scale(0.3)" opacity="0.9">'
    '<polygon points="10,40 200,16 200,42 168,50 146,84 28,92 8,80" fill="#64748b"/>'
    '<rect x="196" y="12" width="100" height="32" rx="5" fill="#64748b"/>'
    '<rect x="294" y="22" width="120" height="10" rx="3" fill="#64748b"/>'
    '</g>'
    '</svg>'
)

EMPTY_ART = (
    '<div style="text-align:center;padding:26px 0;color:#94a3b8">'
    + ui_art.CROSSHAIR_ICON.replace('width="30" height="30"', 'width="64" height="64"')
    + '<div style="margin-top:8px;font-size:.95rem">No listings match these filters.</div>'
    '<div style="font-size:.78rem;color:#64748b">Loosen a filter or clear the search to see more.</div></div>'
)

# ---------------- STYLE: compact, dark, inline (no scroll windows) ----------------
st.markdown(
    """
<style>
header[data-testid="stHeader"] { display: none; }
footer { visibility: hidden; }
.block-container { padding: 0.6rem 1.4rem 0 1.4rem !important; max-width: 100% !important; }
section[data-testid="stSidebar"] > div { padding-top: 0.6rem; }
div[data-testid="stVerticalBlock"] { gap: 0.45rem; }
.hero { display:flex; align-items:center; justify-content:space-between;
        background: linear-gradient(90deg,#0f172a 0%,#1e293b 55%,#0b3b2e 100%);
        border:1px solid #1f2a3c; border-radius:12px; padding:8px 18px; margin-bottom:4px; }
.hero h1 { font-size:1.35rem; margin:0; padding:0; color:#f1f5f9; letter-spacing:.3px; }
.hero .sub { color:#94a3b8; font-size:.78rem; }
.pill { display:inline-block; padding:2px 10px; border-radius:999px; font-size:.72rem;
        background:#14532d; color:#bbf7d0; margin-left:8px; }
.kpi { background:#111827; border:1px solid #1f2937; border-radius:12px; padding:8px 14px; position:relative; overflow:hidden; }
.kpi:before { content:""; position:absolute; left:0; top:0; bottom:0; width:3px; background:var(--accent,#38bdf8); }
.kpi .lbl { color:#94a3b8; font-size:.70rem; text-transform:uppercase; letter-spacing:.8px; }
.kpi .val { color:#f8fafc; font-size:1.45rem; font-weight:700; line-height:1.25; }
.kpi .val.good { color:#22c55e; }
.kpi .val.blue { color:#38bdf8; }
.kpi .val.amber { color:#f59e0b; }
.card { background:#111827; border:1px solid #1f2937; border-radius:12px; padding:10px 14px; }
.card h4 { margin:0 0 8px 0; font-size:.8rem; color:#cbd5e1; font-weight:600; letter-spacing:.3px; }
.dtbl { width:100%; border-collapse:separate; border-spacing:0; font-size:.8rem; table-layout:fixed;
        background:#0f172a; border:1px solid #1f2937; border-radius:12px; overflow:hidden; }
.dtbl th { text-align:left; color:#94a3b8; font-weight:600; font-size:.68rem; text-transform:uppercase;
           letter-spacing:.6px; padding:8px 8px; background:#111827; border-bottom:1px solid #1f2937; }
.dtbl td { padding:6px 8px; border-bottom:1px solid #162033; color:#e2e8f0; white-space:nowrap;
           overflow:hidden; text-overflow:ellipsis; }
.dtbl tr:last-child td { border-bottom:none; }
.dtbl tr:hover td { background:#131d31; }
.dtbl .gun { font-weight:600; }
.dtbl .sm { color:#64748b; font-size:.7rem; font-weight:400; }
.num { text-align:right; font-variant-numeric:tabular-nums; }
.tag { display:inline-block; padding:1px 8px; border-radius:999px; font-size:.68rem; font-weight:600; }
.t-bid { background:#14532d; color:#86efac; }
.t-pass { background:#1f2937; color:#94a3b8; }
.t-auc { background:#3b2a05; color:#fcd34d; }
.t-bin { background:#0c2a3d; color:#7dd3fc; }
.t-un { background:#1f2937; color:#94a3b8; }
.t-val { background:#1e1b4b; color:#c4b5fd; }
.pos { color:#22c55e; font-weight:600; }
.neg { color:#ef4444; font-weight:600; }
.mb { display:inline-block; vertical-align:middle; width:46px; height:6px; background:#1f2937; border-radius:4px; overflow:hidden; margin-right:6px; }
.mf { height:100%; }
.openbtn { color:#04130a !important; background:#22c55e; padding:2px 9px; border-radius:6px; font-weight:700;
           font-size:.72rem; text-decoration:none; }
.brow { display:flex; align-items:center; gap:8px; margin:5px 0; font-size:.74rem; color:#cbd5e1; }
.brow .nm { width:42%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.brow .bar { flex:1; height:9px; background:#1f2937; border-radius:5px; overflow:hidden; }
.brow .bar i { display:block; height:100%; border-radius:5px; background:linear-gradient(90deg,#16a34a,#22c55e); }
.brow .v { width:52px; text-align:right; color:#86efac; font-weight:600; }
.seg { display:flex; height:12px; border-radius:6px; overflow:hidden; margin:4px 0 8px 0; }
.leg { display:flex; flex-wrap:wrap; gap:4px 12px; font-size:.72rem; color:#cbd5e1; }
.leg i { display:inline-block; width:9px; height:9px; border-radius:50%; margin-right:5px; }
.hist { display:flex; align-items:flex-end; gap:8px; height:64px; margin-top:4px; }
.hist div { flex:1; text-align:center; font-size:.64rem; color:#94a3b8; }
.hist div b { display:block; border-radius:4px 4px 0 0; background:linear-gradient(180deg,#38bdf8,#0369a1); margin-bottom:2px; }
button[data-baseweb="tab"] { padding: 4px 14px !important; }
div[data-testid="stTabs"] { margin-top: -4px; }
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
FEED_URL = "https://raw.githubusercontent.com/camdickens/Ffl-searchtool/main/feed_data.json"


@st.cache_data(ttl=300, show_spinner=False)
def fetch_remote_feed():
    try:
        import requests
        r = requests.get(FEED_URL, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, dict) and isinstance(data.get("lots"), list):
                return data
    except Exception:
        pass
    return None


def get_feed():
    data = fetch_remote_feed()
    if data:
        return data
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

    calibers = sorted({str(l.get("caliber") or "").upper() for l in all_lots if l.get("caliber")})
    selected_calibers = st.multiselect("Caliber", calibers, default=[]) if calibers else []

    listing_type = st.radio("Listing type", ["All", "Auctions", "Buy-It-Now"], horizontal=True)

    prices = [num(l.get("current_bid")) for l in all_lots]
    p_max = int(max(prices)) if prices else 5000
    p_max = max(100, int(math.ceil(p_max / 100.0) * 100))
    price_range = st.slider("Price range ($)", 0, p_max, (0, p_max), 25)

    min_profit = st.slider("Min net spread ($)", -300, 800, -300, 25)
    min_margin = st.slider("Min margin (%)", -100, 70, -100, 5)
    valued_only = st.checkbox("Valued listings only", value=False)
    action_only = st.checkbox("Show 'BID' targets only", value=False)
    pre_ban_only = st.checkbox("Pre-ban grandfathered only", value=False) if is_ma else False

    sort_by = st.selectbox("Sort by", ["Best net spread", "Highest margin", "Lowest price", "Highest price", "Source A-Z"])

# ---------------- ENRICH ----------------
for l in all_lots:
    l["disp_retail"] = num(l.get("ma_retail") if is_ma else l.get("federal_retail"))
    l["disp_profit"] = num(l.get("ma_profit") if is_ma else l.get("federal_profit"))
    l["disp_margin"] = num(l.get("ma_margin") if is_ma else l.get("federal_margin"))
    l["disp_act"] = bool(l.get("actionable_ma") if is_ma else l.get("actionable_federal"))
    l["valued"] = l["disp_retail"] > 0
    if "is_auction" in l:
        l["is_auction"] = bool(l.get("is_auction"))
    else:
        l["is_auction"] = l.get("source_site") in ["GunBroker", "HiBid"] or "bid" in str(l.get("title", "")).lower()

# ---------------- FILTER ----------------
filtered_lots = []
for l in all_lots:
    if selected_sources and l.get("source_site") not in selected_sources:
        continue
    if selected_makes and str(l.get("make") or "").title() not in selected_makes:
        continue
    if selected_calibers and str(l.get("caliber") or "").upper() not in selected_calibers:
        continue
    if listing_type == "Auctions" and not l["is_auction"]:
        continue
    if listing_type == "Buy-It-Now" and l["is_auction"]:
        continue
    price = num(l.get("current_bid"))
    if price < price_range[0] or price > price_range[1]:
        continue
    if valued_only and not l["valued"]:
        continue
    if l["valued"] and (l["disp_profit"] < min_profit or l["disp_margin"] < min_margin):
        continue
    if action_only and not l["disp_act"]:
        continue
    if is_ma and pre_ban_only and not l.get("is_pre_ban", False):
        continue
    haystack = f"{l.get('make','')} {l.get('model','')} {l.get('title','')} {l.get('caliber','')} {l.get('compliance_badge','')}".lower()
    if search_query and search_query not in haystack:
        continue
    filtered_lots.append(l)

sorters = {
    "Best net spread": (lambda l: (l["valued"], l["disp_profit"]), True),
    "Highest margin": (lambda l: (l["valued"], l["disp_margin"]), True),
    "Lowest price": (lambda l: num(l.get("current_bid")), False),
    "Highest price": (lambda l: num(l.get("current_bid")), True),
    "Source A-Z": (lambda l: str(l.get("source_site") or ""), False),
}
_key, _rev = sorters[sort_by]
filtered_lots.sort(key=_key, reverse=_rev)

# ---------------- HEADER ----------------
st.markdown(
    f"""<div class="hero"><div><h1>{ui_art.CROSSHAIR_ICON}FFL Deal Radar<span class="pill">● LIVE</span></h1><div class="sub">{esc(mode)} &nbsp;•&nbsp; Last updated {esc(feed.get('last_updated', 'just now'))} &nbsp;•&nbsp; refreshed every 2 hours &nbsp;•&nbsp; {len(filtered_lots)} of {len(all_lots)} listings shown</div></div>{HERO_ART}</div>""",
    unsafe_allow_html=True,
)


def kpi(col, label, value, cls="", accent="#38bdf8"):
    col.markdown(
        f'<div class="kpi" style="--accent:{accent}"><div class="lbl">{label}</div><div class="val {cls}">{value}</div></div>',
        unsafe_allow_html=True,
    )


def gun_name(l):
    make = str(l.get("make") or "").strip()
    model = str(l.get("model") or "").strip()
    if model.lower() == "unknown":
        model = ""
    return (make + " " + model).strip() or str(l.get("title") or "Unknown")[:40]


def table_html(rows):
    head = (
        '<tr><th style="width:7%">Signal</th><th style="width:10%">Source</th><th style="width:8%">Type</th>'
        '<th style="width:22%">Gun</th><th class="num" style="width:8%">Ask / Bid</th>'
        '<th class="num" style="width:8%">Landed</th><th class="num" style="width:8%">Value</th>'
        '<th class="num" style="width:8%">Spread</th><th style="width:10%">Margin</th>'
        '<th style="width:11%">Basis</th></tr>'
    )
    body = []
    for l in rows:
        sig = '<span class="tag t-bid">BID</span>' if l["disp_act"] else '<span class="tag t-pass">PASS</span>'
        typ = '<span class="tag t-auc">Auction</span>' if l["is_auction"] else '<span class="tag t-bin">Buy now</span>'
        cal = esc(l.get("caliber") or "")
        name = esc(gun_name(l))
        sub = f'<div class="sm">{cal}</div>' if cal else ""
        link = esc(l.get("listing_url") or "#")
        title = esc(l.get("title") or "")
        ask = usd(num(l.get("current_bid")))
        if l["valued"]:
            sp = l["disp_profit"]
            cls = "pos" if sp >= 0 else "neg"
            mg = l["disp_margin"]
            pct = max(0, min(60, mg)) / 60.0 * 100
            color = "#22c55e" if mg >= 15 else ("#f59e0b" if mg >= 0 else "#ef4444")
            val = usd(l["disp_retail"])
            spread = f'<span class="{cls}">{usd_signed(sp)}</span>'
            margin = f'<span class="mb"><span class="mf" style="display:block;width:{pct:.0f}%;background:{color}"></span></span>{mg:.0f}%'
            basis = f'<span class="tag t-val">{esc(l.get("compliance_badge") or "Valued")}</span>'
        else:
            val, spread, margin = "&mdash;", "&mdash;", '<span class="sm">no comp yet</span>'
            basis = '<span class="tag t-un">Unvalued</span>'
        body.append(
            f'<tr title="{title}"><td>{sig}</td><td>{esc(l.get("source_site", "Direct"))}</td><td>{typ}</td>'
            f'<td class="gun"><a href="{link}" target="_blank" style="color:#e2e8f0;text-decoration:none">{name}</a>{sub}</td>'
            f'<td class="num">{ask}</td><td class="num">{usd(num(l.get("total_landed_cost")))}</td>'
            f'<td class="num">{val}</td><td class="num">{spread}</td><td>{margin}</td><td>{basis}</td></tr>'
        )
    return f'<table class="dtbl">{head}{"".join(body)}</table>'


def charts_html(items):
    # Top spreads
    top = [l for l in items if l["valued"] and l["disp_profit"] > 0]
    top.sort(key=lambda l: l["disp_profit"], reverse=True)
    top = top[:5]
    if top:
        mx = max(l["disp_profit"] for l in top) or 1
        rows = "".join(
            f'<div class="brow"><div class="nm" title="{esc(gun_name(l))}">{esc(gun_name(l))}</div>'
            f'<div class="bar"><i style="width:{l["disp_profit"] / mx * 100:.0f}%"></i></div>'
            f'<div class="v">{usd(l["disp_profit"])}</div></div>'
            for l in top
        )
    else:
        rows = '<div class="sm" style="color:#64748b;font-size:.76rem">No positive spreads in the current view yet.</div>'
    c1 = f'<div class="card"><h4>💰 TOP NET SPREADS</h4>{rows}</div>'

    # By source
    counts = {}
    for l in items:
        s = str(l.get("source_site") or "Direct")
        counts[s] = counts.get(s, 0) + 1
    total = sum(counts.values()) or 1
    seg, leg = "", ""
    for i, (s, n) in enumerate(sorted(counts.items(), key=lambda kv: -kv[1])):
        color = SOURCE_COLORS[i % len(SOURCE_COLORS)]
        seg += f'<div style="width:{n / total * 100:.1f}%;background:{color}"></div>'
        leg += f'<span><i style="background:{color}"></i>{esc(s)} {n}</span>'
    c2 = f'<div class="card"><h4>🌐 LISTINGS BY SOURCE</h4><div class="seg">{seg}</div><div class="leg">{leg}</div></div>'

    # Price distribution
    buckets = [("<$250", 0, 250), ("$250-500", 250, 500), ("$500-1k", 500, 1000), ("$1k-2k", 1000, 2000), ("$2k+", 2000, 10**9)]
    vals = [num(l.get("current_bid")) for l in items]
    bc = [sum(1 for v in vals if lo <= v < hi) for (_, lo, hi) in buckets]
    mxc = max(bc) or 1
    cols = "".join(
        f'<div><b style="height:{max(3, c / mxc * 44):.0f}px"></b>{c}<br>{lab}</div>'
        for (lab, _, _), c in zip(buckets, bc)
    )
    c3 = f'<div class="card"><h4>📊 PRICE DISTRIBUTION</h4><div class="hist">{cols}</div></div>'
    return c1 + c2 + c3


def render_dashboard(items, key):
    n = len(items)
    valued = [l for l in items if l["valued"]]
    bids = sum(1 for l in items if l["disp_act"])
    best = max((l["disp_profit"] for l in valued), default=0.0)
    avg_margin = (sum(l["disp_margin"] for l in valued) / len(valued)) if valued else 0.0

    k1, k2, k3, k4, k5 = st.columns(5)
    kpi(k1, "Listings", f"{n}", "blue", "#38bdf8")
    kpi(k2, "BID targets", f"{bids}", "good", "#22c55e")
    kpi(k3, "Best net spread", usd(best) if valued else "&mdash;", "good" if best > 0 else "", "#22c55e")
    kpi(k4, "Avg margin", f"{avg_margin:.1f}%" if valued else "&mdash;", "amber", "#f59e0b")
    kpi(k5, "Valued", f"{len(valued)}/{n}", "", "#a78bfa")

    if not items:
        st.markdown(EMPTY_ART, unsafe_allow_html=True)
        return

    ctl_info, ctl_rows, ctl_page = st.columns([4, 1, 1])
    page_size = ctl_rows.selectbox("Rows", [8, 10, 12, 15, 20], index=1, key=f"ps_{key}", label_visibility="collapsed")
    pages = max(1, math.ceil(n / page_size))
    page = ctl_page.number_input("Page", min_value=1, max_value=pages, value=1, step=1, key=f"pg_{key}", label_visibility="collapsed")
    start = (int(page) - 1) * page_size
    end = min(start + page_size, n)
    ctl_info.caption(f"Showing {start + 1}-{end} of {n}  •  page {int(page)}/{pages}  •  click a gun name to open the listing")

    left, right = st.columns([2.6, 1])
    with left:
        st.markdown(table_html(items[start:end]), unsafe_allow_html=True)
    with right:
        st.markdown(charts_html(items), unsafe_allow_html=True)


tab_all, tab_auc, tab_alert, tab_sys = st.tabs(["📋 Inventory", "🔨 Live Auctions", "🔔 Alerts", "⚙️ System"])

with tab_all:
    render_dashboard(filtered_lots, "all")

with tab_auc:
    render_dashboard([l for l in filtered_lots if l["is_auction"]], "auc")

with tab_alert:
    st.subheader("🔔 Instant arbitrage alerts")
    st.write(f"Alert destination: **{user_email}**")
    st.number_input("Target profit spread threshold ($)", value=100.0, step=25.0)
    if st.button("Save alert threshold"):
        st.success("Alert preferences updated.")

with tab_sys:
    st.subheader("System infrastructure")
    per_source = feed.get("per_source") or {}
    st.write(f"**Total listings:** {len(all_lots)}  •  **Feed status:** {'Healthy' if all_lots else 'Sync required'}")
    if per_source:
        st.write("**Listings per source (last run):** " + ", ".join(f"{k}: {v}" for k, v in per_source.items()))
    unvalued = sum(1 for l in all_lots if not l["valued"])
    st.write(f"**Unvalued listings:** {unvalued} of {len(all_lots)} (no comparable listings found yet)")
    st.caption("The feed is refreshed every 2 hours by a GitHub Actions workflow.")
    if st.button("🔄 Force immediate re-sync"):
        try:
            import worker
            worker.main()
            st.success("Synchronized! Reloading...")
            st.rerun()
        except Exception as e:
            st.error(f"Sync error: {e}")
            st.code(traceback.format_exc())
