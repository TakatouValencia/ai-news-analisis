# Panduan Instalasi & Uji Coba Akun Demo — Novaire Hedge Fund XAUUSD EA (MT5)

Expert Advisor ini menggabungkan **AI Quant Macro Regime** dari server Railway + **Hedge Fund Entry Engine** (`Liquidity Sweep`, `Fair Value Gap / EMA Pullback`, `Multi-Timeframe H4/H1`, `ATR Volatility Sizing`, `Breakeven + Partial Close + Trailing`, dan `Daily Drawdown Kill-Switch`).

---

## 1. File yang Tersedia
- Source Code EA: `mt5/Novaire_HedgeFund_XAUUSD.mq5`
- File Hasil Compile Siap Pakai: `mt5/Novaire_HedgeFund_XAUUSD.ex5`

---

## 2. Langkah Pasang di MetaTrader 5 (Akun Demo)
1. Buka **MetaTrader 5** dan pastikan Anda login di **Akun Demo** (bukan Real — EA ini memiliki pengaman default `InpDemoOnly = true` yang otomatis memblokir akun Real saat fase uji coba).
2. Klik menu **File -> Open Data Folder**, lalu buka folder **`MQL5/Experts/`**.
3. Salin file `Novaire_HedgeFund_XAUUSD.ex5` (atau `.mq5`) ke dalam folder `MQL5/Experts/`.
4. Kembali ke MT5, klik kanan **Expert Advisors** di panel Navigator -> klik **Refresh**.

---

## 3. Wajib: Izinkan Koneksi Server AI Quant (`WebRequest`)
Agar EA dapat membaca sinyal makro, US10Y Yields, DXY, Volatility Regime, dan News Blackout secara 24 jam:
1. Di MT5, buka **Tools -> Options** (atau tekan `Ctrl + O`).
2. Pilih tab **Expert Advisors**.
3. Centang:
   - **Allow Algorithmic Trading**
   - **Allow WebRequest for listed URL**
4. Klik dua kali **add new URL** dan masukkan persis URL berikut:
   ```
   https://ai-news-analisis-production-f6fe.up.railway.app
   ```
5. Klik **OK**.

---

## 4. Cara Menjalankan di Chart XAUUSD
1. Buka chart **XAUUSD** (atau `XAUUSDm` / `GOLD` sesuai simbol broker demo Anda) dengan timeframe **`M15`** *(EA otomatis membaca `H1` dan `H4` di balik layar)*.
2. Drag **`Novaire_HedgeFund_XAUUSD`** ke chart XAUUSD `M15`.
3. Pastikan pada tab **Common**, centang **Allow Algo Trading**.
4. Pastikan tombol **Algo Trading** di toolbar atas MT5 berwarna **hijau**.
5. Di pojok kiri atas chart akan muncul HUD status (`DEMO LOCKED`, `Server Bridge: ONLINE`, `Macro Regime`, `Confluence M15`, `Daily Risk`).

---

## 5. Pengaturan Default yang Sudah Dikalibrasi
- `InpDemoOnly = true`: Pengaman khusus Akun Demo.
- `InpRiskPct = 0.50`: Risiko per posisi `0.50%` dari Equity, diskalakan lagi oleh **Volatility Parity Multiplier** server.
- `InpMinConfluence = 68` (`75` saat sesi Asia): Hanya entry saat skor konfluensi Hedge Fund >= ambang ini.
- `InpUseNewsBlackout = true`: Otomatis menahan entry baru 30 menit sebelum hingga 15 menit sesudah news High-Impact USD (`NFP/CPI/PPI/FOMC/PMI`).
- `InpMaxDailyLossPct = 2.50`: Kill-switch otomatis berhenti trading sisa hari jika drawdown harian mencapai `-2.5%`.
- `InpBreakevenRR = 1.0`, `InpPartialRR = 1.4`: Otomatis geser SL ke BEP di `+1.0R`, ambil profit parsial 50% di `+1.4R`, dan trail sisanya dengan ATR hingga `2.6R`.

