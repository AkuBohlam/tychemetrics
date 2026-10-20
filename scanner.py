import os
import json
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
STATE_FILE = "signals.json"

# ==========================================
# 1. INFRASTRUKTUR & MANAJEMEN MEMORI
# ==========================================
def send_alert(message):
    if not BOT_TOKEN or not CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Gagal mengirim Telegram: {e}")

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"updated_at": "", "active_signals": [], "radar_locks": {}}

def save_state(state_data):
    state_data["updated_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    with open(STATE_FILE, "w") as f:
        json.dump(state_data, f, indent=2)

# Perhitungan ATR Institusional (Wilder's Smoothing murni ala MT5)
def calculate_atr_institutional(df, period=14):
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift()).abs()
    low_close = (df['Low'] - df['Close'].shift()).abs()
    
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    
    # Menggunakan metode RMA/EWM persis seperti rumus J. Welles Wilder Jr.
    atr = true_range.ewm(alpha=1/period, adjust=False).mean()
    return atr

# ==========================================
# 2. CORE ENGINE: INSTITUTIONAL 3 PILAR + DYNAMIC RR
# ==========================================
def core_institutional_engine(ticker_symbol, pair_name, current_state):
    try:
        pair_lock = f"CORE_{ticker_symbol}"
        is_gold = "GC=F" in ticker_symbol
        dec = 2 if is_gold else 5
        spread_allowance = 0.50 if is_gold else 0.00005

        # Anti-Spam: Jika sudah aktif, kunci dan skip
        if current_state["radar_locks"].get(pair_lock) == "ACTIVE":
            return current_state

        # --- PILAR 1: TREN (TIMEFRAME H1) ---
        df_h1 = yf.download(ticker_symbol, period="1mo", interval="1h", progress=False)
        if df_h1.empty or len(df_h1) < 200: return current_state
        if isinstance(df_h1.columns, pd.MultiIndex): df_h1.columns = df_h1.columns.get_level_values(0)

        df_h1['MA50'] = df_h1['Close'].rolling(50).mean()
        df_h1['MA200'] = df_h1['Close'].rolling(200).mean()
        
        last_h1 = df_h1.iloc[-2]
        c_h1, ma50, ma200 = float(last_h1['Close']), float(last_h1['MA50']), float(last_h1['MA200'])
        
        trend = "NONE"
        if ma50 > ma200 and c_h1 > ma50: trend = "UPTREND"
        elif ma50 < ma200 and c_h1 < ma50: trend = "DOWNTREND"

        if trend == "NONE": return current_state

        # --- PILAR 2 & DYNAMIC RR (STRUKTUR H1) ---
        lookback = 48 # Struktur 2 hari terakhir (48 jam)
        major_res = float(df_h1['High'].iloc[-lookback:-2].max())
        major_sup = float(df_h1['Low'].iloc[-lookback:-2].min())

        ob_top, ob_bot = 0.0, 0.0
        if trend == "UPTREND":
            ob_bot = major_sup
            ob_top = ob_bot + (5.0 if is_gold else 0.0020)
        elif trend == "DOWNTREND":
            ob_top = major_res
            ob_bot = ob_top - (5.0 if is_gold else 0.0020)

        current_price = float(df_h1['Close'].iloc[-1])
        if not (ob_bot <= current_price <= ob_top):
            return current_state # Harga belum masuk zona Supply/Demand

        # --- PILAR 3: ENGULFING & ATR (TIMEFRAME M5) ---
        df_m5 = yf.download(ticker_symbol, period="5d", interval="5m", progress=False)
        if df_m5.empty: return current_state
        if isinstance(df_m5.columns, pd.MultiIndex): df_m5.columns = df_m5.columns.get_level_values(0)
        
        df_m5['ATR'] = calculate_atr_institutional(df_m5, 14)
        
        prev_m5 = df_m5.iloc[-2] 
        curr_m5 = df_m5.iloc[-1] 
        atr_value = float(curr_m5['ATR'])

        is_bullish_engulfing = (prev_m5['Close'] < prev_m5['Open']) and \
                               (curr_m5['Close'] > curr_m5['Open']) and \
                               (curr_m5['Close'] > prev_m5['Open']) and \
                               (curr_m5['Open'] <= prev_m5['Close'])

        is_bearish_engulfing = (prev_m5['Close'] > prev_m5['Open']) and \
                               (curr_m5['Close'] < curr_m5['Open']) and \
                               (curr_m5['Close'] < prev_m5['Open']) and \
                               (curr_m5['Open'] >= prev_m5['Close'])

        # --- EKSEKUSI DENGAN FILTER RR DINAMIS ---
        if trend == "UPTREND" and is_bullish_engulfing:
            entry_p = float(curr_m5['Close']) + spread_allowance
            sl_p = float(curr_m5['Low']) - atr_value
            risk = abs(entry_p - sl_p)
            
            # Dynamic TP di Resistance Mayor
            reward = major_res - entry_p
            if risk > 0 and reward > 0:
                rr_ratio = reward / risk
                if rr_ratio >= 1.5: # Syarat Minimal Kelayakan RR
                    entry_p, sl_p, tp_p = round(entry_p, dec), round(sl_p, dec), round(major_res, dec)
                    
                    current_state["active_signals"].append({
                        "strategy": "Core: OB+Engulfing", "pair": pair_name, "type": "BUY MARKET",
                        "entry": entry_p, "sl": sl_p, "tp": tp_p, "rr": f"1 : {round(rr_ratio, 1)}", "status": "OPEN"
                    })
                    current_state["radar_locks"][pair_lock] = "ACTIVE"
                    
                    msg = f"🎯 *[EKSEKUSI: CORE INSTITUTIONAL]*\n\n📊 *Instrumen:* {pair_name}\n⚡ *Aksi:* BUY SEKARANG (Market)\n📍 *Entry:* `{entry_p}` *(+Spread)*\n🛑 *SL:* `{sl_p}` *(ATR Protected)*\n💰 *TP:* `{tp_p}` *(Structural Target)*\n\n💡 *Logic:* Demand tervalidasi Engulfing M5.\n🎓 *Risk/Reward:* 1 : {round(rr_ratio, 1)}. Target diletakkan logis di Resistance terdekat, bukan sekadar baku 1:3."
                    send_alert(msg)

        elif trend == "DOWNTREND" and is_bearish_engulfing:
            entry_p = float(curr_m5['Close'])
            sl_p = float(curr_m5['High']) + atr_value + spread_allowance
            risk = abs(sl_p - entry_p)
            
            # Dynamic TP di Support Mayor
            reward = entry_p - major_sup
            if risk > 0 and reward > 0:
                rr_ratio = reward / risk
                if rr_ratio >= 1.5: # Syarat Minimal Kelayakan RR
                    entry_p, sl_p, tp_p = round(entry_p, dec), round(sl_p, dec), round(major_sup, dec)

                    current_state["active_signals"].append({
                        "strategy": "Core: OB+Engulfing", "pair": pair_name, "type": "SELL MARKET",
                        "entry": entry_p, "sl": sl_p, "tp": tp_p, "rr": f"1 : {round(rr_ratio, 1)}", "status": "OPEN"
                    })
                    current_state["radar_locks"][pair_lock] = "ACTIVE"
                    
                    msg = f"🎯 *[EKSEKUSI: CORE INSTITUTIONAL]*\n\n📊 *Instrumen:* {pair_name}\n⚡ *Aksi:* SELL SEKARANG (Market)\n📍 *Entry:* `{entry_p}`\n🛑 *SL:* `{sl_p}` *(ATR+Spread Protected)*\n💰 *TP:* `{tp_p}` *(Structural Target)*\n\n💡 *Logic:* Supply tervalidasi Engulfing M5.\n🎓 *Risk/Reward:* 1 : {round(rr_ratio, 1)}. Target diletakkan logis di Support terdekat, bukan sekadar baku 1:3."
                    send_alert(msg)

        return current_state
    except Exception as e:
        print(f"Error pada Core Engine {ticker_symbol}: {e}")
        return current_state

# ==========================================
# 3. MANAJER UTAMA (RUNNER)
# ==========================================
def run_market_scan():
    current_state = load_state()
    instruments = [
        {"name": "XAU/USD (Gold)", "ticker": "GC=F"},
        {"name": "EUR/USD", "ticker": "EURUSD=X"},
        {"name": "GBP/USD", "ticker": "GBPUSD=X"}
    ]
    
    if len(current_state["active_signals"]) > 10:
        current_state["active_signals"] = current_state["active_signals"][-10:]

    for item in instruments:
        current_state = core_institutional_engine(item["ticker"], item["name"], current_state)
        
    save_state(current_state)

if __name__ == "__main__":
    run_market_scan()
