//+------------------------------------------------------------------+
//|                                    Novaire_HedgeFund_XAUUSD.mq5  |
//|         Novaire AI Quant + Institutional Hedge Fund Hybrid EA    |
//|    24/5 XAUUSD | Macro Regime + Liquidity Sweep + FVG + ATR Risk |
//+------------------------------------------------------------------+
#property copyright "Novaire AI Quant Desk"
#property link      "https://ai-news-analisis-production-f6fe.up.railway.app"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

//--- INPUT PARAMETERS -----------------------------------------------
input group "=== 1. SERVER AI QUANT BRIDGE ==="
input string InpServerUrl         = "https://ai-news-analisis-production-f6fe.up.railway.app/api/ea/signal";
input string InpHeartbeatUrl      = "https://ai-news-analisis-production-f6fe.up.railway.app/api/ea/heartbeat";
input string InpApiKey            = "novaire-demo-2026";
input int    InpPollSeconds       = 60;       // Poll interval ke AI Quant Server (detik)
input bool   InpStrictMacroFilter = true;     // Blokir entry jika melawan Macro Bias kuat (|score| >= 40)
input bool   InpUseNewsBlackout   = true;     // Pause entry saat H-30m s/d H+15m news High Impact

input group "=== 2. KEAMANAN & MODE AKUN ==="
input bool   InpDemoOnly          = true;     // WAJIB TRUE saat uji coba: blokir jika akun REAL!
input long   InpMagicNumber       = 20261113; // Magic number unik EA
input int    InpMaxSpreadPoints   = 55;       // Max spread XAUUSD (points, 55 = 5.5 pips)
input bool   InpBlockRollover     = true;     // Hindari rollover spread lebar (21:55 - 23:05 UTC)

input group "=== 3. HEDGE FUND ENTRY ENGINE (M15 / H1 / H4) ==="
input int    InpMinConfluence     = 68;       // Minimum Confluence Score (0-100) untuk entry
input int    InpAsianMinConf      = 75;       // Score minimum lebih ketat saat sesi Asia sepi
input int    InpSweepLookback     = 24;       // Lookback Liquidity Pool M15 (24 bar = 6 jam)
input double InpMinWickRatio      = 0.38;     // Min rasio ekor rejection untuk Liquidity Sweep
input double InpTrendADXMin       = 20.0;     // ADX H1 minimum untuk mode Trend Pullback/FVG

input group "=== 4. RISK & TRADE MANAGEMENT ==="
input double InpRiskPct           = 0.50;     // Risiko per trade (% Equity)
input double InpSL_ATR_Mult       = 1.80;     // Stop Loss = ATR(M15) * multiplier
input double InpTP_RR             = 2.60;     // Target Profit Risk:Reward ratio
input double InpBreakevenRR       = 1.00;     // Pindah SL ke BEP pada profit +R ini
input double InpPartialRR         = 1.40;     // Partial Close 50% pada profit +R ini (0 = nonaktif)
input double InpTrailATRMult      = 1.20;     // Trailing Stop ATR setelah melewati +1.5R
input double InpMaxDailyLossPct   = 2.50;     // Daily Drawdown Kill-Switch (% Equity)
input int    InpMaxDailyTrades    = 5;        // Maksimum jumlah trade per hari
input int    InpCooldownBars      = 2;        // Jeda minimal M15 bar setelah posisi ditutup loss

//--- GLOBAL OBJECTS & STATE -----------------------------------------
CTrade   trade;

int      g_hEma20_M15 = INVALID_HANDLE, g_hEma50_M15 = INVALID_HANDLE;
int      g_hAtr14_M15 = INVALID_HANDLE, g_hRsi14_M15 = INVALID_HANDLE;
int      g_hEma20_H1  = INVALID_HANDLE, g_hEma50_H1  = INVALID_HANDLE, g_hEma200_H1 = INVALID_HANDLE;
int      g_hAdx14_H1  = INVALID_HANDLE;
int      g_hEma20_H4  = INVALID_HANDLE, g_hEma50_H4  = INVALID_HANDLE;

// Server Macro State
string   g_macroBias       = "NEUTRAL";
int      g_macroScore      = 0;
string   g_volRegime       = "NORMAL";
double   g_volLotMult      = 1.0;
bool     g_newsBlackout    = false;
string   g_blackoutReason  = "CLEAR";
int      g_minutesToEvent  = 9999;
string   g_nextEventName   = "NONE";
string   g_flashBias       = "NONE";
int      g_flashConf       = 0;
double   g_dxyPrice        = 0.0;
double   g_yield10y        = 0.0;
datetime g_lastServerSync  = 0;
datetime g_lastPollTry     = 0;
datetime g_lastHeartbeat   = 0;
string   g_serverConnState = "INIT";

// Execution & Daily Circuit Breaker State
datetime g_lastBarTime     = 0;
datetime g_lastLossClose   = 0;
int      g_currentDayKey   = 0;
double   g_dayStartEquity  = 0.0;
int      g_dailyTradeCount = 0;
bool     g_dailyHalted     = false;

// UI / Audit State
int      g_lastBuyScore    = 0;
int      g_lastSellScore   = 0;
string   g_lastSetupTag    = "SCANNING";
string   g_lastGateNote    = "READY";
ulong    g_partialDone[];

//--- HELPER UTILITIES -----------------------------------------------
string TrimStr(string s)
{
   StringTrimLeft(s);
   StringTrimRight(s);
   return s;
}

bool HasPartialDone(ulong ticket)
{
   int n = ArraySize(g_partialDone);
   for(int i = 0; i < n; i++)
      if(g_partialDone[i] == ticket) return true;
   return false;
}

void MarkPartialDone(ulong ticket)
{
   if(HasPartialDone(ticket)) return;
   int n = ArraySize(g_partialDone);
   ArrayResize(g_partialDone, n + 1);
   g_partialDone[n] = ticket;
}

bool GetBufVal(int handle, int bufIndex, int shift, double &outVal)
{
   double arr[];
   ArraySetAsSeries(arr, true);
   if(CopyBuffer(handle, bufIndex, shift, 1, arr) != 1)
      return false;
   outVal = arr[0];
   return (outVal != EMPTY_VALUE && MathIsValidNumber(outVal));
}

bool GetBufArray(int handle, int bufIndex, int start, int count, double &outArr[])
{
   ArraySetAsSeries(outArr, true);
   return (CopyBuffer(handle, bufIndex, start, count, outArr) == count);
}

int DayKeyFromTime(datetime t)
{
   MqlDateTime dt;
   TimeToStruct(t, dt);
   return dt.year * 10000 + dt.mon * 100 + dt.day;
}

string GetSessionLabel(int utcHour)
{
   if(utcHour >= 12 && utcHour <= 16) return "NY+LDN OVERLAP";
   if(utcHour >= 7  && utcHour <= 11) return "LONDON KILLZONE";
   if(utcHour >= 17 && utcHour <= 20) return "NY PM SESSION";
   if(utcHour >= 21 || utcHour == 22) return "ROLLOVER DEADZONE";
   return "ASIAN SESSION";
}

bool IsRolloverDeadzone()
{
   if(!InpBlockRollover) return false;
   MqlDateTime utc;
   TimeToStruct(TimeGMT(), utc);
   int mins = utc.hour * 60 + utc.min;
   // 21:55 UTC (1315) to 23:05 UTC (1385)
   return (mins >= 1315 && mins <= 1385);
}

//--- SERVER WEB REQUEST BRIDGE --------------------------------------
void ParseKeyValueSignal(string body)
{
   string lines[];
   int count = StringSplit(body, '\n', lines);
   if(count <= 0) return;

   for(int i = 0; i < count; i++)
   {
      string ln = TrimStr(lines[i]);
      if(ln == "") continue;
      int eq = StringFind(ln, "=");
      if(eq <= 0) continue;

      string key = TrimStr(StringSubstr(ln, 0, eq));
      string val = TrimStr(StringSubstr(ln, eq + 1));

      if(key == "MACRO_BIAS")        g_macroBias      = val;
      else if(key == "MACRO_SCORE")  g_macroScore     = (int)StringToInteger(val);
      else if(key == "VOLATILITY_REGIME") g_volRegime = val;
      else if(key == "VOL_LOT_MULT") g_volLotMult     = MathMax(0.25, MathMin(1.50, StringToDouble(val)));
      else if(key == "NEWS_BLACKOUT") g_newsBlackout  = (val == "1" || val == "true");
      else if(key == "BLACKOUT_REASON") g_blackoutReason = val;
      else if(key == "MINUTES_TO_EVENT") g_minutesToEvent = (int)StringToInteger(val);
      else if(key == "NEXT_EVENT_NAME")  g_nextEventName  = val;
      else if(key == "FLASH_BIAS")   g_flashBias      = val;
      else if(key == "FLASH_CONF")   g_flashConf      = (int)StringToInteger(val);
      else if(key == "DXY_PRICE")    g_dxyPrice       = StringToDouble(val);
      else if(key == "YIELD_10Y")    g_yield10y       = StringToDouble(val);
   }
   g_lastServerSync  = TimeCurrent();
   g_serverConnState = "ONLINE";
}

void SyncServerMacroSignal(bool force)
{
   datetime now = TimeCurrent();
   if(!force && (now - g_lastPollTry) < InpPollSeconds)
      return;
   g_lastPollTry = now;

   string url = InpServerUrl + "?format=kv&api_key=" + InpApiKey;
   char postData[];
   char result[];
   string resHeaders = "";
   ResetLastError();
   int httpCode = WebRequest("GET", url, "Accept: text/plain\r\n", 3500, postData, result, resHeaders);

   if(httpCode == 200)
   {
      string body = CharArrayToString(result, 0, WHOLE_ARRAY, CP_UTF8);
      ParseKeyValueSignal(body);
   }
   else
   {
      int err = GetLastError();
      if(err == 4060)
         g_serverConnState = "ALLOW_WEBREQUEST_URL";
      else
         g_serverConnState = "OFFLINE_HTTP_" + IntegerToString(httpCode);
   }
}

void SendHeartbeatTelemetry()
{
   datetime now = TimeCurrent();
   if((now - g_lastHeartbeat) < 120) return;
   g_lastHeartbeat = now;

   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   double bal = AccountInfoDouble(ACCOUNT_BALANCE);
   double pnlPct = (g_dayStartEquity > 0.0) ? ((eq - g_dayStartEquity) / g_dayStartEquity * 100.0) : 0.0;
   int spreadPts = (int)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);

   int openPos = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk > 0 && PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
         openPos++;
   }

   string json = StringFormat(
      "{\"account_mode\":\"%s\",\"symbol\":\"%s\",\"balance\":%.2f,\"equity\":%.2f,\"daily_pnl_pct\":%.2f,\"open_positions\":%d,\"spread_points\":%d,\"last_action\":\"%s\",\"confluence_score\":%d,\"broker_server\":\"%s\"}",
      (AccountInfoInteger(ACCOUNT_TRADE_MODE) == ACCOUNT_TRADE_MODE_DEMO ? "DEMO" : "REAL"),
      _Symbol, bal, eq, pnlPct, openPos, spreadPts, g_lastSetupTag, MathMax(g_lastBuyScore, g_lastSellScore),
      AccountInfoString(ACCOUNT_SERVER)
   );

   char post[];
   StringToCharArray(json, post, 0, WHOLE_ARRAY, CP_UTF8);
   // Remove trailing null terminator added by StringToCharArray
   if(ArraySize(post) > 0 && post[ArraySize(post) - 1] == 0)
      ArrayResize(post, ArraySize(post) - 1);

   char result[];
   string resHeaders = "";
   string url = InpHeartbeatUrl + "?api_key=" + InpApiKey;
   WebRequest("POST", url, "Content-Type: application/json\r\n", 2500, post, result, resHeaders);
}

//--- DAILY CIRCUIT BREAKER & POSITION COUNT -----------------------
void UpdateDailyRiskState()
{
   datetime now = TimeCurrent();
   int today = DayKeyFromTime(now);
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);

   if(today != g_currentDayKey)
   {
      g_currentDayKey   = today;
      g_dayStartEquity  = eq;
      g_dailyTradeCount = 0;
      g_dailyHalted     = false;

      // Count any trades already opened today in history
      MqlDateTime dt;
      TimeToStruct(now, dt);
      dt.hour = 0; dt.min = 0; dt.sec = 0;
      datetime dayBegin = StructToTime(dt);
      if(HistorySelect(dayBegin, now))
      {
         int deals = HistoryDealsTotal();
         for(int i = 0; i < deals; i++)
         {
            ulong dtk = HistoryDealGetTicket(i);
            if(HistoryDealGetInteger(dtk, DEAL_MAGIC) == InpMagicNumber &&
               HistoryDealGetInteger(dtk, DEAL_ENTRY) == DEAL_ENTRY_IN)
               g_dailyTradeCount++;
         }
      }
   }

   if(g_dayStartEquity > 0.0)
   {
      double pnlPct = (eq - g_dayStartEquity) / g_dayStartEquity * 100.0;
      if(pnlPct <= -InpMaxDailyLossPct)
         g_dailyHalted = true;
   }
}

int CountOpenEAOrdersAndPositions()
{
   int total = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk > 0 && PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
         total++;
   }
   return total;
}

bool IsInLossCooldown()
{
   if(InpCooldownBars <= 0) return false;
   datetime now = TimeCurrent();
   if(HistorySelect(now - 86400 * 3, now))
   {
      int deals = HistoryDealsTotal();
      for(int i = deals - 1; i >= 0; i--)
      {
         ulong dtk = HistoryDealGetTicket(i);
         if(HistoryDealGetInteger(dtk, DEAL_MAGIC) != InpMagicNumber) continue;
         if(HistoryDealGetInteger(dtk, DEAL_ENTRY) != DEAL_ENTRY_OUT) continue;
         double prof = HistoryDealGetDouble(dtk, DEAL_PROFIT) + HistoryDealGetDouble(dtk, DEAL_SWAP) + HistoryDealGetDouble(dtk, DEAL_COMMISSION);
         datetime closeTime = (datetime)HistoryDealGetInteger(dtk, DEAL_TIME);
         if(prof < 0.0 && (now - closeTime) < InpCooldownBars * PeriodSeconds(PERIOD_M15))
            return true;
         break;
      }
   }
   return false;
}

//--- LOT SIZING & ORDER EXECUTION -----------------------------------
double CalculateDynamicLots(double slDistancePrice, double setupScale)
{
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   bool isMacroFresh = (g_lastServerSync > 0 && (TimeCurrent() - g_lastServerSync) <= 600);
   double serverMult = isMacroFresh ? g_volLotMult : 0.65; // Conservative half-ish if offline
   double riskMoney = equity * (InpRiskPct / 100.0) * serverMult * setupScale;

   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   if(tickSize <= 0.0 || tickValue <= 0.0 || slDistancePrice <= 0.0)
      return SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);

   double moneyPerLotAtSL = (slDistancePrice / tickSize) * tickValue;
   if(moneyPerLotAtSL <= 0.0)
      return SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);

   double rawLots  = riskMoney / moneyPerLotAtSL;
   double minLot   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double lotStep  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);

   double normLots = MathFloor(rawLots / lotStep) * lotStep;
   normLots = MathMax(minLot, MathMin(maxLot, normLots));
   return NormalizeDouble(normLots, 2);
}

//--- INSTITUTIONAL HEDGE FUND ENTRY ENGINE --------------------------
int GetMultiTFStructureBias(double &outAdxH1)
{
   double e20_h1, e50_h1, e200_h1, c_h1;
   double e20_h4, e50_h4, c_h4;
   if(!GetBufVal(g_hEma20_H1, 0, 1, e20_h1) ||
      !GetBufVal(g_hEma50_H1, 0, 1, e50_h1) ||
      !GetBufVal(g_hEma200_H1, 0, 1, e200_h1) ||
      !GetBufVal(g_hAdx14_H1, 0, 1, outAdxH1) ||
      !GetBufVal(g_hEma20_H4, 0, 1, e20_h4) ||
      !GetBufVal(g_hEma50_H4, 0, 1, e50_h4))
      return 0;

   c_h1 = iClose(_Symbol, PERIOD_H1, 1);
   c_h4 = iClose(_Symbol, PERIOD_H4, 1);

   int h1Bias = 0;
   if(c_h1 > e20_h1 && e20_h1 > e50_h1 && c_h1 > e200_h1) h1Bias = 1;
   else if(c_h1 < e20_h1 && e20_h1 < e50_h1 && c_h1 < e200_h1) h1Bias = -1;
   else if(c_h1 > e50_h1 && e20_h1 > e50_h1) h1Bias = 1;
   else if(c_h1 < e50_h1 && e20_h1 < e50_h1) h1Bias = -1;

   int h4Bias = 0;
   if(c_h4 > e20_h4 && e20_h4 > e50_h4) h4Bias = 1;
   else if(c_h4 < e20_h4 && e20_h4 < e50_h4) h4Bias = -1;

   if(h1Bias == 1 && h4Bias == 1)  return 2;   // Strong Bullish Alignment
   if(h1Bias == -1 && h4Bias == -1) return -2; // Strong Bearish Alignment
   return h1Bias; // +1, -1, or 0
}

void EvaluateHedgeFundSetup(int &outDir, int &outScore, string &outSetupTag, double &outAtrM15)
{
   outDir = 0;
   outScore = 0;
   outSetupTag = "SCANNING";

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int needed = MathMax(InpSweepLookback + 5, 35);
   if(CopyRates(_Symbol, PERIOD_M15, 0, needed, rates) < needed)
      return;

   double ema20[], ema50[], rsi[], atr[];
   if(!GetBufArray(g_hEma20_M15, 0, 0, 6, ema20) ||
      !GetBufArray(g_hEma50_M15, 0, 0, 6, ema50) ||
      !GetBufArray(g_hRsi14_M15, 0, 0, 6, rsi)   ||
      !GetBufArray(g_hAtr14_M15, 0, 0, 6, atr))
      return;

   outAtrM15 = atr[1];
   if(outAtrM15 <= 0.0) return;

   double adxH1 = 0.0;
   int mtfBias = GetMultiTFStructureBias(adxH1);

   // Candle [1] metrics (recently closed M15 candle)
   double o1 = rates[1].open, h1 = rates[1].high, l1 = rates[1].low, c1 = rates[1].close;
   double range1 = MathMax(h1 - l1, _Point);
   double body1  = MathAbs(c1 - o1);
   double upperWick = h1 - MathMax(o1, c1);
   double lowerWick = MathMin(o1, c1) - l1;
   double lowerWickRatio = lowerWick / range1;
   double upperWickRatio = upperWick / range1;
   double bodyRatio = body1 / range1;

   // Liquidity Pool over [2 .. InpSweepLookback + 1]
   double poolHigh = rates[2].high;
   double poolLow  = rates[2].low;
   for(int i = 2; i <= InpSweepLookback + 1; i++)
   {
      if(rates[i].high > poolHigh) poolHigh = rates[i].high;
      if(rates[i].low  < poolLow)  poolLow  = rates[i].low;
   }

   // Fair Value Gap (FVG) & EMA Value Pullback
   bool bullFVG = (rates[3].high < rates[1].low) || (rates[4].high < rates[2].low && l1 <= rates[2].low && c1 > rates[4].high);
   bool bearFVG = (rates[3].low > rates[1].high) || (rates[4].low > rates[2].high && h1 >= rates[2].high && c1 < rates[4].low);

   bool bullSweep = (l1 < poolLow - 0.08 * outAtrM15) && (c1 > poolLow) && (lowerWickRatio >= InpMinWickRatio) && (c1 >= o1 - 0.15 * range1);
   bool bearSweep = (h1 > poolHigh + 0.08 * outAtrM15) && (c1 < poolHigh) && (upperWickRatio >= InpMinWickRatio) && (c1 <= o1 + 0.15 * range1);

   bool bullPullback = (adxH1 >= InpTrendADXMin) && (mtfBias >= 1) && (l1 <= ema20[1] + 0.25 * outAtrM15) && (c1 > ema20[1]) && (c1 > o1) && (bodyRatio >= 0.48) && (c1 > ema50[1]);
   bool bearPullback = (adxH1 >= InpTrendADXMin) && (mtfBias <= -1) && (h1 >= ema20[1] - 0.25 * outAtrM15) && (c1 < ema20[1]) && (c1 < o1) && (bodyRatio >= 0.48) && (c1 < ema50[1]);

   //--- Score BUY Direction (0..100) ---
   int buyScore = 0;
   string buyTag = "NONE";
   if(bullSweep)
   {
      buyScore += 35;
      buyTag = "LIQ_SWEEP_BUY";
      if(bullFVG) buyScore += 8;
   }
   else if(bullPullback)
   {
      buyScore += (bullFVG ? 30 : 24);
      buyTag = (bullFVG ? "FVG_TREND_BUY" : "EMA_VAL_BUY");
   }

   if(buyScore > 0)
   {
      // Structural H4/H1 Points
      if(mtfBias == 2)      buyScore += 25;
      else if(mtfBias == 1) buyScore += 18;
      else if(mtfBias == 0) buyScore += 10;
      else                  buyScore -= 10; // Counter H1/H4 trend

      // Momentum / RSI Confirmation
      if(rsi[1] > rsi[2] && rsi[1] >= 32.0 && rsi[1] <= 63.0) buyScore += 15;
      else if(rsi[2] <= 34.0 && c1 > o1)                      buyScore += 12;

      // Server Macro Quant Alignment
      bool macroFresh = (g_lastServerSync > 0 && (TimeCurrent() - g_lastServerSync) <= 600);
      if(macroFresh)
      {
         if(g_macroBias == "BULLISH")      buyScore += (g_macroScore >= 45 ? 25 : 20);
         else if(g_macroBias == "NEUTRAL") buyScore += 10;
         else if(g_macroBias == "BEARISH") buyScore -= (g_macroScore <= -40 ? 22 : 12);
      }
      else
      {
         buyScore += 6; // Neutral conservative boost when offline
      }

      if(g_flashBias == "BUY" && g_flashConf >= 72) buyScore += 15;
   }

   //--- Score SELL Direction (0..100) ---
   int sellScore = 0;
   string sellTag = "NONE";
   if(bearSweep)
   {
      sellScore += 35;
      sellTag = "LIQ_SWEEP_SELL";
      if(bearFVG) sellScore += 8;
   }
   else if(bearPullback)
   {
      sellScore += (bearFVG ? 30 : 24);
      sellTag = (bearFVG ? "FVG_TREND_SELL" : "EMA_VAL_SELL");
   }

   if(sellScore > 0)
   {
      if(mtfBias == -2)      sellScore += 25;
      else if(mtfBias == -1) sellScore += 18;
      else if(mtfBias == 0)  sellScore += 10;
      else                   sellScore -= 10;

      if(rsi[1] < rsi[2] && rsi[1] >= 37.0 && rsi[1] <= 68.0) sellScore += 15;
      else if(rsi[2] >= 66.0 && c1 < o1)                      sellScore += 12;

      bool macroFresh = (g_lastServerSync > 0 && (TimeCurrent() - g_lastServerSync) <= 600);
      if(macroFresh)
      {
         if(g_macroBias == "BEARISH")      sellScore += (g_macroScore <= -45 ? 25 : 20);
         else if(g_macroBias == "NEUTRAL") sellScore += 10;
         else if(g_macroBias == "BULLISH") sellScore -= (g_macroScore >= 40 ? 22 : 12);
      }
      else
      {
         sellScore += 6;
      }

      if(g_flashBias == "SELL" && g_flashConf >= 72) sellScore += 15;
   }

   buyScore  = MathMax(0, MathMin(100, buyScore));
   sellScore = MathMax(0, MathMin(100, sellScore));
   g_lastBuyScore  = buyScore;
   g_lastSellScore = sellScore;

   if(buyScore >= sellScore && buyScore > 0)
   {
      outDir = 1;
      outScore = buyScore;
      outSetupTag = buyTag;
   }
   else if(sellScore > buyScore && sellScore > 0)
   {
      outDir = -1;
      outScore = sellScore;
      outSetupTag = sellTag;
   }
}

//--- ACTIVE TRADE MANAGEMENT (BEP + PARTIAL + ATR TRAILING) -------
void ManageOpenPositions()
{
   double atrM15 = 0.0;
   if(!GetBufVal(g_hAtr14_M15, 0, 1, atrM15) || atrM15 <= 0.0)
      return;

   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;

      long   posType = PositionGetInteger(POSITION_TYPE);
      double openPrc = PositionGetDouble(POSITION_PRICE_OPEN);
      double curSL   = PositionGetDouble(POSITION_SL);
      double curTP   = PositionGetDouble(POSITION_TP);
      double vol     = PositionGetDouble(POSITION_VOLUME);

      // Infer original 1R from TP distance if SL already moved to BEP, or ATR fallback
      double oneR = (curTP > 0.0 && InpTP_RR > 0.0) ? MathAbs(curTP - openPrc) / InpTP_RR : (atrM15 * InpSL_ATR_Mult);
      if(oneR <= 0.0) continue;

      if(posType == POSITION_TYPE_BUY)
      {
         double profitDist = bid - openPrc;

         // 1. Auto Breakeven at +1.0R
         double beSL = NormalizeDouble(openPrc + 0.05 * atrM15, digits);
         if(profitDist >= oneR * InpBreakevenRR && (curSL < openPrc || curSL == 0.0))
         {
            trade.PositionModify(ticket, beSL, curTP);
            curSL = beSL;
         }

         // 2. Partial Profit 50% at +1.4R
         if(InpPartialRR > 0.0 && profitDist >= oneR * InpPartialRR && !HasPartialDone(ticket))
         {
            double closeVol = MathFloor((vol * 0.5) / lotStep) * lotStep;
            if(closeVol >= minLot && (vol - closeVol) >= minLot)
            {
               if(trade.PositionClosePartial(ticket, NormalizeDouble(closeVol, 2)))
                  MarkPartialDone(ticket);
            }
            else
               MarkPartialDone(ticket);
         }

         // 3. Chandelier ATR Trailing above +1.5R
         if(profitDist >= oneR * 1.50)
         {
            double trailSL = NormalizeDouble(bid - atrM15 * InpTrailATRMult, digits);
            if(trailSL > curSL + _Point * 10)
               trade.PositionModify(ticket, trailSL, curTP);
         }
      }
      else if(posType == POSITION_TYPE_SELL)
      {
         double profitDist = openPrc - ask;

         double beSL = NormalizeDouble(openPrc - 0.05 * atrM15, digits);
         if(profitDist >= oneR * InpBreakevenRR && (curSL > openPrc || curSL == 0.0))
         {
            trade.PositionModify(ticket, beSL, curTP);
            curSL = beSL;
         }

         if(InpPartialRR > 0.0 && profitDist >= oneR * InpPartialRR && !HasPartialDone(ticket))
         {
            double closeVol = MathFloor((vol * 0.5) / lotStep) * lotStep;
            if(closeVol >= minLot && (vol - closeVol) >= minLot)
            {
               if(trade.PositionClosePartial(ticket, NormalizeDouble(closeVol, 2)))
                  MarkPartialDone(ticket);
            }
            else
               MarkPartialDone(ticket);
         }

         if(profitDist >= oneR * 1.50)
         {
            double trailSL = NormalizeDouble(ask + atrM15 * InpTrailATRMult, digits);
            if(curSL == 0.0 || trailSL < curSL - _Point * 10)
               trade.PositionModify(ticket, trailSL, curTP);
         }
      }
   }
}

//--- ON-CHART INSTITUTIONAL HUD PANEL -------------------------------
void RenderHUD()
{
   MqlDateTime utc;
   TimeToStruct(TimeGMT(), utc);
   string sess = GetSessionLabel(utc.hour);
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   double pnlPct = (g_dayStartEquity > 0.0) ? ((eq - g_dayStartEquity) / g_dayStartEquity * 100.0) : 0.0;
   int spreadPts = (int)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   string acctMode = (AccountInfoInteger(ACCOUNT_TRADE_MODE) == ACCOUNT_TRADE_MODE_DEMO) ? "DEMO LOCKED" : "REAL";

   string hud = StringFormat(
      "=== NOVAIRE HEDGE FUND XAUUSD (%s) ===\n"
      "Server Bridge : %s | Next Event: %s (%d m)\n"
      "Macro Regime  : %s (%+d/100) | DXY: %.2f | US10Y: %.2f%%\n"
      "Vol Regime    : %s (Lot x%.2f) | Blackout: %s\n"
      "Session UTC   : %s | Spread: %d pts (Max %d)\n"
      "Confluence M15: BUY=%d/100 | SELL=%d/100 (Min %d)\n"
      "Setup / Gate  : %s | %s\n"
      "Daily Risk    : PnL %+.2f%% (Max -%.1f%%) | Trades: %d/%d | Halt: %s",
      acctMode,
      g_serverConnState, g_nextEventName, g_minutesToEvent,
      g_macroBias, g_macroScore, g_dxyPrice, g_yield10y,
      g_volRegime, g_volLotMult, (g_newsBlackout ? g_blackoutReason : "CLEAR"),
      sess, spreadPts, InpMaxSpreadPoints,
      g_lastBuyScore, g_lastSellScore, InpMinConfluence,
      g_lastSetupTag, g_lastGateNote,
      pnlPct, InpMaxDailyLossPct, g_dailyTradeCount, InpMaxDailyTrades, (g_dailyHalted ? "YES" : "NO")
   );
   Comment(hud);
}

//--- MT5 LIFECYCLE HANDLERS -----------------------------------------
int OnInit()
{
   if(InpDemoOnly && AccountInfoInteger(ACCOUNT_TRADE_MODE) != ACCOUNT_TRADE_MODE_DEMO)
   {
      Alert("[Novaire EA] SAFETY BLOCK: Akun ini BUKAN Akun Demo! Set InpDemoOnly=false hanya setelah uji coba selesai.");
      return(INIT_FAILED);
   }

   string symUp = _Symbol;
   StringToUpper(symUp);
   if(StringFind(symUp, "XAU") < 0 && StringFind(symUp, "GOLD") < 0)
   {
      Alert("[Novaire EA] EA ini dikalibrasi khusus untuk XAUUSD / GOLD. Simbol aktif: ", _Symbol);
      return(INIT_FAILED);
   }

   trade.SetExpertMagicNumber(InpMagicNumber);
   trade.SetDeviationInPoints(30);

   g_hEma20_M15 = iMA(_Symbol, PERIOD_M15, 20, 0, MODE_EMA, PRICE_CLOSE);
   g_hEma50_M15 = iMA(_Symbol, PERIOD_M15, 50, 0, MODE_EMA, PRICE_CLOSE);
   g_hAtr14_M15 = iATR(_Symbol, PERIOD_M15, 14);
   g_hRsi14_M15 = iRSI(_Symbol, PERIOD_M15, 14, PRICE_CLOSE);

   g_hEma20_H1  = iMA(_Symbol, PERIOD_H1, 20, 0, MODE_EMA, PRICE_CLOSE);
   g_hEma50_H1  = iMA(_Symbol, PERIOD_H1, 50, 0, MODE_EMA, PRICE_CLOSE);
   g_hEma200_H1 = iMA(_Symbol, PERIOD_H1, 200, 0, MODE_EMA, PRICE_CLOSE);
   g_hAdx14_H1  = iADX(_Symbol, PERIOD_H1, 14);

   g_hEma20_H4  = iMA(_Symbol, PERIOD_H4, 20, 0, MODE_EMA, PRICE_CLOSE);
   g_hEma50_H4  = iMA(_Symbol, PERIOD_H4, 50, 0, MODE_EMA, PRICE_CLOSE);

   if(g_hEma20_M15 == INVALID_HANDLE || g_hAtr14_M15 == INVALID_HANDLE ||
      g_hEma200_H1 == INVALID_HANDLE || g_hAdx14_H1 == INVALID_HANDLE ||
      g_hEma50_H4 == INVALID_HANDLE)
   {
      Print("[Novaire EA] Gagal inisialisasi indikator multi-timeframe.");
      return(INIT_FAILED);
   }

   UpdateDailyRiskState();
   SyncServerMacroSignal(true);
   EventSetTimer(15);
   RenderHUD();

   Print("[Novaire EA] Initialized cleanly on ", _Symbol, " | Demo Lock: ", (InpDemoOnly ? "ON" : "OFF"));
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   IndicatorRelease(g_hEma20_M15);
   IndicatorRelease(g_hEma50_M15);
   IndicatorRelease(g_hAtr14_M15);
   IndicatorRelease(g_hRsi14_M15);
   IndicatorRelease(g_hEma20_H1);
   IndicatorRelease(g_hEma50_H1);
   IndicatorRelease(g_hEma200_H1);
   IndicatorRelease(g_hAdx14_H1);
   IndicatorRelease(g_hEma20_H4);
   IndicatorRelease(g_hEma50_H4);
   Comment("");
}

void OnTimer()
{
   SyncServerMacroSignal(false);
   SendHeartbeatTelemetry();
   RenderHUD();
}

void OnTick()
{
   UpdateDailyRiskState();
   ManageOpenPositions();

   // Run entry evaluation strictly once per newly closed M15 candle
   datetime curBar = iTime(_Symbol, PERIOD_M15, 0);
   if(curBar == 0 || curBar == g_lastBarTime)
      return;
   g_lastBarTime = curBar;

   SyncServerMacroSignal(false);

   int dir = 0, score = 0;
   double atrM15 = 0.0;
   string setupTag = "NONE";
   EvaluateHedgeFundSetup(dir, score, setupTag, atrM15);
   g_lastSetupTag = setupTag;

   // Gate Checks
   if(g_dailyHalted || g_dailyTradeCount >= InpMaxDailyTrades)
   {
      g_lastGateNote = "BLOCK: DAILY_RISK_LIMIT";
      RenderHUD();
      return;
   }
   if(CountOpenEAOrdersAndPositions() > 0)
   {
      g_lastGateNote = "HOLD: ACTIVE_POSITION";
      RenderHUD();
      return;
   }
   if(InpUseNewsBlackout && g_newsBlackout)
   {
      g_lastGateNote = "SHIELD: " + g_blackoutReason;
      RenderHUD();
      return;
   }
   if(IsRolloverDeadzone())
   {
      g_lastGateNote = "BLOCK: ROLLOVER_SPREAD_HOURS";
      RenderHUD();
      return;
   }
   if(IsInLossCooldown())
   {
      g_lastGateNote = "COOLDOWN: POST_LOSS_WAIT";
      RenderHUD();
      return;
   }

   int spreadPts = (int)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if(spreadPts > InpMaxSpreadPoints)
   {
      g_lastGateNote = "BLOCK: HIGH_SPREAD_" + IntegerToString(spreadPts);
      RenderHUD();
      return;
   }

   MqlDateTime utc;
   TimeToStruct(TimeGMT(), utc);
   int minReq = (utc.hour < 7) ? InpAsianMinConf : InpMinConfluence;

   if(dir == 0 || score < minReq)
   {
      g_lastGateNote = "WAIT: SCORE<" + IntegerToString(minReq);
      RenderHUD();
      return;
   }

   // Strict Macro Alignment Gate
   bool macroFresh = (g_lastServerSync > 0 && (TimeCurrent() - g_lastServerSync) <= 600);
   if(InpStrictMacroFilter && macroFresh)
   {
      if(dir == 1 && g_macroBias == "BEARISH" && g_macroScore <= -40)
      {
         g_lastGateNote = "MACRO_BLOCK: BEARISH_REGIME";
         RenderHUD();
         return;
      }
      if(dir == -1 && g_macroBias == "BULLISH" && g_macroScore >= 40)
      {
         g_lastGateNote = "MACRO_BLOCK: BULLISH_REGIME";
         RenderHUD();
         return;
      }
   }

   // Execution
   double slDist = MathMax(atrM15 * InpSL_ATR_Mult, SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE) * 200);
   double tpDist = slDist * InpTP_RR;
   double setupScale = (score >= 82) ? 1.15 : 1.0;
   double lots = CalculateDynamicLots(slDist, setupScale);
   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);

   string ordComment = StringFormat("NV_%s_%d", setupTag, score);
   bool sent = false;

   if(dir == 1)
   {
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double sl = NormalizeDouble(ask - slDist, digits);
      double tp = NormalizeDouble(ask + tpDist, digits);
      sent = trade.Buy(lots, _Symbol, ask, sl, tp, ordComment);
   }
   else if(dir == -1)
   {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double sl = NormalizeDouble(bid + slDist, digits);
      double tp = NormalizeDouble(bid - tpDist, digits);
      sent = trade.Sell(lots, _Symbol, bid, sl, tp, ordComment);
   }

   if(sent)
   {
      g_dailyTradeCount++;
      g_lastGateNote = (dir == 1 ? "EXEC_BUY " : "EXEC_SELL ") + DoubleToString(lots, 2) + "L";
      Print("[Novaire EA] ", g_lastGateNote, " | Tag=", setupTag, " | Score=", score, " | Macro=", g_macroBias, "(", g_macroScore, ")");
   }
   else
   {
      g_lastGateNote = "ORDER_ERR_" + IntegerToString(GetLastError());
      Print("[Novaire EA] Order failed: ", trade.ResultRetcodeDescription());
   }

   RenderHUD();
}
//+------------------------------------------------------------------+

