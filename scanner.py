import os
import json
import requests
import pandas as pd
from datetime import datetime, timezone
import random

# ==========================================
# 0. KONFIGURASI SISTEM & KREDENSIAL
# ==========================================
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TWELVE_API_KEY = os.getenv("TWELVEDATA_API_KEY")
STATE_FILE = "signals.json"

# Menggunakan ticker Spot murni sesuai standar Twelve Data & XM
INSTRUMENTS = [
    {"name": "XAU/USD (Gold)", "ticker": "XAU/USD"}, 
    {"name": "EUR/USD", "ticker": "EUR/USD"},
    {"name": "GBP/USD", "ticker": "GBP/USD"}
]

# ==========================================
# 1. DATABASE BAHASA (ANTI-ROBOT)
# ==========================================
LANG_BUY_CORE = [
    "Harga turun ke area 'grosir' (Demand) dan candle Engulfing M5 muncul layaknya jejak kaki raksasa. Ini pertanda institusi sedang memborong di harga murah sebelum harga dipompa naik.",
    "Kita berenang searah arus tren! Area diskon H1 telah disentuh, dan konfirmasi Engulfing M5 adalah bukti visual bahwa uang besar (Smart Money) baru saja menyapu penjual ritel yang FOMO."
]
LANG_SELL_CORE = [
    "Harga naik ke area 'mahal' (Supply) dan memancing pembeli ritel (FOMO). Candle Engulfing merah di M5 adalah konfirmasi bahwa institusi mulai melakukan aksi buang barang secara besar-besaran.",
    "Tren besar sedang turun. Harga menyentuh batas atap (Resistance) H1 dan membentuk pola penolakan tajam (Engulfing M5). Ini menunjukkan pemain besar sudah siap membanting harga."
]
LANG_BUY_SCALP = [
    "Institusi meninggalkan celah kosong (Imbalance) saat memompa harga naik. Kita memasang jaring penjemputan persis di pangkal momentum M5.",
    "Terdeteksi jejak Bullish Imbalance segar di H1. Titik pantul disiapkan tepat di area Fractal M5."
]
LANG_SELL_SCALP = [
    "Harga turun tajam meninggalkan celah Bearish Imbalance. Titik masuk disempurnakan pada Fractal Supply M5.",
    "Institusi membuang muatan dan menciptakan Imbalance H1. Jaring Sell Limit dipasang di akar momentum M5."
]

WARN_BUY = [
    "Tips Eksekusi: Harga Entry di atas adalah harga mentah grafik (Bid). Wajib tambahkan nilai spread broker Anda pada eksekusi Entry.",
    "Jangan lupa kalibrasi harga penjemputan Anda. Pastikan Anda menambahkan spread broker pada harga Entry agar tereksekusi sempurna."
]
WARN_SELL = [
    "Catatan penting: Posisi SELL rentan tersapu garis Ask. Wajib tambahkan spread broker Anda pada angka SL agar pengaman tidak bocor.",
    "Manajemen Eksekusi: Lindungi posisi SELL dengan menambahkan spread aktual pada batas Stop Loss."
]

# ==========================================
# 2. INFRASTRUKTUR & MANAJEMEN DATA
# ==========================================
def send_alert(message):
    if not BOT_TOKEN or not CHAT_ID: return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}, timeout=10)
    except: pass

def load_state():
    default = {"updated_at": "", "active_signals": [], "radar_locks": {}}
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                data = json.load(f)
                for k in default:
                    if k not in data: data[k] = default[k]
                return data
        except: return default
    return default

def save_state(state_data):
    state_data["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    with open(STATE_FILE, "w") as f:
        json.dump(state_data, f, indent=2)

def calculate_atr(df, period=14):
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift()).abs()
    low_close = (df['Low'] - df['Close'].shift()).abs()
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    return ranges.max(axis=1).ewm(alpha=1/period, adjust=False).mean()

def fetch_twelve_data(symbol, interval, outputsize=200):
    url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={interval}&apikey={TWELVE_API_KEY}&outputsize={outputsize}"
    try:
        res = requests.get(url, timeout=15).json()
        if 'values' in res:
            df = pd.DataFrame(res['values'])
            df['datetime'] = pd.to_datetime(df['datetime'])
            df = df.sort_values('datetime').reset_index(drop=True)
            for col in ['open', 'high', 'low', 'close']:
                df[col.capitalize()] = df[col].astype(float)
            return df
    except Exception as e:
        print(f"API Error {symbol}: {e}")
    return pd.DataFrame()

# ==========================================
# 3. MESIN 1: CORE INSTITUTIONAL (REAKTIF M5)
# ==========================================
def core_institutional_engine(ticker, pair_name, current_state):
    pair_lock = f"CORE_{ticker}"
    dec = 2 if "XAU" in ticker else 5
    if current_state["radar_locks"].get(pair_lock) == "ACTIVE": return current_state

    df_h1 = fetch_twelve_data(ticker, "1h", 200)
    if df_h1.empty or len(df_h1) < 200: return current_state

    df_h1['MA50'] = df_h1['Close'].rolling(50).mean()
    df_h1['MA200'] = df_h1['Close'].rolling(200).mean()
    
    last_h1 = df_h1.iloc[-2]
    c_h1, ma50, ma200 = last_h1['Close'], last_h1['MA50'], last_h1['MA200']
    
    trend = "UPTREND" if (ma50 > ma200 and c_h1 > ma50) else "DOWNTREND" if (ma50 < ma200 and c_h1 < ma50) else "NONE"
    if trend == "NONE": return current_state

    lookback = 48
    major_res = df_h1['High'].iloc[-lookback:-2].max()
    major_sup = df_h1['Low'].iloc[-lookback:-2].min()

    buffer = 5.0 if "XAU" in ticker else 0.0020
    ob_bot = major_sup if trend == "UPTREND" else (major_res - buffer)
    ob_top = (major_sup + buffer) if trend == "UPTREND" else major_res

    curr_price = df_h1['Close'].iloc[-1]
    if not (ob_bot <= curr_price <= ob_top):
        current_state["radar_locks"].pop(pair_lock, None)
        return current_state 

    df_m5 = fetch_twelve_data(ticker, "5min", 100)
    if df_m5.empty: return current_state
    
    df_m5['ATR'] = calculate_atr(df_m5)
    prev, curr = df_m5.iloc[-2], df_m5.iloc[-1]

    bull_engulf = (prev['Close'] < prev['Open']) and (curr['Close'] > curr['Open']) and (curr['Close'] > prev['Open']) and (curr['Open'] <= prev['Close'])
    bear_engulf = (prev['Close'] > prev['Open']) and (curr['Close'] < curr['Open']) and (curr['Close'] < prev['Open']) and (curr['Open'] >= prev['Close'])

    if not (bull_engulf or bear_engulf):
        if current_state["radar_locks"].get(pair_lock) != "RADAR":
            current_state["radar_locks"][pair_lock] = "RADAR"
            arah = "Demand (Potensi BUY)" if trend == "UPTREND" else "Supply (Potensi SELL)"
            send_alert(f"⚠️ *[FASE 1: RADAR]*\n📊 {pair_name}\n🔍 Memasuki Zona {arah}. Siaga di MT5!")
        return current_state

    # EXECUTION
    is_buy = trend == "UPTREND" and bull_engulf
    is_sell = trend == "DOWNTREND" and bear_engulf
    
    if is_buy or is_sell:
        entry = curr['Close']
        sl = curr['Low'] - curr['ATR'] if is_buy else curr['High'] + curr['ATR']
        target = major_res if is_buy else major_sup
        
        risk = entry - sl if is_buy else sl - entry
        reward = target - entry if is_buy else entry - target
        rr = reward / risk if risk > 0 else 0
        
        if rr >= 1.5:
            if rr > 5.0:
                rr = 5.0
                target = entry + (risk * 5) if is_buy else entry - (risk * 5)
                
            entry, sl, target = round(entry, dec), round(sl, dec), round(target, dec)
            tipe = "BUY EXECUTION" if is_buy else "SELL EXECUTION"
            
            current_state["active_signals"].insert(0, {
                "strategy": "ALGO: CORE_INSTITUTIONAL", "pair": pair_name, "type": tipe,
                "entry": str(entry), "sl": str(sl), "tp": str(target), "rr": f"1 : {round(rr, 1)}", "status": "OPEN"
            })
            current_state["radar_locks"][pair_lock] = "ACTIVE"
            
            msg = f"🎯 *[{tipe}]*\n📊 {pair_name}\n📍 Entry: `{entry}`\n🛑 SL: `{sl}` (ATR)\n💰 TP: `{target}`\n🎓 R/R: 1 : {round(rr, 1)}\n⚠️ {random.choice(WARN_BUY if is_buy else WARN_SELL)}"
            send_alert(msg)

    return current_state

# ==========================================
# 4. MESIN 2: IMBALANCE SCALPER
# ==========================================
def run_scalp_engine(ticker, pair_name, current_state):
    pair_lock = f"SCALP_{ticker}"
    if current_state["radar_locks"].get(pair_lock) == "ACTIVE": return current_state

    dec = 2 if "XAU" in ticker else 5
    df_h1 = fetch_twelve_data(ticker, "1h", 100)
    if df_h1.empty or len(df_h1) < 55: return current_state
    
    df_h1['EMA_21'] = df_h1['Close'].ewm(span=21).mean()
    df_h1['EMA_50'] = df_h1['Close'].ewm(span=50).mean()
    df_h1['Bull_Imb'] = df_h1['Low'] > df_h1['High'].shift(2)
    df_h1['Bear_Imb'] = df_h1['High'] < df_h1['Low'].shift(2)
    df_h1['ATR'] = calculate_atr(df_h1)
    
    last = df_h1.iloc[-2]
    atr = df_h1['ATR'].iloc[-1]
    
    is_buy = last['EMA_21'] > last['EMA_50'] and last['Bull_Imb']
    is_sell = last['EMA_21'] < last['EMA_50'] and last['Bear_Imb']
    
    if is_buy or is_sell:
        entry = last['High'] if is_buy else last['Low']
        sl = last['Low'] - atr if is_buy else last['High'] + atr
        target = entry + (atr * 3) if is_buy else entry - (atr * 3)
        
        risk = entry - sl if is_buy else sl - entry
        reward = target - entry if is_buy else entry - target
        rr = min(reward / risk if risk > 0 else 0, 5.0)
        target = entry + (risk * rr) if is_buy else entry - (risk * rr)
        
        if rr >= 1.5:
            entry, sl, target = round(entry, dec), round(sl, dec), round(target, dec)
            tipe = "BUY LIMIT" if is_buy else "SELL LIMIT"
            
            current_state["active_signals"].insert(0, {
                "strategy": "ALGO: IMBALANCE_SCALP", "pair": pair_name, "type": tipe,
                "entry": str(entry), "sl": str(sl), "tp": str(target), "rr": f"1 : {round(rr, 1)}", "status": "OPEN"
            })
            current_state["radar_locks"][pair_lock] = "ACTIVE"
            
            msg = f"🎯 *[{tipe}]*\n📊 {pair_name}\n📍 Entry Limit: `{entry}`\n🛑 SL: `{sl}` (ATR)\n💰 TP: `{target}`\n⏳ *Batal jika TP tersentuh lebih dulu!*\n⚠️ {random.choice(WARN_BUY if is_buy else WARN_SELL)}"
            send_alert(msg)

    return current_state

# ==========================================
# 5. RUNNER & SLEEP PROTOCOL
# ==========================================
def is_rollover_sleep():
    now_utc = datetime.now(timezone.utc)
    return 21 <= now_utc.hour <= 23

def run_market_scan():
    if not TWELVE_API_KEY:
        print("API Key Twelve Data tidak ditemukan di Secrets.")
        return
        
    if is_rollover_sleep():
        print("Sleep Protocol aktif (Rollover WIB 04:00-07:00). Menghemat kuota dan menghindari spread brutal.")
        return

    current_state = load_state()
    current_state["active_signals"] = current_state["active_signals"][:10]

    for item in INSTRUMENTS:
        current_state = core_institutional_engine(item["ticker"], item["name"], current_state)
        current_state = run_scalp_engine(item["ticker"], item["name"], current_state)
        
    save_state(current_state)

if __name__ == "__main__":
    run_market_scan()
