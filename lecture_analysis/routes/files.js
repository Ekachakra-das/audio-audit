const express = require('express');
const path = require('path');
const fs = require('fs');
const util = require('util');
const execPromise = util.promisify(require('child_process').exec);
const { TRASH_DIR, CACHE_DIR, TEMP_DIR } = require('../config');
const { resolveSafePath } = require('../utils/paths');
const { getAudioMetadata, getCache, saveCache } = require('../utils/audio');
const { spawn } = require('child_process');

const router = express.Router();

function sanitizeTagValue(value) {
    if (value === undefined || value === null) return '';
    return String(value).replace(/[\r\n]+/g, ' ').trim();
}

function buildCombinedNoteTag(badQuality, note) {
    const cleanNote = sanitizeTagValue(note);
    const parts = [];
    if (badQuality) parts.push('Bad_quality');
    if (cleanNote) parts.push(cleanNote);
    if (!parts.length) return '';
    return parts.join(', ');
}

function runCommand(cmd, args) {
    return new Promise((resolve, reject) => {
        const proc = spawn(cmd, args);
        let stderr = '';
        proc.stderr.on('data', (d) => { stderr += d.toString(); });
        proc.on('error', reject);
        proc.on('close', (code) => {
            if (code === 0) resolve();
            else reject(new Error(stderr.trim() || `${cmd} exited with code ${code}`));
        });
    });
}

function inferOptimizedSiblingPath(originalPath) {
    const originalDir = path.dirname(originalPath);
    if (originalDir.endsWith('_OPTIMIZED')) return originalPath;

    const parentDir = path.dirname(originalDir);
    const folderName = path.basename(originalDir);
    return path.join(parentDir, `${folderName}_OPTIMIZED`, path.basename(originalPath));
}

async function writeTagsToAudio(filePath, { badQuality, note }) {
    const logFile = path.join(__dirname, '..', 'bridge_debug.log');
    const absolutePath = resolveSafePath(filePath).normalize('NFC');
    
    if (!absolutePath || !fs.existsSync(absolutePath)) {
        fs.appendFileSync(logFile, `[Tags-Files] File not found: ${absolutePath || filePath}\n`);
        return { path: absolutePath || filePath, updated: false, reason: 'not_found' };
    }

    const isBadQuality = !!badQuality;
    const combinedNote = buildCombinedNoteTag(isBadQuality, note);
    const ext = path.extname(absolutePath);
    const base = ext ? absolutePath.slice(0, -ext.length) : absolutePath;
    const outExt = ext || '.mp3';
    const tempPath = `${base}.meta_tmp${outExt}`.normalize('NFC');

    if (fs.existsSync(tempPath)) {
        try { fs.unlinkSync(tempPath); } catch (e) { }
    }

    fs.appendFileSync(logFile, `[Tags-Files] Writing to ${path.basename(absolutePath)}: "${combinedNote}" (BadQuality: ${isBadQuality})\n`);

    const ffmpegArgs = [
        '-y',
        '-i', absolutePath,
        '-map', '0', // Map ALL streams (audio, images, etc) to be safe
        '-codec', 'copy', // Stream copy
        '-map_metadata', '0', // Keep existing metadata
        '-id3v2_version', '3',
        '-write_id3v1', '1',
        // Clear problematic Adobe/XMP clutters globally
        '-metadata', 'id3v2_priv.XMP=',
        '-metadata', 'XMP=',
        // Reset comment fields
        '-metadata', 'comment=',
        '-metadata', 'description=',
        '-metadata', 'NOTE=',
        '-metadata', 'BAD_QUALITY=',
        tempPath
    ];

    if (combinedNote) {
        ffmpegArgs.splice(-1, 0,
            '-metadata', `NOTE=${combinedNote}`
        );
    }

    try {
        const logFileDetailed = path.join(__dirname, '..', 'bridge_debug.log');
        const { stdout, stderr } = await new Promise((resolve, reject) => {
            const proc = spawn('ffmpeg', ffmpegArgs);
            let out = '', err = '';
            proc.stdout.on('data', d => out += d);
            proc.stderr.on('data', d => err += d);
            proc.on('close', code => {
                if (code === 0) resolve({ stdout: out, stderr: err });
                else reject(new Error(err.trim() || `FFmpeg exited with code ${code}`));
            });
        });

        if (fs.existsSync(tempPath)) {
            fs.renameSync(tempPath, absolutePath);
            fs.appendFileSync(logFileDetailed, `[Tags-Files] Success: ${path.basename(absolutePath)}\n`);
            return { path: absolutePath, updated: true };
        } else {
            throw new Error("FFmpeg finished but output temp file is missing");
        }
    } catch (e) {
        if (fs.existsSync(tempPath)) {
            try { fs.unlinkSync(tempPath); } catch (_err) { }
        }
        fs.appendFileSync(logFile, `[Tags-Files] Error processing ${path.basename(absolutePath)}: ${e.message}\n`);
        throw e;
    }
}

router.get('/files', async (req, res) => {
    const { folder } = req.query;
    if (!folder) return res.status(400).json({ error: "No folder path provided" });

    // Normalize folder path: remove trailing slash for consistent dirname/basename
    const normalizedFolder = folder.replace(/\/$/, "");
    const absoluteFolder = resolveSafePath(normalizedFolder).normalize('NFC');

    console.log(`[ROUTE] /files?folder=${folder}`);
    console.log(`[DEBUG] Resolved absolute folder: ${absoluteFolder}`);

    if (!fs.existsSync(absoluteFolder) || !fs.lstatSync(absoluteFolder).isDirectory()) {
        console.warn(`[WARN] Directory not found: ${absoluteFolder}`);
        return res.status(404).json({ error: "Directory not found" });
    }

    try {
        const parentDir = path.dirname(absoluteFolder);
        const folderName = path.basename(absoluteFolder);
        const optimizedFolder = path.join(parentDir, folderName + "_OPTIMIZED");

        console.log(`Scanning: ${absoluteFolder}`);
        console.log(`Checking for optimized files in: ${optimizedFolder}`);

        const hasOptimizedFolder = fs.existsSync(optimizedFolder) && fs.lstatSync(optimizedFolder).isDirectory();
        const optimizedFiles = new Map(); // normalized_name -> { size, path }
        if (hasOptimizedFolder) {
            fs.readdirSync(optimizedFolder).forEach(f => {
                try {
                    const fPath = path.join(optimizedFolder, f);
                    const stat = fs.lstatSync(fPath);
                    if (stat.isFile()) {
                        // Normalize the filename to NFC for consistent matching
                        optimizedFiles.set(f.normalize('NFC'), { size: stat.size, path: fPath });
                    }
                } catch (e) { }
            });
        }

        const rawFiles = fs.readdirSync(absoluteFolder)
            .filter(f => /\.(mp3|wav|flac|ogg|m4a)$/i.test(f));

        // Load cache once for the entire scan (folder-specific)
        const cache = getCache(absoluteFolder);

        // Fetch durations in parallel batches (max 10 at once to avoid system overload)
        const BATCH_SIZE = 10;
        const filesWithInfo = [];

        for (let i = 0; i < rawFiles.length; i += BATCH_SIZE) {
            const batch = rawFiles.slice(i, i + BATCH_SIZE);
            const batchPromises = batch.map(async (f) => {
                const fullPath = path.join(absoluteFolder, f).normalize('NFC');
                // Check cache first for stats
                const stat = fs.statSync(fullPath);
                const cacheKey = `${f}_${stat.size}_${stat.mtimeMs}`;

                let metadata = cache[cacheKey];
                if (
                    !metadata ||
                    typeof metadata.badQuality !== 'boolean' ||
                    typeof metadata.note !== 'string' ||
                    !Object.prototype.hasOwnProperty.call(metadata, 'allTags') ||
                    metadata.allTags === null ||
                    typeof metadata.allTags !== 'object' ||
                    Array.isArray(metadata.allTags)
                ) {
                    metadata = await getAudioMetadata(fullPath);
                    // Update cache object (in memory)
                    cache[cacheKey] = metadata;
                }

                // Check for optimized version
                const optimizedData = optimizedFiles.get(f.normalize('NFC'));
                let optimizedSize = 0;
                let status = 'idle';
                let finalPath = null;
                let optimizedMetadata = null; // New field

                if (optimizedData) {
                    optimizedSize = optimizedData.size;
                    status = 'completed'; // It exists, so it's done
                    finalPath = optimizedData.path;

                    // Fetch optimized metadata
                    try {
                        optimizedMetadata = await getAudioMetadata(finalPath);
                    } catch (e) { }
                }

                // const isSilentStartEnd = await checkAudioSilent(fullPath); // skipping silent check for speed/stub

                return {
                    name: f,
                    originalName: f,
                    path: fullPath,
                    relPath: path.relative(path.join(__dirname, '..'), fullPath).replace(/\\/g, '/'),
                    size: stat.size,
                    duration: metadata?.duration || 0,
                    durationFormatted: metadata?.duration ? (() => {
                        const h = Math.floor(metadata.duration / 3600);
                        const m = Math.floor((metadata.duration % 3600) / 60);
                        const s = Math.floor(metadata.duration % 60);
                        return h > 0 ? `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}` : `${m}:${s.toString().padStart(2, '0')}`;
                    })() : '0:00',
                    bitrate: metadata?.bitrate || 0,
                    currentBitrate: metadata?.bitrate || 0,
                    sampleRate: metadata?.sampleRate || 0,
                    channels: metadata?.channels || 0,
                    status: status,
                    hasCleaned: status === 'completed',
                    cleanedPath: status === 'completed' ? finalPath : null,
                    optimizedSize: optimizedSize,
                    finalPath: finalPath,
                    actualOptimizedBitrate: optimizedMetadata?.bitrate || 0,
                    badQuality: metadata?.badQuality || false,
                    note: metadata?.note || "",
                    title: metadata?.title || "",
                    artist: metadata?.artist || "",
                    album: metadata?.album || "",
                    allTags: metadata?.allTags || {},
                    optimizedMetadata: optimizedMetadata // Return full object for the tag icon
                };
            });

            const results = await Promise.all(batchPromises);
            filesWithInfo.push(...results);
        }

        // Save updated cache
        saveCache(absoluteFolder, cache);

        res.json({ files: filesWithInfo });

    } catch (e) {
        console.error("Scan error:", e);
        res.status(500).json({ error: e.message });
    }
});

router.post('/delete', (req, res) => {
    const { filePath } = req.body;
    if (!filePath) return res.status(400).json({ error: "Missing filePath" });

    const absolutePath = resolveSafePath(filePath).normalize('NFC');
    if (!fs.existsSync(absolutePath)) return res.status(404).json({ error: "File not found" });

    const fileName = path.basename(absolutePath);
    const destination = path.join(TRASH_DIR, fileName);

    try {
        fs.renameSync(absolutePath, destination);
        res.json({ status: "success", newPath: destination });
    } catch (e) {
        console.error("Delete failed:", e);
        res.status(500).json({ error: e.message });
    }
});

router.post('/restore', (req, res) => {
    // Basic restore logic if needed, or user can manually move from _TRASH
    res.status(501).json({ error: "Not implemented yet" });
});

router.post('/show-in-finder', (req, res) => {
    const { path: p } = req.body;
    if (!p) return res.status(400).json({ error: "Missing path" });

    // resolveSafePath might return the folder if file missing
    const safeP = resolveSafePath(p).normalize('NFC');

    const proc = spawn('open', ['-R', safeP]);
    proc.on('close', (code) => {
        if (code === 0) res.json({ status: "success" });
        else res.status(500).json({ error: "Failed to open Finder" });
    });
});

// Alias for frontend compatibility
router.post('/reveal', (req, res) => {
    // Forward to show-in-finder logic
    // We can't internal redirect easily with POST body without re-parsing or shared func.
    // Just copy logic for now or share handler.
    const { file } = req.body; // Frontend sends { file: path }
    if (!file) return res.status(400).json({ error: "Missing file" });
    const safeP = resolveSafePath(file).normalize('NFC');
    spawn('open', ['-R', safeP]);
    res.json({ status: "success" });
});


router.get('/data', (req, res) => {
    try {
        const readFileSafe = (filename, defaultValue) => {
            try {
                const filePath = path.join(__dirname, '..', filename);
                if (!fs.existsSync(filePath)) return defaultValue;
                const content = fs.readFileSync(filePath, 'utf8');
                return content ? JSON.parse(content) : defaultValue;
            } catch (e) {
                console.error(`Failed to read/parse ${filename}:`, e);
                return defaultValue;
            }
        };

        const defaultFolder = { files: [], stats: { standardized: 0, total: 0, conflicts: 0 } };
        const folder1 = readFileSafe('analysis_folder1.json', defaultFolder);
        const folder2 = readFileSafe('analysis_folder2.json', defaultFolder);
        const globalData = readFileSafe('global_conflicts.json', []);

        res.json({
            folder1: folder1,
            folder2: folder2,
            global: globalData
        });
    } catch (e) {
        console.error("Failed to prepare data response:", e);
        res.status(500).json({ error: "Failed to load data" });
    }
});

router.get('/download', (req, res) => {
    const filePath = resolveSafePath(req.query.path);
    if (!filePath) return res.status(400).send("No path provided");

    if (fs.existsSync(filePath)) {
        res.download(filePath);
    } else {
        res.status(404).send('File not found');
    }
});

router.post('/sync-file-tags', async (req, res) => {
    const logFile = path.join(__dirname, '..', 'bridge_debug.log');
    fs.appendFileSync(logFile, `[ROUTE] /sync-file-tags accessed\n`);

    const {
        path: rawPath,
        originalPath: rawOriginalPath,
        optimizedPath: rawOptimizedPath,
        badQuality = false,
        note = ''
    } = req.body || {};

    const sourcePath = rawOriginalPath || rawPath;
    if (!sourcePath) {
        fs.appendFileSync(logFile, `[ROUTE] /sync-file-tags ERROR: Missing originalPath\n`);
        return res.status(400).json({ error: 'Missing originalPath' });
    }

    const absoluteOriginal = resolveSafePath(sourcePath).normalize('NFC');
    if (!fs.existsSync(absoluteOriginal)) {
        fs.appendFileSync(logFile, `[ROUTE] /sync-file-tags ERROR: Original not found: ${absoluteOriginal}\n`);
        return res.status(404).json({ error: 'Original file not found' });
    }

    fs.appendFileSync(logFile, `[ROUTE] /sync-file-tags processing ${path.basename(absoluteOriginal)}\n`);

    const tags = {
        badQuality: !!badQuality,
        note: sanitizeTagValue(note)
    };
    const combinedNote = buildCombinedNoteTag(tags.badQuality, tags.note);

    let absoluteOptimized = null;
    if (rawOptimizedPath) {
        absoluteOptimized = resolveSafePath(rawOptimizedPath).normalize('NFC');
    } else {
        absoluteOptimized = inferOptimizedSiblingPath(absoluteOriginal).normalize('NFC');
    }

    const targets = [absoluteOriginal];
    const skipped = [];

    if (absoluteOptimized && absoluteOptimized !== absoluteOriginal) {
        if (fs.existsSync(absoluteOptimized)) targets.push(absoluteOptimized);
        else skipped.push(absoluteOptimized);
    }

    try {
        const results = [];
        for (const target of new Set(targets)) {
            results.push(await writeTagsToAudio(target, tags));
        }

        const originalMetadata = await getAudioMetadata(absoluteOriginal);
        let optimizedMetadata = null;
        if (absoluteOptimized && fs.existsSync(absoluteOptimized)) {
            optimizedMetadata = await getAudioMetadata(absoluteOptimized);
        }

        res.json({
            status: 'success',
            originalMetadata,
            optimizedMetadata,
            updated: results.filter(r => r.updated).map(r => r.path),
            skipped
        });
    } catch (e) {
        console.error('Failed to sync file tags:', e);
        res.status(500).json({ error: e.message || 'Failed to sync file tags' });
    }
});

router.post('/restore-original', async (req, res) => {
    const { originalPath, optimizedPath, startTime, endTime, bitrateConfig } = req.body;

    if (!originalPath || !optimizedPath || startTime === undefined || endTime === undefined) {
        return res.status(400).json({ error: "Missing parameters" });
    }

    const absOriginal = resolveSafePath(originalPath).normalize('NFC');
    const absOptimized = resolveSafePath(optimizedPath).normalize('NFC');

    if (!fs.existsSync(absOriginal)) return res.status(404).json({ error: "Original file not found" });
    if (!fs.existsSync(absOptimized)) return res.status(404).json({ error: "Optimized file not found" });

    console.log(`Restoring original segment: ${startTime}s - ${endTime}s`);

    res.setHeader('Content-Type', 'application/x-ndjson');

    const tempOutput = path.join(TEMP_DIR, `restore_${Date.now()}.mp3`);

    let totalDuration = 0;
    try {
        const { stdout } = await execPromise(`ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "${absOptimized}"`);
        totalDuration = parseFloat(stdout.trim());
    } catch (e) {
        console.error("Failed to get duration:", e);
        return res.status(500).json({ error: "Failed to probe file duration" });
    }

    const filter = `[0:a]atrim=end=${startTime}[a1];` +
        `[1:a]atrim=start=${startTime}:end=${endTime},asetpts=PTS-STARTPTS[a2];` +
        `[0:a]atrim=start=${endTime},asetpts=PTS-STARTPTS[a3];` +
        `[a1][a2][a3]concat=n=3:v=0:a=1[out]`;

    const ffmpegArgs = [
        '-y',
        '-i', absOptimized,
        '-i', absOriginal,
        '-filter_complex', filter,
        '-map', '[out]',
        '-codec:a', 'libmp3lame'
    ];

    if (bitrateConfig) {
        if (bitrateConfig.mode === 'vbr') {
            ffmpegArgs.push('-q:a', bitrateConfig.value.replace('v', ''));
        } else {
            ffmpegArgs.push('-b:a', `${bitrateConfig.value}k`);
        }
    } else {
        const metadata = await getAudioMetadata(absOptimized);
        const bitrate = metadata.bitrate || 128;
        ffmpegArgs.push('-b:a', `${bitrate}k`);
    }

    ffmpegArgs.push(tempOutput);

    const ffmpeg = spawn('ffmpeg', ffmpegArgs);

    ffmpeg.on('close', async (code) => {
        if (code === 0) {
            try {
                fs.copyFileSync(tempOutput, absOptimized);
                fs.unlinkSync(tempOutput);

                const stats = fs.statSync(absOptimized);
                const metadata = await getAudioMetadata(absOptimized);

                res.write(JSON.stringify({ 
                    status: "done", 
                    new_size: stats.size,
                    bitrate: metadata.bitrate,
                    metadata: metadata
                }) + '\n');
            } catch (e) {
                res.write(JSON.stringify({ status: "error", error: e.message }) + '\n');
            }
        } else {
            res.write(JSON.stringify({ status: "error", error: "FFmpeg restoration failed" }) + '\n');
        }
        res.end();
    });
});

module.exports = router;
