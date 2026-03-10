#!/bin/bash

# Port for the Lab
PORT=8500
URL="http://localhost:$PORT"

echo "=========================================="
echo "🔬 Starting Audio Laboratory"
echo "🌐 Port: $PORT"
echo "=========================================="

# 1. Switch to workspace directory
cd "$( dirname "${BASH_SOURCE[0]}" )/lecture_analysis"

# 2. Check and activate venv
if [ -f "venv_vf2/bin/activate" ]; then
    source venv_vf2/bin/activate
else
    echo "❌ Error: venv_vf2 not found. Please fix environment first."
    exit 1
fi

# 3. Proactively open or switch to the laboratory tab in Chrome
osascript <<EOF
tell application "Google Chrome"
    set found to false
    set targetUrl to "$URL"
    
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

# 4. Start Streamlit via the python module to be extra safe
export LAB_EXPERIMENTAL_RESEMBLE_MODES=1
python -m streamlit run unified_lab.py --server.port $PORT --server.address localhost --server.maxMessageSize 1000 --server.headless true
