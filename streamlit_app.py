# app_test.py
# Minimal test harness for MOMENTUMINTEL UI with mocked data
# Run with: streamlit run app_test.py

import streamlit as st
from datetime import datetime, timedelta
import random
from types import SimpleNamespace
import pandas as pd
import pandas_ta as ta
import pytz
import time

st.set_page_config(page_title="MOMENTUMINTEL v2.2 (TEST)", page_icon="🚀", layout="wide")
st.title("🚀 MOMENTUMINTEL (TEST MODE)")
st.markdown("**POST-OPEN OPTIONS MOMENTUM INTELLIGENCE ENGINE v2.2 — MOCKED DATA**")

# ----------------- CONFIG -----------------
TEST_MODE = True

MODES = {
    "premarket": {"start": "04:00", "end": "09:30", "name": "PRE-MARKET", "vol_min": 300, "oi_min": 800, "spread_max": 0.08},
    "postopen": {"start": "09:45", "end": "11:30", "name": "POST-OPEN", "vol_min": 750, "oi_min": 1500, "spread_max": 0.06},
    "midday": {"start": "11:30", "end": "14:00", "name": "MIDDAY", "vol_min": 500, "oi_min": 1200, "spread_max": 0.07},
    "powerhour": {"start": "14:00", "end": "16:00", "name": "POWER HOUR", "vol_min": 600, "oi_min": 1000, "spread_max": 0.065}
}

DELTA_MIN, DELTA_MAX = 0.52, 0.58
PREMIUM_MIN = 25000

def get_est_time():
    return datetime.now(pytz.timezone('US/Eastern'))

def auto_detect_mode():
    t = get_est_time().strftime("%H:%M")
    for m, cfg in MODES.items():
        if cfg["start"] <= t <= cfg["end"]:
            return m
    return "postopen"

# ----------------- MOCK HELPERS -----------------
def mock_snapshot_ticker(ticker):
    day = SimpleNamespace(change_percent=round(random.uniform(-6, 6), 2), volume=random.randint(50000, 2000000))
    last_trade = SimpleNamespace(price=round(random.uniform(20, 400), 2))
    snap = SimpleNamespace(ticker=ticker, day=day, last_trade=last_trade, prev_day=SimpleNamespace(volume=random.randint(30000, 500000)))
    return snap

def mock_get_snapshot_indices(tickers):
    return [SimpleNamespace(last_trade=SimpleNamespace(price=random.uniform(12, 30)))]

def mock_get_snapshot_all():
    sample_tickers = ["AAPL","MSFT","NVDA","TSLA","AMD","AMZN","META","NFLX","INTC","BA","F","GM","PLTR","SQ","UBER","ZM","DOCU","SHOP"]
    snaps = []
    for t in sample_tickers:
        s = mock_snapshot_ticker(t)
        s.ticker = t
        snaps.append(s)
    return snaps

def mock_list_snapshot_options_chain(underlying, params=None):
    contracts = []
    base_price = round(random.uniform(20, 400), 2)
    for i in range(6):
        strike = round(base_price * (1 + random.uniform(-0.03, 0.03)), 2)
        delta = random.uniform(DELTA_MIN, DELTA_MAX)
        bid = round(random.uniform(0.5, 5), 2)
        ask = round(bid + random.uniform(0.05, 0.5), 2)
        contract = SimpleNamespace(
            greeks=SimpleNamespace(delta=delta, gamma=random.uniform(0.01, 0.2)),
            ask=ask, bid=bid,
            implied_volatility=random.uniform(20, 120),
            day=SimpleNamespace(volume=random.randint(1, 500)),
            open_interest=random.randint(0, 5000),
            ticker=f"{underlying}_OPT_{i}",
            details=SimpleNamespace(strike=strike, expiration_date=(datetime.now().date() + timedelta(days=random.randint(1,40))).isoformat())
        )
        contracts.append(contract)
    return contracts

def mock_get_aggs(ticker, multiplier, timespan, limit=120):
    now = int(datetime.now().timestamp() * 1000)
    aggs = []
    price = 100.0 + random.uniform(-5,5)
    for i in range(limit):
        price += random.uniform(-0.5, 0.5)
        a = SimpleNamespace(high=price+0.2, low=price-0.2, close=price, volume=random.randint(100,1000), timestamp=now - (limit-i)*60000)
        aggs.append(a)
    return aggs

# ----------------- OVERRIDES FOR TEST MODE -----------------
def fetch_market_regime():
    vix = mock_get_snapshot_indices(["I:VIX"])[0].last_trade.price
    regime = "HIGH VOLATILITY" if vix > 25 else "BULLISH"
    st.success(f"MARKET REGIME: {regime} | VIX {vix:.2f}")
    return regime, vix

def get_top15_momentum():
    snaps = mock_get_snapshot_all()
    candidates = []
    for s in snaps:
        rel_vol = (s.day.volume or 1) / (s.prev_day.volume or 1)
        candidates.append({"ticker": s.ticker, "price": s.last_trade.price, "change_pct": s.day.change_percent, "rel_vol": rel_vol})
    candidates.sort(key=lambda x: x["change_pct"] * x["rel_vol"], reverse=True)
    return candidates[:15]

def fetch_options_chain(underlying, current_price, mode_config):
    return mock_list_snapshot_options_chain(underlying)

def technical_confirmation(ticker, current_price):
    # Build a tiny DataFrame from mock aggs and compute simple indicators
    aggs = mock_get_aggs(ticker, 1, "minute", limit=60)
    df = pd.DataFrame([a.__dict__ for a in aggs])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    try:
        df['vwap'] = ta.vwap(df['high'], df['low'], df['close'], df['volume'])
        df['ema9'] = ta.ema(df['close'], length=9)
        df['ema21'] = ta.ema(df['close'], length=21)
        macd = ta.macd(df['close'])
        df['macd'] = macd['MACD_12_26_9']
        df['rsi'] = ta.rsi(df['close'], length=14)
        latest = df.iloc[-1]
        score = 0
        if latest['close'] > latest['vwap']: score += 25
        if latest['ema9'] > latest['ema21']: score += 25
        if latest['macd'] > 0: score += 20
        if 30 < latest['rsi'] < 70: score += 15
        return {"confluence": score, "vwap_pos": "above" if latest['close'] > latest['vwap'] else "below", "rsi": float(latest['rsi'])}
    except Exception:
        return {"confluence": random.randint(30, 70), "vwap_pos": random.choice(["above","below"]), "rsi": random.uniform(30,70)}

def composite_conviction(flow, tech, regime):
    score = 30 * min(1, (flow.get('volume', 0)) / 2000)
    score += 25 * min(1, abs(flow.get('gamma', 0)) * 50)
    score += 20 * (tech['confluence'] / 100)
    score += 15 if regime in ["BULLISH", "HIGH VOLATILITY"] else 0
    return min(100, int(score))

# ----------------- SCANNER / UI -----------------
st.sidebar.header("Scanner Controls")
mode_key = st.sidebar.selectbox("Time-of-Day Mode", options=list(MODES.keys()), 
                                format_func=lambda x: MODES[x]["name"], index=1)
st.sidebar.markdown("**Auto-detects** your current time — or force a mode here.")
if st.sidebar.button("RUN FULL SCAN NOW", type="primary"):
    run_now = True
else:
    run_now = False

def run_scanner(mode_name=None):
    cfg = MODES[mode_name or auto_detect_mode()]
    st.subheader(f"🔥 RUNNING {cfg['name']} SCANNER")
    regime, vix = fetch_market_regime()
    top15 = get_top15_momentum()
    st.write("📊 TOP 15 MOMENTUM STOCKS")
    df_top15 = pd.DataFrame(top15)
    st.dataframe(df_top15, use_container_width=True)
    all_candidates = []
    progress = st.progress(0)
    for i, stock in enumerate(top15):
        time.sleep(0.15)  # simulate work
        opts = fetch_options_chain(stock["ticker"], stock["price"], cfg)
        for opt in opts:
            tech = technical_confirmation(stock["ticker"], stock["price"])
            flow = {"volume": opt.day.volume, "gamma": opt.greeks.gamma}
            conviction = composite_conviction(flow, tech, regime)
            if conviction >= 60:
                all_candidates.append({
                    "ticker": stock["ticker"],
                    "call_put": "CALL",
                    "contract": f"{opt.details.strike} {opt.details.expiration_date}",
                    "limit_entry": round((opt.bid + opt.ask)/2, 2),
                    "conviction": conviction,
                    "delta": opt.greeks.delta,
                    "iv": opt.implied_volatility,
                    **tech
                })
        progress.progress(int((i+1)/len(top15)*100))
    all_candidates.sort(key=lambda x: x["conviction"], reverse=True)
    top3 = all_candidates[:3]
    st.subheader("🏆 TOP 3 TRADES RIGHT NOW")
    if not top3:
        st.info("No high-conviction candidates found in mock run.")
    for i, t in enumerate(top3, 1):
        with st.expander(f"{i}. {t['ticker']} {t['call_put']} {t['contract']} — Conviction {t['conviction']}/100", expanded=True):
            st.metric("Suggested Limit", f"${t['limit_entry']}")
            st.write(f"**Delta:** {t['delta']:.3f} | **IV:** {t['iv']:.1f}% | **Why NOW:** {regime} momentum + {t['vwap_pos']} VWAP breakout")
    st.success("✅ Mock scan complete!")

# bottom run button
if st.button("🚀 Run Full Autonomous Scan", type="primary"):
    run_scanner(mode_key)

# auto-run if sidebar button pressed
if run_now:
    run_scanner(mode_key)

st.caption("TEST MODE • No API key required • Mocked market and options data")
