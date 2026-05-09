#!/bin/bash
export DISPLAY=:1
export WINEPREFIX=/root/.wine
export WINEARCH=win64
export WINEDEBUG=-all
export WINEDLLOVERRIDES="winemenubuilder.exe="
export WINEESYNC=1

sleep 3

# Resolve mt5-bridge hostname and inject into /etc/hosts for Wine compatibility
BRIDGE_IP=$(getent hosts mt5-bridge | awk '{print $1}')
if [ -n "$BRIDGE_IP" ]; then
    grep -q "mt5-bridge" /etc/hosts || echo "$BRIDGE_IP mt5-bridge" >> /etc/hosts
    echo "[start] Resolved mt5-bridge -> $BRIDGE_IP"
else
    echo "[start] WARNING: Could not resolve mt5-bridge hostname"
fi

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

# Define MetaEditor path clearly
METAEDITOR_EXE="${MT5_EXE%/*}/metaeditor64.exe"

# Deploy DataPublisher EA into MT5 Experts folder
EXPERTS_DIR="$WINEPREFIX/drive_c/Program Files/MetaTrader 5/MQL5/Experts"
mkdir -p "$EXPERTS_DIR"
cp /root/DataPublisher.mq5 "$EXPERTS_DIR/DataPublisher.mq5"
echo "[start] DataPublisher.mq5 deployed to $EXPERTS_DIR"

# Fallback: if not at standard path, search for it
if [ ! -f "$METAEDITOR_EXE" ]; then
    echo "[start] Searching for metaeditor64.exe..."
    METAEDITOR_EXE=$(find "$WINEPREFIX/drive_c" -name "metaeditor64.exe" | head -n 1)
fi

if [ -n "$METAEDITOR_EXE" ] && [ -f "$METAEDITOR_EXE" ]; then
    echo "[start] Compiling DataPublisher.mq5 using $METAEDITOR_EXE..."
    # Clear old log and compile
    rm -f "$EXPERTS_DIR/compile.log"
    wine "$METAEDITOR_EXE" /compile:"$EXPERTS_DIR/DataPublisher.mq5" /log:"$EXPERTS_DIR/compile.log"
    
    # Wait for log file and print it
    for i in $(seq 1 10); do
        [ -f "$EXPERTS_DIR/compile.log" ] && break
        sleep 1
    done
    if [ -f "$EXPERTS_DIR/compile.log" ]; then
        cat "$EXPERTS_DIR/compile.log"
    else
        echo "[start] Compilation triggered, but no log found."
    fi
    echo "[start] Compilation process finished"
else
    echo "[start] ERROR: metaeditor64.exe NOT FOUND anywhere!"
fi

echo "[start] Waiting for mt5-bridge:8765 to be ready..."
for i in $(seq 1 20); do
    if bash -c "echo > /dev/tcp/mt5-bridge/8765" 2>/dev/null; then
        echo "[start] mt5-bridge:8765 is reachable"
        break
    fi
    echo "[start] Waiting for bridge... ($i/20)"
    sleep 3
done

echo "[start] Launching MT5 with config..."
exec wine "$MT5_EXE" /config:/root/mt5_config.ini
