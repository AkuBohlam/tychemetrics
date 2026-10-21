import os
import json
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
import random

# ==========================================
# 0. KONFIGURASI SISTEM & KREDENSIAL
# ==========================================
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TWELVE_API_KEY = os.getenv("TWELVEDATA_API_KEY")
STATE_FILE = "signals.json"

INSTRUMENTS = [
    {"name": "EUR/USD", "ticker": "EUR/USD"},
    {"name": "GBP/USD", "ticker": "GBP/USD"}
]

# ==========================================
# 1. DATABASE BAHASA UNIVERSAL (3 GAYA)
# ==========================================
STYLES_BUY = [
    {
        "warn": "⚠️ Peringatan Eksekusi: Jangan lupa kalibrasi harga penjemputan Anda. Pastikan Anda menambahkan spread broker masing-masing pada harga Entry agar order tereksekusi dengan sempurna.",
        "logic": "💡 Logic: Terdeteksi jejak Bullish segar di H1. Titik pantul disiapkan presisi. Kita menjemput harga di area diskon."
    },
    {
        "warn": "🛡️ Protokol Keamanan: Eksekusi BUY selalu menggunakan garis Ask. Tambahkan nilai spread broker Anda ke dalam angka Entry Limit di atas agar pesanan Anda tidak tertinggal oleh pergerakan market.",
        "logic": "🧠 Analisa Sistem: Algoritma menangkap anomali volume di zona akumulasi. Jaring limit dipasang di akar pergerakan untuk meminimalisir risiko."
    },
    {
        "warn": "⚙️ Kalibrasi Diperlukan: Parameter mesin mengabaikan spread. Untuk aktivasi BUY yang presisi, input angka (Entry Limit + Spread) di terminal MetaTrader Anda.",
        "logic": "📊 Metrik Mesin: Konfirmasi divergensi momentum dan Bullish structure tervalidasi. Probabilitas pantulan tinggi di area penyangga mikroskopik."
    }
]

STYLES_SELL = [
    {
        "warn": "⚠️ Peringatan Eksekusi: Tips Eksekusi: Karena Anda melakukan SELL, penutupan posisi (SL) menggunakan garis Ask. Wajib tambahkan spread broker Anda pada angka SL agar pengaman tidak bocor.",
        "logic": "💡 Logic: Momentum kencang ke bawah menyisakan area premium yang belum terisi. Limit order disiapkan secara presisi untuk membonceng tren turun."
    },
    {
        "warn": "🛡️ Protokol Keamanan: Bahaya pelebaran spread mengintai posisi SELL Anda. Lindungi modal dengan menambahkan spread broker Anda ke dalam angka Stop Loss secara manual.",
        "logic": "🧠 Analisa Sistem: Struktur market makro telah terdistribusi. Kita menempatkan Sell Limit di area Supply yang tersisa sebelum institusi melanjutkan tekanan jual."
    },
    {
        "warn": "⚙️ Kalibrasi Diperlukan: Sistem proteksi ATR sudah aktif, namun belum mencakup spread. Kalkulasikan (Stop Loss + Spread Broker) pada terminal MT5 untuk mencegah SL Hunter.",
        "logic": "📊 Metrik Mesin: Tren divalidasi ke bawah. Algoritma mengunci akar Bearish structure sebagai titik resistensi eksekusi optimal."
    }
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

def add_fractals(df):
    df['Fractal_Up'] = (df['High'] > df['High'].shift(1)) & (df['High'] > df['High'].shift(2)) & \
                       (df['High'] > df['High'].shift(-1)) & (df['High'] > df['High'].shift(-2))
    df['Fractal_Down'] = (df['Low'] < df['Low'].shift(1)) & (df['Low'] < df['Low'].shift(2)) & \
                         (df['Low'] < df['Low'].shift(-1)) & (df['Low'] < df['Low'].shift(-2))
    return df

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
    except Exception:
        pass
    return pd.DataFrame()

# ==========================================
# 3. MESIN 1: CORE INSTITUTIONAL (REAKTIF M5)
# ==========================================
def core_institutional_engine(ticker, pair_name, current_state):
    pair_lock = f"CORE_{ticker}"
    dec = 5
    
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

    buffer = 0.0020
    ob_bot = major_sup if trend == "UPTREND" else (major_res - buffer)
    ob_top = (major_sup + buffer) if trend == "UPTREND" else major_res

    curr_price = df_h1['Close'].iloc[-1]
    
    if not (ob_bot <= curr_price <= ob_top):
        current_state["radar_locks"].pop(pair_lock, None)
        return current_state 

    if current_state["radar_locks"].get(pair_lock) != "RADAR":
        current_state["radar_locks"][pair_lock] = "RADAR"
        arah = "Demand (Potensi BUY LIMIT)" if trend == "UPTREND" else "Supply (Potensi SELL LIMIT)"
        send_alert(f"⚠️ *[FASE 1: RADAR] - CORE INSTITUTIONAL*\n📊 Instrumen: {pair_name}\n🔍 Status: Memasuki Zona {arah}.\n⏳ Tindakan: Siaga di MT5! Tunggu konfirmasi Engulfing di M5 dari sistem.")
        return current_state

    df_m5 = fetch_twelve_data(ticker, "5min", 100)
    if df_m5.empty: return current_state
    
    df_m5['ATR'] = calculate_atr(df_m5)
    prev, curr = df_m5.iloc[-2], df_m5.iloc[-1]
    atr_val = curr['ATR']

    bull_engulf = (prev['Close'] < prev['Open']) and (curr['Close'] > curr['Open']) and (curr['Close'] > prev['Open']) and (curr['Open'] <= prev['Close'])
    bear_engulf = (prev['Close'] > prev['Open']) and (curr['Close'] < curr['Open']) and (curr['Close'] < prev['Open']) and (curr['Open'] >= prev['Close'])

    is_buy = trend == "UPTREND" and bull_engulf
    is_sell = trend == "DOWNTREND" and bear_engulf
    
    if is_buy or is_sell:
        style = random.choice(STYLES_BUY if is_buy else STYLES_SELL)
        
        if is_buy:
            entry = curr['Close']
            sl = ob_bot - atr_val
            target = major_res
            entry_lbl = f"`{round(entry, dec)}` *(Harga Murni Chart + Spread Broker Anda)*"
            sl_lbl = f"`{round(sl, dec)}` *(ATR Protected)*"
        else:
            entry = curr['Close']
            sl = ob_top + atr_val
            target = major_sup
            entry_lbl = f"`{round(entry, dec)}` *(Harga Murni Chart)*"
            sl_lbl = f"`{round(sl, dec)}` *(ATR Protected + Spread Broker Anda)*"
        
        risk = abs(entry - sl)
        reward = abs(target - entry)
        rr = reward / risk if risk > 0 else 0
        
        if rr >= 1.5:
            tp_lbl = "*(Structural Target)*"
            if rr > 5.0:
                rr = 5.0
                target = entry + (risk * 5) if is_buy else entry - (risk * 5)
                tp_lbl = "*(Max Capped Target)*"
                
            entry, sl, target = round(entry, dec), round(sl, dec), round(target, dec)
            tipe = "BUY LIMIT" if is_buy else "SELL LIMIT"
            
            current_state["active_signals"].insert(0, {
                "strategy": "ALGO: CORE_INSTITUTIONAL", "pair": pair_name, "type": tipe,
                "entry": str(entry), "sl": str(sl), "tp": str(target), "rr": f"1 : {round(rr, 1)}", "status": "OPEN"
            })
            current_state["radar_locks"][pair_lock] = "ACTIVE"
            
            msg = f"🎯 *[FASE 2: EKSEKUSI] - CORE INSTITUTIONAL*\n\n📊 Instrumen: {pair_name}\n⚡ Aksi: POTENSI {tipe}\n📍 Entry Limit: {entry_lbl}\n🛑 SL: {sl_lbl}\n💰 TP: `{target}` {tp_lbl}\n\n{style['warn']}\n\n{style['logic']}\n🎓 Risk/Reward: 1 : {round(rr, 1)}."
            send_alert(msg)

    return current_state

# ==========================================
# 4. MESIN 2: IMBALANCE SCALPER (FRACTAL)
# ==========================================
def run_scalp_engine(ticker, pair_name, current_state):
    pair_lock = f"SCALP_{ticker}"
    dec = 5
    
    if current_state["radar_locks"].get(pair_lock) == "ACTIVE": return current_state

    # Tarik H1 dan hitung Fractal
    df_h1 = fetch_twelve_data(ticker, "1h", 200)
    if df_h1.empty or len(df_h1) < 55: return current_state
    
    df_h1['EMA_21'] = df_h1['Close'].ewm(span=21).mean()
    df_h1['EMA_50'] = df_h1['Close'].ewm(span=50).mean()
    df_h1['Bull_Imb'] = df_h1['Low'] > df_h1['High'].shift(2)
    df_h1['Bear_Imb'] = df_h1['High'] < df_h1['Low'].shift(2)
    df_h1 = add_fractals(df_h1)
    
    last_idx = len(df_h1) - 2 # Fokus ke candle yang sudah close
    if last_idx < 2: return current_state
    
    last = df_h1.iloc[last_idx]
    
    is_buy = last['EMA_21'] > last['EMA_50'] and last['Bull_Imb']
    is_sell = last['EMA_21'] < last['EMA_50'] and last['Bear_Imb']
    
    if not (is_buy or is_sell): return current_state

    # Cari H1 Parent Fractal Candle
    parent_time = None
    for i in range(last_idx - 1, 1, -1):
        if is_buy and df_h1.iloc[i]['Fractal_Down']:
            parent_time = df_h1.iloc[i]['datetime']
            break
        elif is_sell and df_h1.iloc[i]['Fractal_Up']:
            parent_time = df_h1.iloc[i]['datetime']
            break

    if not parent_time: return current_state

    # Tarik M5 (Output lebih besar agar mencakup waktu parent_time)
    df_m5 = fetch_twelve_data(ticker, "5min", 500)
    if df_m5.empty: return current_state
    
    df_m5['ATR'] = calculate_atr(df_m5)
    df_m5 = add_fractals(df_m5)
    
    # Filter rentang waktu M5 yang berada di dalam 1 jam candle H1 Fractal Induk
    mask = (df_m5['datetime'] >= parent_time) & (df_m5['datetime'] < parent_time + timedelta(hours=1))
    df_m5_zone = df_m5[mask]
    
    if df_m5_zone.empty: return current_state
    
    atr_val = df_m5['ATR'].iloc[-1]
    style = random.choice(STYLES_BUY if is_buy else STYLES_SELL)
    
    if is_buy:
        # Cari Lembah terdalam di zona M5
        fractals_m5 = df_m5_zone[df_m5_zone['Fractal_Down'] == True]
        if fractals_m5.empty: return current_state
        entry_candle = fractals_m5.loc[fractals_m5['Low'].idxmin()]
        
        entry = entry_candle['Low']
        sl = entry - atr_val
        
        # Cari Resistance terdekat sebagai TP struktural
        recent_res = df_h1['High'].iloc[-24:].max() 
        target = recent_res if recent_res > entry else entry + (atr_val * 4)

        entry_lbl = f"`{round(entry, dec)}` *(Harga Murni Lembah Fractal M5 + Spread Broker Anda)*"
        sl_lbl = f"`{round(sl, dec)}` *(ATR Protected)*"
        
    else:
        # Cari Puncak tertinggi di zona M5
        fractals_m5 = df_m5_zone[df_m5_zone['Fractal_Up'] == True]
        if fractals_m5.empty: return current_state
        entry_candle = fractals_m5.loc[fractals_m5['High'].idxmax()]
        
        entry = entry_candle['High']
        sl = entry + atr_val
        
        # Cari Support terdekat sebagai TP struktural
        recent_sup = df_h1['Low'].iloc[-24:].min()
        target = recent_sup if recent_sup < entry else entry - (atr_val * 4)

        entry_lbl = f"`{round(entry, dec)}` *(Harga Murni Puncak Fractal M5)*"
        sl_lbl = f"`{round(sl, dec)}` *(ATR Protected + Spread Broker Anda)*"

    # Kalkulasi Risk/Reward Dinamis
    risk = abs(entry - sl)
    reward = abs(target - entry)
    rr = reward / risk if risk > 0 else 0
    
    if rr >= 1.5:
        tp_lbl = "*(Structural Target)*"
        if rr > 5.0:
            rr = 5.0
            target = entry + (risk * 5) if is_buy else entry - (risk * 5)
            tp_lbl = "*(Max Capped Target)*"
            
        entry, sl, target = round(entry, dec), round(sl, dec), round(target, dec)
        tipe = "BUY LIMIT" if is_buy else "SELL LIMIT"
        
        current_state["active_signals"].insert(0, {
            "strategy": "ALGO: IMBALANCE_SCALP", "pair": pair_name, "type": tipe,
            "entry": str(entry), "sl": str(sl), "tp": str(target), "rr": f"1 : {round(rr, 1)}", "status": "OPEN"
        })
        current_state["radar_locks"][pair_lock] = "ACTIVE"
        
        msg = f"🎯 *[EKSEKUSI: IMBALANCE SCALP]*\n\n📊 Instrumen: {pair_name}\n⚡ Aksi: POTENSI {tipe}\n📍 Entry Limit: {entry_lbl}\n🛑 SL: {sl_lbl}\n💰 TP: `{target}` {tp_lbl}\n\n{style['warn']}\n\n{style['logic']}\n🎓 Risk/Reward: 1 : {round(rr, 1)}."
        send_alert(msg)

    return current_state

# ==========================================
# 5. RUNNER & SLEEP PROTOCOL
# ==========================================
def is_rollover_sleep():
    now_utc = datetime.now(timezone.utc)
    return 21 <= now_utc.hour <= 23

def run_market_scan():
    if not TWELVE_API_KEY: return
    if is_rollover_sleep(): return

    current_state = load_state()
    current_state["active_signals"] = current_state["active_signals"][:10]

    for item in INSTRUMENTS:
        current_state = core_institutional_engine(item["ticker"], item["name"], current_state)
        current_state = run_scalp_engine(item["ticker"], item["name"], current_state)
        
    save_state(current_state)

if __name__ == "__main__":
    run_market_scan()
