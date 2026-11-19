"""Original, hand-drawn SVG artwork and login page for FFL Deal Radar.

All graphics here are generic, original vector shapes created for this project.
"""
import streamlit as st

CROSSHAIR_ICON = (
    '<svg width="30" height="30" viewBox="0 0 40 40" style="vertical-align:-6px;margin-right:8px" '
    'xmlns="http://www.w3.org/2000/svg">'
    '<circle cx="20" cy="20" r="14" fill="none" stroke="#22c55e" stroke-width="2.5"/>'
    '<circle cx="20" cy="20" r="6" fill="none" stroke="#22c55e" stroke-width="2"/>'
    '<circle cx="20" cy="20" r="1.8" fill="#22c55e"/>'
    '<path d="M20 1v10M20 29v10M1 20h10M29 20h10" stroke="#22c55e" stroke-width="2.5" stroke-linecap="round"/>'
    '</svg>'
)

_ART = (
    '<svg viewBox="0 0 640 400" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto">'
    '<defs>'
    '<radialGradient id="glow" cx="50%" cy="45%" r="60%">'
    '<stop offset="0%" stop-color="#22c55e" stop-opacity="0.28"/>'
    '<stop offset="100%" stop-color="#22c55e" stop-opacity="0"/>'
    '</radialGradient>'
    '<linearGradient id="metal" x1="0" y1="0" x2="0" y2="1">'
    '<stop offset="0%" stop-color="#cbd5e1"/>'
    '<stop offset="100%" stop-color="#64748b"/>'
    '</linearGradient>'
    '<linearGradient id="metal2" x1="0" y1="0" x2="0" y2="1">'
    '<stop offset="0%" stop-color="#94a3b8"/>'
    '<stop offset="100%" stop-color="#334155"/>'
    '</linearGradient>'
    '</defs>'
    '<rect width="640" height="400" rx="18" fill="#0b1220"/>'
    '<rect width="640" height="400" rx="18" fill="url(#glow)"/>'
    '<g stroke="#1e293b" stroke-width="1">'
    '<path d="M0 50H640M0 100H640M0 150H640M0 200H640M0 250H640M0 300H640M0 350H640"/>'
    '<path d="M80 0V400M160 0V400M240 0V400M320 0V400M400 0V400M480 0V400M560 0V400"/>'
    '</g>'
    '<g fill="none" stroke="#22c55e" opacity="0.35">'
    '<circle cx="320" cy="190" r="170" stroke-width="1.5"/>'
    '<circle cx="320" cy="190" r="125" stroke-width="1.5"/>'
    '<circle cx="320" cy="190" r="80" stroke-width="1.5"/>'
    '<path d="M320 8V372M138 190H502" stroke-width="1.5" stroke-dasharray="6 8"/>'
    '</g>'
    # pistol silhouette (generic, original)
    '<g transform="translate(150 70)">'
    '<path d="M10 40 H250 Q268 40 268 58 V76 H150 L142 96 Q122 120 94 112 L82 112 L70 198 '
    'Q68 210 54 210 H18 Q4 210 6 196 L28 76 H10 Q0 76 0 66 V50 Q0 40 10 40 Z" fill="url(#metal)"/>'
    '<path d="M82 112 Q100 134 134 120 L142 100" fill="none" stroke="#0b1220" stroke-width="7"/>'
    '<rect x="14" y="48" width="240" height="6" rx="3" fill="#0b1220" opacity="0.35"/>'
    '<g stroke="#0b1220" stroke-width="3" opacity="0.5">'
    '<path d="M182 48V70M192 48V70M202 48V70M212 48V70M222 48V70"/>'
    '</g>'
    '<rect x="236" y="32" width="14" height="9" rx="2" fill="#94a3b8"/>'
    '<rect x="8" y="32" width="12" height="9" rx="2" fill="#94a3b8"/>'
    '<path d="M36 100 L28 150 M44 100 L36 150 M52 100 L44 150" stroke="#0b1220" stroke-width="3" opacity="0.4"/>'
    '</g>'
    # rifle silhouette (generic, original)
    '<g transform="translate(40 290)" opacity="0.9">'
    '<polygon points="10,40 200,16 200,42 168,50 146,84 28,92 8,80" fill="url(#metal2)"/>'
    '<rect x="196" y="12" width="100" height="32" rx="5" fill="url(#metal2)"/>'
    '<rect x="294" y="22" width="300" height="10" rx="3" fill="url(#metal2)"/>'
    '<rect x="214" y="-14" width="90" height="16" rx="8" fill="#475569"/>'
    '<rect x="232" y="0" width="8" height="14" fill="#475569"/>'
    '<rect x="280" y="0" width="8" height="14" fill="#475569"/>'
    '<rect x="586" y="18" width="14" height="18" rx="3" fill="#475569"/>'
    '<path d="M258 44 Q262 66 244 70" fill="none" stroke="#475569" stroke-width="5"/>'
    '</g>'
    '<g fill="#22c55e" font-family="monospace" font-size="12" opacity="0.8">'
    '<text x="30" y="34">SCANNING 9 SOURCES</text>'
    '<text x="470" y="34">SPREAD  +$212</text>'
    '<text x="470" y="52" fill="#38bdf8">MARGIN  34%</text>'
    '</g>'
    '<circle cx="610" cy="30" r="5" fill="#22c55e"/>'
    '</svg>'
)

_LOGIN_CSS = """
<style>
header[data-testid="stHeader"] { display:none; }
footer { visibility:hidden; }
section[data-testid="stSidebar"] { display:none; }
.stApp { background: radial-gradient(1200px 600px at 20% 0%, #0f2a22 0%, #070b14 55%, #05080f 100%); }
.block-container { padding-top: 4vh !important; max-width: 1200px !important; }
.login-title { font-size:2.1rem; font-weight:800; color:#f8fafc; margin:0 0 4px 0; letter-spacing:.3px; }
.login-title span { color:#22c55e; }
.login-sub { color:#94a3b8; font-size:.98rem; margin-bottom:18px; }
.chips { display:flex; gap:8px; flex-wrap:wrap; margin:14px 0 4px 0; }
.chip { background:#0f172a; border:1px solid #1e293b; color:#cbd5e1; border-radius:999px;
        padding:5px 12px; font-size:.78rem; }
.chip b { color:#22c55e; }
.login-card { background:linear-gradient(180deg,#0f172a,#0b1220); border:1px solid #1f2a3c;
              border-radius:16px; padding:26px 26px 18px 26px; box-shadow:0 10px 40px rgba(0,0,0,.45); }
.login-note { color:#64748b; font-size:.74rem; margin-top:10px; }
button[kind="primary"] { background:linear-gradient(90deg,#16a34a,#22c55e) !important; border:0 !important;
                         color:#04130a !important; font-weight:700 !important; height:3rem; }
</style>
"""


def inject_login_css():
    st.markdown(_LOGIN_CSS, unsafe_allow_html=True)


def render_login(unauthorized_email=None):
    """Full login screen. Call st.stop() afterwards."""
    inject_login_css()
    left, right = st.columns([1.35, 1], gap="large")
    with left:
        st.markdown(_ART, unsafe_allow_html=True)
    with right:
        st.markdown(
            '<div style="height:6vh"></div>'
            '<div class="login-card">'
            '<div class="login-title">FFL Deal <span>Radar</span></div>'
            '<div class="login-sub">Dealer portal. Spot underpriced used guns across the web, '
            'ranked by real profit spread.</div>'
            '<div class="chips">'
            '<span class="chip"><b>●</b> Updated hourly</span>'
            '<span class="chip"><b>●</b> Profit and margin</span>'
            '<span class="chip"><b>●</b> MA / Federal modes</span>'
            '</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        if unauthorized_email is not None:
            st.error(f"{unauthorized_email or 'This account'} is not authorized for this portal.")
            st.button("Sign out", on_click=st.logout, use_container_width=True, type="primary")
        else:
            st.button("Sign in with Google", on_click=st.login, use_container_width=True, type="primary")
            st.markdown('<div class="login-note">Access is limited to approved dealer accounts.</div>',
                        unsafe_allow_html=True)
