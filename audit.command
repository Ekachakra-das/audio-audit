#!/bin/bash

# Configuration
BRIDGE_PORT=3000
UI_PORT=6022
BRIDGE_URL="http://localhost:$BRIDGE_PORT"
UI_URL="http://localhost:$UI_PORT"
ACCENT=$'\033[38;5;216m'
MUTED=$'\033[38;5;110m'
BOLD=$'\033[1m'
RESET=$'\033[0m'

osascript <<'EOF' >/dev/null 2>&1
tell application "Terminal"
    if (count of windows) > 0 then
        set w to front window
        set {leftEdge, topEdge, rightEdge, bottomEdge} to bounds of w
        set bounds of w to {leftEdge, topEdge, rightEdge + 50, bottomEdge}
    end if
end tell
EOF

echo "=========================================="
printf "%s%s\n" "$ACCENT" "██████╗ ██████╗  █████╗ ██████╗ ██╗  ██╗██╗   ██╗██████╗  █████╗ ██████╗  █████╗ "
printf "%s%s\n" "$ACCENT" "██╔══██╗██╔══██╗██╔══██╗██╔══██╗██║  ██║██║   ██║██╔══██╗██╔══██╗██╔══██╗██╔══██╗"
printf "%s%s\n" "$ACCENT" "██████╔╝██████╔╝███████║██████╔╝███████║██║   ██║██████╔╝███████║██║  ██║███████║"
printf "%s%s\n" "$ACCENT" "██╔═══╝ ██╔══██╗██╔══██║██╔══██╗██╔══██║██║   ██║██╔═══╝ ██╔══██║██║  ██║██╔══██║"
printf "%s%s\n" "$ACCENT" "██║     ██║  ██║██║  ██║██████╔╝██║  ██║╚██████╔╝██║     ██║  ██║██████╔╝██║  ██║"
printf "%s%s\n" "$ACCENT" "╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚═╝     ╚═╝  ╚═╝╚═════╝ ╚═╝  ╚═╝"
printf "%s%s\n" "$ACCENT" " "
printf "%s%s\n" "$ACCENT" " █████╗ ██╗   ██╗██████╗ ██╗████████╗"
printf "%s%s\n" "$ACCENT" "██╔══██╗██║   ██║██╔══██╗██║╚══██╔══╝"
printf "%s%s\n" "$ACCENT" "███████║██║   ██║██║  ██║██║   ██║   "
printf "%s%s\n" "$ACCENT" "██╔══██║██║   ██║██║  ██║██║   ██║   "
printf "%s%s\n" "$ACCENT" "██║  ██║╚██████╔╝██████╔╝██║   ██║   "
printf "%s%s\n" "$ACCENT" "╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚═╝   ╚═╝   "
printf "%s%s\n" "$RESET" ""
printf "%s%sStarting%s\n" "$MUTED" "$BOLD" "$RESET"
printf "%sBridge%s  %s\n" "$MUTED" "$RESET" "$BRIDGE_URL"
printf "%sUI%s      %s\n" "$MUTED" "$RESET" "$UI_URL"
echo "=========================================="

# 1. Start Bridge (Node.js Backend)
cd "$( dirname "${BASH_SOURCE[0]}" )/lecture_analysis"
if [ ! -d "node_modules" ]; then
    echo "📦 Installing Bridge dependencies..."
    npm install
fi
node bridge.js > bridge.log 2>&1 &
BRIDGE_PID=$!
echo "✅ Bridge started (PID: $BRIDGE_PID)"

# 2. Start UI (Vite Frontend)
cd ui
if [ ! -d "node_modules" ]; then
    echo "📦 Installing UI dependencies..."
    npm install
fi

# 3. Proactively open or switch to the UI tab in Chrome
osascript <<EOF
tell application "Google Chrome"
    set found to false
    set targetUrl to "$UI_URL"
    
    repeat with w in windows
        set tabIndex to 0
        repeat with t in tabs of w
            set tabIndex to tabIndex + 1
            if URL of t starts with targetUrl then
                set active tab index of w to tabIndex
                set index of w to 1
                activate
                tell t to reload
                set found to true
                exit repeat
            end if
        end repeat
        if found then exit repeat
    end repeat
    
    if not found then
        open location targetUrl
        activate
    end if
end tell
EOF

# Start UI and keep it in foreground
npm run dev -- --port $UI_PORT

# Cleanup on exit
trap "kill $BRIDGE_PID" EXIT
