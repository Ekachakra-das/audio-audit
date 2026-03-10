const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// --- CONFIGURATION ---
const ROOT_DIR = path.resolve(__dirname, '..');
const TARGET_DIR = path.join(ROOT_DIR, '!Prabhupada classes');
const OUTPUT_DIR = __dirname;
const JSON_OUTPUT = path.join(OUTPUT_DIR, 'analysis_folder1.json');

// --- HELPERS ---
function getDuration(filePath) {
    try {
        const stdout = execSync(`ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "${filePath}"`);
        return parseFloat(stdout.toString().trim());
    } catch (e) {
        return 0;
    }
}

function formatDuration(seconds) {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.round(seconds % 60);
    return `${h > 0 ? h + ':' : ''}${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

function normalizeCity(code) {
    const map = {
        'BOM': 'MUMBAI', 'NY': 'NEW YORK', 'LA': 'LOS ANGELES', 'LON': 'LONDON',
        'ND': 'NEW DELHI', 'DEL': 'NEW DELHI', 'CAL': 'KOLKATA', 'VRN': 'VRINDAVAN',
        'MAY': 'MAYAPUR', 'HYD': 'HYDERABAD', 'SF': 'SAN FRANCISCO', 'MON': 'MONTREAL',
        'PAR': 'PARIS', 'ROM': 'ROME', 'GEN': 'GENEVA', 'STO': 'STOCKHOLM',
        'MEL': 'MELBOURNE', 'SYD': 'SYDNEY', 'AUC': 'AUCKLAND', 'FIJ': 'FIJI',
        'HON': 'HONOLULU', 'TOK': 'TOKYO', 'HK': 'HONG KONG', 'NAI': 'NAIROBI',
        'DUR': 'DURBAN', 'JOH': 'JOHANNESBURG', 'MAU': 'MAURITIUS', 'MEX': 'MEXICO CITY'
    };
    return map[code?.toUpperCase()] || code?.toUpperCase() || 'UNKNOWN';
}

function pad(num) {
    return num.toString().padStart(2, '0');
}

function generateStandardName(parsed) {
    if (!parsed.date) return null;
    let middle = 'UNKNOWN';
    if (parsed.type === 'SCRIPTURE') {
        middle = `${parsed.book.toUpperCase()}-${pad(parsed.chapter)}-${pad(parsed.verse)}`;
    } else if (parsed.type === 'WALK') {
        middle = 'MW';
    } else if (parsed.type === 'CONVERSATION') {
        middle = 'RC';
    } else if (parsed.type === 'DICTATION') {
        middle = `KB-DICT-${pad(parsed.chapter)}`;
    } else if (parsed.type === 'STORY') {
        middle = `STORY-${pad(parsed.chapter)}`;
    } else if (parsed.type === 'JAPA') {
        middle = `JAPA-${normalizeCity(parsed.title)}`;
    } else {
        middle = parsed.type || 'LECTURE';
    }
    const city = normalizeCity(parsed.cityCode);
    return `${parsed.date}__${middle}__${city}`;
}

function parseFilename(filename) {
    // Replace underscores with spaces for parsing compatibility
    const cleanName = filename.replace(/_/g, ' ');
    
    let regex = /^(Bg|SB|CC|ISO|ISO|NOD|TLC|Nectar|Isopanisad)\s*(.*?)\s+([A-Z]{2,4})\s+(\d{4}-\d{2}-\d{2})/i;
    let match = cleanName.match(regex);
    if (match) {
        const book = match[1];
        let ref = match[2].replace(/[.\s]/g, '-');
        let chapter = '00';
        let verse = '00';
        const parts = ref.split('-');
        if (parts.length >= 2) { chapter = parts[0]; verse = parts[1]; }
        else if (parts.length === 1) { chapter = parts[0]; }
        return { type: 'SCRIPTURE', book, chapter, verse, cityCode: match[3], date: match[4] };
    }
    regex = /^(MW|Morning Walk)\s+([A-Z]{2,4})?\s*(\d{4}-\d{2}-\d{2})/i;
    match = cleanName.match(regex);
    if (match) return { type: 'WALK', cityCode: match[2] || 'UNKNOWN', date: match[3] };
    regex = /^(RC|Room Conversation)\s+([A-Z]{2,4})?\s*(\d{4}-\d{2}-\d{2})/i;
    match = cleanName.match(regex);
    if (match) return { type: 'CONVERSATION', cityCode: match[2] || 'UNKNOWN', date: match[3] };
    regex = /([A-Z]{2,4})\s+(\d{4}-\d{2}-\d{2})/i;
    match = cleanName.match(regex);
    if (match) return { type: 'LECTURE', cityCode: match[1], date: match[2] };
    regex = /Krsna Book Dict (\d+)/i;
    match = cleanName.match(regex);
    if (match) return { type: 'DICTATION', book: 'KB', chapter: match[1], date: '0000-00-00' };
    regex = /Story (\d+)/i;
    match = cleanName.match(regex);
    if (match) return { type: 'STORY', chapter: match[1], date: '0000-00-00' };
    if (cleanName.includes('джапа') || cleanName.includes('Japa')) {
        return { type: 'JAPA', title: cleanName.replace('.mp3', ''), date: '0000-00-00' };
    }
    return {};
}

// --- SCANNING ---
function scan(dir, list = []) {
    const items = fs.readdirSync(dir, { withFileTypes: true });
    for (const item of items) {
        const fullPath = path.join(dir, item.name);
        if (item.isDirectory()) {
            scan(fullPath, list);
        } else if (item.isFile() && item.name.endsWith('.mp3')) {
            const parsed = parseFilename(item.name);
            const stdName = generateStandardName(parsed);
            const stats = fs.statSync(fullPath);
            const duration = getDuration(fullPath);

            const relPath = path.relative(OUTPUT_DIR, fullPath);
            list.push({
                originalName: item.name,
                path: fullPath,
                relPath: relPath,
                parsed: parsed,
                standardizedName: stdName,
                size: stats.size,
                duration: duration,
                durationFormatted: formatDuration(duration)
            });
            if (list.length % 50 === 0) console.log(`Processed ${list.length} files...`);
        }
    }
    return list;
}

// --- MAIN ---
console.log("Scanning !Prabhupada classes (Deep Scan)...");
const files = scan(TARGET_DIR);

const registryByName = {};
const registryByDeep = {};
const unparsed = [];

for (const f of files) {
    if (f.standardizedName) {
        if (!registryByName[f.standardizedName]) {
            registryByName[f.standardizedName] = [];
        }
        registryByName[f.standardizedName].push(f);
    } else {
        unparsed.push(f);
    }

    // Deep check key: Size and Duration
    const deepKey = `${f.size}_${Math.round(f.duration)}`;
    if (!registryByDeep[deepKey]) registryByDeep[deepKey] = [];
    registryByDeep[deepKey].push(f);
}

// Identify Conflicts
const conflicts = [];
const processedPaths = new Set();

// 1. First, add 100% duplicates by Size and Duration
for (const key in registryByDeep) {
    if (registryByDeep[key].length > 1) {
        conflicts.push({
            isIdentical: true,
            key: `DEEP: ${registryByDeep[key][0].durationFormatted} | ${Math.round(registryByDeep[key][0].size / 1024 / 1024)}MB`,
            files: registryByDeep[key]
        });
        registryByDeep[key].forEach(f => processedPaths.add(f.path));
    }
}

// 2. Then, add remaining conflicts by Standardized Name
for (const key in registryByName) {
    const filesInGroup = registryByName[key];
    const unprocessedInGroup = filesInGroup.filter(f => !processedPaths.has(f.path));

    if (filesInGroup.length > 1) {
        // If some files from this group were already added as identical, 
        // we still want to show the context of the name group if it has other duplicates
        // OR if the group itself has duplicates but they weren't identical
        conflicts.push({
            isIdentical: false,
            key: key,
            files: filesInGroup
        });
    }
}

// Sort: IDENTICAL ONES FIRST
conflicts.sort((a, b) => {
    if (a.isIdentical && !b.isIdentical) return -1;
    if (!a.isIdentical && b.isIdentical) return 1;
    return 0;
});

// Load Verification Results
let verificationData = {};
try {
    const VERIFY_FILE = path.join(OUTPUT_DIR, 'verification_report.json');
    if (fs.existsSync(VERIFY_FILE)) {
        const raw = fs.readFileSync(VERIFY_FILE, 'utf8');
        const report = JSON.parse(raw);
        for (const item of report) {
            verificationData[item.key] = item.comparisons;
        }
    }
} catch (e) { }

const result = {
    source: "!Prabhupada classes",
    stats: {
        total: files.length,
        standardized: files.length - unparsed.length,
        conflicts: conflicts.length
    },
    registry: registryByName, // FULL REGISTRY for cross-checking
    files: conflicts.map(d => ({
        key: d.key,
        files: d.files,
        isIdentical: d.isIdentical,
        verification: verificationData[d.key] || null
    })),
    conflicts: conflicts.map(d => ({
        key: d.key,
        files: d.files,
        isIdentical: d.isIdentical,
        verification: verificationData[d.key] || null
    })),
    unparsed: unparsed
};

fs.writeFileSync(JSON_OUTPUT, JSON.stringify(result, null, 2));
console.log(`Exported Deep Scan JSON: ${JSON_OUTPUT}`);
console.log(`Total: ${files.length}, Conflicts: ${conflicts.length}`);

