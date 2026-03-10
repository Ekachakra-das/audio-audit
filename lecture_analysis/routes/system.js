const express = require('express');
const path = require('path');
const fs = require('fs');
const { spawn, spawnSync } = require('child_process');
const { PYTHON_PATH, SCRIPT_PATH, DECISIONS_FILE_PATH } = require('../config');
const { resolveSafePath } = require('../utils/paths');

const router = express.Router();
let currentCleanProcess = null;

function hasActiveCleanProcess() {
    return !!(currentCleanProcess && !currentCleanProcess.killed);
}

function setCurrentCleanProcess(proc) {
    currentCleanProcess = proc || null;
}

function clearCurrentCleanProcess(proc) {
    if (!proc || currentCleanProcess === proc) {
        currentCleanProcess = null;
    }
}

// --- ROUTES ---

router.post('/pick-folder', (req, res) => {
    const { initialPath } = req.body || {};
    let script = 'POSIX path of (choose folder with prompt "Select folder with audio files"';
    if (initialPath && fs.existsSync(initialPath)) {
        // Double quotes for AppleScript path escaping
        script += ` default location POSIX file "${initialPath}"`;
    }
    script += ')';

    const proc = spawn('sh', ['-c', `osascript -e '${script}'`]);
    let output = '';
    proc.stdout.on('data', (data) => { output += data.toString(); });
    proc.on('close', (code) => {
        if (code === 0 && output.trim()) {
            res.json({ status: "success", path: output.trim() });
        } else {
            res.status(400).json({ status: "error", error: "User cancelled or operation failed" });
        }
    });
});

router.post('/verify', (req, res) => {
    const { files, duration, offset } = req.body;

    if (!files || !Array.isArray(files) || files.length < 2) {
        return res.status(400).json({ error: "Please provide at least 2 files." });
    }

    // Resolving paths relative to CWD if they are relative or broken
    const absoluteFiles = files.map(f => resolveSafePath(f).normalize('NFC'));

    console.log(`Analyzing (${duration || 2} min, offset ${offset || 0} min):`, absoluteFiles);

    // Set headers for streaming response
    res.setHeader('Content-Type', 'text/plain');
    res.setHeader('Transfer-Encoding', 'chunked');

    const pythonProcess = spawn(PYTHON_PATH, [SCRIPT_PATH]);

    // Send data to Python script via stdin
    pythonProcess.stdin.write(JSON.stringify({
        files: absoluteFiles,
        duration: duration || 2,
        offset: offset || 0
    }));
    pythonProcess.stdin.end();

    pythonProcess.stdout.on('data', (data) => {
        res.write(data);
    });

    pythonProcess.stderr.on('data', (data) => {
        console.error(`Root Verify Error: ${data}`);
    });

    pythonProcess.on('close', (code) => {
        res.end();
    });
});

router.post('/kill-clean', (req, res) => {
    if (hasActiveCleanProcess()) {
        currentCleanProcess.kill('SIGKILL');
        currentCleanProcess = null;
        console.log("Killed active cleaning process.");
        res.json({ status: "killed" });
    } else {
        res.json({ status: "no_process" });
    }
});

router.get('/clean-status', (req, res) => {
    const isActive = hasActiveCleanProcess();
    res.json({
        active: isActive,
        pid: isActive ? currentCleanProcess.pid : null
    });
});

router.get('/decisions', (req, res) => {
    if (fs.existsSync(DECISIONS_FILE_PATH)) {
        res.json(JSON.parse(fs.readFileSync(DECISIONS_FILE_PATH)));
    } else {
        res.json([]);
    }
});

router.post('/decisions', (req, res) => {
    fs.writeFileSync(DECISIONS_FILE_PATH, JSON.stringify(req.body, null, 2));
    res.json({ status: "saved" });
});

// Getter/Setter for cleanup process to be shared if needed, 
// though simpler is to keep it local to module if only used by kill-clean.
// But check if /clean-audio sets it. 
// Ah, /clean-audio sets `currentCleanProcess`. 
// We need to export a way to set it from other modules?
// Or better, move /clean-audio here? No, it belongs in audio.js.
// So we need a shared state or pass it.
// Let's make a simple shared state object for process tracking?
// Or just export a function to set it.

router.get('/cpu-temp', (req, res) => {
    let temp = null;

    // Single source: smctemp -c
    const smcResult = spawnSync('smctemp', ['-c'], {
        encoding: 'utf8',
        timeout: 2500
    });
    const smcOutput = `${smcResult.stdout || ''}\n${smcResult.stderr || ''}`;
    const smcMatch = smcOutput.match(/(-?\d+(?:\.\d+)?)/);
    if (smcMatch) {
        temp = parseFloat(smcMatch[1]);
    }

    const topResult = spawnSync('top', ['-l', '1', '-n', '0'], {
        encoding: 'utf8',
        timeout: 3000
    });
    const topOutput = `${topResult.stdout || ''}\n${topResult.stderr || ''}`;
    const usageMatch = topOutput.match(/CPU usage: ([\d.]+)% user, ([\d.]+)% sys/);

    res.json({
        temp,
        usage: usageMatch ? (parseFloat(usageMatch[1]) + parseFloat(usageMatch[2])) : null
    });
});

module.exports = {
    router,
    hasActiveCleanProcess,
    setCurrentCleanProcess,
    clearCurrentCleanProcess,
};
