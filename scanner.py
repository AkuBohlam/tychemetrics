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
            "entry": 2652.50,
            "sl": "2648.50 (40 Pips)",
            "tp": "2662.50 (100 Pips)",
            "rr": "1 : 2.5",
            "cancel_threshold": 2645.00,
            "plan_type": "BUY",
            "reason_watch": "Harga bergerak menuju zona support kuat H1. Tunggu reaksi pantulan candle dan jangan terburu-buru entry.",
            "reason_exec": "Konfirmasi candle rejection valid di area entry 2652.50. Buyer resmi masuk dan mendominasi.",
            "reason_cancel": "Harga tembus ke bawah level support (breakdown). Struktur validasi buy gugur.",
            "warn_dist": 6.0,
            "exec_dist": 1.5
        },
        {
            "pair": "EUR/USD",
            "ticker": "EURUSD=X",
            "entry": 1.0820,
            "sl": "1.0805 (15 Pips)",
            "tp": "1.0865 (45 Pips)",
            "rr": "1 : 3.0",
            "cancel_threshold": 1.0790,
            "plan_type": "BUY",
            "reason_watch": "Mendekati level golden rasio Fibonacci 61.8%. Pantau reaksi di area 1.0820.",
            "reason_exec": "Pola pantulan terkonfirmasi di 1.0820. Target momentum kenaikan kembali aktif.",
            "reason_cancel": "Struktur higher low gagal dipertahankan. Setup beli dibatalkan.",
            "warn_dist": 0.0025,
            "exec_dist": 0.0006
        },
        {
            "pair": "GBP/USD",
            "ticker": "GBPUSD=X",
            "entry": 1.2980,
            "sl": "1.2960 (20 Pips)",
            "tp": "1.3040 (60 Pips)",
            "rr": "1 : 3.0",
            "cancel_threshold": 1.2940,
            "plan_type": "BUY",
            "reason_watch": "Harga mendekati area retest 1.2980. Tunggu konfirmasi volume sebelum eksekusi.",
            "reason_exec": "Rejection terverifikasi di 1.2980 dengan kenaikan volume buyer. Siap entry.",
            "reason_cancel": "Breakout gagal (fakeout) dan harga drop menembus support kunci. Setup batal.",
            "warn_dist": 0.0030,
            "exec_dist": 0.0008
        }
    ]

    for item in watchlist:
        curr = get_current_price(item["ticker"])
        if curr is None:
            continue

        is_cancelled = False
        if item["plan_type"] == "BUY" and curr < item["cancel_threshold"]:
            is_cancelled = True

        if is_cancelled:
            pesan = (
                f"❌ *TYCHEMETRICS SETUP CANCEL / BATAL*\n\n"
                f"📊 *Instrumen:* {item['pair']}\n"
                f"⚡ *Status:* Setup Dibatalkan (Tidak Valid)\n"
                f"🎯 *Area Rencana Awal:* {item['entry']}\n"
                f"💰 *Harga Terkini:* {curr}\n\n"
                f"💡 *Alasan Pembatalan:*\n{item['reason_cancel']}\n\n"
                f"🛡️ *Manajemen Risiko:* Jangan buka posisi. Disiplin modal adalah prioritas."
            )
            send_alert(pesan)
            continue

        selisih = abs(curr - item["entry"])

        if selisih <= item["exec_dist"]:
            pesan = (
                f"🚨 *TYCHEMETRICS FINAL CALL / EKSEKUSI*\n\n"
                f"📊 *Instrumen:* {item['pair']}\n"
                f"⚡ *Status:* Keputusan Final (~5-10 Menit ke Titik Entry)\n"
                f"🔥 *Rekomendasi:* VALID {item['plan_type']}\n"
                f"🎯 *Area Eksekusi:* `{item['entry']}`\n"
                f"🛑 *Batas Rugi (SL):* `{item['sl']}`\n"
                f"💰 *Target Untung (TP):* `{item['tp']}`\n"
                f"⚖️ *R:R Ratio:* {item['rr']}\n\n"
                f"💡 *Alasan & Konfirmasi:*\n{item['reason_exec']}\n\n"
                f"🛡️ *Manajemen Risiko:* Gunakan kalkulator lot di web terminal, maksimal risiko 1% modal."
            )
            send_alert(pesan)

        elif selisih <= item["warn_dist"]:
            pesan = (
                f"🟡 *TYCHEMETRICS RADAR PANTAU*\n\n"
                f"📊 *Instrumen:* {item['pair']}\n"
                f"⚡ *Status:* Siap-Siap (~30 Menit Sebelum Area)\n"
                f"✋ *Instruksi:* WAIT & OBSERVE (JANGAN ENTRY SEKARANG)\n"
                f"🎯 *Zona Target:* `{item['entry']}`\n\n"
                f"💡 *Edukasi & Analisa Awal:*\n{item['reason_watch']}\n\n"
                f"🛡️ *Peringatan:* Tunggu notifikasi FINAL CALL atau konfirmasi di aplikasi sebelum membuka posisi."
            )
            send_alert(pesan)

if __name__ == "__main__":
    run_market_scan()
