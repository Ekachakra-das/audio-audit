const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// --- CONFIGURATION ---
const ROOT_DIR = path.resolve(__dirname, '..');
const TARGET_DIR = path.join(ROOT_DIR, 'Prabhupada Vani');
const OUTPUT_DIR = __dirname;
const JSON_OUTPUT = path.join(OUTPUT_DIR, 'analysis_folder2.json');

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

function normalizeCity(name) {
    if (!name) return 'UNKNOWN';
    name = name.trim().toUpperCase();
    if (name.includes('BOMBAY') || name.includes('MUMBAI')) return 'MUMBAI';
    if (name.includes('NEW YORK')) return 'NEW YORK';
    if (name.includes('LOS ANGELES')) return 'LOS ANGELES';
    if (name.includes('LONDON')) return 'LONDON';
    if (name.includes('DELHI')) return 'NEW DELHI';
    if (name.includes('VRINDAVAN')) return 'VRINDAVAN';
    if (name.includes('MAYAPUR')) return 'MAYAPUR';
    if (name.includes('HYDERABAD')) return 'HYDERABAD';
    if (name.includes('FRANCISCO')) return 'SAN FRANCISCO';
    if (name.includes('MONTREAL')) return 'MONTREAL';
    if (name.includes('PARIS')) return 'PARIS';
    if (name.includes('ROME')) return 'ROME';
    if (name.includes('GENEVA')) return 'GENEVA';
    if (name.includes('STOCKHOLM')) return 'STOCKHOLM';
    if (name.includes('MELBOURNE')) return 'MELBOURNE';
    if (name.includes('SYDNEY')) return 'SYDNEY';
    if (name.includes('AUCKLAND')) return 'AUCKLAND';
    if (name.includes('FIJI')) return 'FIJI';
    if (name.includes('HONOLULU')) return 'HONOLULU';
    if (name.includes('TOKYO')) return 'TOKYO';
    if (name.includes('HONG KONG')) return 'HONG KONG';
    if (name.includes('NAIROBI')) return 'NAIROBI';
    if (name.includes('DURBAN')) return 'DURBAN';
    if (name.includes('JOHANNESBURG')) return 'JOHANNESBURG';
    if (name.includes('MAURITIUS')) return 'MAURITIUS';
    if (name.includes('MEXICO')) return 'MEXICO CITY';
    if (name.includes('CARACAS')) return 'CARACAS';
    if (name.includes('JAGANNATHA PURI')) return 'PURI';
    return name;
}

function pad(num) {
    return num.toString().padStart(2, '0');
}

function parseDate(dateStr) {
    if (!dateStr) return '0000-00-00';
    const months = {
        'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04', 'May': '05', 'Jun': '06',
        'Jul': '07', 'Aug': '08', 'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12',
        'January': '01', 'February': '02', 'March': '03', 'April': '04', 'June': '06',
        'July': '07', 'August': '08', 'September': '09', 'October': '10', 'November': '11', 'December': '12'
    };
    const clean = dateStr.replace(/\./g, '');
    const parts = clean.split(/[ ,]+/);
    let month = '00';
    let day = '00';
    let year = '0000';
    if (parts.length >= 3) {
        for (const [mName, mCode] of Object.entries(months)) {
            if (parts[0].startsWith(mName)) { month = mCode; break; }
        }
        day = pad(parts[1]);
        year = parts[2];
    }
    return `${year}-${month}-${day}`;
}

function parseFilename(filename) {
    // Replace all underscores with spaces for parsing purposes - it's the safest way to maintain compatibility
    const cleanName = filename.replace(/_/g, ' ');
    
    let regex = /^(BG|SB|CC|ISO)\s+([\d\.\-\–]+)\s+[\(\[]?(.*?)[\)\]]?,?\s+(.*?)(\.mp3)?$/i;
    let match = cleanName.match(regex);
    if (match) {
        const book = match[1];
        const ref = match[2];
        const dateStr = match[3];
        const cityStr = match[4];
        const refParts = ref.split('.');
        let chapter = '00';
        let verse = '00';
        if (refParts.length === 2) { chapter = refParts[0]; verse = refParts[1]; }
        else if (refParts.length === 3) {
            chapter = refParts[0];
            verse = refParts[1];
            if (refParts.length > 2) { chapter = refParts[0] + '.' + refParts[1]; verse = refParts[2]; }
        }
        return { type: 'SCRIPTURE', book, chapter, verse, cityCode: normalizeCity(cityStr), date: parseDate(dateStr) };
    }
    regex = /^(.*?)\s+[\(\[]?(.*?\d{4}.*?)[\)\]]?,?\s+(.*?)(\.mp3)?$/i;
    match = cleanName.match(regex);
    if (match) return { type: 'LECTURE', title: match[1], cityCode: normalizeCity(match[3]), date: parseDate(match[2]) };
    return {};
}

function generateStandardName(parsed) {
    if (!parsed.date) return null;
    let middle = 'UNKNOWN';
    if (parsed.type === 'SCRIPTURE') {
        middle = `${parsed.book.toUpperCase()}-${pad(parsed.chapter)}-${pad(parsed.verse)}`;
    } else {
        middle = 'LECTURE';
        if (parsed.title) {
            const t = parsed.title.toUpperCase();
            if (t.includes('MORNING WALK')) middle = 'MW';
            if (t.includes('ROOM CONVERSATION')) middle = 'RC';
            if (t.includes('ARRIVAL')) middle = 'ARRIVAL';
            if (t.includes('FESTIVAL')) middle = 'FESTIVAL';
            if (t.includes('INITIATION')) middle = 'INIT';
        }
    }
    const city = normalizeCity(parsed.cityCode);
    return `${parsed.date}__${middle}__${city}`;
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
console.log("Scanning Prabhupada Vani (Deep Scan)...");
const files = scan(TARGET_DIR);

const registryByName = {};
const registryByDeep = {};
const unparsed = [];

for (const f of files) {
    if (f.standardizedName) {
        if (!registryByName[f.standardizedName]) registryByName[f.standardizedName] = [];
        registryByName[f.standardizedName].push(f);
    } else {
        unparsed.push(f);
    }

    // Deep check key: Size and Duration
    const deepKey = `${f.size}_${Math.round(f.duration)}`;
    if (!registryByDeep[deepKey]) registryByDeep[deepKey] = [];
    registryByDeep[deepKey].push(f);
}

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

    if (filesInGroup.length > 1 && unprocessedInGroup.length > 0) {
        // If some files from this group were already added as identical, 
        // we still want to show the context of the name group if it has other duplicates
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

const result = {
    source: "Prabhupada Vani",
    stats: {
        total: files.length,
        standardized: files.length - unparsed.length,
        conflicts: conflicts.length
    },
    registry: registryByName,
    files: conflicts,
    conflicts: conflicts,
    unparsed: unparsed
};

fs.writeFileSync(JSON_OUTPUT, JSON.stringify(result, null, 2));
console.log(`Exported Deep Scan JSON: ${JSON_OUTPUT}`);
console.log(`Total: ${files.length}, Conflicts: ${conflicts.length}`);

