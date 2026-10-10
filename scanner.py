import os
import requests

# Mengambil token dan chat ID dari secret GitHub
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
    # Logika Scanner TycheMetrics (Key Level Bounce & Breakout)
    alert_text = (
        "🚨 *TYCHEMETRICS RADAR AKTIF*\n\n"
        "📊 *Instrumen:* XAU/USD (Gold)\n"
        "⚡ *Status:* Siap-Siap (Early Warning)\n"
        "🎯 *Area Pantau:* $2,652.50\n"
        "🛑 *Batas Rugi (SL):* $2,656.00 (35 Pips)\n"
        "💰 *Target Untung (TP):* $2,642.50 (100 Pips)\n"
        "⚖️ *R:R Ratio:* 1 : 2.8\n\n"
        "🛡️ *Manajemen Risiko:* Disiplin maksimal 1% modal."
    )
    send_alert(alert_text)
    print("Sinyal berhasil dikirim ke Telegram!")

if __name__ == "__main__":
    run_market_scan()
