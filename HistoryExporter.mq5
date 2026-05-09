//+------------------------------------------------------------------+
//| HistoryExporter.mq5 - Export OHLCV history to bridge           |
//+------------------------------------------------------------------+
#property copyright "MT5 Bridge"
#property version   "1.00"
#property script_show_inputs

input string BridgeURL  = "http://127.0.0.1:8000/history";
input string Symbols    = "BTCUSD,ETHUSD,BNBUSD,XRPUSD,EURUSD,GBPUSD,XAUUSD";
input string Timeframe  = "D1";   // M1,M5,M15,M30,H1,H4,D1,W1
input int    Years      = 5;
input int    BatchSize  = 500;

ENUM_TIMEFRAMES StrToTF(string tf)
{
   if(tf == "M1")  return PERIOD_M1;
   if(tf == "M5")  return PERIOD_M5;
   if(tf == "M15") return PERIOD_M15;
   if(tf == "M30") return PERIOD_M30;
   if(tf == "H1")  return PERIOD_H1;
   if(tf == "H4")  return PERIOD_H4;
   if(tf == "D1")  return PERIOD_D1;
   if(tf == "W1")  return PERIOD_W1;
   if(tf == "MN1") return PERIOD_MN1;
   return PERIOD_D1;
}

bool PostBatch(string symbol, string tf, MqlRates &rates[], int start, int count)
{
   string payload = "{\"symbol\":\"" + symbol + "\",\"timeframe\":\"" + tf + "\",\"bars\":[";
   for(int i = start; i < start + count && i < ArraySize(rates); i++) {
      if(i > start) payload += ",";
      payload += StringFormat(
         "{\"time\":%d,\"open\":%.5f,\"high\":%.5f,\"low\":%.5f,\"close\":%.5f,\"volume\":%d}",
         (int)rates[i].time,
         rates[i].open, rates[i].high, rates[i].low, rates[i].close,
         (int)rates[i].tick_volume
      );
   }
   payload += "]}";

   char post_data[], result[];
   string headers;
   StringToCharArray(payload, post_data, 0, StringLen(payload));

   int res = WebRequest("POST", BridgeURL, "Content-Type: application/json\r\n", 10000, post_data, result, headers);
   return res == 200;
}

void OnStart()
{
   ENUM_TIMEFRAMES period = StrToTF(Timeframe);
   datetime from_time = TimeCurrent() - (datetime)(Years * 365 * 86400);
   datetime to_time   = TimeCurrent();

   string sym_list[];
   int sym_count = StringSplit(Symbols, ',', sym_list);

   for(int s = 0; s < sym_count; s++) {
      string sym = sym_list[s];
      StringTrimRight(sym);
      StringTrimLeft(sym);
      if(sym == "") continue;

      MqlRates rates[];
      int copied = CopyRates(sym, period, from_time, to_time, rates);
      if(copied <= 0) {
         Print("CopyRates failed for ", sym, " error: ", GetLastError());
         continue;
      }

      Print("Exporting ", sym, " ", Timeframe, ": ", copied, " bars");

      int batches = (int)MathCeil((double)copied / BatchSize);
      int ok = 0;
      for(int b = 0; b < batches; b++) {
         int start = b * BatchSize;
         int count = MathMin(BatchSize, copied - start);
         if(PostBatch(sym, Timeframe, rates, start, count))
            ok += count;
         else
            Print("Batch ", b+1, "/", batches, " failed for ", sym);
         Sleep(100);
      }
      Print("Done ", sym, ": ", ok, "/", copied, " bars sent");
   }
   Print("Export complete.");
}
//+------------------------------------------------------------------+
