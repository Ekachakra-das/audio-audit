const path = require('path');
const fs = require('fs');

const PORT = 3000;

// Path to the Python executable in the virtual environment
const PYTHON_PATH = path.join(__dirname, 'venv', 'bin', 'python');
const PYTHON_PATH_VF2 = path.join(__dirname, 'venv_vf2', 'bin', 'python');
const SCRIPT_PATH = path.join(__dirname, 'verify_transcription.py');
const TEMP_DIR = path.join(__dirname, 'temp');
const CACHE_DIR = path.join(__dirname, 'analysis_data');
const TRASH_DIR = path.resolve(__dirname, '_TRASH');
const DECISIONS_FILE_PATH = path.join(__dirname, 'decisions.json');

// Ensure directories exist
function ensureDirs() {
    [TEMP_DIR, CACHE_DIR, TRASH_DIR].forEach(dir => {
        if (!fs.existsSync(dir)) {
            fs.mkdirSync(dir, { recursive: true });
            console.log(`Created directory: ${dir}`);
        }
    });

    // Auto-cleanup temp dir on startup
    if (fs.existsSync(TEMP_DIR)) {
        console.log("Cleaning temp directory...");
        fs.readdirSync(TEMP_DIR).forEach(f => {
            try { fs.unlinkSync(path.join(TEMP_DIR, f)); } catch (e) { }
        });
    }

    // Ensure decisions.json exists
    if (!fs.existsSync(DECISIONS_FILE_PATH)) {
        fs.writeFileSync(DECISIONS_FILE_PATH, JSON.stringify([]));
    }
}

module.exports = {
    PORT,
    PYTHON_PATH,
    PYTHON_PATH_VF2,
    SCRIPT_PATH,
    TEMP_DIR,
    CACHE_DIR,
    TRASH_DIR,
    DECISIONS_FILE_PATH,
    ensureDirs
};
