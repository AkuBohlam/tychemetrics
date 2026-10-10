import os
import requests

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_alert(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    requests.post(url, json=payload)

def run_market_scan():
    watchlist = [
        {
            "pair": "GBP/USD",
            "area": "1.2980",
            "sl": "1.2960 (20 Pips)",
            "tp": "1.3040 (60 Pips)",
            "rr": "1 : 3.0"
        },
        {
            "pair": "XAU/USD (Gold)",
            "area": "2652.50",
            "sl": "2656.00 (35 Pips)",
            "tp": "2642.50 (100 Pips)",
            "rr": "1 : 2.8"
        },
        {
            "pair": "EUR/USD",
            "area": "1.0820",
            "sl": "1.0805 (15 Pips)",
            "tp": "1.0865 (45 Pips)",
            "rr": "1 : 3.0"
        }
    ]

    for item in watchlist:
        pesan = (
            f"🚨 *TYCHEMETRICS RADAR AKTIF*\n\n"
            f"📊 *Instrumen:* {item['pair']}\n"
            f"⚡ *Status:* Siap-Siap (Key Level Pantau)\n"
            f"🎯 *Area:* {item['area']}\n"
            f"🛑 *Batas Rugi (SL):* {item['sl']}\n"
            f"💰 *Target Untung (TP):* {item['tp']}\n"
            f"⚖️ *R:R Ratio:* {item['rr']}\n\n"
            f"🛡️ *Manajemen Risiko:* Gunakan kalkulator di aplikasi, maksimal risiko 1% modal."
        )
        send_alert(pesan)

    print("Sinyal radar berhasil dikirim!")

if __name__ == "__main__":
    run_market_scan()
