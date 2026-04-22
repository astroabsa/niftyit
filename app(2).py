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
    "NIFTY": {
        "display_name": "NIFTY",
        "quote_key": "NSE_INDEX|Nifty 50",
        "quote_data_key": "NSE_INDEX:Nifty 50",
        "option_key": "NSE_INDEX|Nifty 50",
    },
    "SENSEX": {
        "display_name": "SENSEX",
        "quote_key": "BSE_INDEX|SENSEX",
        "quote_data_key": "BSE_INDEX:SENSEX",
        "option_key": "BSE_INDEX|SENSEX",
    },
    "BANKNIFTY": {
        "display_name": "BANKNIFTY",
        "quote_key": "NSE_INDEX|Nifty Bank",
        "quote_data_key": "NSE_INDEX:Nifty Bank",
        "option_key": "NSE_INDEX|Nifty Bank",
    },
    "FINNIFTY": {
        "display_name": "FINNIFTY",
        "quote_key": "NSE_INDEX|Nifty Fin Service",
        "quote_data_key": "NSE_INDEX:Nifty Fin Service",
        "option_key": "NSE_INDEX|Nifty Fin Service",
    },
    "MIDCPNIFTY": {
        "display_name": "MIDCPNIFTY",
        "quote_key": "NSE_INDEX|NIFTY MID SELECT",
        "quote_data_key": "NSE_INDEX:NIFTY MID SELECT",
        "option_key": "NSE_INDEX|NIFTY MID SELECT",
    },
}

DARK_TEMPLATE = "plotly_dark"
RED = "#ff4d4f"
GREEN = "#12e67d"
PURPLE = "#b46cff"
YELLOW = "#f1c40f"
MUTED = "#a5a5a5"


def get_secret(name, default=None):
    if name in st.secrets:
        return st.secrets[name]
    return default


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
    "last_status": ("System ready", "info"),
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


st.markdown(
    """
    <style>
    .status-box {padding: 0.9rem 1rem; border-radius: 12px; font-weight: 700; margin-bottom: 1rem;}
    .status-info {background: #1f3c58; color: #edf6ff;}
    .status-success {background: #173f2a; color: #e9fff2;}
    .status-error {background: #4a1f28; color: #fff0f3;}
    .metric-card {background:#121212; border:1px solid #2c2c2c; padding:0.8rem; border-radius:12px; text-align:center;}
    .metric-title {color:#bcbcbc; font-size:0.8rem; margin-bottom:0.25rem;}
    .metric-value {font-size:1.5rem; font-weight:800;}
    .trade-box {background:#000; border:1px solid #2e6cff; border-radius:14px; padding:1rem;}
    .small-note {color:#a5a5a5; font-size:0.9rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


def headers():
    if not ACCESS_TOKEN:
        raise RuntimeError("Missing ACCESS_TOKEN in Streamlit secrets")
    return {"Authorization": f"Bearer {ACCESS_TOKEN}", "Accept": "application/json"}


@st.cache_data(ttl=300, show_spinner=False)
def load_expiry_choices(option_key):
    url = f"https://api.upstox.com/v2/option/contract?instrument_key={option_key}"
    r = requests.get(url, headers=headers(), timeout=10)
    r.raise_for_status()
    payload = r.json()
    contracts = payload.get("data", []) if isinstance(payload, dict) else []
    expiries = sorted({item.get("expiry") for item in contracts if item.get("expiry")})
    return expiries or [DEFAULT_EXPIRY_DATE]



def get_market_data(config):
    quote_keys = [config["quote_key"], INDIA_VIX_QUOTE_KEY]
    url = f"https://api.upstox.com/v2/market-quote/quotes?instrument_key={','.join(quote_keys)}"
    r = requests.get(url, headers=headers(), timeout=10)
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
    r = requests.get(url, headers=headers(), timeout=15)
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



def build_bar_chart(subset, left_col, right_col, title):
    fig = go.Figure()
    fig.add_bar(x=subset["strike_price"].astype(str), y=subset[left_col], name="CALL", marker_color=RED)
    fig.add_bar(x=subset["strike_price"].astype(str), y=subset[right_col], name="PUT", marker_color=GREEN)
    fig.update_layout(template=DARK_TEMPLATE, barmode="group", title=title, height=330, margin=dict(l=10, r=10, t=40, b=10))
    return fig



def build_line_chart(history, title, color):
    fig = go.Figure()
    if history:
        x = [item[0] for item in history]
        y = [item[1] for item in history]
        fig.add_trace(go.Scatter(x=x, y=y, mode="lines+markers", line=dict(color=color, width=2), marker=dict(size=6)))
    fig.update_layout(template=DARK_TEMPLATE, title=title, height=320, margin=dict(l=10, r=10, t=40, b=10), xaxis_title="Time")
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

    active_res_strike = int(subset.loc[subset["call_chg_oi"].idxmax(), "strike_price"])
    active_sup_strike = int(subset.loc[subset["put_chg_oi"].idxmax(), "strike_price"])
    battleground = int(subset.loc[subset["call_chg_oi"].abs().idxmax(), "strike_price"])

    bull_prob = max(5, min(95, 50 + (total_pcr - 1.0) * 40 + (vix_chg * -2)))

    alert_msg = "SIDEWAYS"
    alert_emoji = "⚖️"
    status_type = "info"
    if spot > active_res_strike:
        alert_msg = "STRONG BREAKOUT"
        alert_emoji = "🚀"
        status_type = "success"
    elif spot < active_sup_strike:
        alert_msg = "STRONG BREAKDOWN"
        alert_emoji = "📉"
        status_type = "error"

    trade_signal = f"{symbol} {alert_msg}"
    trade_reason = f"Exp {expiry} | Res {active_res_strike} | Sup {active_sup_strike} | PCR {total_pcr:.2f} | Auto-refresh active"
    status_text = f"{symbol} [{expiry}] + India VIX: {alert_emoji} {alert_msg}"

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
        lines.extend([
            f"Active Res: {active_res_strike}",
            f"Active Sup: {active_sup_strike}",
            f"Status: {alert_emoji} {alert_msg}",
        ])
        send_telegram("\n".join(lines))
        st.session_state.last_reported_minute = now.minute

    st.session_state.prev_vix = vix
    st.session_state.last_signal = trade_signal
    st.session_state.last_reason = trade_reason
    st.session_state.last_status = (status_text, status_type)

    return {
        "df": df,
        "subset": subset,
        "spot": spot,
        "vix": vix,
        "vix_chg": vix_chg,
        "pcr": total_pcr,
        "active_res": active_res_strike,
        "active_sup": active_sup_strike,
        "battleground": battleground,
        "bull_prob": bull_prob,
        "alert_msg": alert_msg,
        "status_type": status_type,
        "time": curr_time,
    }


st.title("FNO Intelligence Terminal")
st.caption("Streamlit version of your F&O scanner with Upstox + Telegram secrets support.")

if not ACCESS_TOKEN:
    st.error("Missing ACCESS_TOKEN. Add it in Streamlit secrets before running.")
    st.stop()

with st.sidebar:
    st.header("Controls")
    symbol = st.selectbox("Symbol", list(INSTRUMENTS.keys()), index=0)
    config = INSTRUMENTS[symbol]

    try:
        expiries = load_expiry_choices(config["option_key"])
    except Exception as e:
        expiries = [DEFAULT_EXPIRY_DATE]
        st.warning(f"Could not load expiries: {e}")

    default_index = expiries.index(DEFAULT_EXPIRY_DATE) if DEFAULT_EXPIRY_DATE in expiries else 0
    expiry = st.selectbox("Expiry", expiries, index=default_index)
    refresh_rate = st.slider("Refresh seconds", 5, 60, REFRESH_RATE, 1)
    auto_refresh = st.toggle("Auto refresh", value=True)
    manual_refresh = st.button("Refresh now", use_container_width=True)
    clear_history = st.button("Clear trend history", use_container_width=True)

    st.markdown("---")
    st.write("Secrets in use")
    st.code("ACCESS_TOKEN\nTG_BOT_TOKEN\nTG_CHAT_ID\nDEFAULT_EXPIRY_DATE\nREFRESH_RATE")

if clear_history:
    st.session_state.pcr_history = []
    st.session_state.vix_history = []
    st.session_state.prev_vix = None
    st.session_state.last_reported_minute = None

run_cycle = manual_refresh or auto_refresh
result = None
error_message = None

if run_cycle:
    try:
        spot, vix = get_market_data(config)
        chain = get_option_chain(config, expiry)
        result = analyze(chain, spot, vix, config["display_name"], expiry)
    except Exception as e:
        error_message = str(e)
        st.session_state.last_status = (f"❌ {error_message}", "error")

status_text, status_type = st.session_state.last_status
st.markdown(f'<div class="status-box status-{status_type}">{status_text}</div>', unsafe_allow_html=True)

if error_message:
    st.error(error_message)

metrics = st.columns(6)
spot_text = f"{result['spot']:,.2f}" if result else "--"
pcr_text = f"{result['pcr']:.2f}" if result else "--"
vix_text = f"{result['vix']:.2f}" if result and result['vix'] is not None else "--"
vix_delta = f"{result['vix_chg']:+.2f}%" if result and result['vix'] is not None else None
bull_text = f"{result['bull_prob']:.0f}%" if result else "--"
res_text = str(result['active_res']) if result else "--"
sup_text = str(result['active_sup']) if result else "--"

metrics[0].metric(f"{config['display_name']} Spot", spot_text)
metrics[1].metric("PCR", pcr_text)
metrics[2].metric("India VIX", vix_text, vix_delta)
metrics[3].metric("Bull Probability", bull_text)
metrics[4].metric("Active Resistance", res_text)
metrics[5].metric("Active Support", sup_text)

mid1, mid2 = st.columns([3, 1])
with mid2:
    st.markdown(f'<div class="metric-card"><div class="metric-title">BATTLEGROUND</div><div class="metric-value">{result["battleground"] if result else "--"}</div></div>', unsafe_allow_html=True)
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    st.markdown(f'<div class="metric-card"><div class="metric-title">SYNC</div><div class="metric-value">{refresh_rate}s</div></div>', unsafe_allow_html=True)
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    trade_bias = result['alert_msg'] if result else "WAIT"
    st.markdown(f'<div class="metric-card"><div class="metric-title">MARKET STATE</div><div class="metric-value">{trade_bias}</div></div>', unsafe_allow_html=True)

with mid1:
    if result is not None:
        oi_fig = build_bar_chart(result["subset"], "call_options.market_data.oi", "put_options.market_data.oi", "OI Buildup")
        chg_fig = build_bar_chart(result["subset"], "call_chg_oi", "put_chg_oi", "Change in OI")
        c1, c2 = st.columns(2)
        c1.plotly_chart(oi_fig, use_container_width=True)
        c2.plotly_chart(chg_fig, use_container_width=True)
    else:
        st.info("No chart data yet. Click refresh or enable auto refresh.")

bottom1, bottom2 = st.columns(2)
with bottom1:
    pcr_fig = build_line_chart(st.session_state.pcr_history, "PCR Trend", PURPLE)
    st.plotly_chart(pcr_fig, use_container_width=True)
with bottom2:
    vix_color = GREEN
    if len(st.session_state.vix_history) > 1 and st.session_state.vix_history[-1][1] >= st.session_state.vix_history[0][1]:
        vix_color = "#ff6b6b"
    vix_fig = build_line_chart(st.session_state.vix_history, "India VIX Trend", vix_color)
    st.plotly_chart(vix_fig, use_container_width=True)

st.markdown("<div class='trade-box'>", unsafe_allow_html=True)
st.subheader(st.session_state.last_signal)
st.write(st.session_state.last_reason)
if result is not None:
    st.progress(int(result["bull_prob"]) / 100)
    st.caption(f"Updated at {result['time']}")
st.markdown("</div>", unsafe_allow_html=True)

if result is not None:
    show_cols = [
        "strike_price",
        "call_options.market_data.oi",
        "put_options.market_data.oi",
        "call_chg_oi",
        "put_chg_oi",
    ]
    table_df = result["subset"][show_cols].rename(columns={
        "strike_price": "Strike",
        "call_options.market_data.oi": "Call OI",
        "put_options.market_data.oi": "Put OI",
        "call_chg_oi": "Call Chg OI",
        "put_chg_oi": "Put Chg OI",
    })
    st.dataframe(table_df, use_container_width=True, hide_index=True)

if auto_refresh:
    time.sleep(refresh_rate)
    st.rerun()
