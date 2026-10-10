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
    response = requests.post(url, json=payload)
    print(f"Status Telegram API: {response.status_code}")
    print(f"Respon Telegram API: {response.text}")

def test_run():
    pesan_test = (
        f"🚨 *TYCHEMETRICS RADAR AKTIF*\n\n"
        f"📊 *Instrumen:* XAU/USD (Gold)\n"
        f"⚡ *Status:* Siap-Siap (~30 Menit ke Level Pantau)\n"
        f"🎯 *Area:* 2652.50\n"
        f"🛑 *Batas Rugi (SL):* 2648.50 (40 Pips)\n"
        f"💰 *Target Untung (TP):* 2662.50 (100 Pips)\n"
        f"⚖️ *R:R Ratio:* 1 : 2.5\n\n"
        f"💡 *Edukasi & Alasan Setup:*\n"
        f"Ini adalah pesan uji coba koneksi bot ke Saluran VIP TycheMetrics.\n\n"
        f"🛡️ *Manajemen Risiko:* Gunakan kalkulator di aplikasi, maksimal risiko 1% modal."
    )
    send_alert(pesan_test)

if __name__ == "__main__":
    test_run()
