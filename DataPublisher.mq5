//+------------------------------------------------------------------+
//| DataPublisher.mq5 - Publishes tick data via HTTP POST           |
//+------------------------------------------------------------------+
#property copyright "MT5 Bridge"
#property version   "2.00"
#property strict

input string BridgeURL  = "http://127.0.0.1:8000/push";
input string Symbol1    = "EURUSD";
input string Symbol2    = "XAUUSD";
input string Symbol3    = "BTCUSD";

string symbols[];

int OnInit()
{
   int count = 3;
   ArrayResize(symbols, count);
   symbols[0] = Symbol1;
   symbols[1] = Symbol2;
   symbols[2] = Symbol3;

   EventSetMillisecondTimer(500);
   Print("DataPublisher started, posting to: ", BridgeURL);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   EventKillTimer();
}

void OnTimer()
{
   string payload = "{\"ticks\":[";
   bool first = true;
   for (int i = 0; i < ArraySize(symbols); i++) {
      MqlTick tick;
      if (SymbolInfoTick(symbols[i], tick)) {
         if (!first) payload += ",";
         payload += StringFormat(
            "{\"symbol\":\"%s\",\"bid\":%.2f,\"ask\":%.2f,\"time\":%d}",
            symbols[i], tick.bid, tick.ask, (int)tick.time
         );
         first = false;
      }
   }
   payload += "]}";

   char post_data[];
   char result[];
   string response_headers;
   StringToCharArray(payload, post_data, 0, StringLen(payload));

   int res = WebRequest(
      "POST",
      BridgeURL,
      "Content-Type: application/json\r\n",
      3000,
      post_data,
      result,
      response_headers
   );

   if (res == -1)
      Print("WebRequest failed, error: ", GetLastError(), " - Add ", BridgeURL, " to MT5 Options > Expert Advisors");
}

void OnTick() {}
//+------------------------------------------------------------------+
