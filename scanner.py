import os
import json
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
STATE_FILE = "signals.json"

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
    return {"updated_at": "", "active_signal": None, "radar": {}}

def save_state(state_data):
    state_data["updated_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    with open(STATE_FILE, "w") as f:
        json.dump(state_data, f, indent=2)

def calculate_liquidity_setup(ticker_symbol, pair_name, current_state):
    try:
        df = yf.download(ticker_symbol, period="5d", interval="15m", progress=False)
        if df.empty or len(df) < 100:
            return current_state

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        lookback_period = -100
        major_resistance = float(df['High'].iloc[lookback_period:-5].max())
        major_support = float(df['Low'].iloc[lookback_period:-5].min())

        last_candle = df.iloc[-1]
        close_price = float(last_candle['Close'])
        high_price = float(last_candle['High'])
        low_price = float(last_candle['Low'])
        open_price = float(last_candle['Open'])

        is_gold = "GC=F" in ticker_symbol
        multiplier = 10.0 if is_gold else 10000.0
        decimals = 2 if is_gold else 5
        
        radar_distance = 3.0 if is_gold else 0.0030 

        pair_key = ticker_symbol
        radar_status = current_state.get("radar", {}).get(pair_key, "NEUTRAL")

        # ==========================================
        # PANTAUAN RADAR (EARLY WARNING)
        # ==========================================
        
        if radar_status == "NEUTRAL" and (major_resistance - close_price) <= radar_distance and close_price < major_resistance:
            pesan_radar = (
                f"⚠️ *[RADAR INSTITUSIONAL]*\n\n"
                f"🔍 *Instrumen:* {pair_name}\n"
                f"📈 *Status:* Mendekati Zona Likuiditas Atas (Resistance: `{round(major_resistance, decimals)}`).\n\n"
                f"⏳ *Tindakan:* Jangan eksekusi apapun. Pantau chart Anda. Kita menunggu manipulasi harga (Stop Hunt) di area ini sebelum konfirmasi SELL."
            )
            send_alert(pesan_radar)
            current_state["radar"][pair_key] = "WATCHING_RESISTANCE"
            return current_state

        elif radar_status == "NEUTRAL" and (close_price - major_support) <= radar_distance and close_price > major_support:
            pesan_radar = (
                f"⚠️ *[RADAR INSTITUSIONAL]*\n\n"
                f"🔍 *Instrumen:* {pair_name}\n"
                f"📉 *Status:* Mendekati Zona Likuiditas Bawah (Support: `{round(major_support, decimals)}`).\n\n"
                f"⏳ *Tindakan:* Jangan eksekusi apapun. Pantau chart Anda. Kita menunggu manipulasi harga (Stop Hunt) di area ini sebelum konfirmasi BUY."
            )
            send_alert(pesan_radar)
            current_state["radar"][pair_key] = "WATCHING_SUPPORT"
            return current_state

        # ==========================================
        # KONFIRMASI EKSEKUSI (LIQUIDITY SWEEP)
        # ==========================================
        
        if radar_status == "WATCHING_RESISTANCE":
            if high_price > major_resistance and close_price < major_resistance and close_price < open_price:
                entry_price = round(close_price, decimals)
                sl_price = round(high_price + (1.5 if is_gold else 0.0015), decimals)
                risk_dist = abs(sl_price - entry_price)
                tp_price = round(entry_price - (risk_dist * 2.5), decimals)

                setup = {
                    "pair": pair_name,
                    "type": "SELL",
                    "entry": entry_price,
                    "sl": sl_price,
                    "tp": tp_price,
                    "risk_pips": round(risk_dist * multiplier, 1),
                    "reward_pips": round(abs(entry_price - tp_price) * multiplier, 1),
                    "rr": "1 : 2.5",
                    "reason": f"Konfirmasi Liquidity Sweep. Harga memakan likuiditas atas di {round(major_resistance, decimals)} namun ditolak kuat ke bawah."
                }
                current_state["active_signal"] = setup
                current_state["radar"][pair_key] = "NEUTRAL"
                
                pesan_eksekusi = (
                    f"🎯 *[VALID EXECUTION]*\n\n"
                    f"📊 *Instrumen:* {setup['pair']}\n"
                    f"⚡ *Aksi:* VALID {setup['type']}\n"
                    f"📍 *Level Entry:* `{setup['entry']}`\n"
                    f"🛑 *Stop Loss (SL):* `{setup['sl']}` ({setup['risk_pips']} Pips)\n"
                    f"💰 *Take Profit (TP):* `{setup['tp']}` ({setup['reward_pips']} Pips)\n\n"
                    f"💡 *Logika:* {setup['reason']}"
                )
                send_alert(pesan_eksekusi)
                return current_state

        elif radar_status == "WATCHING_SUPPORT":
            if low_price < major_support and close_price > major_support and close_price > open_price:
                entry_price = round(close_price, decimals)
                sl_price = round(low_price - (1.5 if is_gold else 0.0015), decimals)
                risk_dist = abs(entry_price - sl_price)
                tp_price = round(entry_price + (risk_dist * 2.5), decimals)

                setup = {
                    "pair": pair_name,
                    "type": "BUY",
                    "entry": entry_price,
                    "sl": sl_price,
                    "tp": tp_price,
                    "risk_pips": round(risk_dist * multiplier, 1),
                    "reward_pips": round(abs(tp_price - entry_price) * multiplier, 1),
                    "rr": "1 : 2.5",
                    "reason": f"Konfirmasi Liquidity Sweep. Harga memakan SL ritel di bawah {round(major_support, decimals)} dan ditolak kuat kembali ke atas."
                }
                current_state["active_signal"] = setup
                current_state["radar"][pair_key] = "NEUTRAL"
                
                pesan_eksekusi = (
                    f"🎯 *[VALID EXECUTION]*\n\n"
                    f"📊 *Instrumen:* {setup['pair']}\n"
                    f"⚡ *Aksi:* VALID {setup['type']}\n"
                    f"📍 *Level Entry:* `{setup['entry']}`\n"
                    f"🛑 *Stop Loss (SL):* `{setup['sl']}` ({setup['risk_pips']} Pips)\n"
                    f"💰 *Take Profit (TP):* `{setup['tp']}` ({setup['reward_pips']} Pips)\n\n"
                    f"💡 *Logika:* {setup['reason']}"
                )
                send_alert(pesan_eksekusi)
                return current_state

        if radar_status == "WATCHING_RESISTANCE" and (major_resistance - close_price) > (radar_distance * 2):
            current_state["radar"][pair_key] = "NEUTRAL"
        elif radar_status == "WATCHING_SUPPORT" and (close_price - major_support) > (radar_distance * 2):
            current_state["radar"][pair_key] = "NEUTRAL"

        return current_state

    except Exception as e:
        print(f"Error menganalisis {pair_name}: {e}")
        return current_state

def run_market_scan():
    current_state = load_state()
    instruments = [
        {"name": "XAU/USD (Gold)", "ticker": "GC=F"},
        {"name": "EUR/USD", "ticker": "EURUSD=X"},
        {"name": "GBP/USD", "ticker": "GBPUSD=X"}
    ]
    for item in instruments:
        current_state = calculate_liquidity_setup(item["ticker"], item["name"], current_state)
    save_state(current_state)

if __name__ == "__main__":
    run_market_scan()
