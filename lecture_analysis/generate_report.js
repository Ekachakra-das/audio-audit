const fs = require('fs');
const path = require('path');

const OUTPUT_DIR = __dirname;
const REPORT_FILE = path.join(OUTPUT_DIR, 'index.html');
const UI_TEMPLATE_FILE = path.join(OUTPUT_DIR, 'ui', 'dist', 'index.html');

const DATA_FILE_1 = path.join(OUTPUT_DIR, 'analysis_folder1.json');
const DATA_FILE_2 = path.join(OUTPUT_DIR, 'analysis_folder2.json');
const GLOBAL_DATA = path.join(OUTPUT_DIR, 'global_conflicts.json');

// --- READ DATA ---
console.log("Loading analysis data...");
let data1 = null, data2 = null, globalData = [];

try {
    if (fs.existsSync(DATA_FILE_1)) data1 = JSON.parse(fs.readFileSync(DATA_FILE_1, 'utf8'));
    if (fs.existsSync(DATA_FILE_2)) data2 = JSON.parse(fs.readFileSync(DATA_FILE_2, 'utf8'));
    if (fs.existsSync(GLOBAL_DATA)) globalData = JSON.parse(fs.readFileSync(GLOBAL_DATA, 'utf8'));
} catch (e) { console.error("Error loading JSON data:", e); }

// --- CHECK UI TEMPLATE ---
if (!fs.existsSync(UI_TEMPLATE_FILE)) {
    console.error("❌ UI Build not found!");
    console.error("Please run: cd ui && npm run build");
    process.exit(1);
}

// --- INJECT DATA INTO TEMPLATE ---
const auditData = {
    folder1: data1,
    folder2: data2,
    global: globalData
};

let template = fs.readFileSync(UI_TEMPLATE_FILE, 'utf8');

// Inject the data object before the first script
const dataInjection = `<script>window.auditData = ${JSON.stringify(auditData)};</script>`;
const finalHtml = template.replace('</head>', `${dataInjection}</head>`);

fs.writeFileSync(REPORT_FILE, finalHtml);
console.log(`✅ Svelte Report generated: ${REPORT_FILE}`);

