import os
import json
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_alert(message):
    if not BOT_TOKEN or not CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Gagal mengirim Telegram: {e}")

def update_signals_json(setup):
    data = {
        "updated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "active_signal": setup
    }
    with open("signals.json", "w") as f:
        json.dump(data, f, indent=2)
    print("Berhasil memperbarui signals.json")

def calculate_technical_setup(ticker_symbol, pair_name):
    try:
        df = yf.download(ticker_symbol, period="5d", interval="15m", progress=False)
        if df.empty or len(df) < 100:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # Indikator EMA 50 & EMA 200
        df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
        df['EMA200'] = df['Close'].ewm(span=200, adjust=False).mean()

        # Indikator RSI 14
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))

        last_row = df.iloc[-1]
        close_price = float(last_row['Close'])
        open_price = float(last_row['Open'])
        ema50 = float(last_row['EMA50'])
        ema200 = float(last_row['EMA200'])
        rsi = float(last_row['RSI'])

        swing_high = float(df['High'].iloc[-30:].max())
        swing_low = float(df['Low'].iloc[-30:].min())
        diff = swing_high - swing_low

        if diff <= 0:
            return None

        fib_50 = swing_high - (diff * 0.50)
        fib_786 = swing_high - (diff * 0.786)
        fib_sell_50 = swing_low + (diff * 0.50)
        fib_sell_786 = swing_low + (diff * 0.786)

        is_gold = "GC=F" in ticker_symbol
        multiplier = 10.0 if is_gold else 10000.0
        decimals = 2 if is_gold else 5

        # BUY SETUP
        if (ema50 > ema200 and close_price > ema200) and \
           (fib_786 <= close_price <= fib_50) and \
           (close_price > open_price) and \
           (38 <= rsi <= 52):

            entry_price = round(close_price, decimals)
            sl_price = round(swing_low - (diff * 0.05), decimals)
            risk_dist = abs(entry_price - sl_price)
            if risk_dist <= 0: return None

            tp_price = round(entry_price + (risk_dist * 2.8), decimals)
            return {
                "pair": pair_name,
                "type": "BUY",
                "entry": entry_price,
                "sl": sl_price,
                "tp": tp_price,
                "risk_pips": round(risk_dist * multiplier, 1),
                "reward_pips": round(abs(tp_price - entry_price) * multiplier, 1),
                "rr": "1 : 2.8",
                "fib_zone": "Fibonacci 61.8% Golden Pocket",
                "reason": f"Struktur Makro Bullish (di atas EMA 200). Pantulan valid di Golden Pocket dengan pola candle rejection dan RSI {round(rsi, 1)}."
            }

        # SELL SETUP
        elif (ema50 < ema200 and close_price < ema200) and \
             (fib_sell_50 <= close_price <= fib_sell_786) and \
             (close_price < open_price) and \
             (48 <= rsi <= 62):

            entry_price = round(close_price, decimals)
            sl_price = round(swing_high + (diff * 0.05), decimals)
            risk_dist = abs(sl_price - entry_price)
            if risk_dist <= 0: return None

            tp_price = round(entry_price - (risk_dist * 2.8), decimals)
            return {
                "pair": pair_name,
                "type": "SELL",
                "entry": entry_price,
                "sl": sl_price,
                "tp": tp_price,
                "risk_pips": round(risk_dist * multiplier, 1),
                "reward_pips": round(abs(entry_price - tp_price) * multiplier, 1),
                "rr": "1 : 2.8",
                "fib_zone": "Fibonacci 61.8% Rejection Pocket",
                "reason": f"Struktur Makro Bearish (di bawah EMA 200). Penolakan harga terverifikasi di Golden Pocket dengan candle rejection dan RSI {round(rsi, 1)}."
            }

        return None
    except Exception as e:
        print(f"Error menganalisis {pair_name}: {e}")
        return None

def run_market_scan():
    instruments = [
        {"name": "XAU/USD (Gold)", "ticker": "GC=F"},
        {"name": "EUR/USD", "ticker": "EURUSD=X"},
        {"name": "GBP/USD", "ticker": "GBPUSD=X"}
    ]

    for item in instruments:
        setup = calculate_technical_setup(item["ticker"], item["name"])
        if setup:
            # 1. Update data untuk Web
            update_signals_json(setup)
            
            # 2. Kirim notifikasi ke Telegram
            pesan = (
                f"🏛️ *TYCHEMETRICS INSTITUTIONAL EXECUTION*\n\n"
                f"📊 *Instrumen:* {setup['pair']}\n"
                f"⚡ *Sinyal:* VALID {setup['type']}\n"
                f"📐 *Setup:* {setup['fib_zone']}\n"
                f"🎯 *Level Entry:* `{setup['entry']}`\n"
                f"🛑 *Batas Rugi (SL):* `{setup['sl']}` ({setup['risk_pips']} Pips)\n"
                f"💰 *Target Untung (TP):* `{setup['tp']}` ({setup['reward_pips']} Pips)\n"
                f"⚖️ *Risk to Reward:* {setup['rr']}\n\n"
                f"💡 *Alasan Algoritma:*\n{setup['reason']}\n\n"
                f"🛡️ *Manajemen Risiko:* Eksekusi disiplin dengan risiko maksimal 1.0% modal via kalkulator TycheMetrics."
            )
            send_alert(pesan)
            break

if __name__ == "__main__":
    run_market_scan()
