#!/bin/bash
# LM Studio Forwarder Proxy Launcher (Linux/Mac)
# This script starts the mitmproxy that forwards game API calls to LM Studio

echo ""
echo "========================================================================"
echo "LM STUDIO FORWARDER PROXY"
echo "========================================================================"
echo ""
echo "This proxy will forward all game API calls to your local LM Studio."
echo ""
echo "REQUIREMENTS:"
echo "  1. LM Studio must be running with a model loaded"
echo "  2. LM Studio server must be started"
echo "  3. Default LM Studio port is 1234"
echo ""
echo "If you need to change the port, edit lmstudio_forwarder.py line 20"
echo ""
echo "========================================================================"
echo ""
echo "Starting forwarder on localhost:8080..."
echo ""

# Check if mitmproxy is installed
if ! command -v mitmdump &> /dev/null; then
    echo "[ERROR] mitmproxy is not installed!"
    echo ""
    echo "Please install mitmproxy first:"
    echo "  pip install mitmproxy"
    echo ""
    echo "Or visit: https://mitmproxy.org/"
    echo ""
    exit 1
fi

# Run mitmproxy with LM Studio forwarder addon
mitmdump -s lmstudio_forwarder.py \
    --listen-port 8080 \
    --ssl-insecure \
    --set confdir=./mitm_config

echo ""
echo "Forwarder stopped."
