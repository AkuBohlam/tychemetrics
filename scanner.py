import os
import requests
import yfinance as yf

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

def get_current_price(ticker):
    try:
        data = yf.Ticker(ticker).history(period="1d", interval="1m")
        if not data.empty:
            return float(data['Close'].iloc[-1])
    except Exception:
        pass
    return None

def run_market_scan():
    watchlist = [
        {
            "pair": "XAU/USD (Gold)",
            "ticker": "GC=F",
            "target_entry": 2652.50,
            "sl": "2656.00 (35 Pips)",
            "tp": "2642.50 (100 Pips)",
            "rr": "1 : 2.8",
            "warn_dist": 6.0,   # Rentang siaga ~30 menit
            "exec_dist": 1.5    # Rentang eksekusi ~5 menit
        },
        {
            "pair": "EUR/USD",
            "ticker": "EURUSD=X",
            "target_entry": 1.0820,
            "sl": "1.0805 (15 Pips)",
            "tp": "1.0865 (45 Pips)",
            "rr": "1 : 3.0",
            "warn_dist": 0.0025,
            "exec_dist": 0.0006
        },
        {
            "pair": "GBP/USD",
            "ticker": "GBPUSD=X",
            "target_entry": 1.2980,
            "sl": "1.2960 (20 Pips)",
            "tp": "1.3040 (60 Pips)",
            "rr": "1 : 3.0",
            "warn_dist": 0.0030,
            "exec_dist": 0.0008
        }
    ]

    alert_terkirim = 0

    for item in watchlist:
        curr_price = get_current_price(item["ticker"])
        
        # Lewati jika harga pasar belum terbaca
        if curr_price is None:
            continue

        selisih = abs(curr_price - item["target_entry"])

        # Seleksi momentum: hanya kirim jika masuk kriteria waktu/jarak
        status_teks = None
        if selisih <= item["exec_dist"]:
            status_teks = "Eksekusi Sekarang (~5 Menit ke Level Entry)"
        elif selisih <= item["warn_dist"]:
            status_teks = "Siap-Siap (~30 Menit ke Level Pantau)"

        # Jika tidak ada momentum di pair ini, jangan kirim pesan apa pun
        if not status_teks:
            continue

        pesan = (
            f"🚨 *TYCHEMETRICS RADAR AKTIF*\n\n"
            f"📊 *Instrumen:* {item['pair']}\n"
            f"⚡ *Status:* {status_teks}\n"
            f"🎯 *Area:* {item['target_entry']}\n"
            f"🛑 *Batas Rugi (SL):* {item['sl']}\n"
            f"💰 *Target Untung (TP):* {item['tp']}\n"
            f"⚖️ *R:R Ratio:* {item['rr']}\n\n"
            f"🛡️ *Manajemen Risiko:* Gunakan kalkulator di aplikasi, maksimal risiko 1% modal."
        )
        send_alert(pesan)
        alert_terkirim += 1

    if alert_terkirim == 0:
        print("Pemindaian selesai: Belum ada pair yang mendekati momentum.")
    else:
        print(f"Pemindaian selesai: {alert_terkirim} sinyal momentum berhasil dikirim.")

if __name__ == "__main__":
    run_market_scan()
