import time
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

st.set_page_config(page_title="FNO Intelligence Terminal", layout="wide")

INDIA_VIX_QUOTE_KEY = "NSE_INDEX|India VIX"
INDIA_VIX_DATA_KEY = "NSE_INDEX:India VIX"
INSTRUMENTS = {
    "NIFTY": {"display_name": "NIFTY", "quote_key": "NSE_INDEX|Nifty 50", "quote_data_key": "NSE_INDEX:Nifty 50", "option_key": "NSE_INDEX|Nifty 50"},
    "SENSEX": {"display_name": "SENSEX", "quote_key": "BSE_INDEX|SENSEX", "quote_data_key": "BSE_INDEX:SENSEX", "option_key": "BSE_INDEX|SENSEX"},
    "BANKNIFTY": {"display_name": "BANKNIFTY", "quote_key": "NSE_INDEX|Nifty Bank", "quote_data_key": "NSE_INDEX:Nifty Bank", "option_key": "NSE_INDEX|Nifty Bank"},
    "FINNIFTY": {"display_name": "FINNIFTY", "quote_key": "NSE_INDEX|Nifty Fin Service", "quote_data_key": "NSE_INDEX:Nifty Fin Service", "option_key": "NSE_INDEX|Nifty Fin Service"},
    "MIDCPNIFTY": {"display_name": "MIDCPNIFTY", "quote_key": "NSE_INDEX|NIFTY MID SELECT", "quote_data_key": "NSE_INDEX:NIFTY MID SELECT", "option_key": "NSE_INDEX|NIFTY MID SELECT"},
}

RED = "#ff4d4f"
GREEN = "#20e27a"
PURPLE = "#b46cff"
YELLOW = "#f4c542"
BLUE = "#39a4ff"
BG = "#0c0d0f"
GRID = "rgba(255,255,255,0.08)"
BORDER = "rgba(255,255,255,0.09)"
TEXT = "#f5f7fa"
MUTED = "#99a1ab"
SELECT_BG = "#000000"
SELECT_BORDER = "#2a74b8"
MENU_BG = "#000000"


def get_secret(name, default=None):
    return st.secrets[name] if name in st.secrets else default


ACCESS_TOKEN = get_secret("ACCESS_TOKEN", "")
TG_BOT_TOKEN = get_secret("TG_BOT_TOKEN", "")
TG_CHAT_ID = get_secret("TG_CHAT_ID", "")
DEFAULT_EXPIRY_DATE = get_secret("DEFAULT_EXPIRY_DATE", "2026-04-28")
REFRESH_RATE = int(get_secret("REFRESH_RATE", 10))

for key, default in {
    "pcr_history": [],
    "vix_history": [],
    "last_reported_minute": None,
    "prev_vix": None,
    "last_signal": "AI SCANNING...",
    "last_reason": "Waiting for data...",
    "last_status": ("SYSTEM READY - SELECT SYMBOL AND EXPIRY", "info"),
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

st.markdown(
    f"""
    <style>
    .stApp {{background:{BG}; color:{TEXT};}}
    .block-container {{padding-top:0.65rem; padding-bottom:0.5rem; max-width:100%;}}
    h1, h2, h3, h4, h5, h6, p, div, span, label {{color:{TEXT};}}
    [data-testid="stHeader"] {{background:transparent;}}
    [data-testid="stToolbar"] {{right:0.8rem;}}
    .top-shell {{background:linear-gradient(90deg,#1a1c20,#1d1e21); border:1px solid {BORDER}; border-radius:8px; padding:10px 14px; margin-bottom:12px; min-height:62px; display:flex; align-items:center;}}
    .top-shell-select {{margin-bottom:12px;}}

    /* ── Selectbox control box ── */
    .top-shell-select [data-baseweb="select"] > div:first-child,
    .top-shell-select [data-baseweb="select"] > div:first-child:hover,
    .top-shell-select [data-baseweb="select"] > div:first-child:focus-within {{
        background-color: {SELECT_BG} !important;
        background: {SELECT_BG} !important;
        border: 1px solid {SELECT_BORDER} !important;
        box-shadow: none !important;
        min-height: 48px !important;
    }}

    /* ── All children inside the select control ── */
    .top-shell-select [data-baseweb="select"] *,
    .top-shell-select [data-baseweb="input"],
    .top-shell-select [data-baseweb="input"] > div,
    .top-shell-select [data-baseweb="base-input"],
    .top-shell-select [data-baseweb="base-input"] > div {{
        background-color: {SELECT_BG} !important;
        background: {SELECT_BG} !important;
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
        caret-color: #ffffff !important;
    }}

    /* ── Arrow / chevron icon ── */
    .top-shell-select [data-baseweb="select"] svg,
    .top-shell-select [data-baseweb="select"] svg * {{
        fill: #ffffff !important;
        color: #ffffff !important;
    }}

    /* ── Dropdown popup list ── */
    [data-baseweb="popover"],
    [data-baseweb="popover"] > div,
    [data-baseweb="popover"] ul,
    [data-baseweb="menu"],
    ul[role="listbox"] {{
        background-color: {MENU_BG} !important;
        background: {MENU_BG} !important;
        color: #ffffff !important;
        border: 1px solid {SELECT_BORDER} !important;
    }}

    /* ── Dropdown list items ── */
    [data-baseweb="popover"] li,
    [data-baseweb="menu"] li,
    [data-baseweb="menu"] [role="option"],
    ul[role="listbox"] li {{
        background-color: {MENU_BG} !important;
        background: {MENU_BG} !important;
        color: #ffffff !important;
    }}

    /* ── Hover state ── */
    [data-baseweb="popover"] li:hover,
    [data-baseweb="menu"] [role="option"]:hover,
    ul[role="listbox"] li:hover {{
        background-color: #1a1a1a !important;
        background: #1a1a1a !important;
        color: #ffffff !important;
    }}

    /* ── Selected item ── */
    [data-baseweb="popover"] li[aria-selected="true"],
    [data-baseweb="menu"] [role="option"][aria-selected="true"],
    ul[role="listbox"] li[aria-selected="true"] {{
        background-color: #1d5f99 !important;
        background: #1d5f99 !important;
        color: #ffffff !important;
    }}

    /* ── All text inside popup ── */
    [data-baseweb="popover"] *,
    [data-baseweb="menu"] * {{
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
    }}

    .metric-inline {{font-size:13px; font-weight:800; margin-top:25px; white-space:nowrap;}}
    .metric-blue {{color:{BLUE};}}
    .metric-purple {{color:{PURPLE};}}
    .metric-yellow {{color:{YELLOW};}}
    .sync-wrap {{display:flex; align-items:center; gap:10px; margin-top:24px; justify-content:flex-end;}}
    .sync-text {{font-size:12px; color:{BLUE}; font-weight:800;}}
    .sync-bar {{height:10px; width:110px; background:#3d434c; border-radius:999px; overflow:hidden;}}
    .sync-bar > div {{height:100%; width:80%; background:{BLUE}; border-radius:999px;}}
    .status-banner {{background:#c93c2a; color:white; padding:12px 18px; border-radius:8px; font-size:18px; font-weight:900; text-align:center; margin-bottom:12px; letter-spacing:0.02em;}}
    .panel {{background:#0f1012; border:1px solid {BORDER}; border-radius:8px; padding:8px;}}
    .mini-card {{background:#141518; border:1px solid {BORDER}; border-radius:8px; padding:16px 12px; text-align:center; margin-bottom:14px; min-height:84px; display:flex; flex-direction:column; justify-content:center;}}
    .mini-title {{font-size:11px; font-weight:800; margin-bottom:8px;}}
    .mini-red {{color:#f25d52;}}
    .mini-green {{color:#28dd7d;}}
    .mini-orange {{color:#e89d45;}}
    .mini-value {{font-size:22px; font-weight:900; color:white;}}
    .prob-shell {{background:#111214; border-radius:8px; padding:14px 18px; margin-top:10px; margin-bottom:10px; border:1px solid {BORDER};}}
    .prob-row {{display:flex; align-items:center; gap:20px;}}
    .prob-text {{font-size:18px; font-weight:900; min-width:120px;}}
    .prob-bar {{flex:1; height:12px; background:#4b4f56; border-radius:999px; overflow:hidden;}}
    .prob-fill {{height:100%; background:#2d82c7; border-radius:999px;}}
    .trade-box {{background:#050607; border:1px solid #2166ff; border-radius:10px; padding:16px 20px; margin-top:12px;}}
    .trade-title {{font-size:24px; font-weight:900; color:{BLUE};}}
    .trade-note {{font-size:13px; color:#b8bec7; margin-top:6px;}}
    .small-caption {{font-size:12px; color:{MUTED}; text-align:right; margin-top:6px;}}
    .stButton > button {{width:100%; border-radius:8px; border:none; min-height:42px; font-weight:800; background:#ff1d13; color:white;}}
    .stButton > button:hover {{background:#ff2b22; color:white;}}
    .stDataFrame {{border:1px solid {BORDER}; border-radius:8px; overflow:hidden;}}
    </style>
    """,
    unsafe_allow_html=True,
)


def api_headers():
    if not ACCESS_TOKEN:
        raise RuntimeError("Missing ACCESS_TOKEN in Streamlit secrets")
    return {"Authorization": f"Bearer {ACCESS_TOKEN}", "Accept": "application/json"}


@st.cache_data(ttl=300, show_spinner=False)
def load_expiry_choices(option_key):
    url = f"https://api.upstox.com/v2/option/contract?instrument_key={option_key}"
    r = requests.get(url, headers=api_headers(), timeout=10)
    r.raise_for_status()
    payload = r.json()
    contracts = payload.get("data", []) if isinstance(payload, dict) else []
    expiries = sorted({item.get("expiry") for item in contracts if item.get("expiry")})
    return expiries or [DEFAULT_EXPIRY_DATE]


def get_market_data(config):
    quote_keys = [config["quote_key"], INDIA_VIX_QUOTE_KEY]
    url = f"https://api.upstox.com/v2/market-quote/quotes?instrument_key={','.join(quote_keys)}"
    r = requests.get(url, headers=api_headers(), timeout=10)
    if r.status_code == 401:
        raise RuntimeError("Invalid ACCESS_TOKEN")
    r.raise_for_status()
    data = r.json().get("data", {})
    quote_key = config["quote_data_key"]
    if quote_key not in data:
        raise RuntimeError(f"Quote not found for {config['display_name']}")
    spot = float(data[quote_key]["last_price"])
    vix = float(data[INDIA_VIX_DATA_KEY]["last_price"]) if INDIA_VIX_DATA_KEY in data else None
    return spot, vix


def get_option_chain(config, expiry):
    url = f"https://api.upstox.com/v2/option/chain?instrument_key={config['option_key']}&expiry_date={expiry}"
    r = requests.get(url, headers=api_headers(), timeout=15)
    if r.status_code == 401:
        raise RuntimeError("Invalid ACCESS_TOKEN")
    r.raise_for_status()
    payload = r.json()
    data = payload.get("data", []) if isinstance(payload, dict) else []
    if not data:
        raise RuntimeError(f"Option chain not found for {config['display_name']} @ {expiry}")
    return data


def send_telegram(msg):
    if not TG_BOT_TOKEN or not TG_CHAT_ID or not msg.strip():
        return False
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    try:
        requests.get(url, params={"chat_id": TG_CHAT_ID, "text": msg}, timeout=8)
        return True
    except Exception:
        return False


def base_layout(title, height=330):
    return dict(
        template="plotly_dark",
        title=dict(text=title, x=0.5, xanchor="center", font=dict(size=18, color="#f0f0f0")),
        paper_bgcolor="#0f1012",
        plot_bgcolor="#0f1012",
        height=height,
        margin=dict(l=8, r=8, t=42, b=8),
        legend=dict(orientation="h", y=1.02, x=1, xanchor="right"),
        xaxis=dict(showgrid=True, gridcolor=GRID, zeroline=False, tickfont=dict(color="#d3d7dd")),
        yaxis=dict(showgrid=True, gridcolor=GRID, zeroline=False, tickfont=dict(color="#d3d7dd")),
    )


def build_bar_chart(subset, left_col, right_col, title):
    fig = go.Figure()
    x = subset["strike_price"].astype(str)
    fig.add_bar(x=x, y=subset[left_col], name="CALL", marker_color=RED)
    fig.add_bar(x=x, y=subset[right_col], name="PUT", marker_color=GREEN)
    fig.update_layout(**base_layout(title, 330), barmode="group")
    return fig


def build_line_chart(history, title, color):
    fig = go.Figure()
    if history:
        x = [item[0] for item in history]
        y = [item[1] for item in history]
        fig.add_trace(go.Scatter(x=x, y=y, mode="lines+markers", line=dict(color=color, width=2), marker=dict(size=5)))
    fig.update_layout(**base_layout(title, 300), showlegend=False)
    return fig


def analyze(data, spot, vix, symbol, expiry):
    df = pd.json_normalize(data).sort_values("strike_price")
    if df.empty:
        raise RuntimeError("Empty option chain")
    df["call_chg_oi"] = df["call_options.market_data.oi"] - df["call_options.market_data.prev_oi"]
    df["put_chg_oi"] = df["put_options.market_data.oi"] - df["put_options.market_data.prev_oi"]
    call_sum = df["call_options.market_data.oi"].sum()
    put_sum = df["put_options.market_data.oi"].sum()
    total_pcr = round(put_sum / call_sum, 2) if call_sum else 0.0
    df["dist"] = (df["strike_price"] - spot).abs()
    nearest_idx = df["dist"].idxmin()
    center_pos = df.index.get_loc(nearest_idx)
    subset = df.iloc[max(0, center_pos - 2): min(len(df), center_pos + 3)].copy()
    if subset.empty:
        subset = df.head(5).copy()

    curr_time = datetime.now().strftime("%H:%M:%S")
    st.session_state.pcr_history.append((curr_time, total_pcr))
    st.session_state.pcr_history = st.session_state.pcr_history[-100:]

    vix_chg = 0.0
    if vix is not None:
        st.session_state.vix_history.append((curr_time, vix))
        st.session_state.vix_history = st.session_state.vix_history[-100:]
        prev_vix = st.session_state.prev_vix
        vix_chg = ((vix - prev_vix) / prev_vix * 100) if prev_vix else 0.0

    active_res = int(subset.loc[subset["call_chg_oi"].idxmax(), "strike_price"])
    active_sup = int(subset.loc[subset["put_chg_oi"].idxmax(), "strike_price"])
    battleground = int(subset.loc[subset["call_chg_oi"].abs().idxmax(), "strike_price"])
    bull_prob = max(5, min(95, 50 + (total_pcr - 1.0) * 40 + (vix_chg * -2)))

    alert_msg = "SIDEWAYS"
    alert_emoji = "⚖️"
    status_type = "info"
    if spot > active_res:
        alert_msg = "STRONG BREAKOUT"
        alert_emoji = "🚀"
        status_type = "success"
    elif spot < active_sup:
        alert_msg = "STRONG BREAKDOWN"
        alert_emoji = "⚠️"
        status_type = "error"

    st.session_state.last_signal = f"{symbol} {alert_msg}"
    st.session_state.last_reason = f"Exp {expiry} | Res {active_res} | Sup {active_sup} | PCR {total_pcr:.2f} | Auto-refresh ok"
    st.session_state.last_status = (f"{symbol} [{expiry}] + NIFTY VIX: {alert_emoji} {alert_msg}", status_type)

    now = datetime.now()
    if now.minute != st.session_state.last_reported_minute:
        lines = [
            f"🧠 {symbol} AI PREDICTION: {bull_prob:.0f}% {'BULLISH' if bull_prob >= 50 else 'BEARISH'}",
            f"Expiry: {expiry}",
            f"Spot: {spot:.1f}",
            f"PCR: {total_pcr:.2f}",
        ]
        if vix is not None:
            lines.append(f"India VIX: {vix:.2f}")
        lines.extend([f"Active Res: {active_res}", f"Active Sup: {active_sup}", f"Status: {alert_emoji} {alert_msg}"])
        send_telegram("\\n".join(lines))
        st.session_state.last_reported_minute = now.minute

    st.session_state.prev_vix = vix

    return {
        "subset": subset,
        "spot": spot,
        "vix": vix,
        "vix_chg": vix_chg,
        "pcr": total_pcr,
        "active_res": active_res,
        "active_sup": active_sup,
        "battleground": battleground,
        "bull_prob": bull_prob,
        "alert_msg": alert_msg,
        "time": curr_time,
    }


if not ACCESS_TOKEN:
    st.error("Missing ACCESS_TOKEN in secrets.toml")
    st.stop()

control_cols = st.columns([1.6, 1.6, 2.2, 1.5, 2.2, 1.4, 1.6])
with control_cols[0]:
    st.markdown('<div class="top-shell-select">', unsafe_allow_html=True)
    symbol = st.selectbox("Symbol", list(INSTRUMENTS.keys()), label_visibility="collapsed")
    st.markdown('</div>', unsafe_allow_html=True)

config = INSTRUMENTS[symbol]

try:
    expiries = load_expiry_choices(config["option_key"])
except Exception:
    expiries = [DEFAULT_EXPIRY_DATE]

with control_cols[1]:
    st.markdown('<div class="top-shell-select">', unsafe_allow_html=True)
    default_index = expiries.index(DEFAULT_EXPIRY_DATE) if DEFAULT_EXPIRY_DATE in expiries else 0
    expiry = st.selectbox("Expiry", expiries, index=default_index, label_visibility="collapsed")
    st.markdown('</div>', unsafe_allow_html=True)

result = None
error_message = None
auto_refresh = True
try:
    spot, vix = get_market_data(config)
    chain = get_option_chain(config, expiry)
    result = analyze(chain, spot, vix, config["display_name"], expiry)
except Exception as e:
    error_message = str(e)
    st.session_state.last_status = (f"❌ {error_message}", "error")

spot_text = f"{result['spot']:,.2f}" if result else "--"
pcr_text = f"{result['pcr']:.2f}" if result else "--"
vix_text = f"{result['vix']:.2f} ({result['vix_chg']:+.2f}%)" if result and result['vix'] is not None else "--"

with control_cols[2]:
    st.markdown(f'<div class="top-shell"><div class="metric-inline metric-blue">{config["display_name"]} SPOT: {spot_text}</div></div>', unsafe_allow_html=True)
with control_cols[3]:
    st.markdown(f'<div class="top-shell"><div class="metric-inline metric-purple">PCR: {pcr_text}</div></div>', unsafe_allow_html=True)
with control_cols[4]:
    st.markdown(f'<div class="top-shell"><div class="metric-inline metric-yellow">INDIA VIX: {vix_text}</div></div>', unsafe_allow_html=True)
with control_cols[5]:
    st.markdown(f'<div class="top-shell"><div class="sync-wrap"><div class="sync-text">SYNC: {REFRESH_RATE}s</div><div class="sync-bar"><div></div></div></div></div>', unsafe_allow_html=True)
with control_cols[6]:
    if st.button("STOP"):
        auto_refresh = False

status_text, status_type = st.session_state.last_status
status_color_map = {"info": "#2b4f77", "success": "#17743b", "error": "#c93c2a"}
st.markdown(f'<div class="status-banner" style="background:{status_color_map.get(status_type, "#c93c2a")}">{status_text}</div>', unsafe_allow_html=True)

upper_left, upper_mid, upper_right = st.columns([4.2, 4.2, 1.35])
with upper_left:
    if result is not None:
        st.plotly_chart(build_bar_chart(result["subset"], "call_options.market_data.oi", "put_options.market_data.oi", "OI BUILDUP"), use_container_width=True)
    else:
        st.info(error_message or "No data")
with upper_mid:
    if result is not None:
        st.plotly_chart(build_bar_chart(result["subset"], "call_chg_oi", "put_chg_oi", "CHANGE IN OI"), use_container_width=True)
    else:
        st.info(error_message or "No data")
with upper_right:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown(f'<div class="mini-card"><div class="mini-title mini-red">ACTIVE RES (CHG)</div><div class="mini-value">{result["active_res"] if result else "--"}</div></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="mini-card"><div class="mini-title mini-green">ACTIVE SUP (CHG)</div><div class="mini-value">{result["active_sup"] if result else "--"}</div></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="mini-card"><div class="mini-title mini-orange">BATTLEGROUND</div><div class="mini-value">{result["battleground"] if result else "--"}</div></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

bear_label = f"{int(result['bull_prob'])}% BULL" if result and result['bull_prob'] >= 50 else f"{int(result['bull_prob'])}% BEAR" if result else "--"
prob_fill = int(result['bull_prob']) if result else 50
st.markdown(f'<div class="prob-shell"><div class="prob-row"><div class="prob-text">{bear_label}</div><div class="prob-bar"><div class="prob-fill" style="width:{prob_fill}%"></div></div></div></div>', unsafe_allow_html=True)

bottom_left, bottom_right = st.columns(2)
with bottom_left:
    st.plotly_chart(build_line_chart(st.session_state.pcr_history, "PCR TREND", PURPLE), use_container_width=True)
with bottom_right:
    st.plotly_chart(build_line_chart(st.session_state.vix_history, "INDIA VIX TREND", GREEN), use_container_width=True)

st.markdown(f'<div class="trade-box"><div class="trade-title">{st.session_state.last_signal}</div><div class="trade-note">{st.session_state.last_reason}</div></div>', unsafe_allow_html=True)
if result is not None:
    st.markdown(f'<div class="small-caption">Updated at {result["time"]}</div>', unsafe_allow_html=True)
    table_df = result["subset"][["strike_price", "call_options.market_data.oi", "put_options.market_data.oi", "call_chg_oi", "put_chg_oi"]].rename(columns={
        "strike_price": "Strike",
        "call_options.market_data.oi": "Call OI",
        "put_options.market_data.oi": "Put OI",
        "call_chg_oi": "Call Chg OI",
        "put_chg_oi": "Put Chg OI",
    })
    with st.expander("Show data table"):
        st.dataframe(table_df, use_container_width=True, hide_index=True)

if auto_refresh:
    time.sleep(REFRESH_RATE)
    st.rerun()
