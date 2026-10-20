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

        # ==========================================
        # FASE 3: PEMBATALAN (EMERGENCY CANCEL)
        # ==========================================
        active_signal = current_state.get("active_signal")
        if active_signal and active_signal.get("pair") == pair_name:
            sig_type = active_signal["type"]
            entry_p = active_signal["entry"]
            sl_p = active_signal["sl"]
            tp_p = active_signal["tp"]

            if sig_type == "SELL":
                if high_price >= sl_p or low_price <= tp_p:
                    current_state["active_signal"] = None
                    return current_state
                
                if close_price > major_resistance and close_price > open_price:
                    pesan_batal = (
                        f"🚫 *[EMERGENCY CANCEL: PROTEKSI MODAL]*\n\n"
                        f"📊 *Instrumen:* {pair_name}\n"
                        f"⚠️ *Rekomendasi Dibatalkan:* {sig_type} pada `{entry_p}`\n\n"
                        f"❌ *Alasan:* Arus pesanan (Order Flow) berbalik secara drastis. Struktur harga yang kita harapkan telah patah oleh volume yang berlawanan.\n\n"
                        f"🎓 *Edukasi Psikologi:* Menelan kerugian kecil (Cut Loss dini) jauh lebih baik daripada bersikap keras kepala dan berharap harga turun kembali. Trader profesional tidak dinilai dari seberapa sering mereka menang, tapi dari kedisiplinan mereka memotong kerugian saat probabilitas sudah tidak berpihak.\n\n"
                        f"⚡ *Tindakan:* Segera TUTUP POSISI Anda secara manual sekarang juga!"
                    )
                    send_alert(pesan_batal)
                    current_state["active_signal"] = None
                    return current_state

            elif sig_type == "BUY":
                if low_price <= sl_p or high_price >= tp_p:
                    current_state["active_signal"] = None
                    return current_state
                
                if close_price < major_support and close_price < open_price:
                    pesan_batal = (
                        f"🚫 *[EMERGENCY CANCEL: PROTEKSI MODAL]*\n\n"
                        f"📊 *Instrumen:* {pair_name}\n"
                        f"⚠️ *Rekomendasi Dibatalkan:* {sig_type} pada `{entry_p}`\n\n"
                        f"❌ *Alasan:* Arus pesanan (Order Flow) berbalik secara drastis. Struktur harga yang kita harapkan telah patah oleh tekanan jual yang besar.\n\n"
                        f"🎓 *Edukasi Psikologi:* Menelan kerugian kecil (Cut Loss dini) jauh lebih baik daripada bersikap keras kepala dan berharap harga naik kembali. Trader profesional tidak dinilai dari seberapa sering mereka menang, tapi dari kedisiplinan mereka memotong kerugian saat probabilitas sudah tidak berpihak.\n\n"
                        f"⚡ *Tindakan:* Segera TUTUP POSISI Anda secara manual sekarang juga!"
                    )
                    send_alert(pesan_batal)
                    current_state["active_signal"] = None
                    return current_state
            
            if not active_signal.get("escort_sent"):
                pesan_kawal = (
                    f"🛡️ *[PENGAMANAN POSISI AKTIF]*\n\n"
                    f"📊 *Instrumen:* {pair_name}\n"
                    f"⚡ *Status:* Posisi {sig_type} Anda sedang berjalan (Entry: `{entry_p}`).\n\n"
                    f"🎓 *Edukasi Trading:* Dalam dunia trading institusional, masuk ke pasar (entry) baru setengah dari perjuangan. Setengahnya lagi adalah 'Manajemen Posisi Aktif'. Kondisi makro bisa berubah dalam hitungan menit.\n\n"
                    f"👀 *Tindakan Anda:* Tetap awasi layar MT5/TradingView Anda. Jika algoritma kami mendeteksi anomali pergerakan harga, kami akan mengirim instruksi Pembatalan (Emergency Cut) untuk menyelamatkan sisa modal Anda."
                )
                send_alert(pesan_kawal)
                current_state["active_signal"]["escort_sent"] = True
            
            return current_state

        # ==========================================
        # FASE 1: RADAR (PERINGATAN DINI)
        # ==========================================
        radar_status = current_state.get("radar", {}).get(pair_key, "NEUTRAL")
        
        edukasi_res_vars = [
            "Harga sedang memasuki 'zona rawan' tempat trader ritel biasanya meletakkan Stop Loss mereka. Institusi besar sangat menyukai area ini untuk memompa harga sesaat sebelum membantingnya turun.",
            "Area Resistance ini memikat banyak trader pemula untuk berspekulasi Sell lebih awal. Institusi seringkali memanfaatkannya dengan mendorong harga naik sedikit lagi untuk menyapu Stop Loss mereka.",
            "Secara algoritmik, zona ini penuh dengan likuiditas (kumpulan order). Bandar cenderung memanipulasi harga ke atas menembus area ini untuk menjebak 'early sellers' sebelum tren asli dimulai."
        ]
        tindakan_res_vars = [
            "TAHAN DIRI. Jangan bereaksi dulu. Kita sedang menunggu konfirmasi apakah terjadi jebakan (Stop Hunt) atau malah Breakout murni. Bersiaplah di depan chart.",
            "TETAP WASPADA. Biarkan trader ritel terjebak lebih dulu. Pantau chart Anda dan tunggu instruksi eksekusi resmi dari bot setelah konfirmasi penolakan (rejection).",
            "PANTAU SAJA DULU. Jangan buru-buru menekan tombol SELL. Biarkan institusi menyelesaikan manipulasi harganya. Tangan di atas mouse."
        ]

        edukasi_sup_vars = [
            "Harga sedang memasuki 'zona rawan' tempat trader ritel biasanya meletakkan Stop Loss mereka. Institusi besar sangat menyukai area ini untuk menekan harga sesaat sebelum menariknya naik dengan kuat.",
            "Area Support ini adalah target empuk bagi 'Smart Money'. Mereka sering menekan harga turun menembus batas ini untuk memicu kepanikan (panic selling) sebelum akhirnya memborong di harga murah.",
            "Zona likuiditas bawah telah tercapai. Secara historis, institusi suka menciptakan penembusan palsu (fake breakdown) di level ini untuk mengumpulkan order BUY dari trader yang sudah putus asa."
        ]
        tindakan_sup_vars = [
            "TAHAN DIRI. Jangan bereaksi dulu. Kita sedang menunggu konfirmasi apakah terjadi jebakan (Stop Hunt) atau malah Breakdown murni. Bersiaplah di depan chart.",
            "TETAP WASPADA. Biarkan kepanikan ritel mereda lebih dulu. Pantau chart Anda dan tunggu instruksi eksekusi resmi dari bot setelah konfirmasi pembalikan arah.",
            "PANTAU SAJA DULU. Jangan buru-buru menekan tombol BUY untuk 'menangkap pisau jatuh'. Biarkan institusi menyelesaikan manipulasi harganya."
        ]

        if radar_status == "NEUTRAL" and (major_resistance - close_price) <= radar_distance and close_price < major_resistance:
            pesan_radar = (
                f"⚠️ *[RADAR INSTITUSIONAL AKTIF]*\n\n"
                f"🔍 *Instrumen:* {pair_name}\n"
                f"📈 *Area Pantauan:* Mendekati Zona Resistance (`{round(major_resistance, decimals)}`).\n\n"
                f"🧠 *Edukasi Market:* {random.choice(edukasi_res_vars)}\n\n"
                f"⏳ *Tindakan Anda:* {random.choice(tindakan_res_vars)}"
            )
            send_alert(pesan_radar)
            current_state["radar"][pair_key] = "WATCHING_RESISTANCE"
            return current_state

        elif radar_status == "NEUTRAL" and (close_price - major_support) <= radar_distance and close_price > major_support:
            pesan_radar = (
                f"⚠️ *[RADAR INSTITUSIONAL AKTIF]*\n\n"
                f"🔍 *Instrumen:* {pair_name}\n"
                f"📉 *Area Pantauan:* Mendekati Zona Support (`{round(major_support, decimals)}`).\n\n"
                f"🧠 *Edukasi Market:* {random.choice(edukasi_sup_vars)}\n\n"
                f"⏳ *Tindakan Anda:* {random.choice(tindakan_sup_vars)}"
            )
            send_alert(pesan_radar)
            current_state["radar"][pair_key] = "WATCHING_SUPPORT"
            return current_state

        # ==========================================
        # FASE 2: EKSEKUSI (REKOMENDASI)
        # ==========================================
        if radar_status == "WATCHING_RESISTANCE":
            if high_price > major_resistance and close_price < major_resistance and close_price < open_price:
                entry_price = round(close_price, decimals)
                sl_price = round(high_price + (1.5 if is_gold else 0.0015), decimals)
                risk_dist = abs(sl_price - entry_price)
                
                tp_price = round(major_support + (1.0 if is_gold else 0.0010), decimals)
                reward_dist = abs(entry_price - tp_price)
                
                actual_rr = reward_dist / risk_dist if risk_dist > 0 else 0
                if actual_rr < 2.0:
                    current_state["radar"][pair_key] = "NEUTRAL"
                    return current_state 

                web_reason = f"Bearish Liquidity Sweep terkonfirmasi di Resistance ({round(major_resistance, decimals)}). Peluang probabilitas tinggi untuk SELL."
                
                telegram_sell_vars = [
                    "Jebakan bandar terkonfirmasi! Harga sengaja didorong naik menembus area Resistance untuk memancing optimisme trader awam (FOMO). Begitu likuiditas terkumpul, harga langsung ditolak kuat dan dibanting turun. Ini jejak institusi besar (Liquidity Sweep).",
                    "Rejeksi institusional tervalidasi! Pola penembusan palsu (fakeout) di atas Resistance menunjukkan bahwa 'Smart Money' hanya menyapu Stop Loss ritel sebelum mendistribusikan pesanan jual masif mereka. Ada potensi probabilitas tinggi untuk ikut arus turun ini.",
                    "Momentum palsu berhasil diidentifikasi. Institusi membiarkan harga naik sesaat, memicu harapan breakout, lalu membantingnya dengan volume besar di timeframe ini. Setup institusional SELL kini terlihat sangat menjanjikan."
                ]
                telegram_reason = random.choice(telegram_sell_vars)

                setup = {
                    "pair": pair_name,
                    "type": "SELL",
                    "entry": entry_price,
                    "sl": sl_price,
                    "tp": tp_price,
                    "risk_pips": round(risk_dist * multiplier, 1),
                    "reward_pips": round(reward_dist * multiplier, 1),
                    "rr": f"1 : {round(actual_rr, 1)}",
                    "reason": web_reason,
                    "escort_sent": False
                }
                current_state["active_signal"] = setup
                current_state["radar"][pair_key] = "NEUTRAL"
                
                pesan_eksekusi = (
                    f"🎯 *[REKOMENDASI EKSEKUSI: IKUTI ARUS INSTITUSI]*\n\n"
                    f"📊 *Instrumen:* {setup['pair']}\n"
                    f"⚡ *Peluang Aksi:* POTENSI {setup['type']}\n"
                    f"📍 *Level Entry:* `{setup['entry']}`\n"
                    f"🛑 *Stop Loss (SL):* `{setup['sl']}` ({setup['risk_pips']} Pips)\n"
                    f"💰 *Take Profit (TP):* `{setup['tp']}` ({setup['reward_pips']} Pips)\n\n"
                    f"💡 *Smart Money Logic:* {telegram_reason}\n\n"
                    f"🎓 *Edukasi Risiko:* Tidak ada strategi yang 100% pasti. Rasio keuntungan terhadap risiko kita adalah {setup['rr']}. Selalu gunakan Kalkulator Web kami untuk memastikan risiko Anda maksimal hanya 1% dari total modal."
                )
                send_alert(pesan_eksekusi)
                return current_state

        elif radar_status == "WATCHING_SUPPORT":
            if low_price < major_support and close_price > major_support and close_price > open_price:
                entry_price = round(close_price, decimals)
                sl_price = round(low_price - (1.5 if is_gold else 0.0015), decimals)
                risk_dist = abs(entry_price - sl_price)
                
                tp_price = round(major_resistance - (1.0 if is_gold else 0.0010), decimals)
                reward_dist = abs(tp_price - entry_price)
                
                actual_rr = reward_dist / risk_dist if risk_dist > 0 else 0
                if actual_rr < 2.0:
                    current_state["radar"][pair_key] = "NEUTRAL"
                    return current_state 

                web_reason = f"Bullish Liquidity Sweep terkonfirmasi di Support ({round(major_support, decimals)}). Peluang probabilitas tinggi untuk BUY."
                
                telegram_buy_vars = [
                    "Jebakan bandar terkonfirmasi! Harga sengaja didorong turun menembus area Support untuk memancing kepanikan (panic selling) dari trader awam. Begitu likuiditas terkumpul, harga langsung ditolak kuat dan ditarik naik. Ini jejak institusi besar.",
                    "Rejeksi institusional tervalidasi! Pola penembusan palsu (fakeout) di bawah Support menunjukkan bahwa 'Smart Money' hanya menyapu Stop Loss ritel sebelum mengakumulasi pesanan beli masif mereka. Ada potensi probabilitas tinggi untuk ikut arus naik ini.",
                    "Kepanikan palsu berhasil diidentifikasi. Institusi membiarkan harga turun tajam sesaat untuk menciptakan ilusi downtrend, lalu memborongnya dengan volume besar. Setup institusional BUY kini terlihat sangat menjanjikan."
                ]
                telegram_reason = random.choice(telegram_buy_vars)

                setup = {
                    "pair": pair_name,
                    "type": "BUY",
                    "entry": entry_price,
                    "sl": sl_price,
                    "tp": tp_price,
                    "risk_pips": round(risk_dist * multiplier, 1),
                    "reward_pips": round(reward_dist * multiplier, 1),
                    "rr": f"1 : {round(actual_rr, 1)}",
                    "reason": web_reason,
                    "escort_sent": False
                }
                current_state["active_signal"] = setup
                current_state["radar"][pair_key] = "NEUTRAL"
                
                pesan_eksekusi = (
                    f"🎯 *[REKOMENDASI EKSEKUSI: IKUTI ARUS INSTITUSI]*\n\n"
                    f"📊 *Instrumen:* {setup['pair']}\n"
                    f"⚡ *Peluang Aksi:* POTENSI {setup['type']}\n"
                    f"📍 *Level Entry:* `{setup['entry']}`\n"
                    f"🛑 *Stop Loss (SL):* `{setup['sl']}` ({setup['risk_pips']} Pips)\n"
                    f"💰 *Take Profit (TP):* `{setup['tp']}` ({setup['reward_pips']} Pips)\n\n"
                    f"💡 *Smart Money Logic:* {telegram_reason}\n\n"
                    f"🎓 *Edukasi Risiko:* Tidak ada strategi yang 100% pasti. Rasio keuntungan terhadap risiko kita adalah {setup['rr']}. Selalu gunakan Kalkulator Web kami untuk memastikan risiko Anda maksimal hanya 1% dari total modal."
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
