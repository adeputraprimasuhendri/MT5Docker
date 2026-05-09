#!/bin/bash
export WINEPREFIX=/root/.wine
export WINEARCH=win64
export WINEDEBUG=-all
export DISPLAY=:1

# Init wine prefix
wineboot --init 2>/dev/null
wineserver -w

# Patch system.reg langsung — hapus AeDebug agar installer tidak detect debugger
sed -i '/\[Software\\\\Microsoft\\\\Windows NT\\\\CurrentVersion\\\\AeDebug\]/,/^[[:space:]]*$/d' "$WINEPREFIX/system.reg"

echo "[init_wine] done"
