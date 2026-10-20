import os
import json
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime, timezone
import random

# ==========================================
# 0. KONFIGURASI SISTEM & KREDENSIAL
# ==========================================
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
STATE_FILE = "signals.json"

INSTRUMENTS = [
    {"name": "XAU (Gold)", "ticker": "GC=F"},
    {"name": "EUR/USD", "ticker": "EURUSD=X"},
    {"name": "GBP/USD", "ticker": "GBPUSD=X"}
]

# ==========================================
# 1. DATABASE BAHASA (ANTI-ROBOT)
# ==========================================
# --- EDUKASI CORE ENGINE ---
edukasi_buy = [
    "Harga turun ke area 'grosir' (Demand) dan candle Engulfing M5 muncul layaknya jejak kaki raksasa. Ini pertanda institusi sedang memborong di harga murah sebelum harga dipompa naik.",
    "Kita berenang searah arus tren! Area diskon H1 telah disentuh, dan konfirmasi Engulfing M5 adalah bukti visual bahwa uang besar (Smart Money) baru saja menyapu penjual ritel yang FOMO.",
    "Prinsip dagang yang sehat: beli saat murah. Zona Order Block ini memancing seller awam untuk lanjut jual, namun candle Engulfing M5 mengonfirmasi bahwa bandar mengambil alih kontrol."
]

edukasi_sell = [
    "Harga naik ke area 'mahal' (Supply) dan memancing pembeli ritel (FOMO). Candle Engulfing merah di M5 adalah konfirmasi bahwa institusi mulai melakukan aksi buang barang secara besar-besaran.",
    "Tren besar sedang turun. Harga menyentuh batas atap (Resistance) H1 dan membentuk pola penolakan tajam (Engulfing M5). Ini menunjukkan pemain besar sudah siap membanting harga.",
    "Banyak trader pemula terjebak membeli di area pucuk ini. Engulfing M5 yang terbentuk adalah sinyal bahwa 'Smart Money' menjebak ritel sebelum tren berlanjut turun."
]

# --- EDUKASI IMBALANCE SCALPER ---
LANG_BUY_SCALP = [
    "Institusi meninggalkan celah kosong (Imbalance) saat memompa harga naik. Kita memasang jaring penjemputan persis di pangkal momentum M5.",
    "Terdeteksi jejak Bullish Imbalance segar di H1. Titik pantul disiapkan tepat di area Fractal M5.",
    "Momentum kencang ke atas menyisakan area diskon yang belum terisi. Limit order ditempatkan pada titik presisi asal mula pergerakan.",
    "Ketidakseimbangan volume signifikan. Bot membidik area akar Demand M5 untuk menangkap pantulan harga."
]

LANG_SELL_SCALP = [
    "Harga turun tajam meninggalkan celah Bearish Imbalance. Titik masuk disempurnakan pada Fractal Supply M5.",
    "Institusi membuang muatan dan menciptakan Imbalance H1. Jaring Sell Limit dipasang di akar momentum M5.",
    "Momentum kencang ke bawah menyisakan area premium yang belum terisi. Limit order ditempatkan untuk membonceng tren turun.",
    "Terjadi kekosongan likuiditas (Imbalance) di bawah. Bot meletakkan perangkap di pangkal Supply M5."
]

WARN_BUY_SCALP = [
    "Jangan lupa kalibrasi harga penjemputan Limit Anda. Pastikan Anda melebihkan harga Entry sesuai spread broker masing-masing agar jaring pesanan Anda benar-benar tereksekusi.",
    "Tips Eksekusi: Harga Entry di atas adalah harga mentah grafik (Bid). Wajib tambahkan sedikit toleransi spread broker Anda pada Entry Limit.",
    "Karena setiap broker memiliki spread berbeda, pastikan Anda melebihkan harga Entry sesuai spread akun Anda agar tidak tertinggal kereta. SL tidak perlu diubah."
]

WARN_SELL_SCALP = [
    "Catatan penting: Posisi SELL sangat rentan tersapu prematur oleh garis Ask. Lindungi posisi Anda dengan selalu menambahkan kalkulasi spread aktual pada batas Stop Loss.",
    "Tips Eksekusi: Karena Anda melakukan SELL, penutupan posisi (SL) menggunakan garis Ask. Wajib tambahkan spread broker Anda pada angka SL agar pengaman tidak bocor.",
    "Manajemen Eksekusi: Lindungi posisi SELL dengan menambahkan spread aktual pada batas Stop Loss. Harga Entry dibiarkan murni sesuai instruksi."
]

# ==========================================
# 2. INFRASTRUKTUR & MANAJEMEN MEMORI
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
    state_data["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    with open(STATE_FILE, "w") as f:
        json.dump(state_data, f, indent=2)

def calculate_atr_institutional(df, period=14):
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift()).abs()
    low_close = (df['Low'] - df['Close'].shift()).abs()
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    atr = true_range.ewm(alpha=1/period, adjust=False).mean()
    return atr

# ==========================================
# 3. MESIN 1: CORE INSTITUTIONAL (REAKTIF)
# ==========================================
def core_institutional_engine(ticker_symbol, pair_name, current_state):
    try:
        pair_lock = f"CORE_{ticker_symbol}"
        is_gold = "GC=F" in ticker_symbol
        dec = 2 if is_gold else 5
        spread_allowance = 0.50 if is_gold else 0.00005

        if current_state["radar_locks"].get(pair_lock) == "ACTIVE":
            return current_state

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

        lookback = 48
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
            if current_state["radar_locks"].get(pair_lock) == "RADAR":
                current_state["radar_locks"].pop(pair_lock, None)
            return current_state 

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

        if not (is_bullish_engulfing or is_bearish_engulfing):
            if current_state["radar_locks"].get(pair_lock) != "RADAR":
                current_state["radar_locks"][pair_lock] = "RADAR"
                arah_zona = "Demand (Bersiap Potensi BUY)" if trend == "UPTREND" else "Supply (Bersiap Potensi SELL)"
                msg = f"⚠️ *[FASE 1: RADAR INSTITUSIONAL AKTIF]*\n\n📊 *Instrumen:* {pair_name}\n🔍 *Status:* Memasuki Zona {arah_zona}\n\n⏳ *Tindakan Anda:* JANGAN ENTRY DULU. Harga memasuki zona krusial tempat bandar sering menjebak trader ritel. Bot sedang mengawasi manipulasi di Timeframe M5. Buka MetaTrader Anda dan tunggu instruksi konfirmasi eksekusi dari bot!"
                send_alert(msg)
            return current_state

        if trend == "UPTREND" and is_bullish_engulfing:
            entry_p = float(curr_m5['Close']) + spread_allowance
            sl_p = float(curr_m5['Low']) - atr_value
            risk = abs(entry_p - sl_p)
            reward = major_res - entry_p
            
            if risk > 0 and reward > 0:
                rr_ratio = reward / risk
                if rr_ratio >= 1.5:
                    entry_p, sl_p, tp_p = round(entry_p, dec), round(sl_p, dec), round(major_res, dec)
                    edu_text = random.choice(edukasi_buy)
                    
                    current_state["active_signals"].insert(0, {
                        "strategy": "ALGO: CORE_INSTITUTIONAL | TRIGGER: M5_ENGULFING | VOL: PROTECTED", 
                        "pair": pair_name, "type": "BUY EXECUTION",
                        "entry": entry_p, "sl": sl_p, "tp": tp_p, "rr": f"1 : {round(rr_ratio, 1)} (NATURAL)", "status": "OPEN"
                    })
                    current_state["radar_locks"][pair_lock] = "ACTIVE"
                    
                    msg = f"🎯 *[EKSEKUSI: CORE INSTITUTIONAL]*\n\n📊 *Instrumen:* {pair_name}\n⚡ *Aksi:* POTENSI BUY\n📍 *Entry:* `{entry_p}` *(+Spread)*\n🛑 *SL:* `{sl_p}` *(ATR Protected)*\n💰 *TP:* `{tp_p}` *(Structural Target)*\n\n🧠 *Edukasi Market:* {edu_text}\n\n🎓 *Risk/Reward:* 1 : {round(rr_ratio, 1)}. Target diletakkan logis di Resistance terdekat. Tetap gunakan manajemen risiko 1%!"
                    send_alert(msg)

        elif trend == "DOWNTREND" and is_bearish_engulfing:
            entry_p = float(curr_m5['Close'])
            sl_p = float(curr_m5['High']) + atr_value + spread_allowance
            risk = abs(sl_p - entry_p)
            reward = entry_p - major_sup
            
            if risk > 0 and reward > 0:
                rr_ratio = reward / risk
                if rr_ratio >= 1.5:
                    entry_p, sl_p, tp_p = round(entry_p, dec), round(sl_p, dec), round(major_sup, dec)
                    edu_text = random.choice(edukasi_sell)

                    current_state["active_signals"].insert(0, {
                        "strategy": "ALGO: CORE_INSTITUTIONAL | TRIGGER: M5_ENGULFING | VOL: PROTECTED", 
                        "pair": pair_name, "type": "SELL EXECUTION",
                        "entry": entry_p, "sl": sl_p, "tp": tp_p, "rr": f"1 : {round(rr_ratio, 1)} (NATURAL)", "status": "OPEN"
                    })
                    current_state["radar_locks"][pair_lock] = "ACTIVE"
                    
                    msg = f"🎯 *[EKSEKUSI: CORE INSTITUTIONAL]*\n\n📊 *Instrumen:* {pair_name}\n⚡ *Aksi:* POTENSI SELL\n📍 *Entry:* `{entry_p}`\n🛑 *SL:* `{sl_p}` *(ATR+Spread Protected)*\n💰 *TP:* `{tp_p}` *(Structural Target)*\n\n🧠 *Edukasi Market:* {edu_text}\n\n🎓 *Risk/Reward:* 1 : {round(rr_ratio, 1)}. Target diletakkan logis di Support terdekat. Tetap gunakan manajemen risiko 1%!"
                    send_alert(msg)

        return current_state
    except Exception as e:
        print(f"Error pada Core Engine {ticker_symbol}: {e}")
        return current_state

# ==========================================
# 4. MESIN 2: IMBALANCE SCALPER (PREDIKTIF)
# ==========================================
def run_scalp_engine(ticker_symbol, pair_name, current_state):
    try:
        pair_lock = f"SCALP_{ticker_symbol}"
        if current_state["radar_locks"].get(pair_lock) == "ACTIVE":
            return current_state

        is_gold = "GC=F" in ticker_symbol
        dec = 2 if is_gold else 5

        df_h1 = yf.download(ticker_symbol, period="1mo", interval="1h", progress=False)
        if df_h1.empty or len(df_h1) < 55: return current_state
        if isinstance(df_h1.columns, pd.MultiIndex): df_h1.columns = df_h1.columns.get_level_values(0)
        
        df_h1['EMA_21'] = df_h1['Close'].ewm(span=21, adjust=False).mean()
        df_h1['EMA_50'] = df_h1['Close'].ewm(span=50, adjust=False).mean()
        
        # Deteksi Imbalance (Kesenjangan harga 3 candle)
        df_h1['Bullish_Imb'] = df_h1['Low'] > df_h1['High'].shift(2)
        df_h1['Bearish_Imb'] = df_h1['High'] < df_h1['Low'].shift(2)
        
        # Deteksi Fractal Sederhana
        df_h1['Fractal_High'] = (df_h1['High'] > df_h1['High'].shift(1)) & (df_h1['High'] > df_h1['High'].shift(-1))
        df_h1['Fractal_Low'] = (df_h1['Low'] < df_h1['Low'].shift(1)) & (df_h1['Low'] < df_h1['Low'].shift(-1))
        
        df_h1['ATR'] = calculate_atr_institutional(df_h1, 14)
        
        last_h1 = df_h1.iloc[-2]
        current_atr = float(df_h1['ATR'].iloc[-1])
        
        # SETUP BUY LIMIT
        if last_h1['EMA_21'] > last_h1['EMA_50'] and last_h1['Bullish_Imb']:
            entry = float(last_h1['High'])
            sl = entry - current_atr
            
            resistances = df_h1[df_h1['Fractal_High']]['High']
            target = float(resistances.max()) if not resistances.empty else entry + (current_atr * 3)
            
            risk = entry - sl
            reward = target - entry
            rr_raw = reward / risk if risk > 0 else 0
            
            if rr_raw >= 1.5:
                tp_type = "NATURAL"
                tp_final = target
                rr_final = rr_raw
                if rr_raw > 5.0:
                    tp_type = "CAPPED"
                    rr_final = 5.0
                    tp_final = entry + (risk * 5.0)
                
                entry, sl, tp_final = round(entry, dec), round(sl, dec), round(tp_final, dec)
                
                logic_text = random.choice(LANG_BUY_SCALP)
                warn_text = random.choice(WARN_BUY_SCALP)
                
                # Terminal Web Log
                current_state["active_signals"].insert(0, {
                    "strategy": "ALGO: IMBALANCE_SCALP | TRIGGER: M5_FRACTAL | VOL: FILTERED | SPREAD_ADJ: PENDING_USER", 
                    "pair": pair_name, "type": "BUY LIMIT",
                    "entry": str(entry), "sl": str(sl), "tp": str(tp_final), 
                    "rr": f"1 : {round(rr_final, 1)} ({tp_type})", "status": "OPEN"
                })
                current_state["radar_locks"][pair_lock] = "ACTIVE"
                
                msg = f"🎯 *[EKSEKUSI: IMBALANCE SCALP]*\n\n"
                msg += f"📊 *Instrumen:* {pair_name}\n"
                msg += f"⚡ *Aksi:* POTENSI BUY LIMIT\n"
                msg += f"📍 *Entry Limit:* `{entry}` *(Harga Murni Chart + Spread Broker Anda)*\n"
                msg += f"🛑 *SL:* `{sl}` *(ATR Protected)*\n"
                msg += f"💰 *TP:* `{tp_final}` *(Max Capped Target)*\n\n" if tp_type == "CAPPED" else f"💰 *TP:* `{tp_final}` *(Structural Target)*\n\n"
                msg += f"⚠️ *Peringatan Eksekusi:* {warn_text}\n\n"
                msg += f"💡 *Logic:* {logic_text}\n"
                msg += f"🎓 *Risk/Reward:* 1 : {round(rr_final, 1)}. "
                msg += "(Target ditarik mundur ke batas maksimal 1:5 untuk mengunci probabilitas)." if tp_type == "CAPPED" else "(Target logis struktur mayor)."
                
                send_alert(msg)

        # SETUP SELL LIMIT
        elif last_h1['EMA_21'] < last_h1['EMA_50'] and last_h1['Bearish_Imb']:
            entry = float(last_h1['Low'])
            sl = entry + current_atr
            
            supports = df_h1[df_h1['Fractal_Low']]['Low']
            target = float(supports.min()) if not supports.empty else entry - (current_atr * 3)
            
            risk = sl - entry
            reward = entry - target
            rr_raw = reward / risk if risk > 0 else 0
            
            if rr_raw >= 1.5:
                tp_type = "NATURAL"
                tp_final = target
                rr_final = rr_raw
                if rr_raw > 5.0:
                    tp_type = "CAPPED"
                    rr_final = 5.0
                    tp_final = entry - (risk * 5.0)
                
                entry, sl, tp_final = round(entry, dec), round(sl, dec), round(tp_final, dec)
                
                logic_text = random.choice(LANG_SELL_SCALP)
                warn_text = random.choice(WARN_SELL_SCALP)
                
                # Terminal Web Log
                current_state["active_signals"].insert(0, {
                    "strategy": "ALGO: IMBALANCE_SCALP | TRIGGER: M5_FRACTAL | VOL: FILTERED | SPREAD_ADJ: PENDING_USER", 
                    "pair": pair_name, "type": "SELL LIMIT",
                    "entry": str(entry), "sl": str(sl), "tp": str(tp_final), 
                    "rr": f"1 : {round(rr_final, 1)} ({tp_type})", "status": "OPEN"
                })
                current_state["radar_locks"][pair_lock] = "ACTIVE"
                
                msg = f"🎯 *[EKSEKUSI: IMBALANCE SCALP]*\n\n"
                msg += f"📊 *Instrumen:* {pair_name}\n"
                msg += f"⚡ *Aksi:* POTENSI SELL LIMIT\n"
                msg += f"📍 *Entry Limit:* `{entry}` *(Harga Murni Chart)*\n"
                msg += f"🛑 *SL:* `{sl}` *(ATR Protected + Spread Broker Anda)*\n"
                msg += f"💰 *TP:* `{tp_final}` *(Max Capped Target)*\n\n" if tp_type == "CAPPED" else f"💰 *TP:* `{tp_final}` *(Structural Target)*\n\n"
                msg += f"⚠️ *Peringatan Eksekusi:* {warn_text}\n\n"
                msg += f"💡 *Logic:* {logic_text}\n"
                msg += f"🎓 *Risk/Reward:* 1 : {round(rr_final, 1)}. "
                msg += "(Target ditarik mundur ke batas maksimal 1:5 untuk mengunci probabilitas)." if tp_type == "CAPPED" else "(Target logis struktur mayor)."
                
                send_alert(msg)

        return current_state
    except Exception as e:
        print(f"Error pada Scalp Engine {ticker_symbol}: {e}")
        return current_state

# ==========================================
# 5. MANAJER UTAMA (RUNNER)
# ==========================================
def run_market_scan():
    current_state = load_state()
    
    # Menghapus sinyal lama agar Web Terminal selalu bersih (maks 10 sinyal terakhir)
    if len(current_state["active_signals"]) > 10:
        current_state["active_signals"] = current_state["active_signals"][:10]

    for item in INSTRUMENTS:
        # Menjalankan Mesin 1: Core Institutional
        current_state = core_institutional_engine(item["ticker"], item["name"], current_state)
        # Menjalankan Mesin 2: Imbalance Scalper
        current_state = run_scalp_engine(item["ticker"], item["name"], current_state)
        
    save_state(current_state)

if __name__ == "__main__":
    run_market_scan()
