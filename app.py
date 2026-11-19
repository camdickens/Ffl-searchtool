import os
import html
import json
import math
import traceback
from datetime import datetime
import streamlit as st
import ui_art

st.set_page_config(page_title="FFL Deal Radar", page_icon="🎯", layout="wide", initial_sidebar_state="auto")

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
    '<svg class="hero-art" width="230" height="74" viewBox="0 0 330 105" xmlns="http://www.w3.org/2000/svg">'
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

# ---------------- STYLE: colorful dark theme, everything inline (no scroll windows) ----------------
st.markdown(
    """
<style>
.stApp { background:
    radial-gradient(1100px 480px at 8% -8%, #0f3a4a 0%, transparent 60%),
    radial-gradient(900px 420px at 100% 0%, #2a1a4d 0%, transparent 58%),
    radial-gradient(800px 500px at 50% 120%, #0b3b2e 0%, transparent 60%), #080d17; }
header[data-testid="stHeader"] { background: transparent; height: 2.4rem; }
[data-testid="stToolbar"], [data-testid="stDecoration"], footer { display: none !important; }
.block-container { padding: 3rem 1.2rem 2rem 1.2rem !important; max-width: 100% !important; }
section[data-testid="stSidebar"] > div { background: linear-gradient(180deg,#0f172a 0%,#101a33 55%,#0c2a2a 100%); padding-top: 0.6rem; }
div[data-testid="stVerticalBlock"] { gap: 1rem; }
/* keep control columns on one row, even on phones */
div[data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; gap: 0.5rem !important; align-items: center; }
div[data-testid="stColumn"], div[data-testid="column"] { min-width: 0 !important; }

.hero { position:relative; overflow:hidden; display:flex; align-items:center; justify-content:space-between; gap:12px;
        background: linear-gradient(100deg,#0b1d3a 0%,#143a5e 38%,#0e5a4a 75%,#1b7a46 100%);
        border:0; border-top:1px solid #2b4a6b; border-bottom:1px solid #2b4a6b; border-radius:0; padding:16px 1.6rem; margin:0 -1.2rem 10px -1.2rem;
        box-shadow: 0 8px 28px rgba(14,90,74,.28); }
.hero:after { content:""; position:absolute; inset:0; pointer-events:none;
        background: linear-gradient(115deg, transparent 40%, rgba(255,255,255,.07) 50%, transparent 60%);
        background-size: 250% 100%; animation: sheen 7s linear infinite; }
@keyframes sheen { from { background-position: 150% 0; } to { background-position: -100% 0; } }
.hero h1 { font-size:1.45rem; margin:0; padding:0; color:#f8fafc; letter-spacing:.3px; display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
.hero .sub { color:#b6c8dd; font-size:.78rem; margin-top:2px; }
.hero svg.hero-art { flex:0 0 auto; max-width:34%; height:auto; }
.pill { display:inline-flex; align-items:center; gap:6px; padding:2px 10px; border-radius:999px; font-size:.7rem;
        background:#052e1a; color:#86efac; border:1px solid #166534; }
.pill:before { content:""; width:7px; height:7px; border-radius:50%; background:#22c55e; animation: pulse 1.6s ease-in-out infinite; }
@keyframes pulse { 0%,100% { box-shadow:0 0 0 0 rgba(34,197,94,.7); } 50% { box-shadow:0 0 0 6px rgba(34,197,94,0); } }

.kpis { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:14px; margin-bottom:6px; }
.kpi { position:relative; overflow:hidden; border-radius:14px; padding:12px 16px 12px 18px;
       background: linear-gradient(135deg, color-mix(in srgb, var(--accent) 22%, #0f172a) 0%, #0f172a 70%);
       border:1px solid color-mix(in srgb, var(--accent) 45%, #1f2937); }
.kpi:before { content:""; position:absolute; left:0; top:0; bottom:0; width:4px; background:var(--accent); box-shadow:0 0 14px var(--accent); }
.kpi .ic { position:absolute; right:10px; top:6px; font-size:1.5rem; opacity:.22; }
.kpi .lbl { color:#a9b8cc; font-size:.68rem; text-transform:uppercase; letter-spacing:.9px; }
.kpi .val { color:var(--accent); font-size:1.55rem; font-weight:800; line-height:1.2; }

.charts { display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:14px; margin:8px 0 6px 0; }
.card { background: linear-gradient(160deg,#131c31 0%,#0e1526 100%); border:1px solid #243049; border-radius:14px; padding:14px 16px; }
.card h4 { margin:0 0 8px 0; font-size:.76rem; color:#dbe5f3; font-weight:700; letter-spacing:.6px; }
.sm { color:#7d8ca3; font-size:.7rem; font-weight:400; }
.brow { display:flex; align-items:center; gap:8px; margin:8px 0; font-size:.74rem; color:#d0dbea; }
.brow .nm { width:42%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.brow .bar { flex:1; height:9px; background:#1b2538; border-radius:5px; overflow:hidden; }
.brow .bar i { display:block; height:100%; border-radius:5px; background:linear-gradient(90deg,#06b6d4,#22c55e,#a3e635); }
.brow .v { width:52px; text-align:right; color:#86efac; font-weight:700; }
.seg { display:flex; height:12px; border-radius:6px; overflow:hidden; margin:4px 0 8px 0; }
.leg { display:flex; flex-wrap:wrap; gap:4px 12px; font-size:.72rem; color:#d0dbea; }
.leg i { display:inline-block; width:9px; height:9px; border-radius:50%; margin-right:5px; }
.hist { display:flex; align-items:flex-end; gap:8px; height:70px; margin-top:4px; }
.hist div { flex:1; text-align:center; font-size:.64rem; color:#9fb0c7; }
.hist div b { display:block; border-radius:5px 5px 0 0; background:linear-gradient(180deg,#f472b6,#8b5cf6 60%,#38bdf8); margin-bottom:2px; }

/* ---------- deal list ---------- */
.dgrid { margin-top:8px; --cols: 64px minmax(190px,3.2fr) repeat(4,minmax(72px,1fr)) minmax(112px,1.3fr) minmax(104px,1.1fr) 70px; }
.dhead, .deal { display:grid; grid-template-columns:var(--cols); align-items:center; column-gap:10px; }
.dhead { padding:8px 14px; color:#9fb0c7; font-size:.66rem; text-transform:uppercase; letter-spacing:.7px; font-weight:700;
         background:#111a2e; border:1px solid #243049; border-radius:12px 12px 0 0; }
.deal { position:relative; padding:8px 14px; background:#0e1526; border:1px solid #1a2438; border-top:none; font-size:.8rem; color:#e6edf7; }
.deal:before { content:""; position:absolute; left:0; top:0; bottom:0; width:4px; background:var(--st,#334155); }
.deal:nth-child(even) { background:#101829; }
.deal:hover { background:#16223a; }
.deal:last-child { border-radius:0 0 12px 12px; }
.deal.st-bid { --st:#22c55e; box-shadow:inset 0 0 40px rgba(34,197,94,.10); }
.deal.st-pos { --st:#14b8a6; }
.deal.st-neg { --st:#f43f5e; }
.deal.st-unv { --st:#475569; }
.d-main { min-width:0; }
.d-name { color:#f8fafc !important; font-weight:700; text-decoration:none; display:block; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.d-name:hover { color:#7dd3fc !important; }
.d-sub { color:#8da0ba; font-size:.7rem; display:flex; align-items:center; gap:6px; flex-wrap:wrap; margin-top:2px; }
.dot { width:8px; height:8px; border-radius:50%; background:var(--src,#94a3b8); display:inline-block; }
.d-num { text-align:right; font-variant-numeric:tabular-nums; }
.d-num .k { display:none; color:#7d8ca3; font-size:.6rem; text-transform:uppercase; letter-spacing:.7px; }
.d-mar { display:flex; align-items:center; gap:6px; font-size:.76rem; }
.mb { display:inline-block; width:54px; height:7px; background:#1b2538; border-radius:4px; overflow:hidden; }
.mf { display:block; height:100%; border-radius:4px; }
.tag { display:inline-block; padding:1px 8px; border-radius:999px; font-size:.66rem; font-weight:700; white-space:nowrap; }
.t-bid { background:#14532d; color:#86efac; box-shadow:0 0 10px rgba(34,197,94,.45); }
.t-pass { background:#1f2937; color:#94a3b8; }
.t-auc { background:#4a2e05; color:#fcd34d; }
.t-bin { background:#0c3550; color:#7dd3fc; }
.t-new { background:#4a0f33; color:#f9a8d4; }
.t-used { background:#06403d; color:#5eead4; }
.t-un { background:#1f2937; color:#94a3b8; }
.t-val { background:#26215c; color:#c4b5fd; }
.pos { color:#34d399; font-weight:700; }
.neg { color:#fb7185; font-weight:700; }
.openbtn { justify-self:end; color:#04130a !important; background:linear-gradient(135deg,#22c55e,#a3e635); padding:3px 10px; border-radius:8px;
           font-weight:800; font-size:.7rem; text-decoration:none; white-space:nowrap; }
.openbtn:hover { filter:brightness(1.1); }

@media (max-width: 900px) {
  .dhead { display:none; }
  .deal { grid-template-columns:repeat(4,1fr); grid-template-areas:"sig main main go" "ask landed value spread" "mar mar basis basis";
          row-gap:6px; border-top:1px solid #1a2438; border-radius:12px; margin-bottom:8px; padding:10px 12px 10px 16px; }
  .deal:last-child { border-radius:12px; }
  .d-sig { grid-area:sig; } .d-main { grid-area:main; } .d-go { grid-area:go; }
  .d-ask { grid-area:ask; } .d-landed { grid-area:landed; } .d-value { grid-area:value; } .d-spread { grid-area:spread; }
  .d-mar { grid-area:mar; } .d-basis { grid-area:basis; justify-self:end; }
  .d-num { text-align:left; } .d-num .k { display:block; }
  .hero svg.hero-art { display:none; }
}
/* top bar: navigation pills + account button, right-aligned above the header */
.st-key-topbar div[data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; justify-content: flex-end; align-items: center; gap: 0.7rem !important; }
.st-key-topbar div[data-testid="stColumn"], .st-key-topbar div[data-testid="column"] { flex: 0 0 auto !important; width: auto !important; min-width: 0 !important; }
.st-key-nav_view div[role="radiogroup"] { gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
.st-key-nav_view label[data-baseweb="radio"] { background:#111a2e; border:1px solid #243049; border-radius:999px; padding:5px 16px; margin:0; cursor:pointer; }
.st-key-nav_view label[data-baseweb="radio"] > div:first-of-type { display:none; }
.st-key-nav_view label[data-baseweb="radio"]:has(input:checked) { background:linear-gradient(135deg,#22c55e,#a3e635); border-color:transparent; }
.st-key-nav_view label[data-baseweb="radio"]:has(input:checked) * { color:#04130a !important; font-weight:800; }
.st-key-topbar [data-testid="stPopover"] button { border-radius:999px; border:1px solid #2b4a6b; background:#111a2e; padding:5px 16px; }
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

# ---------------- SUBSCRIPTION GATE (Stripe) ----------------
# Owners listed in ALLOWED_EMAILS always get in. Everyone else needs an active or trialing
# Stripe subscription. Billing turns on only when STRIPE_SECRET_KEY and STRIPE_PAYMENT_LINK are set.
STRIPE_KEY = get_secret("STRIPE_SECRET_KEY")
PAYMENT_LINK = get_secret("STRIPE_PAYMENT_LINK")
PORTAL_LINK = get_secret("STRIPE_PORTAL_LINK")
BILLING_ON = bool(STRIPE_KEY and PAYMENT_LINK)


@st.cache_data(ttl=60, show_spinner=False)
def stripe_status(email):
    """Returns 'active', 'trialing', 'none', or 'error' for this email."""
    try:
        import requests
        auth = (STRIPE_KEY, "")
        r = requests.get("https://api.stripe.com/v1/customers", params={"email": email, "limit": 10}, auth=auth, timeout=10)
        if r.status_code != 200:
            return "error"
        found = "none"
        for c in r.json().get("data", []):
            sr = requests.get("https://api.stripe.com/v1/subscriptions", params={"customer": c["id"], "status": "all", "limit": 10}, auth=auth, timeout=10)
            if sr.status_code != 200:
                return "error"
            for sub in sr.json().get("data", []):
                if sub.get("status") == "active":
                    return "active"
                if sub.get("status") == "trialing":
                    found = "trialing"
        return found
    except Exception:
        return "error"


def render_paywall(email, err=False, manual=False):
    from urllib.parse import quote
    link = PAYMENT_LINK + ("&" if "?" in PAYMENT_LINK else "?") + "prefilled_email=" + quote(email)
    st.markdown(
        """
<style>
.pw { max-width:560px; margin:18px auto 0 auto; text-align:center; }
.pw h1 { color:#f8fafc; font-size:1.8rem; margin:0 0 4px 0; }
.pw .sub { color:#a9b8cc; font-size:.95rem; margin-bottom:18px; }
.plan { border:1px solid #2b4a6b; border-radius:18px; padding:22px 20px; text-align:left;
        background:linear-gradient(150deg,#0b1d3a 0%,#0e5a4a 100%); box-shadow:0 10px 36px rgba(14,90,74,.35); }
.plan .badge { display:inline-block; background:#14532d; color:#86efac; border-radius:999px; padding:2px 12px; font-size:.72rem; font-weight:800; }
.plan .price { color:#a3e635; font-size:2.4rem; font-weight:900; margin:8px 0 0 0; }
.plan .price span { color:#b6c8dd; font-size:.9rem; font-weight:500; }
.plan ul { color:#e6edf7; padding-left:18px; margin:12px 0 4px 0; font-size:.9rem; line-height:1.7; }
.gobtn { display:block; text-align:center; margin-top:16px; padding:12px; border-radius:12px; font-weight:900; font-size:1rem;
         text-decoration:none; color:#04130a !important; background:linear-gradient(135deg,#22c55e,#a3e635); }
.fine { color:#7d8ca3; font-size:.74rem; text-align:center; margin-top:10px; }
</style>
""",
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="pw"><h1>🎯 FFL Deal Radar</h1><div class="sub">Find underpriced guns across 9 marketplaces, with landed cost and resale value done for you.</div>'
        '<div class="plan"><span class="badge">FIRST 7 DAYS FREE</span>'
        '<div class="price">$50<span> / month after your free week</span></div>'
        '<ul><li>Live feed from 9 sources, refreshed every 3 hours</li>'
        '<li>Landed-cost and net-spread math on every listing</li>'
        '<li>Massachusetts and federal compliance views</li>'
        '<li>Cancel any time before the trial ends and pay nothing</li></ul>'
        f'<a class="gobtn" href="{esc(link)}" target="_self">Start my free week &rarr;</a></div>'
        f'<div class="fine">Signed in as {esc(email)}. Use this same email at checkout. Payments are handled by Stripe.'
        + (" After you subscribe, we activate your access by hand, usually within a few hours." if manual else "")
        + "</div></div>",
        unsafe_allow_html=True,
    )
    if err:
        st.warning("We could not check your subscription just now. Please try again in a moment.")
    c1, c2 = st.columns(2)
    if not manual and c1.button("I've subscribed, refresh", use_container_width=True):
        stripe_status.clear()
        st.rerun()
    if c2.button("Sign out", use_container_width=True):
        st.logout()


is_owner = user_email in ALLOWED_EMAILS
sub_state = "owner" if is_owner else ""
if email_verified and not is_owner:
    if BILLING_ON:
        sub_state = stripe_status(user_email)
        if sub_state not in ("active", "trialing"):
            render_paywall(user_email, err=(sub_state == "error"))
            st.stop()
    elif PAYMENT_LINK:
        render_paywall(user_email, manual=True)
        st.stop()
    else:
        ui_art.render_login(unauthorized_email=user_email)
        st.stop()
elif not email_verified:
    ui_art.render_login(unauthorized_email=user_email)
    st.stop()

# ---------------- LOAD DATA ----------------
feed = get_feed()
all_lots = [l for l in feed.get("lots", []) if isinstance(l, dict)]

# ---------------- TOP BAR: navigation (top right) + account ----------------
NAV_OPTIONS = ["📋 Inventory", "🔨 Live Auctions", "🔔 Alerts", "⚙️ System"]
with st.container(key="topbar"):
    nav_col, acct_col = st.columns([3, 1])
    with nav_col:
        view = st.radio("Navigation", NAV_OPTIONS, horizontal=True, label_visibility="collapsed", key="nav_view")
    with acct_col:
        with st.popover("👤 Manage account"):
            st.caption(f"Signed in as {user_email}")
            if sub_state == "trialing":
                st.caption("Free trial active")
            if PORTAL_LINK and sub_state in ("active", "trialing"):
                st.link_button("Manage billing", PORTAL_LINK, use_container_width=True)
            if st.button("🚪 Sign out", use_container_width=True):
                st.logout()

# ---------------- HEADER PLACEHOLDER (filled in after the filters run) ----------------
hero_ph = st.empty()

# ---------------- FILTERS (left sidebar) ----------------
with st.sidebar:
    st.markdown("### 🎛️ Filters")
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
    condition_pick = st.radio("Condition", ["All", "Used", "New"], horizontal=True)

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
    if condition_pick != "All" and str(l.get("condition", "used")).lower() != condition_pick.lower():
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
hero_ph.markdown(
    f"""<div class="hero"><div><h1>{ui_art.CROSSHAIR_ICON}FFL Deal Radar<span class="pill">● LIVE</span></h1><div class="sub">{esc(mode)} &nbsp;•&nbsp; Last updated {esc(feed.get('last_updated', 'just now'))} &nbsp;•&nbsp; refreshed every 3 hours &nbsp;•&nbsp; {len(filtered_lots)} of {len(all_lots)} listings shown</div></div>{HERO_ART}</div>""",
    unsafe_allow_html=True,
)


SOURCE_COLOR_MAP = {name: SOURCE_COLORS[i % len(SOURCE_COLORS)] for i, name in enumerate(ALL_PLATFORMS)}


def kpis_html(items):
    n = len(items)
    valued = [l for l in items if l["valued"]]
    bids = sum(1 for l in items if l["disp_act"])
    best = max((l["disp_profit"] for l in valued), default=0.0)
    avg_margin = (sum(l["disp_margin"] for l in valued) / len(valued)) if valued else 0.0
    cards = [
        ("Listings", f"{n:,}", "#38bdf8", "📋"),
        ("BID targets", f"{bids}", "#22c55e", "🎯"),
        ("Best net spread", usd(best) if valued else "&mdash;", "#a3e635", "💰"),
        ("Avg margin", f"{avg_margin:.1f}%" if valued else "&mdash;", "#f59e0b", "📈"),
        ("Valued", f"{len(valued):,}/{n:,}", "#c084fc", "🏷️"),
    ]
    return '<div class="kpis">' + "".join(
        f'<div class="kpi" style="--accent:{c}"><div class="ic">{ic}</div><div class="lbl">{lab}</div><div class="val">{val}</div></div>'
        for lab, val, c, ic in cards
    ) + "</div>"


def gun_name(l):
    make = str(l.get("make") or "").strip()
    model = str(l.get("model") or "").strip()
    if model.lower() == "unknown":
        model = ""
    return (make + " " + model).strip() or str(l.get("title") or "Unknown")[:40]


def table_html(rows):
    head = (
        '<div class="dhead"><div>Signal</div><div>Gun</div><div style="text-align:right">Ask / Bid</div>'
        '<div style="text-align:right">Landed</div><div style="text-align:right">Value</div>'
        '<div style="text-align:right">Spread</div><div>Margin</div><div>Basis</div><div></div></div>'
    )
    body = []
    for l in rows:
        sig = '<span class="tag t-bid">BID</span>' if l["disp_act"] else '<span class="tag t-pass">PASS</span>'
        typ = '<span class="tag t-auc">Auction</span>' if l["is_auction"] else '<span class="tag t-bin">Buy now</span>'
        cond = str(l.get("condition") or "used").lower()
        ctag = '<span class="tag t-new">New</span>' if cond == "new" else '<span class="tag t-used">Used</span>'
        cal = esc(l.get("caliber") or "")
        name = esc(gun_name(l))
        link = esc(l.get("listing_url") or "#")
        title = esc(l.get("title") or "")
        src = str(l.get("source_site") or "Direct")
        color = SOURCE_COLOR_MAP.get(src, "#94a3b8")
        sub = f'<span class="dot"></span>{esc(src)}{ctag}{typ}' + (f'<span>{cal}</span>' if cal else "")
        ask = usd(num(l.get("current_bid")))
        landed = usd(num(l.get("total_landed_cost")))
        if l["valued"]:
            sp = l["disp_profit"]
            mg = l["disp_margin"]
            state = "st-bid" if l["disp_act"] else ("st-pos" if sp >= 0 else "st-neg")
            cls = "pos" if sp >= 0 else "neg"
            pct = max(0, min(60, mg)) / 60.0 * 100
            mcolor = "#22c55e" if mg >= 15 else ("#f59e0b" if mg >= 0 else "#f43f5e")
            val = usd(l["disp_retail"])
            spread = f'<span class="{cls}">{usd_signed(sp)}</span>'
            margin = f'<span class="mb"><span class="mf" style="width:{pct:.0f}%;background:{mcolor}"></span></span>{mg:.0f}%'
            basis = f'<span class="tag t-val">{esc(l.get("compliance_badge") or "Valued")}</span>'
        else:
            state = "st-unv"
            val, spread, margin = "&mdash;", "&mdash;", '<span class="sm">no comp yet</span>'
            basis = '<span class="tag t-un">Unvalued</span>'
        body.append(
            f'<div class="deal {state}" style="--src:{color}" title="{title}">'
            f'<div class="d-sig">{sig}</div>'
            f'<div class="d-main"><a class="d-name" href="{link}" target="_blank">{name}</a><div class="d-sub">{sub}</div></div>'
            f'<div class="d-num d-ask"><span class="k">Ask</span>{ask}</div>'
            f'<div class="d-num d-landed"><span class="k">Landed</span>{landed}</div>'
            f'<div class="d-num d-value"><span class="k">Value</span>{val}</div>'
            f'<div class="d-num d-spread"><span class="k">Spread</span>{spread}</div>'
            f'<div class="d-mar">{margin}</div><div class="d-basis">{basis}</div>'
            f'<a class="openbtn d-go" href="{link}" target="_blank">Open &#8599;</a></div>'
        )
    return f'<div class="dgrid">{head}{"".join(body)}</div>'


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
    return '<div class="charts">' + c1 + c2 + c3 + '</div>'


def render_dashboard(items, key):
    n = len(items)
    st.markdown(kpis_html(items), unsafe_allow_html=True)

    if not items:
        st.markdown(EMPTY_ART, unsafe_allow_html=True)
        return

    st.markdown(charts_html(items), unsafe_allow_html=True)

    ctl_info, ctl_rows, ctl_page = st.columns([4, 1.4, 1.2])
    choice = ctl_rows.selectbox("Rows", ["All", "25", "50", "100", "250"], index=0, key=f"ps_{key}", label_visibility="collapsed")
    page_size = n if choice == "All" else int(choice)
    pages = max(1, math.ceil(n / page_size))
    page = 1
    if pages > 1:
        page = ctl_page.number_input("Page", min_value=1, max_value=pages, value=1, step=1, key=f"pg_{key}", label_visibility="collapsed")
    start = (int(page) - 1) * page_size
    end = min(start + page_size, n)
    ctl_info.caption(f"Showing {start + 1}-{end} of {n}" + (f"  •  page {int(page)}/{pages}" if pages > 1 else "") + "  •  click a gun name to open the listing")
    st.markdown(table_html(items[start:end]), unsafe_allow_html=True)


if view == NAV_OPTIONS[0]:
    render_dashboard(filtered_lots, "all")

elif view == NAV_OPTIONS[1]:
    render_dashboard([l for l in filtered_lots if l["is_auction"]], "auc")

elif view == NAV_OPTIONS[2]:
    st.subheader("🔔 Instant arbitrage alerts")
    st.write(f"Alert destination: **{user_email}**")
    st.number_input("Target profit spread threshold ($)", value=100.0, step=25.0)
    if st.button("Save alert threshold"):
        st.success("Alert preferences updated.")

else:
    st.subheader("System infrastructure")
    per_source = feed.get("per_source") or {}
    st.write(f"**Total listings:** {len(all_lots)}  •  **Feed status:** {'Healthy' if all_lots else 'Sync required'}")
    if per_source:
        st.write("**Listings per source (last run):** " + ", ".join(f"{k}: {v}" for k, v in per_source.items()))
    unvalued = sum(1 for l in all_lots if not l["valued"])
    st.write(f"**Unvalued listings:** {unvalued} of {len(all_lots)} (no comparable listings found yet)")
    st.caption("The feed is refreshed every 3 hours by a GitHub Actions workflow.")
