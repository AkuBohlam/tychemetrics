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

def ambil_harga(simbol):
    try:
        data = yf.Ticker(simbol).history(period="1d", interval="1m")
        if not data.empty:
            return round(float(data['Close'].iloc[-1]), 4 if "USD=X" in simbol else 2)
    except Exception:
        pass
    return None

def run_market_scan():
    # Pemetaan ticker yfinance
    instrumen = [
        {"nama": "XAU/USD (Gold)", "ticker": "GC=F", "unit": "\$"},
        {"nama": "EUR/USD", "ticker": "EURUSD=X", "unit": ""},
        {"nama": "GBP/USD", "ticker": "GBPUSD=X", "unit": ""}
    ]

    laporan = ["⚡ *TYCHEMETRICS LIVE PRICE RADAR*\n"]

    for item in instrumen:
        harga = ambil_harga(item["ticker"])
        harga_tampil = f"{item['unit']}{harga}" if harga else "Pasar Libur / Menunggu Data"
        laporan.append(f"📊 *{item['nama']}*\n💰 Harga Terkini: `{harga_tampil}`\n")

    laporan.append("🛡️ *Manajemen Risiko:* Selalu verifikasi konfirmasi sebelum entry.")
    
    pesan_final = "\n".join(laporan)
    send_alert(pesan_final)
    print("Data harga pasar berhasil dikirim!")

if __name__ == "__main__":
    run_market_scan()
