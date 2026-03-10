const express = require('express');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');
const { PYTHON_PATH, PYTHON_PATH_VF2, TEMP_DIR, PORT } = require('../config');
const { resolveSafePath } = require('../utils/paths');
const { getCache, saveCache, getFileHash, getAudioMetadata } = require('../utils/audio');
const {
    hasActiveCleanProcess,
    setCurrentCleanProcess,
    clearCurrentCleanProcess,
} = require('./system');

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

function writeCombinedNoteTag(filePath, badQuality, note) {
    return new Promise((resolve, reject) => {
        const logFile = path.join(__dirname, '..', 'bridge_debug.log');
        if (!filePath || !fs.existsSync(filePath)) {
            fs.appendFileSync(logFile, `[Tags] File not found: ${filePath}\n`);
            return resolve(false);
        }

        const isBadQuality = !!badQuality;
        const combinedNote = buildCombinedNoteTag(isBadQuality, note);
        const ext = path.extname(filePath);
        const base = ext ? filePath.slice(0, -ext.length) : filePath;
        const outExt = ext || '.mp3';
        const tempPath = `${base}.meta_tmp${outExt}`.normalize('NFC');

        if (fs.existsSync(tempPath)) {
            try { fs.unlinkSync(tempPath); } catch (e) { }
        }

        // Extremely aggressive metadata clearing for ID3v2.3 compatibility
        const ffArgs = [
            '-y',
            '-i', filePath,
            '-map', '0',
            '-codec:a', 'copy',
            '-map_metadata', '0',
            '-id3v2_version', '3',
            '-write_id3v1', '1',
            '-metadata', 'id3v2_priv.XMP=',
            '-metadata', 'XMP=',
            '-metadata', 'comment=',
            '-metadata', 'description=',
            '-metadata', 'NOTE=',
            '-metadata', 'BAD_QUALITY=',
            tempPath
        ];

        if (combinedNote) {
            ffArgs.splice(-1, 0,
                '-metadata', `NOTE=${combinedNote}`
            );
        }

        fs.appendFileSync(logFile, `[Tags] Writing to ${path.basename(filePath)}: "${combinedNote}" (BadQuality: ${isBadQuality})\n`);

        const proc = spawn('ffmpeg', ffArgs);
        let stderr = '';
        proc.stderr.on('data', (d) => { stderr += d.toString(); });
        proc.on('error', (err) => {
            fs.appendFileSync(logFile, `[Tags] Spawn error: ${err.message}\n`);
            reject(err);
        });

        proc.on('close', (code) => {
            if (code !== 0) {
                if (fs.existsSync(tempPath)) {
                    try { fs.unlinkSync(tempPath); } catch (_e) { }
                }
                const errMsg = stderr.trim() || `Tag write failed (code ${code})`;
                fs.appendFileSync(logFile, `[Tags] FFmpeg error: ${errMsg}\n`);
                return reject(new Error(errMsg));
            }
            try {
                if (fs.existsSync(tempPath)) {
                    fs.renameSync(tempPath, filePath);
                    fs.appendFileSync(logFile, `[Tags] Success: ${path.basename(filePath)}\n`);
                    resolve(true);
                } else {
                    reject(new Error("Output temp file missing"));
                }
            } catch (e) {
                fs.appendFileSync(logFile, `[Tags] Rename error: ${e.message}\n`);
                reject(e);
            }
        });
    });
}

router.post('/convert-audio', async (req, res) => {
    const { inputPath: rawInput, outputPath: rawOutput, bitrate, badQuality = false, note = '' } = req.body;
    
    // Add logging to debug.log
    fs.appendFileSync(path.join(__dirname, '..', 'bridge_debug.log'), `[CONVERT] ${new Date().toISOString()} Input: ${rawInput}, Bitrate: ${bitrate}\n`);

    if (!rawInput || !rawOutput || !bitrate) {
        return res.status(400).json({ status: "error", error: "Missing parameters (inputPath, outputPath, bitrate)" });
    }

    const absoluteInput = resolveSafePath(rawInput).normalize('NFC');
    console.log(`[DEBUG] convert-audio input: ${absoluteInput}, bitrate: ${bitrate}`);
    if (!fs.existsSync(absoluteInput)) return res.status(404).json({ status: "error", error: "Input file not found" });

    let absoluteOutput = rawOutput.normalize('NFC');
    if (!path.isAbsolute(rawOutput)) {
        absoluteOutput = path.join(path.dirname(absoluteInput), rawOutput).normalize('NFC');
    }

    // Ensure output directory exists
    const outputDir = path.dirname(absoluteOutput);
    if (!fs.existsSync(outputDir)) {
        fs.mkdirSync(outputDir, { recursive: true });
    }

    console.log(`Converting audio: ${absoluteInput} -> ${absoluteOutput} (${bitrate}k)`);
    fs.appendFileSync(path.join(__dirname, '..', 'bridge_debug.log'), `[CONVERT] ${new Date().toISOString()} Saving to: ${absoluteOutput}\n`);

    // 1. Get duration first for progress calculation
    let duration = 0;
    try {
        const ffprobe = spawn('ffprobe', [
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            absoluteInput
        ]);
        let ffprobeOutput = '';
        for await (const chunk of ffprobe.stdout) {
            ffprobeOutput += chunk;
        }
        duration = parseFloat(ffprobeOutput.trim());
        if (isNaN(duration) || duration <= 0) {
            duration = 1; // Prevent division by zero
        }
    } catch (e) {
        console.error("Failed to get duration:", e);
        duration = 1; // Fallback
    }

    // 2. Start conversion with progress
    res.setHeader('Content-Type', 'application/x-ndjson');
    res.write(JSON.stringify({ status: "progress", progress: 0, message: "Starting conversion..." }) + '\n');

    // We'll use ffmpeg directly
    const ffmpegArgs = [
        '-y',
        '-i', absoluteInput,
        '-vn', // Strip video/cover art
        '-map', '0:a', // Only audio stream
        '-map_metadata', '0', // Preserve existing tags from source
        '-codec:a', 'libmp3lame',
        '-id3v2_version', '3', // Ensure modern ID3 for compatibility
        '-write_id3v1', '1',    // Also write v1 for older players
    ];

    const bitrateStr = String(bitrate);
    if (bitrateStr === 'original') {
        ffmpegArgs.push('-b:a', '320k'); // Fallback for "original" label if params missing
    } else if (bitrateStr.startsWith('v')) {
        ffmpegArgs.push('-qscale:a', bitrateStr.substring(1));
    } else {
        ffmpegArgs.push('-b:a', `${bitrateStr}k`);
    }

    // Use a temporary output file to avoid overwriting input if input == output
    const tempOutput = (absoluteOutput + ".tmp").normalize('NFC');
    ffmpegArgs.push('-progress', 'pipe:1', '-f', 'mp3', tempOutput);

    const fullCmd = `ffmpeg ${ffmpegArgs.map(a => a.includes(' ') ? `"${a}"` : a).join(' ')}`;
    console.log(`[FFmpeg Spawn] ${fullCmd}`);
    fs.appendFileSync(path.join(__dirname, '..', 'bridge_debug.log'), `[FFmpeg] ${new Date().toISOString()} CPU_CMD: ${fullCmd}\n`);
    
    const ffmpeg = spawn('ffmpeg', ffmpegArgs);

    // Stop process if client closed connection
    req.on('close', () => {
        if (ffmpeg.exitCode === null) {
            console.log(`[Abort] Convert-audio path: ${path.basename(absoluteInput)}`);
            ffmpeg.kill('SIGKILL');
            // Clean up temp file
            if (fs.existsSync(tempOutput)) fs.unlinkSync(tempOutput);
        }
    });

    ffmpeg.stdout.on('data', (data) => {
        const lines = data.toString().split('\n');
        const progress = {};
        lines.forEach(line => {
            const [key, value] = line.split('=');
            if (key && value) progress[key.trim()] = value.trim();
        });

        if (progress.out_time_ms && duration > 0) {
            const currentSec = parseInt(progress.out_time_ms) / 1000000; // out_time_ms is in microseconds
            const percent = Math.min(99, Math.round((currentSec / duration) * 100));
            res.write(JSON.stringify({ status: "progress", progress: percent }) + '\n');
        }
    });

    ffmpeg.stderr.on('data', (data) => {
        // Log stderr to catch errors that don't crash proper but might explain hang
        const msg = data.toString();
        if (msg.toLowerCase().includes('error')) {
            console.error(`[FFmpeg Error] ${msg}`);
        }
    });

    ffmpeg.on('close', async (code) => {
        if (code === 0) {
            // Rename temp file to final output
            try {
                fs.renameSync(tempOutput, absoluteOutput);
                try {
                    await writeCombinedNoteTag(absoluteOutput, !!badQuality, note);
                } catch (tagErr) {
                    console.warn("[convert-audio] tag write warning:", tagErr.message);
                }
                const newSize = fs.statSync(absoluteOutput).size;
                const meta = await getAudioMetadata(absoluteOutput);
                const result = {
                    status: "success",
                    output_path: absoluteOutput,
                    new_size: newSize,
                    bitrate: meta.bitrate || bitrate,
                    metadata: meta
                };
                console.log(`[Success] Saved: ${absoluteOutput}, Size: ${newSize}, Bitrate: ${bitrate}`);
                fs.appendFileSync(path.join(__dirname, '..', 'bridge_debug.log'), `[CONVERT] ${new Date().toISOString()} Success: ${JSON.stringify(result)}\n`);
                res.write(JSON.stringify(result) + '\n');
                res.end();
            } catch (e) {
                console.error("Error renaming temp file:", e);
                res.write(JSON.stringify({ status: "error", error: "Failed to save file: " + e.message }) + '\n');
                res.end();
            }
        } else {
            // Cleanup on failure
            if (fs.existsSync(tempOutput)) fs.unlinkSync(tempOutput);
            res.write(JSON.stringify({ status: "error", error: "ffmpeg exited with code " + code }) + '\n');
            res.end();
        }
    });

    req.on('close', () => {
        ffmpeg.kill();
    });
});

// Alias for backward compatibility
router.post('/clean', (req, res) => {
    // Some parts of frontend might expect a single JSON instead of NDJSON
    // If it's a preview, we might want to collect all and return at once?
    // But since App.svelte handles the stream if it's there... wait.
    // Actually App.svelte for /clean DOES NOT use a reader, it uses res.json().
    // So /clean MUST return a single JSON.

    const { mode = 'preview' } = req.body;

    // Create a mock res object to capture the final 'completed' message
    let finalData = null;
    const mockRes = {
        setHeader: () => { },
        write: (data) => {
            try {
                const json = JSON.parse(data.trim());
                if (json.status === 'completed' || json.status === 'error' || json.status === 'success') {
                    finalData = json;
                }
            } catch (e) { }
        },
        end: () => {
            if (finalData) {
                res.json(finalData);
            } else {
                res.status(500).json({ status: 'error', message: 'No final data received' });
            }
        },
        status: (code) => {
            res.status(code);
            return mockRes;
        },
        json: (data) => {
            res.json(data);
        },
        on: (event, handler) => {
            req.on(event, handler);
        }
    };

    // Forward to clean-audio internal handler (we'll make it an exported function or just call it)
    handleCleanAudio(req, mockRes);
});

async function handleCleanAudio(req, res) {
    let pythonError = "";
    fs.appendFileSync(path.join(__dirname, '..', 'bridge_debug.log'), `[ROUTE] ${new Date().toISOString()} /clean or /clean-audio accessed\n`);
    const {
        inputPath: rawInput,
        outputPath: customOutput,
        mode = 'preview',
        method = 'denoiser',
        offset = 0,
        noiseStart,
        noiseEnd,
        bitrate,
        gain,
        mix,
        echoStrength,
        echo_strength,
        badQuality = false,
        note = ''
    } = req.body;

    if (!rawInput) {
        fs.appendFileSync(path.join(__dirname, '..', 'bridge_debug.log'), `[Clean] ${new Date().toISOString()} Error: Missing inputPath\n`);
        return res.status(400).json({ error: "Missing inputPath" });
    }

    const absoluteInput = resolveSafePath(rawInput).normalize('NFC');
    console.log(`[DEBUG] clean-audio input: ${absoluteInput}, bitrate: ${bitrate}, method: ${method}`);
    fs.appendFileSync(path.join(__dirname, '..', 'bridge_debug.log'), `[Clean] ${new Date().toISOString()} Input: ${absoluteInput}\n`);

    if (!fs.existsSync(absoluteInput)) {
        fs.appendFileSync(path.join(__dirname, '..', 'bridge_debug.log'), `[Clean] ${new Date().toISOString()} Error: File not found at ${absoluteInput}\n`);
        return res.status(404).json({ error: "Input file not found" });
    }

    // Determine output path
    let absoluteOutput;
    let outName;

    if (customOutput) {
        // FULL PROCESSING MODE: Output directly to the target location
        absoluteOutput = customOutput.normalize('NFC');
        // Ensure directory exists
        const outDir = path.dirname(absoluteOutput);
        if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });
        outName = path.basename(absoluteOutput);
    } else {
        // PREVIEW MODE: Use temp directory
        const timestamp = Date.now();
        const filename = path.basename(absoluteInput);
        outName = `${filename}_cleaned_${method}_${timestamp}.mp3`;
        absoluteOutput = path.join(TEMP_DIR, outName).normalize('NFC');
    }

    console.log(`🧼 Cleaning audio [${method}]: ${absoluteInput} (offset: ${offset}, bitrate: ${bitrate}k)`);

    let scriptToUse = path.join(__dirname, '..', 'clean_audio.py');
    let pythonToUse = PYTHON_PATH;

    const methodClean = (method || '').trim();
    if (methodClean && methodClean.includes('resemble')) {
        scriptToUse = path.join(__dirname, '..', 'resemble_worker.py');
        pythonToUse = PYTHON_PATH_VF2;
    } else if (methodClean === 'remove_echo' || methodClean === 'deecho') {
        scriptToUse = path.join(__dirname, '..', 'deecho_worker.py');
    } else if (methodClean === 'lavasr') {
        scriptToUse = path.join(__dirname, '..', 'lavasr_worker.py');
        pythonToUse = PYTHON_PATH_VF2;
    } else if (methodClean === 'voicefixer') {
        scriptToUse = path.join(__dirname, '..', 'voicefixer_worker.py');
        pythonToUse = PYTHON_PATH_VF2;
    }

    console.log(`[Bridge Routing] Method: '${method}' -> Cleaned: '${methodClean}' -> Script: ${path.basename(scriptToUse)}`);

    const args = [
        '-u',
        scriptToUse,
        '--input', absoluteInput,
        '--output', absoluteOutput, // Initial target, will be overridden if using temp
        '--mode', mode,
        '--offset', String(offset)
    ];

    if (req.body.duration) {
        args.push('--duration', String(req.body.duration));
    }

    if (scriptToUse.endsWith('clean_audio.py')) {
        args.push('--method', method);
    }

    // Only pass noise/nr parameters to scripts that consume them.
    if (
        !scriptToUse.includes('resemble_worker.py') &&
        !scriptToUse.includes('voicefixer_worker.py') &&
        !scriptToUse.includes('lavasr_worker.py')
    ) {
        if (noiseStart !== undefined && noiseEnd !== undefined) {
            args.push('--noise_start', String(noiseStart));
            args.push('--noise_end', String(noiseEnd));
        }

        if (req.body.nrAmount !== undefined) args.push('--nr_amount', String(req.body.nrAmount));
        if (req.body.nrSensitivity !== undefined) args.push('--nr_sensitivity', String(req.body.nrSensitivity));
    }

    if (
        req.body.volume !== undefined &&
        !scriptToUse.includes('resemble_worker.py') &&
        !scriptToUse.includes('voicefixer_worker.py') &&
        !scriptToUse.includes('lavasr_worker.py')
    ) {
        args.push('--volume', String(req.body.volume));
    }

    if (bitrate) {
        args.push('--bitrate', String(bitrate));
    }

    if (scriptToUse.includes('resemble_worker.py')) {
        if (gain !== undefined) args.push('--gain', String(gain));
        if (mix !== undefined) args.push('--mix', String(mix));
    } else if (scriptToUse.includes('lavasr_worker.py')) {
        if (req.body.lavasr_denoise !== undefined) args.push('--denoise', req.body.lavasr_denoise ? '1' : '0');
        if (req.body.lavasr_superres !== undefined) args.push('--superres', req.body.lavasr_superres ? '1' : '0');
        if (req.body.lavasr_mix !== undefined) args.push('--mix', String(req.body.lavasr_mix));
        if (req.body.lavasr_gain !== undefined) args.push('--gain', String(req.body.lavasr_gain));
        if (req.body.lavasr_input_sr !== undefined) args.push('--input_sr', String(req.body.lavasr_input_sr));
        if (req.body.lavasr_batch !== undefined) args.push('--batch', req.body.lavasr_batch ? '1' : '0');
    } else if (scriptToUse.includes('voicefixer_worker.py')) {
        if (req.body.vf_mode !== undefined) args.push('--vf_mode', String(req.body.vf_mode));
    } else if (scriptToUse.includes('deecho_worker.py')) {
        const resolvedEchoStrength = echo_strength !== undefined ? echo_strength : echoStrength;
        if (resolvedEchoStrength !== undefined) args.push('--echo_strength', String(resolvedEchoStrength));
    }

    // Use a temporary output file if it's a full processing mode to avoid truncation/corruption
    const isFullProcessing = !!customOutput;
    const isPreviewProcessing = mode === 'preview' && !isFullProcessing;
    const finalOutput = absoluteOutput;
    let workingOutput = finalOutput;
    if (isFullProcessing) {
        const ext = path.extname(finalOutput) || '.mp3';
        const base = ext ? finalOutput.slice(0, -ext.length) : finalOutput;
        workingOutput = `${base}.tmp${ext}`.normalize('NFC');
    }

    // Update args to use workingOutput
    const outputArgIndex = args.indexOf('--output');
    if (outputArgIndex !== -1 && outputArgIndex + 1 < args.length) {
        args[outputArgIndex + 1] = workingOutput;
    }

    // Keep strict lock only for full optimization jobs.
    // Preview generation should remain available while a batch file is being optimized.
    if (!isPreviewProcessing && hasActiveCleanProcess && hasActiveCleanProcess()) {
        return res.status(409).json({
            status: 'error',
            error: 'Another optimization is already running',
        });
    }

    res.setHeader('Content-Type', 'application/x-ndjson');
    res.write(JSON.stringify({ status: "progress", progress: 0, message: "Initializing cleaner..." }) + '\n');

    console.log(`[Python Spawn] ${pythonToUse} ${args.map(a => a.includes(' ') ? `"${a}"` : a).join(' ')}`);

    // Send immediate acknowledgment to keep UI responsive
    res.write(JSON.stringify({ status: 'processing', progress: 0, message: "Starting optimizer..." }) + '\n');

    let pythonProcess;
    try {
        pythonProcess = spawn(pythonToUse, args, {
            env: { ...process.env, PYTHONUNBUFFERED: '1' }
        });
    } catch (spawnErr) {
        console.error("[Clean] Spawn Failed:", spawnErr);
        return res.status(500).json({ error: "Spawn failed: " + spawnErr.message });
    }

    if (!isPreviewProcessing && setCurrentCleanProcess) {
        setCurrentCleanProcess(pythonProcess);
    }

    pythonProcess.on('error', (err) => {
        console.error("[Clean] Failed to spawn python process:", err);
        res.write(JSON.stringify({ status: 'error', error: "Failed to start processing: " + err.message }) + '\n');
        res.end();
    });
    const usesRealTqdmProgress = scriptToUse.includes('resemble_worker.py');

    pythonProcess.stdout.on('data', async (data) => {
        const text = data.toString();
        const lines = text.split(/[\n\r]/);
        for (const line of lines) {
            if (line.trim()) {
                // console.log(`[Clean Line] ${line.trim()}`); // Optional verbose
                if (line.includes('PROGRESS:')) {
                    if (usesRealTqdmProgress) {
                        continue;
                    }
                    const parts = line.split(':');
                    if (parts.length > 1) {
                        const percent = parseInt(parts[1].trim());
                        if (!isNaN(percent)) {
                            res.write(JSON.stringify({ status: 'processing', progress: percent }) + '\n');
                        }
                    }
                } else if (line.includes('DONE')) {
                    console.log('[Clean] Completed successfully signal received');
                }
            }
        }
    });

    pythonProcess.stderr.on('data', (data) => {
        const text = data.toString();
        const lines = text.split(/[\n\r]/);
        lines.forEach(line => {
            const tqdmMatch = line.match(/(\d+)%\s*\|/);
            if (tqdmMatch) {
                const percent = parseInt(tqdmMatch[1]);
                console.log(`[Clean Progress from tqdm] Sending: ${percent}%`);
                res.write(JSON.stringify({ status: 'processing', progress: percent }) + '\n');
            }
        });

        if (text.trim()) {
            console.error(`[Clean Error]: ${text.trim()}`);
            if (text.toLowerCase().includes("error") || text.toLowerCase().includes("exception") || text.toLowerCase().includes("traceback")) {
                pythonError = text.trim();
            }
        }
    });

    pythonProcess.on('close', async (code) => {
        if (clearCurrentCleanProcess) clearCurrentCleanProcess(pythonProcess);
        if (code === 0) {
            if (isFullProcessing) {
                // Post-processing for full mode: Rename and tag
                try {
                    if (fs.existsSync(finalOutput)) fs.unlinkSync(finalOutput);
                    if (fs.existsSync(workingOutput)) {
                        fs.renameSync(workingOutput, finalOutput);
                        console.log(`[Clean] Successfully stored optimized file: ${path.basename(finalOutput)}`);
                        try {
                            await writeCombinedNoteTag(finalOutput, !!badQuality, note);
                        } catch (tagErr) {
                            console.warn("[clean-audio] tag write warning:", tagErr.message);
                        }
                    } else {
                        throw new Error("Worker finished but output file is missing");
                    }

                    let newSize = 0;
                    try { newSize = fs.statSync(finalOutput).size; } catch (e) { }

                    const meta = await getAudioMetadata(finalOutput);
                    const result = {
                        status: 'completed',
                        url: `http://localhost:${PORT}/audio?path=${encodeURIComponent(finalOutput)}`,
                        previewUrl: `/temp/${outName}`,
                        filename: outName,
                        output_path: finalOutput,
                        new_size: newSize,
                        bitrate: meta.bitrate || bitrate,
                        metadata: meta
                    };
                    res.write(JSON.stringify(result) + '\n');
                } catch (e) {
                    console.error("[Clean] Post-processing failed:", e);
                    res.write(JSON.stringify({ status: 'error', message: "File storage failed: " + e.message }) + '\n');
                }
                res.end();
            } else if (mode === 'preview') {
                const filename = path.basename(absoluteInput, path.extname(absoluteInput));
                const timestamp = Date.now();
                const originalStereoFile = path.join(TEMP_DIR, `${filename}_${timestamp}_original_stereo.mp3`);
                const originalMonoFile = path.join(TEMP_DIR, `${filename}_${timestamp}_original_mono.mp3`);

                const runFfmpeg = (args) => new Promise((resolve) => {
                    const proc = spawn('ffmpeg', args);
                    proc.on('close', (c) => resolve(c === 0));
                });

                const stereoArgs = [
                    '-y', '-ss', String(offset), '-i', absoluteInput,
                    '-t', '60', '-vn', '-codec:a', 'libmp3lame', '-b:a', '320k',
                    originalStereoFile
                ];
                const monoArgs = [
                    '-y', '-ss', String(offset), '-i', absoluteInput,
                    '-t', '60', '-vn', '-ac', '1', '-codec:a', 'libmp3lame', '-b:a', '320k',
                    originalMonoFile
                ];

                Promise.all([runFfmpeg(stereoArgs), runFfmpeg(monoArgs)]).then(([stereoOk, monoOk]) => {
                    const result = {
                        status: 'completed',
                        url: `http://localhost:${PORT}/temp/${outName}`,
                        previewUrl: `/temp/${outName}`,
                        filename: outName
                    };
                    if (stereoOk) result.originalStereoUrl = `/temp/${path.basename(originalStereoFile)}`;
                    if (monoOk) result.originalMonoUrl = `/temp/${path.basename(originalMonoFile)}`;

                    res.write(JSON.stringify(result) + '\n');
                    res.end();
                });
            } else {
                res.end();
            }
        } else {
            if (isFullProcessing && fs.existsSync(workingOutput)) {
                try { fs.unlinkSync(workingOutput); } catch (e) { }
            }
            res.write(JSON.stringify({ status: 'error', message: pythonError || `Process exited with code ${code}`, code: code }) + '\n');
            res.end();
        }
    });

    // req.on('close') omitted to avoid premature killing of the process in some environments.
    // Concurrency is handled by setCurrentCleanProcess in system.js
}
router.post('/clean-audio', handleCleanAudio);

router.get('/analyze-spectrum', async (req, res) => {
    const { path: rawPath } = req.query;
    if (!rawPath) return res.status(400).json({ error: "Missing path" });

    const inputPath = resolveSafePath(rawPath).normalize('NFC');
    if (!fs.existsSync(inputPath)) return res.status(404).json({ error: "File not found" });

    // Assuming analyze_audio.py is in root
    const python = spawn(PYTHON_PATH, [path.join(__dirname, '..', 'analyze_audio.py'), inputPath]);

    let output = '';
    python.stdout.on('data', (data) => output += data.toString());
    python.on('close', (code) => {
        try {
            // Handle multiple JSON lines (progress + result)
            const lines = output.trim().split(/\r?\n/);
            let lastJson = null;
            for (let i = lines.length - 1; i >= 0; i--) {
                try {
                    const line = lines[i].trim();
                    if (!line) continue;
                    const json = JSON.parse(line);
                    if ((json.status === "success" || json.status === "error") && json.status !== "progress") {
                        lastJson = json;
                        break;
                    }
                } catch (e) { }
            }

            if (lastJson) {
                res.json(lastJson);
            } else {
                // Fallback if no specific status, or maybe first line?
                // Some old versions might just return result.
                // Try parsing whole output if single object?
                try {
                    const whole = JSON.parse(output);
                    res.json(whole);
                } catch (e) {
                    throw new Error("No valid result JSON found");
                }
            }
        } catch (e) {
            res.status(500).json({ error: "Analysis failed", details: output });
        }
    });
});

// Get audio file metadata via ffprobe
router.get('/audio-info', (req, res) => {
    const { path: rawPath } = req.query;
    if (!rawPath) return res.status(400).json({ error: "No path provided" });

    // Try to resolve path (relative to CWD or absolute)
    let absolutePath = resolveSafePath(rawPath).normalize('NFC');

    // Fallback: if it's a temp file, look in TEMP_DIR
    if (!fs.existsSync(absolutePath) && rawPath.startsWith('temp/')) {
        absolutePath = path.join(TEMP_DIR, path.basename(rawPath)).normalize('NFC');
    }

    if (!fs.existsSync(absolutePath)) {
        return res.status(404).json({ error: "File not found: " + absolutePath });
    }

    const ffprobe = spawn('ffprobe', [
        '-v', 'quiet',
        '-print_format', 'json',
        '-show_streams',
        '-show_format',
        '-select_streams', 'a:0',
        absolutePath
    ]);

    let output = '';
    ffprobe.stdout.on('data', (d) => output += d.toString());
    ffprobe.on('close', (code) => {
        if (code !== 0) return res.status(500).json({ error: "ffprobe failed" });
        try {
            const info = JSON.parse(output);
            const stream = info.streams?.[0] || {};
            const format = info.format || {};

            const sampleRate = parseInt(stream.sample_rate || 0);
            const channels = parseInt(stream.channels || 0);
            let bitrate = stream.bit_rate ? parseInt(stream.bit_rate) : (format.bit_rate ? parseInt(format.bit_rate) : null);
            bitrate = bitrate ? Math.round(bitrate / 1000) : null;

            const sizeBytes = parseInt(format.size || 0);

            res.json({
                sampleRate,
                sampleRateLabel: sampleRate >= 1000 ? `${(sampleRate / 1000).toFixed(1)}kHz` : `${sampleRate}Hz`,
                bitrate,
                bitrateLabel: bitrate ? `${bitrate}kbps` : 'VBR',
                channels,
                channelsLabel: channels === 1 ? 'Mono' : channels === 2 ? 'Stereo' : `${channels}ch`,
                size: sizeBytes,
                sizeLabel: sizeBytes ? `${(sizeBytes / (1024 * 1024)).toFixed(1)}MB` : ''
            });
        } catch (e) {
            res.status(500).json({ error: "Failed to parse info" });
        }
    });
});

router.post('/open-audacity', (req, res) => {
    const file = resolveSafePath(req.body.file).normalize('NFC');
    if (!file) return res.status(400).json({ error: "No file provided" });
    if (!fs.existsSync(file)) return res.status(404).json({ error: "File not found" });

    const child = spawn('open', ['-a', 'Audacity', file]);
    child.on('close', (code) => {
        if (code === 0) res.json({ status: "success" });
        else res.status(500).json({ error: "Failed to open in Audacity. Is it installed?" });
    });
});

router.post('/open-rx', (req, res) => {
    const file = resolveSafePath(req.body.file).normalize('NFC');
    if (!file) return res.status(400).json({ error: "No file provided" });
    if (!fs.existsSync(file)) return res.status(404).json({ error: "File not found" });

    const child = spawn('open', ['-a', 'iZotope RX 11 Audio Editor', file]);
    child.on('close', (code) => {
        if (code === 0) res.json({ status: "success" });
        else res.status(500).json({ error: "Failed to open in RX 11. Is it installed?" });
    });
});

router.post('/zoomed-spectrogram', (req, res) => {
    const { filePath: rawPath, offset, duration } = req.body;
    const logMsg = `📡 [SPECTROGRAM REQUEST] ${new Date().toISOString()} - Path: ${rawPath}, Offset: ${offset}, Duration: ${duration}`;
    fs.appendFileSync(path.join(__dirname, '..', 'server.log'), logMsg + '\n');
    console.log(logMsg);
    if (!rawPath) {
        console.error("❌ [SERVER] No path provided in spectrogram request");
        return res.status(400).json({ error: "No path provided" });
    }

    const absolutePath = resolveSafePath(rawPath).normalize('NFC');
    if (!fs.existsSync(absolutePath)) return res.status(404).json({ error: "File not found" });

    res.setHeader('Content-Type', 'application/x-ndjson');
    res.setHeader('Transfer-Encoding', 'chunked');
    res.setHeader('Cache-Control', 'no-cache, no-transform');
    res.setHeader('X-Content-Type-Options', 'nosniff');

    // Disable TCP buffering
    if (res.socket) res.socket.setNoDelay(true);

    // Heartbeat to push through any buffers
    res.write(JSON.stringify({ status: "progress", progress: 0, message: "Server connection established" }) + '\n');
    if (res.flush) res.flush();

    const args = [
        '-u', // Unbuffered binary stdout and stderr
        path.join(__dirname, '..', 'analyze_audio.py'),
        absolutePath,
        '--offset', String(offset || 0),
        '--duration', String(duration || 30),
        '--zoom'
    ];

    console.log(`🔍 [SERVER DEBUG] Generating zoomed spectrogram: ${absolutePath} (offset: ${offset}, duration: ${duration})`);
    const python = spawn(PYTHON_PATH, args);

    python.on('error', (err) => {
        console.error(`❌ [SERVER DEBUG] Failed to start python: ${err.message}`);
        res.write(JSON.stringify({ status: "error", error: "Failed to start analysis process", details: err.message }) + '\n');
        res.end();
    });

    python.stdout.on('data', (data) => {
        console.log(`📤 [SERVER DEBUG] Python stdout data (${data.length} bytes)`);
        res.write(data);
        if (res.flush) res.flush();
    });

    python.stderr.on('data', (data) => {
        const msg = data.toString();
        console.error(`⚠️ [SERVER DEBUG] Python stderr: ${msg.trim()}`);
        if (msg.includes('"status": "error"')) {
            res.write(msg);
        } else if (msg.toLowerCase().includes('error') || msg.toLowerCase().includes('traceback')) {
            // Send wrapped error if not already JSON
            try {
                if (!msg.trim().startsWith('{')) {
                    res.write(JSON.stringify({ status: "error", error: "Python Error", details: msg.trim() }) + '\n');
                } else {
                    res.write(msg);
                }
            } catch (e) {
                res.write(JSON.stringify({ status: "error", error: "Python Process Error" }) + '\n');
            }
        }
    });

    python.on('close', (code) => {
        console.log(`🛑 [SERVER DEBUG] Python process closed with code ${code}`);
        if (code !== 0) {
            console.error(`❌ [SERVER DEBUG] Spectrogram process exited with code ${code}`);
        }
        res.end();
    });

    res.on('close', () => {
        if (python.exitCode === null) {
            console.log("♻️ [SERVER DEBUG] Killing python process due to request closure");
            python.kill('SIGTERM');
        }
    });
});

router.post('/compare-samples', async (req, res) => {
    const { filePath, startTime, duration = 10, bitrates = [64, 96, 128] } = req.body;
    console.log(`📡 Comparison Request: ${filePath} at ${startTime}s for ${duration}s`);

    if (!filePath || startTime === undefined) {
        return res.status(400).json({ error: "Missing parameters" });
    }

    const absolutePath = resolveSafePath(filePath).normalize('NFC');
    if (!fs.existsSync(absolutePath)) {
        return res.status(404).json({ error: "File not found" });
    }

    // --- CLEANUP PREVIOUS SAMPLES ---
    try {
        const files = fs.readdirSync(TEMP_DIR);
        files.forEach(f => {
            if (f.includes('_compare_')) {
                try { fs.unlinkSync(path.join(TEMP_DIR, f)); } catch (e) { }
            }
        });
    } catch (e) {
        console.error("Temp cleanup failed:", e);
    }

    const timestamp = Date.now();
    const filename = path.basename(absolutePath);

    // Helper to run ffmpeg
    const runFfmpeg = (args) => new Promise((resolve, reject) => {
        const proc = spawn('ffmpeg', args);
        proc.on('close', (code) => {
            if (code === 0) resolve();
            else reject(new Error(`ffmpeg failed with code ${code}`));
        });
    });

    try {
        const tasks = [];

        // 1. Add high-quality original as reference (FIRST)
        const originalName = `${filename}_compare_${timestamp}_original.mp3`;
        const originalPath = path.join(TEMP_DIR, originalName);
        tasks.push((async () => {
            await runFfmpeg([
                '-y',
                '-ss', String(startTime),
                '-i', absolutePath,
                '-t', String(duration),
                '-vn',
                '-codec:a', 'libmp3lame',
                '-b:a', '320k',
                originalPath
            ]);
            return {
                bitrate: 'original',
                label: 'Original',
                url: `http://localhost:${PORT}/temp/${originalName}`
            };
        })());

        // 2. Generate Samples for each bitrate
        bitrates.forEach((br) => {
            const outName = `${filename}_compare_${timestamp}_${br}k.mp3`;
            const outPath = path.join(TEMP_DIR, outName);

            tasks.push((async () => {
                await runFfmpeg([
                    '-y',
                    '-ss', String(startTime),
                    '-i', absolutePath,
                    '-t', String(duration),
                    '-vn',
                    '-codec:a', 'libmp3lame',
                    '-b:a', `${br}k`,
                    outPath
                ]);
                return {
                    bitrate: parseInt(br),
                    label: `${br} kbps`,
                    url: `http://localhost:${PORT}/temp/${outName}`
                };
            })());
        });

        const generated = await Promise.all(tasks);

        // Sort to ensure Original is on top, then bitrates descending
        generated.sort((a, b) => {
            if (a.bitrate === 'original') return -1;
            if (b.bitrate === 'original') return 1;
            return b.bitrate - a.bitrate;
        });

        res.json({ status: "success", samples: generated });

    } catch (e) {
        console.error("Comparison generation failed:", e);
        res.status(500).json({ status: "error", error: e.message });
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

    // ffprobe to get total duration
    let totalDuration = 0;
    try {
        const ffprobe = spawn('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', absOptimized]);
        let ffprobeOutput = '';
        for await (const chunk of ffprobe.stdout) ffprobeOutput += chunk;
        totalDuration = parseFloat(ffprobeOutput.trim());
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
        try {
            const metadata = await getAudioMetadata(absOptimized);
            const bitrate = metadata.bitrate || 128;
            ffmpegArgs.push('-b:a', `${bitrate}k`);
        } catch (e) {
            console.warn("Failed to get metadata for bitrate detection:", e);
            ffmpegArgs.push('-b:a', '128k');
        }
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
                    status: "completed", 
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

router.get('/clean/log', (req, res) => {
    const logPath = path.join(__dirname, '..', 'bridge_debug.log');
    if (fs.existsSync(logPath)) {
        try {
            const stats = fs.statSync(logPath);
            const size = stats.size;
            const start = Math.max(0, size - 50000);
            const stream = fs.createReadStream(logPath, { start });
            stream.pipe(res);
        } catch (e) {
            res.send("");
        }
    } else {
        res.send("");
    }
});

router.post('/stop-clean', (req, res) => {
    res.redirect(307, '/kill-clean');
});

router.post('/analyze-audio', (req, res) => {
    const { path: rawPath, full } = req.body;
    if (!rawPath) return res.status(400).json({ error: "No path provided" });

    const absolutePath = resolveSafePath(rawPath).normalize('NFC');
    if (!fs.existsSync(absolutePath)) return res.status(404).json({ error: "File not found" });

    // Check Cache
    const folderPath = path.dirname(absolutePath);
    const fileHash = getFileHash(absolutePath);
    const cacheType = full ? 'full' : 'preview';
    const cacheKey = `${fileHash}_${cacheType}`;
    const cache = getCache(folderPath);

    if (cache[cacheKey] && !req.body.force) {
        const cachedData = cache[cacheKey];
        res.setHeader('Content-Type', 'application/x-ndjson');
        res.write(JSON.stringify({ status: "success", ...cachedData, is_full_scan: !!full }) + '\n');
        res.end();
        return;
    }

    const ANALYZE_SCRIPT = path.join(__dirname, '..', 'analyze_audio.py');
    const args = ['-u', ANALYZE_SCRIPT, absolutePath];
    if (full) args.push('--full');

    const pythonProcess = spawn(PYTHON_PATH, args, {
        env: { ...process.env, PYTHONUNBUFFERED: '1' }
    });

    let isFinished = false;
    let errorOutput = '';

    res.on('close', () => {
        if (!isFinished && pythonProcess.exitCode === null) {
            pythonProcess.kill('SIGKILL');
        }
    });

    res.setHeader('Content-Type', 'application/x-ndjson');

    pythonProcess.stdout.on('data', (data) => {
        const chunk = data.toString();
        res.write(chunk);

        // Try to find success result in the chunk to cache it
        const lines = chunk.split('\n');
        lines.forEach(line => {
            if (line.includes('"status": "success"')) {
                try {
                    const firstBrace = line.indexOf('{');
                    const jsonStr = line.substring(firstBrace);
                    const result = JSON.parse(jsonStr);
                    const c = getCache(folderPath);
                    c[cacheKey] = result;
                    saveCache(folderPath, c);
                } catch (e) { }
            }
        });
    });

    pythonProcess.stderr.on('data', (data) => {
        const str = data.toString();
        errorOutput += str;
        const lines = str.split(/[\n\r]/);
        lines.forEach(line => {
            const tqdmMatch = line.match(/(\d+)%\s*\|/);
            if (tqdmMatch) {
                const percent = parseInt(tqdmMatch[1]);
                res.write(JSON.stringify({ status: 'progress', progress: percent }) + '\n');
            }
        });
    });

    pythonProcess.on('close', (code) => {
        isFinished = true;
        if (code !== 0 && !res.writableEnded) {
            res.write(JSON.stringify({ status: "error", error: errorOutput || "Analysis failed" }) + '\n');
        }
        res.end();
    });
});


router.post('/clean/cancel', (req, res) => {
    res.redirect(307, '/kill-clean');
});

router.get('/audio', (req, res) => {
    const filePath = resolveSafePath(req.query.path).normalize('NFC');
    if (!filePath || !fs.existsSync(filePath)) return res.status(404).send('File not found');

    const stat = fs.statSync(filePath);
    const fileSize = stat.size;
    const range = req.headers.range;

    if (range) {
        const parts = range.replace(/bytes=/, "").split("-");
        const start = parseInt(parts[0], 10);
        const end = parts[1] ? parseInt(parts[1], 10) : fileSize - 1;
        const chunksize = (end - start) + 1;
        const file = fs.createReadStream(filePath, { start, end });
        const head = {
            'Content-Range': `bytes ${start}-${end}/${fileSize}`,
            'Accept-Ranges': 'bytes',
            'Content-Length': chunksize,
            'Content-Type': 'audio/mpeg',
        };
        res.writeHead(206, head);
        file.pipe(res);
    } else {
        const head = {
            'Content-Length': fileSize,
            'Content-Type': 'audio/mpeg',
        };
        res.writeHead(200, head);
        fs.createReadStream(filePath).pipe(res);
    }
});

router.get('/audio-info', (req, res) => {
    const filePath = resolveSafePath(req.query.path).normalize('NFC');
    if (!filePath || !fs.existsSync(filePath)) return res.status(404).json({ error: "File not found" });

    const ffprobeProcess = spawn('ffprobe', [
        '-v', 'quiet',
        '-print_format', 'json',
        '-show_streams',
        '-show_format',
        '-select_streams', 'a:0',
        filePath
    ]);

    let output = '';
    ffprobeProcess.stdout.on('data', d => output += d);
    ffprobeProcess.on('close', code => {
        if (code !== 0) return res.status(500).json({ error: "Failed info" });
        try {
            const info = JSON.parse(output);
            const stream = info.streams?.[0] || {};
            const format = info.format || {};
            const sampleRate = parseInt(stream.sample_rate || 0);
            const channels = parseInt(stream.channels || 0);
            let bitrate = stream.bit_rate ? parseInt(stream.bit_rate) : (format.bit_rate ? parseInt(format.bit_rate) : null);
            bitrate = bitrate ? Math.round(bitrate / 1000) : null;
            const sizeBytes = parseInt(format.size || 0);

            res.json({
                sampleRate,
                sampleRateLabel: sampleRate >= 1000 ? `${(sampleRate / 1000).toFixed(1)}kHz` : `${sampleRate}Hz`,
                bitrate,
                bitrateLabel: bitrate ? `${bitrate}kbps` : 'VBR',
                channels,
                channelsLabel: channels === 1 ? 'Mono' : channels === 2 ? 'Stereo' : `${channels}ch`,
                size: sizeBytes,
                sizeLabel: sizeBytes ? `${(sizeBytes / (1024 * 1024)).toFixed(1)}MB` : ''
            });
        } catch (e) {
            res.status(500).json({ error: "Parse failed" });
        }
    });
});

module.exports = router;
