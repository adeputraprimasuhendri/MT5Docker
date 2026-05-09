//+------------------------------------------------------------------+
//| DataPublisher.mq5 - Publishes tick/bar data via WebSocket       |
//+------------------------------------------------------------------+
#property copyright "MT5 Bridge"
#property version   "1.00"
#property strict

input string   ServerHost = "127.0.0.1";
input int      ServerPort = 8765;
input string   Symbol1    = "EURUSD";
input string   Symbol2    = "GBPUSD";
input string   Symbol3    = "USDJPY";

#include <Trade\Trade.mqh>

int socket = INVALID_HANDLE;
string symbols[];

int OnInit()
{
   int count = 3;
   ArrayResize(symbols, count);
   symbols[0] = Symbol1;
   symbols[1] = Symbol2;
   symbols[2] = Symbol3;

   socket = SocketCreate();
   if (socket == INVALID_HANDLE) {
      Print("Failed to create socket");
      return INIT_FAILED;
   }

   if (!SocketConnect(socket, ServerHost, ServerPort, 5000)) {
      Print("Cannot connect to bridge: ", ServerHost, ":", ServerPort);
   } else {
      Print("Connected to bridge");
   }

   EventSetMillisecondTimer(500);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   if (socket != INVALID_HANDLE)
      SocketClose(socket);
}

void OnTimer()
{
   if (socket == INVALID_HANDLE || !SocketIsConnected(socket)) {
      socket = SocketCreate();
      SocketConnect(socket, ServerHost, ServerPort, 3000);
      return;
   }

   string payload = "{\"ticks\":[";
   for (int i = 0; i < ArraySize(symbols); i++) {
      MqlTick tick;
      if (SymbolInfoTick(symbols[i], tick)) {
         if (i > 0) payload += ",";
         payload += StringFormat(
            "{\"symbol\":\"%s\",\"bid\":%.5f,\"ask\":%.5f,\"time\":%d}",
            symbols[i], tick.bid, tick.ask, (int)tick.time
         );
      }
   }
   payload += "]}";

   uchar data[];
   StringToCharArray(payload, data, 0, StringLen(payload));
   SocketSend(socket, data, ArraySize(data));
}

void OnTick() {}
//+------------------------------------------------------------------+
