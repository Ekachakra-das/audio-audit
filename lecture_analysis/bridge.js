const express = require('express');
const cors = require('cors');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');
const { PORT, ensureDirs, TEMP_DIR } = require('./config');

const app = express();
const logFile = path.join(__dirname, 'server.log');
let isRestarting = false;
const DEMO_MODE = process.env.DEMO_MODE === 'true';

function logToFile(msg) {
    const timestamp = new Date().toISOString();
    try {
        fs.appendFileSync(logFile, `[${timestamp}] ${msg}\n`);
    } catch (err) {
        console.error("Failed to write to log file:", err);
    }
    console.log(msg);
}

// Initialize directories
ensureDirs();

// Global request logger - MUST BE FIRST
app.use((req, res, next) => {
    logToFile(`${req.method} ${req.url}`);
    next();
});

app.use(cors());
app.use(express.json());

if (DEMO_MODE) {
    const blockedRoutes = new Set([
        '/convert-audio',
        '/clean',
        '/clean-audio',
        '/analyze-audio',
        '/analyze-spectrum',
        '/zoomed-spectrogram',
        '/compare-samples',
        '/restore-original',
        '/open-audacity',
        '/open-rx',
        '/pick-folder',
        '/reveal',
        '/delete',
        '/restore',
        '/sync-file-tags',
        '/kill-clean',
        '/stop-clean',
        '/clean/cancel',
        '/restart',
        '/verify'
    ]);

    app.use((req, res, next) => {
        if (blockedRoutes.has(req.path)) {
            return res.status(403).json({
                status: 'error',
                error: 'Demo mode: processing and local actions are disabled'
            });
        }
        next();
    });
}

// Import Routes
const audioRoutes = require('./routes/audio');
const fileRoutes = require('./routes/files');
const systemRoutes = require('./routes/system').router;

// Use Routes
app.use('/', audioRoutes);
app.use('/', fileRoutes);
app.use('/', systemRoutes);

// Static serve for audio files
const { resolveSafePath } = require('./utils/paths');
app.use('/audio', (req, res) => {
    const filePath = req.query.path;
    if (!filePath) return res.status(400).send("Missing path");
    const safePath = resolveSafePath(filePath);
    if (fs.existsSync(safePath)) {
        res.sendFile(safePath);
    } else {
        console.warn(`[WARN] File not found in /audio: ${filePath}`);
        res.status(404).send("File not found");
    }
});

app.use('/temp', express.static(TEMP_DIR));

app.post('/restart', (req, res) => {
    if (isRestarting) {
        return res.status(409).json({ status: 'error', error: 'Restart already in progress' });
    }

    isRestarting = true;
    try {
        const bridgePath = path.join(__dirname, 'bridge.js');
        const escapedNode = process.execPath.replace(/"/g, '\\"');
        const escapedBridge = bridgePath.replace(/"/g, '\\"');
        const escapedLog = logFile.replace(/"/g, '\\"');
        const restartCmd = `while lsof -nP -iTCP:${PORT} -sTCP:LISTEN -t >/dev/null 2>&1; do sleep 0.2; done; nohup "${escapedNode}" "${escapedBridge}" >> "${escapedLog}" 2>&1 &`;

        const child = spawn('sh', ['-c', restartCmd], {
            cwd: __dirname,
            detached: true,
            stdio: 'ignore'
        });
        child.unref();

        res.json({ status: 'restarting', pid: child.pid });

        setTimeout(() => {
            process.exit(0);
        }, 350);
    } catch (e) {
        isRestarting = false;
        console.error('[restart] Failed:', e);
        res.status(500).json({ status: 'error', error: e.message });
    }
});

app.listen(PORT, () => {
    logToFile(`Server running on http://localhost:${PORT}`);
    logToFile(`Server CWD: ${process.cwd()}`);
    logToFile(`Python env: ${require('./config').PYTHON_PATH}`);
});
