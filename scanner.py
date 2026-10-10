import os
import requests
import yfinance as yf
import pandas as pd

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_alert(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Gagal mengirim pesan Telegram: {e}")

def calculate_technical_setup(ticker_symbol, pair_name):
    try:
        # Mengambil data candle 15 menit (15m) untuk 5 hari bursa terakhir
        df = yf.download(ticker_symbol, period="5d", interval="15m", progress=False)
        if df.empty or len(df) < 100:
            return None

        # Antisipasi struktur MultiIndex kolom dari pustaka yfinance
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # 1. Macro Trend Filter: EMA 50 dan EMA 200
        df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
        df['EMA200'] = df['Close'].ewm(span=200, adjust=False).mean()

        # 2. Rebound Momentum Filter: RSI 14
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

        # 3. Dynamic Swing Analysis (30 candle terakhir)
        swing_high = float(df['High'].iloc[-30:].max())
        swing_low = float(df['Low'].iloc[-30:].min())
        diff = swing_high - swing_low

        if diff <= 0:
            return None

        # Level Fibonacci Retracement Emas
        fib_50 = swing_high - (diff * 0.50)
        fib_786 = swing_high - (diff * 0.786)

        fib_sell_50 = swing_low + (diff * 0.50)
        fib_sell_786 = swing_low + (diff * 0.786)

        is_gold = "GC=F" in ticker_symbol
        multiplier = 10.0 if is_gold else 10000.0
        decimals = 2 if is_gold else 5

        # SYARAT HIGH-CONVICTION BUY:
        # - Tren Bullish: EMA 50 > EMA 200 dan Harga > EMA 200
        # - Masuk Golden Pocket Retracement (50% s/d 78.6%)
        # - Candle Rejection Bullish (Close > Open)
        # - RSI dalam rentang rebound sehat (38 s/d 52)
        if (ema50 > ema200 and close_price > ema200) and \
           (fib_786 <= close_price <= fib_50) and \
           (close_price > open_price) and \
           (38 <= rsi <= 52):

            entry_price = round(close_price, decimals)
            sl_price = round(swing_low - (diff * 0.05), decimals)
            risk_dist = abs(entry_price - sl_price)

            if risk_dist <= 0:
                return None

            tp_price = round(entry_price + (risk_dist * 2.8), decimals)
            pips_risk = round(risk_dist * multiplier, 1)
            pips_reward = round(abs(tp_price - entry_price) * multiplier, 1)

            return {
                "pair": pair_name,
                "type": "BUY",
                "entry": entry_price,
                "sl": sl_price,
                "tp": tp_price,
                "risk_pips": pips_risk,
                "reward_pips": pips_reward,
                "rr": "1 : 2.8",
                "fib_zone": "Fibonacci 61.8% - 78.6% Golden Pocket",
                "reason": f"Struktur Makro Bullish (di atas EMA 200). Pantulan valid di Golden Pocket dengan pola candle rejection dan RSI {round(rsi, 1)}."
            }

        # SYARAT HIGH-CONVICTION SELL:
        # - Tren Bearish: EMA 50 < EMA 200 dan Harga < EMA 200
        # - Masuk Golden Pocket Retracement (50% s/d 78.6%)
        # - Candle Rejection Bearish (Close < Open)
        # - RSI dalam rentang pullback sehat (48 s/d 62)
        elif (ema50 < ema200 and close_price < ema200) and \
             (fib_sell_50 <= close_price <= fib_sell_786) and \
             (close_price < open_price) and \
             (48 <= rsi <= 62):

            entry_price = round(close_price, decimals)
            sl_price = round(swing_high + (diff * 0.05), decimals)
            risk_dist = abs(sl_price - entry_price)

            if risk_dist <= 0:
                return None

            tp_price = round(entry_price - (risk_dist * 2.8), decimals)
            pips_risk = round(risk_dist * multiplier, 1)
            pips_reward = round(abs(entry_price - tp_price) * multiplier, 1)

            return {
                "pair": pair_name,
                "type": "SELL",
                "entry": entry_price,
                "sl": sl_price,
                "tp": tp_price,
                "risk_pips": pips_risk,
                "reward_pips": pips_reward,
                "rr": "1 : 2.8",
                "fib_zone": "Fibonacci 61.8% - 78.6% Rejection Pocket",
                "reason": f"Struktur Makro Bearish (di bawah EMA 200). Penolakan harga terverifikasi di Golden Pocket dengan candle rejection dan RSI {round(rsi, 1)}."
            }

        return None
    except Exception as e:
        print(f"Pengecualian saat analisis {pair_name}: {e}")
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

if __name__ == "__main__":
    run_market_scan()
