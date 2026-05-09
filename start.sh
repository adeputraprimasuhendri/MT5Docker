#!/bin/bash
export DISPLAY=:1
export WINEPREFIX=/root/.wine
export WINEARCH=win64
export WINEDEBUG=-all
export WINEDLLOVERRIDES="winemenubuilder.exe="
export WINEESYNC=1

sleep 3

MT5_EXE="$WINEPREFIX/drive_c/Program Files/MetaTrader 5/terminal64.exe"

if [ ! -f "$MT5_EXE" ]; then
    INSTALLER=/tmp/mt5setup.exe
    echo "[start] Downloading MT5..."
    wget -q -O "$INSTALLER" "https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe"

    echo "[start] Init wine & patch AeDebug..."
    /init_wine.sh

    echo "[start] Running installer..."
    wine "$INSTALLER" 2>/dev/null

    # tunggu sampai terminal64.exe muncul (max 3 menit)
    for i in $(seq 1 36); do
        [ -f "$MT5_EXE" ] && break
        sleep 5
    done
fi

if [ ! -f "$MT5_EXE" ]; then
    echo "[start] ERROR: MT5 tidak terinstall"
    exit 1
fi

echo "[start] Launching MT5..."
exec wine "$MT5_EXE" 2>/dev/null
