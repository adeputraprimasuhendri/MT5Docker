//+------------------------------------------------------------------+
//| DataPublisher.mq5 - Publishes tick/bar data via WebSocket       |
//+------------------------------------------------------------------+
#property copyright "MT5 Bridge"
#property version   "1.00"
#property strict

input string   ServerHost = "mt5-bridge";
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

   // Socket creation and connection moved to OnTimer to avoid INIT_FAILED/4014 issues
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
   if (!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED)) {
      static bool warned = false;
      if (!warned) { Print("Waiting for Algo Trading to be enabled..."); warned = true; }
      return;
   }

   if (socket == INVALID_HANDLE || !SocketIsConnected(socket)) {
      if (socket != INVALID_HANDLE) SocketClose(socket);
      socket = SocketCreate();
      if (socket != INVALID_HANDLE) {
         if (SocketConnect(socket, ServerHost, ServerPort, 1000)) {
            Print("Connected to bridge");
         } else {
            Print("Connection failed: ", GetLastError());
            SocketClose(socket);
            socket = INVALID_HANDLE;
         }
      }
      return;
   }

   string payload = "{\"ticks\":[";
   int count = 0;
   for (int i = 0; i < ArraySize(symbols); i++) {
      MqlTick tick;
      if (SymbolInfoTick(symbols[i], tick)) {
         if (count > 0) payload += ",";
         payload += StringFormat(
            "{\"symbol\":\"%s\",\"bid\":%.5f,\"ask\":%.5f,\"time\":%d}",
            symbols[i], tick.bid, tick.ask, (int)tick.time
         );
         count++;
      } else {
         static datetime last_err_time = 0;
         if (TimeCurrent() - last_err_time > 60) {
            Print("Warning: Symbol ", symbols[i], " not found or no data. Make sure it is in Market Watch.");
            last_err_time = TimeCurrent();
         }
      }
   }
   payload += "]";
   
   // Add heartbeat info
   payload += StringFormat(",\"heartbeat\":%d}", (int)TimeCurrent());

   uchar data[];
   int len = StringLen(payload);
   ArrayResize(data, len);
   StringToCharArray(payload, data, 0, len);
   
   int sent = SocketSend(socket, data, len);
   if (sent <= 0) {
      Print("Send failed, closing socket");
      SocketClose(socket);
      socket = INVALID_HANDLE;
   }
}

void OnTick() {}
//+------------------------------------------------------------------+
