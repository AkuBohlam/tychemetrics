import os
import json
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime
import random

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
STATE_FILE = "signals.json"

# ==========================================
# 0. DATABASE EDUKASI AWAM (RANDOMIZER)
# ==========================================
edukasi_buy = [
    "Harga turun ke area 'grosir' (Demand) dan candle Engulfing M5 muncul layaknya jejak kaki raksasa. Ini pertanda institusi sedang memborong di harga murah sebelum harga dipompa naik.",
    "Kita berenang searah arus tren! Area diskon H1 telah disentuh, dan konfirmasi Engulfing M5 adalah bukti visual bahwa uang besar (Smart Money) baru saja menyapu penjual ritel yang FOMO.",
    "Prinsip dagang yang sehat: beli saat murah. Zona Order Block ini memancing seller awam untuk lanjut jual, namun candle Engulfing M5 mengonfirmasi bahwa bandar mengambil alih kontrol untuk memantulkan harga.",
    "Tidak perlu menebak dasar jurang. Kita membiarkan harga masuk ke zona Pantauan H1, lalu menunggu konfirmasi pola momentum Engulfing M5 sebagai tanda bahwa institusi sudah selesai mengumpulkan barang."
]

edukasi_sell = [
    "Harga naik ke area 'mahal' (Supply) dan memancing pembeli ritel (FOMO). Candle Engulfing merah di M5 adalah konfirmasi bahwa institusi mulai melakukan aksi buang barang secara besar-besaran.",
    "Tren besar sedang turun. Harga menyentuh batas atap (Resistance) H1 dan membentuk pola penolakan tajam (Engulfing M5). Ini menunjukkan pemain besar sudah siap membanting harga kembali ke bawah.",
    "Banyak trader pemula terjebak membeli di area pucuk ini. Engulfing M5 yang terbentuk adalah sinyal bahwa 'Smart Money' menjebak ritel sebelum tren berlanjut turun.",
    "Sabar adalah kunci. Harga telah menguji area Supply H1, dan konfirmasi pola Engulfing di M5 membuktikan bahwa momentum perlawanan dari institusi telah mendominasi."
]

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

def calculate_atr_institutional(df, period=14):
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift()).abs()
    low_close = (df['Low'] - df['Close'].shift()).abs()
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    atr = true_range.ewm(alpha=1/period, adjust=False).mean()
    return atr

# ==========================================
# 2. CORE ENGINE: 3 PILAR + FASE PERINGATAN
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
        
        # JIKA HARGA KELUAR DARI ZONA (BATAL)
        if not (ob_bot <= current_price <= ob_top):
            if current_state["radar_locks"].get(pair_lock) == "RADAR":
                current_state["radar_locks"].pop(pair_lock, None) # Reset Radar
            return current_state 

        # --- PILAR 3: ENGULFING & ATR (M5) ---
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

        # --- FASE 1: RADAR (HARGA MASUK ZONA TAPI BELUM ENGULFING) ---
        if not (is_bullish_engulfing or is_bearish_engulfing):
            if current_state["radar_locks"].get(pair_lock) != "RADAR":
                current_state["radar_locks"][pair_lock] = "RADAR"
                arah_zona = "Demand (Bersiap Potensi BUY)" if trend == "UPTREND" else "Supply (Bersiap Potensi SELL)"
                msg = f"⚠️ *[FASE 1: RADAR INSTITUSIONAL AKTIF]*\n\n📊 *Instrumen:* {pair_name}\n🔍 *Status:* Memasuki Zona {arah_zona}\n\n⏳ *Tindakan Anda:* JANGAN ENTRY DULU. Harga memasuki zona krusial tempat bandar sering menjebak trader ritel. Bot sedang mengawasi manipulasi di Timeframe M5. Buka MetaTrader Anda dan tunggu instruksi konfirmasi eksekusi dari bot!"
                send_alert(msg)
            return current_state

        # --- FASE 2: EKSEKUSI (ENGULFING TERBENTUK DI DALAM ZONA) ---
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
                    
                    current_state["active_signals"].append({
                        "strategy": "Core: OB+Engulfing", "pair": pair_name, "type": "POTENSI BUY",
                        "entry": entry_p, "sl": sl_p, "tp": tp_p, "rr": f"1 : {round(rr_ratio, 1)}", "status": "OPEN"
                    })
                    current_state["radar_locks"][pair_lock] = "ACTIVE"
                    
                    msg = f"🎯 *[FASE 2: KONFIRMASI EKSEKUSI]*\n\n📊 *Instrumen:* {pair_name}\n⚡ *Aksi:* POTENSI BUY\n📍 *Entry:* `{entry_p}` *(+Spread)*\n🛑 *SL:* `{sl_p}` *(ATR Protected)*\n💰 *TP:* `{tp_p}` *(Structural Target)*\n\n🧠 *Edukasi Market:* {edu_text}\n\n🎓 *Risk/Reward:* 1 : {round(rr_ratio, 1)}. Target diletakkan logis di Resistance terdekat. Tetap gunakan manajemen risiko 1%!"
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

                    current_state["active_signals"].append({
                        "strategy": "Core: OB+Engulfing", "pair": pair_name, "type": "POTENSI SELL",
                        "entry": entry_p, "sl": sl_p, "tp": tp_p, "rr": f"1 : {round(rr_ratio, 1)}", "status": "OPEN"
                    })
                    current_state["radar_locks"][pair_lock] = "ACTIVE"
                    
                    msg = f"🎯 *[FASE 2: KONFIRMASI EKSEKUSI]*\n\n📊 *Instrumen:* {pair_name}\n⚡ *Aksi:* POTENSI SELL\n📍 *Entry:* `{entry_p}`\n🛑 *SL:* `{sl_p}` *(ATR+Spread Protected)*\n💰 *TP:* `{tp_p}` *(Structural Target)*\n\n🧠 *Edukasi Market:* {edu_text}\n\n🎓 *Risk/Reward:* 1 : {round(rr_ratio, 1)}. Target diletakkan logis di Support terdekat. Tetap gunakan manajemen risiko 1%!"
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
