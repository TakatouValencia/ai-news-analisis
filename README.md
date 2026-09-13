# EANews Analisis • AI Fundamental & News Signal Engine (XAU/USD)

Sistem AI analisis fundamental dan berita ekonomi *High Impact* (FOMC, NFP, CPI, PPI, Jobless Claims) serta sentimen geopolitik untuk memprediksi bias arah emas (XAU/USD), potensi spike, dan probabilitas pergerakan satu arah (*One-Way*) vs dua arah (*Two-Way*), dengan integrasi pengiriman sinyal via Discord Webhook dan Web Dashboard modern.

---

## 🌟 Fitur Utama

1. **Expected XAUUSD Bias**:
   - Menghasilkan sinyal `XAU BUY` atau `XAU SELL` berdasarkan deviasi rilis data makroekonomi dan sentimen safe-haven geopolitik.
2. **Context Confidence (%) & XAU Score**:
   - `Context %`: Keyakinan konsensus fundamental (e.g. `88%` - `94%`).
   - `XAU Score`: Nilai numerik kuantitatif antara `-10.00` hingga `+10.00`.
3. **Next USD News Countdown**:
   - Pemantauan waktu hitung mundur (*live ticking countdown*) ke rilis berita ekonomi terdekat.
   - Perbandingan angka *Forecast* vs *Previous* vs *Actual*.
4. **Spike Potential (%)**:
   - Estimasi probabilitas lonjakan volatilitas harga emas (e.g. `90%`).
5. **One-Way vs Two-Way Probability (%)**:
   - Memprediksi apakah pergerakan harga cenderung satu arah (*trending breakout*) atau dua arah (*whipsaw/false breakout*).
6. **Discord Webhook Signal Engine**:
   - Mengirim kartu sinyal *Rich Embed Dark Mode* elegan ke channel Discord Anda secara otomatis pada fase T-30 menit, T-5 menit, dan Flash reaksi rilis data.
7. **Web Dashboard Glassmorphism**:
   - Tampilan visual modern mobile-first yang responsif, terinspirasi langsung dari UI referensi Anda.

---

## 🚀 Cara Menjalankan

1. **Jalankan Server**:
   ```bash
   py -3.13 main.py
   ```
2. **Buka Web Dashboard**:
   Buka browser di: `http://localhost:8000`

3. **Hubungkan Discord**:
   - Klik tombol **⚙️ Setup Webhook** di Web Dashboard.
   - Masukkan URL Discord Webhook dari channel Discord Anda.
   - Klik **Simpan**, lalu uji kirim sinyal dengan klik **🚀 Kirim Sinyal Discord**.

---

## 📁 Struktur Proyek

```
EANews Analisis/
├── .env                       # File kredensial (API Key & Webhook)
├── config.py                  # Konfigurasi aplikasi
├── main.py                    # Server FastAPI & API Endpoints
├── modules/
│   ├── calendar_service.py    # Pengambil kalender berita High Impact USD
│   ├── geopolitical_service.py# Intelejen berita geopolitik & makro
│   ├── ai_analyzer.py         # AI LLM Analyzer & Rule-based NLP fallback
│   ├── quant_engine.py        # Algoritma perhitungan XAU Score, Bias & Spike
│   ├── discord_webhook.py     # Generator Rich Embed & pengirim Discord Webhook
│   └── scheduler_service.py   # Pemantau jadwal & pengirim otomatis
├── web/
│   ├── index.html             # Tampilan dashboard
│   └── static/
│       ├── css/style.css      # Styling dark glassmorphism
│       └── js/app.js          # Logika timer & sinkronisasi UI
└── test_signal.py             # Skrip pengujian mandiri
```
