<script>
    import { onMount, onDestroy, tick } from "svelte";
    import Chart from "chart.js/auto";
    import {
        FolderOpen,
        Activity,
        Settings2,
        Zap,
        AlertCircle,
        Loader2,
        HelpCircle,
        X,
        Thermometer,
        Coffee,
        ChevronLeft,
        ChevronRight,
        ChevronsLeft,
        ChevronsRight,
    } from "lucide-svelte";
    import {
        setGlobalTrack,
        subscribeToGlobalTrack,
        dispatchAudioCommand,
        subscribeToAudioCommands,
        subscribeToPlaybackState,
        setPlaylist,
    } from "./audioStore.js";
    import { globalUiState } from "./globalState.svelte.js";
    import FocusModeOverlay from "./components/audio-optimizer/FocusModeOverlay.svelte";
    import CompareModal from "./components/audio-optimizer/CompareModal.svelte";
    import BatchSettingsModal from "./components/audio-optimizer/BatchSettingsModal.svelte";
    import HelpModal from "./components/audio-optimizer/HelpModal.svelte";
    import FileRow from "./components/audio-optimizer/FileRow.svelte";
    import EmptyState from "./components/audio-optimizer/EmptyState.svelte";
    import BatchProgressBar from "./components/audio-optimizer/BatchProgressBar.svelte";
    import StatsHeader from "./components/audio-optimizer/StatsHeader.svelte";
    import Pagination from "./components/audio-optimizer/Pagination.svelte";
    import SpectrogramModal from "./components/audio-optimizer/SpectrogramModal.svelte";
    import { formatDurationHmsShort } from "./utils/formatters.js";

    const OPTIMIZER_SCROLL_KEY = "optimizer-scroll-pos";
    const OPTIMIZER_SELECT_COUNT_KEY = "optimizer-select-count-last";
    const BATCH_SESSION_KEY = "optimizer-batch-session-v1";
    const optimizerRuntime =
        globalThis.__optimizerRuntime ??
        (globalThis.__optimizerRuntime = {
            cleanStatusPromise: null,
            refreshFilesPromise: null,
            queueWatchdogTimeout: null,
            activeInstanceId: null,
        });
    const optimizerInstanceId = Symbol("audio-optimizer-instance");
    optimizerRuntime.activeInstanceId = optimizerInstanceId;
    let silentAudio;
    const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === "true";
    const BRIDGE_BASE_URL = (
        import.meta.env.VITE_BRIDGE_BASE_URL || "http://localhost:3000"
    ).replace(/\/+$/, "");
    const DEMO_BLOCKED_MESSAGE =
        "Public demo mode: processing and local bridge actions are disabled.";
    const DEMO_FOLDER_PATH = "/demo/Prabhupada-Vani-Lectures";
    const DEMO_FILE_TEMPLATES = [
        "BG_12_13_Bombay_1974_05_12.mp3",
        "SB_1_2_6_Calcutta_1975_03_21.mp3",
        "Conversation_Tehran_1976_08_08.mp3",
        "Morning_Walk_Mayapur_1977_02_19.mp3",
        "Lecture_London_1973_07_15.mp3",
        "Interview_Paris_1972_07_20.mp3",
        "Address_New_York_1976_07_18.mp3",
        "Evening_Darsana_Bombay_1976_08_14.mp3",
        "Room_Conversation_LA_1975_06_23.mp3",
        "SB_6_1_6_Honolulu_1975_06_08.mp3",
        "BG_1_44_London_1973_07_31.mp3",
        "Lecture_Melbourne_1975_05_19.mp3",
    ];

    function withBridgeUrl(path) {
        if (!path) return BRIDGE_BASE_URL;
        if (path.startsWith("http://") || path.startsWith("https://")) {
            return path;
        }
        const normalizedPath = path.startsWith("/") ? path : `/${path}`;
        return `${BRIDGE_BASE_URL}${normalizedPath}`;
    }

    function isDemoBlocked(actionLabel = "This action", toastType = "info") {
        if (!DEMO_MODE) return false;
        showTransientToast(
            `${actionLabel} is unavailable in demo mode.`,
            toastType,
            2200,
        );
        return true;
    }

    async function bridgeFetch(path, options, { silentInDemo = false } = {}) {
        if (DEMO_MODE) {
            if (!silentInDemo) {
                showTransientToast(DEMO_BLOCKED_MESSAGE, "info", 2200);
            }
            const err = new Error("Demo mode: bridge is disabled");
            err.code = "DEMO_MODE_BLOCKED";
            throw err;
        }
        return fetch(withBridgeUrl(path), options);
    }

    function createDemoFiles() {
        return DEMO_FILE_TEMPLATES.map((name, index) => {
            const duration = 420 + index * 37;
            const size = (18 + index * 2.2) * 1024 * 1024;
            const optimizedSize = index % 4 === 0 ? 0 : size * (0.52 + (index % 3) * 0.08);
            const currentBitrate = 320;
            const recommended = [96, 128, 160, 192][index % 4];
            const hasIssue = index % 5 === 0;
            const path = `${DEMO_FOLDER_PATH}/${name}`;

            return {
                name,
                originalName: name,
                path,
                relPath: path,
                size: Math.round(size),
                duration,
                durationFormatted: `${Math.floor(duration / 60)}:${String(duration % 60).padStart(2, "0")}`,
                bitrate: currentBitrate,
                currentBitrate,
                sampleRate: 44100,
                channels: 2,
                recommended_bitrate: recommended,
                status: optimizedSize > 0 ? "completed" : "analyzed",
                hasCleaned: optimizedSize > 0,
                cleanedPath: optimizedSize > 0 ? `${DEMO_FOLDER_PATH}_OPTIMIZED/${name}` : null,
                optimizedSize: Math.round(optimizedSize),
                finalPath: optimizedSize > 0 ? `${DEMO_FOLDER_PATH}_OPTIMIZED/${name}` : null,
                actualOptimizedBitrate: optimizedSize > 0 ? recommended : 0,
                badQuality: hasIssue,
                note: hasIssue ? "Needs careful cleanup before archive export." : "",
                title: name.replace(/_/g, " ").replace(".mp3", ""),
                artist: "A.C. Bhaktivedanta Swami Prabhupada",
                album: "Prabhupada Audio Archive",
                allTags: {
                    TITLE: name.replace(/_/g, " ").replace(".mp3", ""),
                    ARTIST: "A.C. Bhaktivedanta Swami Prabhupada",
                    ALBUM: "Prabhupada Audio Archive",
                },
                optimizedMetadata: optimizedSize > 0 ? { bitrate: recommended, allTags: { NOTE: "Demo optimized sample" } } : null,
            };
        });
    }

    async function loadDemoFiles({ withDelay = false } = {}) {
        if (!DEMO_MODE || !isLiveOptimizerInstance()) return;
        if (withDelay) {
            isScanning = true;
            await wait(450);
        }
        const demoFiles = createDemoFiles();
        files = mergeBatchStateIntoFiles(demoFiles);
        folderPath = DEMO_FOLDER_PATH;
        badQualityPaths = new Set(demoFiles.filter((f) => f.badQuality).map((f) => f.path));
        fileNotes = Object.fromEntries(
            demoFiles.filter((f) => f.note).map((f) => [f.path, f.note]),
        );
        if (withDelay) {
            isScanning = false;
            showTransientToast("Demo dataset refreshed.", "info", 1200);
        }
    }

    function isLiveOptimizerInstance() {
        return optimizerRuntime.activeInstanceId === optimizerInstanceId;
    }

    function isBatchActive() {
        return (
            isProcessingQueue ||
            activeQueueTaskPath !== null ||
            conversionQueue.length > 0 ||
            isInterFilePausing ||
            thermalThrottling ||
            manualQueuePaused
        );
    }
    let isBatchSessionActive = $derived(
        isProcessingQueue ||
            activeQueueTaskPath !== null ||
            conversionQueue.length > 0 ||
            isInterFilePausing ||
            thermalThrottling ||
            manualQueuePaused,
    );
    let queuePendingCount = $derived(
        conversionQueue.filter(
            (task) => task?.filePath && task.filePath !== activeQueueTaskPath,
        ).length,
    );

    $effect(() => {
        if (!silentAudio) return;
        if (isProcessingQueue || isInterFilePausing || thermalThrottling) {
            silentAudio.play().catch(() => {});
            if ("mediaSession" in navigator) {
                navigator.mediaSession.playbackState = "playing";
            }
        } else {
            silentAudio.pause();
            if ("mediaSession" in navigator) {
                navigator.mediaSession.playbackState = "paused";
            }
        }
    });

    // --- State ---
    let folderPath = $state(
        localStorage.getItem("optimizer-folder-path") || "",
    );
    let files = $state([]);
    let isScanning = $state(false);
    let isProcessing = $state(false);
    let isComparing = $state(false);
    let error = $state(null);
    let toast = $state({ show: false, message: "", type: "info" });
    let toastTimeout = null;
    let fileProgressIntervals = $state(new Map()); // Track intervals per file index
    let selectedFileForChart = $state(null);
    let selectedFileForCompare = $state(null);
    let scrollContainer = $state(null);
    let hasInitializedPageScroll = $state(false);
    let hasRestoredOptimizerScroll = $state(false);
    let isRestoringOptimizerScroll = $state(false);
    let compareStartTime = $state(
        parseInt(localStorage.getItem("optimizer-compare-start-time")) || 0,
    );
    let compareDuration = $state(
        parseInt(localStorage.getItem("optimizer-compare-duration")) || 120,
    );
    let compareBitrates = $state(
        JSON.parse(localStorage.getItem("optimizer-compare-bitrates")) || [
            64, 96, 128,
        ],
    );
    let comparisonSamples = $derived([
        // Only add the full "Original" file if there isn't already an "original" bitrate sample from the server (compareSamples)
        ...(selectedFileForCompare &&
        !selectedFileForCompare.compareSamples?.some(
            (s) =>
                s.bitrate === "original" ||
                s.label.toLowerCase() === "original",
        )
            ? [
                  {
                      label: "Original",
                      url: selectedFileForCompare.path,
                      bitrate: "original",
                  },
              ]
            : []),
        ...(selectedFileForCompare?.compareSamples || []),
        ...(selectedFileForCompare?.manualSamples || []),
    ]);

    // Batch Progress Tracking
    let batchStartTime = $state(0);
    let totalProcessedDuration = $state(0);
    let totalProcessTime = $state(0);
    let batchTotalFiles = $state(0);
    let batchProcessedCount = $state(0);
    let batchETA = $state(null);
    let batchProcessingSpeed = $state(0); // seconds of audio processed per second of real time
    const ETA_HISTORY_KEY = "optimizer-eta-history-v1";
    const ETA_HISTORY_LIMIT = 100;
    let etaHistory = $state([]);
    let comparePlaybackTime = $state(0);
    let activeSampleUrl = $state(null);
    let pendingCompareSeek = $state(null);

    // Noise Cleaning State
    let cleanMethod = $state(
        localStorage.getItem("optimizer-clean-method") || "resemble_denoise",
    ); // 'manual', 'resemble_denoise'
    let noiseStart = $state(0);
    let noiseEnd = $state(2);
    let isCleaning = $state(false);
    let cleanProgress = $state(0);
    let cleanProgressTarget = $state(0); // Target progress from backend
    let cleanProgressInterval = $state(null); // Interval for smooth animation
    let volumeGain = $state(
        parseFloat(localStorage.getItem("optimizer-volume-gain")) || 1.0,
    );
    let targetBitrateForClean = $state(
        parseInt(localStorage.getItem("optimizer-target-bitrate")) || 128,
    ); // Default 128kbps for optimized files
    let resembleGain = $state(
        parseFloat(localStorage.getItem("optimizer-resemble-gain")) || 1.0,
    );
    let resembleMix = $state(
        parseFloat(localStorage.getItem("optimizer-resemble-mix")) || 1.0,
    );
    let lavasrDenoise = $state(
        localStorage.getItem("optimizer-lavasr-denoise") !== "false",
    );
    let lavasrSuperres = $state(
        localStorage.getItem("optimizer-lavasr-superres") !== "false",
    );
    let lavasrMix = $state(
        parseFloat(localStorage.getItem("optimizer-lavasr-mix")) || 1.0,
    );
    let lavasrGain = $state(
        parseFloat(localStorage.getItem("optimizer-lavasr-gain")) || 1.0,
    );
    let lavasrInputSr = $state(
        parseInt(localStorage.getItem("optimizer-lavasr-input-sr")) || 16000,
    );
    let lavasrBatch = $state(
        localStorage.getItem("optimizer-lavasr-batch") === "true",
    );
    let echoReduction = $state(
        parseFloat(localStorage.getItem("optimizer-echo-reduction")) || 0.45,
    );
    let cleaningLog = $state("");
    let zoomedSpectrogramUrl = $state(null);
    let isFetchingSpectrogram = $state(false);
    let spectrogramProgress = $state("");
    let isPlayingNoise = $state(false);
    let showSpectrogramModal = $state(false);
    let showCompareModal = $state(false);

    function showTransientToast(message, type = "info", duration = 1800) {
        if (!message) return;
        if (toastTimeout) clearTimeout(toastTimeout);
        toast = { show: true, message, type };
        toastTimeout = setTimeout(() => {
            toast = { ...toast, show: false };
        }, duration);
    }

    async function waitForBridgeReady(timeoutMs = 20000) {
        if (DEMO_MODE) return false;
        const start = Date.now();
        while (Date.now() - start < timeoutMs) {
            try {
                const res = await bridgeFetch("/files", undefined, {
                    silentInDemo: true,
                });
                if (res.ok || res.status === 400) {
                    return true;
                }
            } catch {}
            await new Promise((resolve) => setTimeout(resolve, 700));
        }
        return false;
    }

    async function wait(ms) {
        await new Promise((resolve) => setTimeout(resolve, ms));
    }

    let demoFocusTimer = null;
    let demoFocusCleanupTimer = null;

    function clearDemoFocusSimulation() {
        if (demoFocusTimer) {
            clearInterval(demoFocusTimer);
            demoFocusTimer = null;
        }
        if (demoFocusCleanupTimer) {
            clearTimeout(demoFocusCleanupTimer);
            demoFocusCleanupTimer = null;
        }
    }

    function resetDemoFocusState() {
        if (!DEMO_MODE) return;
        clearDemoFocusSimulation();
        isProcessingQueue = false;
        conversionQueue = [];
        activeQueueTaskPath = null;
        stopAfterCurrentRequested = false;
        manualQueuePaused = false;
        isInterFilePausing = false;
        interFilePauseRemaining = 0;
        thermalThrottling = false;
        thermalThrottlingRemaining = 0;
        batchETA = null;
        batchProcessingSpeed = 0;
        cpuTemp = null;
        cpuUsage = null;
    }

    async function openFocusModeDemo() {
        if (!DEMO_MODE) {
            openBatchSettings("all");
            return;
        }

        clearDemoFocusSimulation();

        if (files.length === 0) {
            await loadDemoFiles();
        }
        if (files.length === 0) return;

        const demoBatchSize = Math.min(5, files.length);
        const demoQueuePaths = files
            .slice(0, demoBatchSize)
            .map((file) => file.path);
        const target = files.find((file) => file.path === demoQueuePaths[0]);
        if (!target) return;

        files = files.map((file, idx) => ({
            ...file,
            status:
                idx === 0
                    ? "converting"
                    : idx < demoBatchSize
                      ? "queued"
                      : file.hasCleaned || file.finalPath
                        ? "completed"
                        : "analyzed",
            progress: idx < demoBatchSize ? 0 : file.progress || 0,
            progressTarget: idx < demoBatchSize ? 0 : file.progressTarget || 0,
        }));

        batchStartTime = Date.now();
        totalProcessedDuration = 0;
        totalProcessTime = 0;
        batchProcessedCount = 0;
        batchTotalFiles = demoBatchSize;
        batchETA = demoBatchSize * 60;
        batchProcessingSpeed = 0;
        cpuTemp = 68;
        cpuUsage = 42;
        activeQueueTaskPath = target.path;
        isProcessingQueue = true;
        conversionQueue = demoQueuePaths.map((filePath) => ({
            filePath,
            sampleOrBitrate: null,
            customInputPath: null,
            allowReprocess: false,
        }));
        showBatchSettingsModal = false;
        isFocusMode = true;
        showTransientToast(
            `Batch optimization demo started (1/${demoBatchSize}).`,
            "info",
            1500,
        );

        const cycleMs = 60_000;
        const cycleStart = Date.now();

        demoFocusTimer = setInterval(() => {
            if (!isFocusMode || !isBatchSessionActive || manualQueuePaused) return;

            const elapsed = Date.now() - cycleStart;
            const ratio = Math.min(0.99, elapsed / cycleMs);
            const progress = Math.floor(ratio * 100);

            files = files.map((file) => {
                if (!demoQueuePaths.includes(file.path)) return file;
                if (file.path !== target.path) {
                    return {
                        ...file,
                        status: "queued",
                        progress: 0,
                        progressTarget: 0,
                    };
                }
                return {
                    ...file,
                    status: "converting",
                    progress,
                    progressTarget: progress,
                };
            });

            const elapsedSec = Math.max(1, Math.floor(elapsed / 1000));
            const durationSec = Number(target.duration) || 600;
            batchETA = Math.max(20, Math.ceil((1 - ratio) * cycleMs / 1000));
            batchProcessingSpeed = Number(
                (Math.min(durationSec, elapsedSec) / elapsedSec).toFixed(2),
            );
            cpuTemp = 66 + Math.round((Math.sin(elapsedSec / 8) + 1) * 3);
            cpuUsage = 38 + Math.round((Math.cos(elapsedSec / 7) + 1) * 12);
        }, 800);
    }

    async function restartBridge() {
        if (isDemoBlocked("Bridge restart")) return;
        if (isRestartingBridge) return;

        isRestartingBridge = true;
        restartBridgeMessage = "Идет перезагрузка моста...";
        showSettingsPopup = false;

        try {
            let restartRequested = false;
            if (navigator.sendBeacon) {
                try {
                    restartRequested = navigator.sendBeacon(
                        withBridgeUrl("/restart"),
                        new Blob([], { type: "text/plain" }),
                    );
                } catch {}
            }

            if (!restartRequested) {
                bridgeFetch("/restart", {
                    method: "POST",
                    keepalive: true,
                    mode: "no-cors",
                }).catch((restartRequestError) => {
                    console.warn(
                        "Restart request ended with a network error; probing bridge anyway.",
                        restartRequestError,
                    );
                });
            }

            restartBridgeMessage = "Ожидаем запуск моста...";
            const ready = await waitForBridgeReady();
            if (!ready) {
                throw new Error("Bridge did not come back in time");
            }

            restartBridgeMessage = "Мост поднялся. Перезагружаем страницу...";
            window.location.reload();
        } catch (e) {
            console.error("Bridge restart failed:", e);
            isRestartingBridge = false;
            restartBridgeMessage = "";
            showTransientToast(`Bridge restart failed: ${e.message}`, "error", 3000);
        }
    }

    onDestroy(() => {
        if (isLiveOptimizerInstance()) {
            optimizerRuntime.activeInstanceId = null;
        }
        clearDemoFocusSimulation();
        if (toastTimeout) clearTimeout(toastTimeout);
    });

    function loadEtaHistory() {
        try {
            const raw = localStorage.getItem(ETA_HISTORY_KEY);
            if (!raw) {
                etaHistory = [];
                return;
            }
            const parsed = JSON.parse(raw);
            if (!Array.isArray(parsed)) {
                etaHistory = [];
                return;
            }
            etaHistory = parsed
                .filter(
                    (row) =>
                        Number.isFinite(row?.duration) &&
                        row.duration > 0 &&
                        Number.isFinite(row?.processTime) &&
                        row.processTime > 0,
                )
                .slice(-ETA_HISTORY_LIMIT);
        } catch (e) {
            console.warn("[ETA] Failed to load ETA history:", e);
            etaHistory = [];
        }
    }

    function saveEtaHistory() {
        try {
            localStorage.setItem(ETA_HISTORY_KEY, JSON.stringify(etaHistory));
        } catch (e) {
            console.warn("[ETA] Failed to save ETA history:", e);
        }
    }

    function recordEtaSample(duration, processTime) {
        if (
            !Number.isFinite(duration) ||
            duration <= 0 ||
            !Number.isFinite(processTime) ||
            processTime <= 0
        ) {
            return;
        }
        etaHistory = [
            ...etaHistory,
            {
                duration,
                processTime,
                ts: Date.now(),
            },
        ].slice(-ETA_HISTORY_LIMIT);
        saveEtaHistory();
    }

    function estimateProcessingTimeByDuration(durationSec) {
        if (!Number.isFinite(durationSec) || durationSec <= 0) return null;

        const samples = etaHistory.filter(
            (row) =>
                Number.isFinite(row.duration) &&
                row.duration > 0 &&
                Number.isFinite(row.processTime) &&
                row.processTime > 0,
        );
        if (samples.length < 3) {
            if (batchProcessingSpeed > 0) {
                return durationSec / batchProcessingSpeed;
            }
            return null;
        }

        // Linear estimate: processTime ~= a + b * duration.
        let sumX = 0;
        let sumY = 0;
        let sumXX = 0;
        let sumXY = 0;
        for (const row of samples) {
            sumX += row.duration;
            sumY += row.processTime;
            sumXX += row.duration * row.duration;
            sumXY += row.duration * row.processTime;
        }

        const n = samples.length;
        const denom = n * sumXX - sumX * sumX;
        const avgRatio = sumY / Math.max(sumX, 1);
        let slope = avgRatio;
        let intercept = 0;

        if (Math.abs(denom) > 1e-9) {
            slope = (n * sumXY - sumX * sumY) / denom;
            intercept = (sumY - slope * sumX) / n;
        }

        if (!Number.isFinite(slope) || slope <= 0) slope = avgRatio;
        if (!Number.isFinite(intercept)) intercept = 0;

        const linearEstimate = intercept + slope * durationSec;
        if (Number.isFinite(linearEstimate) && linearEstimate > 0) {
            return linearEstimate;
        }
        return durationSec * avgRatio;
    }

    function getRemainingAudioDurationSec() {
        let remainingDuration = 0;
        files.forEach((f) => {
            if (f.status !== "queued" && f.status !== "converting") return;

            const fileDuration = Number(f.duration) || 0;
            if (fileDuration <= 0) return;

            if (f.status === "converting") {
                const progress = Number(f.progress) || 0;
                const remainingRatio =
                    progress > 0 && progress < 100 ? 1 - progress / 100 : 1;
                remainingDuration += fileDuration * remainingRatio;
                return;
            }
            remainingDuration += fileDuration;
        });
        return remainingDuration;
    }

    function updateBatchEtaEstimate() {
        const remainingDuration = getRemainingAudioDurationSec();
        if (remainingDuration <= 0) {
            // Duration data may be unavailable (e.g. queue assembled from lab actions).
            // Keep ETA unknown instead of showing a misleading "0m remaining".
            batchETA = null;
            return;
        }

        let remainingFileCount = 0;
        files.forEach((f) => {
            if (f.status === "queued" || f.status === "converting") {
                remainingFileCount += 1;
            }
        });

        let pauseOverheadSec = 0;
        if (interFilePauseEnabled && remainingFileCount > 1) {
            // Number of pauses between remaining files.
            const pausesBetweenFiles = remainingFileCount - 1;
            pauseOverheadSec = pausesBetweenFiles * interFilePauseDuration * 60;

            // If we are currently in a pause, replace one full pause with the live remaining timer.
            if (isInterFilePausing && interFilePauseRemaining > 0) {
                pauseOverheadSec -= interFilePauseDuration * 60;
                pauseOverheadSec += interFilePauseRemaining;
            }
        }

        if (etaHistory.length >= 3) {
            let estimate = 0;
            files.forEach((f) => {
                if (f.status !== "queued" && f.status !== "converting") return;

                const fileDuration = Number(f.duration) || 0;
                if (fileDuration <= 0) return;

                let effectiveDuration = fileDuration;
                if (f.status === "converting") {
                    const progress = Number(f.progress) || 0;
                    if (progress > 0 && progress < 100) {
                        effectiveDuration = fileDuration * (1 - progress / 100);
                    }
                }

                const est = estimateProcessingTimeByDuration(effectiveDuration);
                if (Number.isFinite(est) && est > 0) {
                    estimate += est;
                }
            });

            if (estimate > 0) {
                batchETA = Math.ceil(estimate + pauseOverheadSec);
                return;
            }
        }

        if (batchProcessingSpeed > 0) {
            batchETA = Math.ceil(
                remainingDuration / batchProcessingSpeed + pauseOverheadSec,
            );
        }
    }

    // VoiceFixer State
    let vfMode = $state(
        parseInt(localStorage.getItem("optimizer-vf-mode")) || 0,
    ); // 0=Standard, 1=Enhanced, 2=Deep

    // Pagination State
    let currentPage = $state(
        Math.max(1, parseInt(localStorage.getItem("optimizer-current-page")) || 1),
    );
    let pageSize = $state(
        parseInt(localStorage.getItem("optimizer-page-size")) || 20,
    );
    $effect(() => {
        localStorage.setItem("optimizer-page-size", pageSize.toString());
    });

    let totalPages = $derived(Math.ceil(files.length / pageSize));
    let paginatedFiles = $derived(
        files.slice((currentPage - 1) * pageSize, currentPage * pageSize),
    );

    let isAllOnPageSelected = $derived(
        paginatedFiles.length > 0 &&
            paginatedFiles.every((f) => selectedPaths.has(f.path)),
    );

    // Sync current view with global playlist
    $effect(() => {
        const playlist = paginatedFiles.map((f, i) => {
            const globalIndex = (currentPage - 1) * pageSize + i;
            return {
                path: f.path,
                title: f.name,
                optimizedPath: f.status === "completed" ? f.finalPath : null, // Fix: Use finalPath instead of original path f.path
                isOptimized: f.status === "completed",
                btnId: `btn-play-${globalIndex}`, // Match global index-based IDs
            };
        });
        setPlaylist(playlist);
    });

    // Keep current page within bounds after files are loaded
    $effect(() => {
        if (files.length === 0) return;
        if (currentPage > totalPages && totalPages > 0) {
            currentPage = totalPages;
        }
    });

    $effect(() => {
        localStorage.setItem("optimizer-current-page", currentPage.toString());
    });

    // Scroll to top when page changes
    $effect(() => {
        if (!currentPage || !scrollContainer) return;
        if (!hasInitializedPageScroll) {
            hasInitializedPageScroll = true;
            return; // avoid overriding restored scroll on initial render
        }
        scrollContainer.scrollTo({ top: 0, behavior: "smooth" });
    });

    let showHelp = $state(false);
    let lastCpuTempErrorToastAt = $state(0);
    let globalActiveTrack = $state(null); // Local mirror of global store track
    let isGlobalPlaying = $state(false);
    let chartContainer = $state(null);
    let chartInstance = $state(null);
    let lastFocusedIndex = $state(null);
    let flaggedPaths = $state(
        new Set(
            JSON.parse(localStorage.getItem("optimizer-flagged-paths") || "[]"),
        ),
    );
    let denoisedPaths = $state(
        new Set(
            JSON.parse(
                localStorage.getItem("optimizer-denoised-paths") || "[]",
            ),
        ),
    );
    let badQualityPaths = $state(
        new Set(
            JSON.parse(
                localStorage.getItem("optimizer-bad-quality-paths") || "[]",
            ),
        ),
    );
    let fileNotes = $state(
        JSON.parse(localStorage.getItem("optimizer-file-notes") || "{}"),
    );

    function getFileByPath(path) {
        return files.find((f) => f.path === path);
    }

    async function syncFileTags(path, overrides = {}) {
        if (!path) return;
        if (DEMO_MODE) return;
        console.log(`[syncFileTags] Triggering for ${path}`, overrides);

        const file = getFileByPath(path);
        const payload = {
            originalPath: path,
            optimizedPath:
                overrides.optimizedPath !== undefined
                    ? overrides.optimizedPath
                    : file?.finalPath,
            badQuality:
                overrides.badQuality !== undefined
                    ? !!overrides.badQuality
                    : badQualityPaths.has(path),
            note:
                overrides.note !== undefined
                    ? overrides.note
                    : (fileNotes[path] || ""),
        };

        try {
            const res = await bridgeFetch("/sync-file-tags", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });

            if (!res.ok) {
                const msg = await res.text();
                throw new Error(msg || `HTTP ${res.status}`);
            }

            const data = await res.json();
            const index = files.findIndex((f) => f.path === path);
            if (index !== -1) {
                const updatedFile = { ...files[index] };
                if (data.originalMetadata) {
                    updatedFile.badQuality = data.originalMetadata.badQuality;
                    updatedFile.note = data.originalMetadata.note;
                    updatedFile.title = data.originalMetadata.title;
                    updatedFile.artist = data.originalMetadata.artist;
                    updatedFile.allTags = data.originalMetadata.allTags;
                }
                if (data.optimizedMetadata) {
                    updatedFile.optimizedMetadata = data.optimizedMetadata;
                }
                files[index] = updatedFile;
            }

            // Success - show subtle feedback
            showTransientToast("Tags synced", "info", 1000);
        } catch (e) {
            console.error("Failed to sync metadata tags:", e);
            showTransientToast("Tag sync failed", "error");
        }
    }

    function setFileNote(path, note) {
        fileNotes = { ...fileNotes, [path]: note };
        syncFileTags(path, { note });
    }

    function getFileNote(path) {
        return fileNotes[path] || "";
    }

    let conversionQueue = $state([]);
    let isProcessingQueue = $state(false);
    let stopAfterCurrentRequested = $state(false);
    let manualQueuePaused = $state(false);
    let selectedPaths = $state(new Set());
    let activeQueueTaskPath = $state(null);
    let hasAttemptedBatchRestore = $state(false);
    let pendingBatchRestore = $state(null);
    let isApplyingBatchRestore = $state(false);
    let cleanStatusCheckInFlight = $state(false);

    let currentTime = $state(Date.now());
    let showSettingsPopup = $state(false);
    let isRestartingBridge = $state(false);
    let restartBridgeMessage = $state("");
    let skipNextPlainToggle = $state({ index: -1, until: 0 });
    let rememberScroll = $state(
        localStorage.getItem("audit-remember-scroll") === "true",
    );
    let showBatchSettingsModal = $state(false);
    /** @type {"selected" | "all"} */
    let batchTargetMode = $state("selected");
    let lastSelectedIndex = $state(null);
    let isFocusMode = $state(false);
    let cpuTemp = $state(null);
    let cpuUsage = $state(null);
    let thermalThrottling = $state(false);
    let thermalThrottlingRemaining = $state(0); // seconds
    let lastThrottlingClosedAt = $state(0); // Grace period after manual resume
    let prevThermalThrottling = false;
    $effect(() => {
        if (prevThermalThrottling && !thermalThrottling) {
            lastThrottlingClosedAt = Date.now();
        }
        prevThermalThrottling = thermalThrottling;
    });

    const INTER_FILE_PAUSE_SKIP_TEMP_C = 75;

    // Inter-file Pause Logic
    let interFilePauseEnabled = $state(
        localStorage.getItem("optimizer-inter-pause-enabled") === "true",
    );
    let interFilePauseDuration = $state(
        parseInt(localStorage.getItem("optimizer-inter-pause-duration")) || 1,
    ); // minutes
    let skipInterFilePauseWhenCool = $state(
        localStorage.getItem("optimizer-skip-inter-pause-when-cool") === "true",
    );
    let isInterFilePausing = $state(false);
    let interFilePauseRemaining = $state(0); // seconds

    $effect(() => {
        localStorage.setItem(
            "optimizer-inter-pause-enabled",
            String(interFilePauseEnabled),
        );
    });
    $effect(() => {
        localStorage.setItem("audit-remember-scroll", String(rememberScroll));
    });
    $effect(() => {
        localStorage.setItem(
            "optimizer-inter-pause-duration",
            String(interFilePauseDuration),
        );
    });
    $effect(() => {
        localStorage.setItem(
            "optimizer-skip-inter-pause-when-cool",
            String(skipInterFilePauseWhenCool),
        );
    });

    $effect(() => {
        // Keep ETA live while queue settings/progress/pause timer change.
        if (
            batchTotalFiles > 0 &&
            (isProcessingQueue ||
                isInterFilePausing ||
                batchProcessedCount < batchTotalFiles)
        ) {
            updateBatchEtaEstimate();
        }
    });

    function shouldSkipInterFilePause() {
        return (
            skipInterFilePauseWhenCool &&
            cpuTemp !== null &&
            cpuTemp < INTER_FILE_PAUSE_SKIP_TEMP_C
        );
    }

    // Update current time every second for live elapsed time display
    $effect(() => {
        const interval = setInterval(() => {
            currentTime = Date.now();
        }, 1000);
        return () => clearInterval(interval);
    });

    $effect(() => {
        localStorage.setItem("optimizer-resemble-gain", String(resembleGain));
    });
    $effect(() => {
        localStorage.setItem("optimizer-resemble-mix", String(resembleMix));
    });
    $effect(() => {
        localStorage.setItem("optimizer-lavasr-denoise", String(lavasrDenoise));
    });
    $effect(() => {
        localStorage.setItem("optimizer-lavasr-superres", String(lavasrSuperres));
    });
    $effect(() => {
        localStorage.setItem("optimizer-lavasr-mix", String(lavasrMix));
    });
    $effect(() => {
        localStorage.setItem("optimizer-lavasr-gain", String(lavasrGain));
    });
    $effect(() => {
        localStorage.setItem("optimizer-lavasr-input-sr", String(lavasrInputSr));
    });
    $effect(() => {
        localStorage.setItem("optimizer-lavasr-batch", String(lavasrBatch));
    });
    $effect(() => {
        localStorage.setItem("optimizer-volume-gain", String(volumeGain));
    });
    $effect(() => {
        localStorage.setItem("optimizer-vf-mode", String(vfMode));
    });
    $effect(() => {
        localStorage.setItem(
            "optimizer-echo-reduction",
            String(echoReduction),
        );
    });
    $effect(() => {
        localStorage.setItem("optimizer-clean-method", cleanMethod);
    });
    $effect(() => {
        localStorage.setItem(
            "optimizer-target-bitrate",
            String(targetBitrateForClean),
        );
    });

    // Sync Global Spinner
    $effect(() => {
        // If we are processing, set true.
        if (
            isProcessingQueue ||
            isScanning ||
            isCleaning ||
            files.some((f) => f.status === "analyzing")
        ) {
            globalUiState.isProcessing = true;
        } else {
            // Only set to false if we are NOT processing.
            // WARNING: This assumes AudioOptimizer is the main driver.
            // If App.svelte is running a preview, this might turn it off?
            // To be safer, we should only set TRUE here, and let the specific actions manage false?
            // Or use a counter.
            // For now, given the requirement, let's just make sure we reflect OUR status.
            // If App.svelte sets it true, and we set it false, it flickers.
            // However, Svelte 5 state is fine.
            globalUiState.isProcessing = false;
        }
    });

    // Statistics
    let stats = $derived.by(() => {
        const analyzed = files.filter(
            (f) => f.status === "analyzed" || f.status === "completed",
        );
        const totalOriginal = files.reduce((acc, f) => acc + (f.size || 0), 0);
        const totalOptimized = files.reduce((acc, f) => acc + (f.optimizedSize || 0), 0);
        
        const totalSavings = files.reduce(
            (acc, f) => acc + (f.optimizedSize ? (f.size - f.optimizedSize) : 0),
            0,
        );
        const canOptimize = analyzed.filter(
            (f) => f.recommended_bitrate < f.currentBitrate,
        ).length;
        const completedCount = files.filter(
            (f) => f.status === "completed",
        ).length;
        const convertingCount = files.filter(
            (f) => f.status === "converting",
        ).length;
        const queuedCount = files.filter((f) => f.status === "queued").length;

        const toMB = (bytes) => (bytes / (1024 * 1024));

        return {
            total: files.length,
            analyzed: analyzed.length,
            completed: completedCount,
            converting: convertingCount,
            queued: queuedCount,
            totalOriginalMB: toMB(totalOriginal).toFixed(1),
            totalOptimizedMB: toMB(totalOptimized).toFixed(1),
            totalSavingsMB: toMB(totalSavings).toFixed(1),
            canOptimize,
        };
    });

    let lastUsedCleaningParams = $state(null);

    function findFileIndexByPath(filePath) {
        if (!filePath) return -1;
        return files.findIndex((f) => f.path === filePath);
    }

    function normalizeConvertingStatuses(activePath = null) {
        let changed = false;
        const queuedPaths = new Set(
            conversionQueue
                .map((task) => task?.filePath)
                .filter(Boolean),
        );

        const nextFiles = files.map((existingFile) => {
            if (
                existingFile?.status !== "converting" ||
                existingFile.path === activePath
            ) {
                return existingFile;
            }

            changed = true;
            return {
                ...existingFile,
                status: queuedPaths.has(existingFile.path)
                    ? "queued"
                    : existingFile.finalPath
                      ? "completed"
                      : "analyzed",
            };
        });

        if (changed) {
            files = nextFiles;
        }
    }

    function shouldApplyProgressUpdate(currentProgress, nextProgress) {
        const current = Number(currentProgress);
        const next = Number(nextProgress);

        if (!Number.isFinite(next)) return false;
        if (!Number.isFinite(current)) return true;

        // Keep the UI at 0 while backend emits optimistic warmup jumps like 10/20
        // before real progress begins from 0-3%.
        if ((next === 10 || next === 20) && current < 5) {
            return false;
        }

        // Once a file has visually reached 100%, do not allow stale late updates
        // to drag it backwards into intermediate post-processing percentages.
        if (current >= 100 && next < 100) {
            return false;
        }

        return true;
    }

    function mergeBatchStateIntoFiles(nextFiles) {
        if (!Array.isArray(nextFiles) || nextFiles.length === 0) {
            return nextFiles;
        }

        const previousByPath = new Map(
            files
                .filter((file) => file?.path)
                .map((file) => [file.path, file]),
        );
        const queuedPaths = new Set(
            conversionQueue
                .map((task) => task?.filePath)
                .filter(Boolean),
        );

        return nextFiles.map((incomingFile) => {
            const previous = previousByPath.get(incomingFile.path);
            if (!previous) {
                return incomingFile;
            }

            const isActiveFile = activeQueueTaskPath === incomingFile.path;
            const isQueuedFile = queuedPaths.has(incomingFile.path);
            const shouldKeepBatchState =
                isActiveFile ||
                isQueuedFile ||
                previous.status === "converting" ||
                previous.status === "queued";

            if (!shouldKeepBatchState) {
                return {
                    ...incomingFile,
                    progress:
                        typeof previous.progress === "number"
                            ? previous.progress
                            : incomingFile.progress,
                };
            }

            return {
                ...incomingFile,
                status: isActiveFile
                    ? "converting"
                    : isQueuedFile
                      ? "queued"
                      : previous.status,
                progress:
                    typeof previous.progress === "number"
                        ? previous.progress
                        : incomingFile.progress,
                optimizationStartTime:
                    previous.optimizationStartTime ??
                    incomingFile.optimizationStartTime,
                optimizationDuration:
                    previous.optimizationDuration ??
                    incomingFile.optimizationDuration,
                error: previous.error ?? incomingFile.error,
            };
        });
    }

    function serializeQueueTask(task) {
        if (!task?.filePath) return null;
        return {
            filePath: task.filePath,
            sampleOrBitrate: task.sampleOrBitrate ?? null,
            customInputPath: task.customInputPath ?? null,
            allowReprocess: !!task.allowReprocess,
        };
    }

    function clearBatchSession() {
        localStorage.removeItem(BATCH_SESSION_KEY);
    }

    function loadBatchSession() {
        try {
            const raw = localStorage.getItem(BATCH_SESSION_KEY);
            if (!raw) return null;
            const parsed = JSON.parse(raw);
            if (!parsed || parsed.folderPath !== folderPath) return null;
            return parsed;
        } catch (e) {
            console.warn("Failed to load batch session:", e);
            return null;
        }
    }

    async function fetchCleanStatus() {
        if (!isLiveOptimizerInstance()) {
            return { active: true, pid: null };
        }
        if (optimizerRuntime.cleanStatusPromise) {
            return optimizerRuntime.cleanStatusPromise;
        }

        optimizerRuntime.cleanStatusPromise = (async () => {
            try {
                const res = await bridgeFetch("/clean-status", undefined, {
                    silentInDemo: true,
                });
                if (!res.ok) {
                    throw new Error(`HTTP ${res.status}`);
                }
                return await res.json();
            } catch (e) {
                console.warn("Failed to fetch clean status:", e);
                return { active: false, pid: null };
            } finally {
                optimizerRuntime.cleanStatusPromise = null;
            }
        })();

        return optimizerRuntime.cleanStatusPromise;
    }

    async function refreshFilesFromBridge({ restoreBatch = true } = {}) {
        if (!isLiveOptimizerInstance() || !folderPath) return;
        if (optimizerRuntime.refreshFilesPromise) {
            return optimizerRuntime.refreshFilesPromise;
        }

        optimizerRuntime.refreshFilesPromise = (async () => {
            let res;
            let lastError = null;
            for (let attempt = 0; attempt < 5; attempt++) {
                try {
                    res = await bridgeFetch(
                        `/files?folder=${encodeURIComponent(folderPath)}`,
                        undefined,
                        { silentInDemo: true },
                    );
                    break;
                } catch (e) {
                    lastError = e;
                    if (attempt < 4) {
                        await wait(700);
                    }
                }
            }

            if (!res) {
                throw lastError || new Error("Bridge unavailable");
            }
            if (!res.ok) throw new Error(await res.text());

            const data = await res.json();
            const fileList = data.files || (Array.isArray(data) ? data : []);
            files = mergeBatchStateIntoFiles(
                fileList.map((f) => ({
                    currentBitrate: null,
                    channels: null,
                    maxFreq: null,
                    quality: null,
                    recommended_bitrate: null,
                    spectralData: null,
                    error: null,
                    ...f,
                })),
            );

            const nextBadQualityPaths = new Set(
                JSON.parse(
                    localStorage.getItem("optimizer-bad-quality-paths") || "[]",
                ),
            );
            const nextFileNotes = {
                ...JSON.parse(localStorage.getItem("optimizer-file-notes") || "{}"),
            };

            for (const f of fileList) {
                if (!f?.path) continue;
                if (f.badQuality) {
                    nextBadQualityPaths.add(f.path);
                }
                if (typeof f.note === "string") {
                    nextFileNotes[f.path] = f.note.trim();
                }
            }

            badQualityPaths = nextBadQualityPaths;
            fileNotes = nextFileNotes;
            localStorage.setItem(
                "optimizer-bad-quality-paths",
                JSON.stringify(Array.from(nextBadQualityPaths)),
            );
            localStorage.setItem(
                "optimizer-file-notes",
                JSON.stringify(nextFileNotes),
            );

            if (restoreBatch) {
                await restoreBatchSessionIfNeeded();
            }
        })();

        try {
            return await optimizerRuntime.refreshFilesPromise;
        } finally {
            optimizerRuntime.refreshFilesPromise = null;
        }
    }

    async function recoverConversionAfterStreamClose(filePath) {
        if (!isLiveOptimizerInstance()) return false;
        console.warn(
            "[performConversion] Stream ended before terminal event. Waiting for backend to finish current task.",
            { filePath },
        );

        const startedAt = Date.now();
        const timeoutMs = 2 * 60 * 60 * 1000;

        while (Date.now() - startedAt < timeoutMs) {
            if (!isLiveOptimizerInstance()) {
                return false;
            }
            const status = await fetchCleanStatus();
            if (status.active) {
                await wait(1500);
                continue;
            }

            await refreshFilesFromBridge({ restoreBatch: false });
            const refreshedFile = getFileByPath(filePath);
            if (refreshedFile?.finalPath || refreshedFile?.status === "completed") {
                console.info(
                    "[performConversion] Recovered successful completion after early stream close.",
                    { filePath },
                );
                return true;
            }

            throw new Error(
                "Optimization stream closed early before backend reported completion",
            );
        }

        throw new Error(
            "Lost optimization stream while backend kept running for too long",
        );
    }

    function applyRestoredBatchSession(session, includeActiveTask = true) {
        if (!session || session.folderPath !== folderPath) return false;

        const taskPaths = [];
        if (includeActiveTask && session.activeQueueTaskPath) {
            taskPaths.push(session.activeQueueTaskPath);
        }
        for (const task of session.conversionQueue || []) {
            if (task?.filePath) {
                taskPaths.push(task.filePath);
            }
        }

        const dedupedTaskPaths = [...new Set(taskPaths)];
        const restoredTasks = [];
        for (const filePath of dedupedTaskPaths) {
            const queueTask =
                (session.conversionQueue || []).find((task) => task.filePath === filePath) ||
                { filePath, sampleOrBitrate: session.lastUsedCleaningParams || null, customInputPath: null };
            const index = findFileIndexByPath(filePath);
            if (index === -1) continue;
            if (files[index]?.status === "completed" && files[index]?.finalPath) continue;

            files[index] = {
                ...files[index],
                status: "queued",
                progress: 0,
                error: null,
            };
            restoredTasks.push({
                filePath,
                sampleOrBitrate: queueTask.sampleOrBitrate ?? null,
                customInputPath: queueTask.customInputPath ?? null,
                allowReprocess: !!queueTask.allowReprocess,
            });
        }

        if (restoredTasks.length === 0) {
            clearBatchSession();
            return false;
        }

        isApplyingBatchRestore = true;
        conversionQueue = restoredTasks;
        selectedPaths = new Set(
            (session.selectedPaths || []).filter((filePath) => findFileIndexByPath(filePath) !== -1),
        );
        batchStartTime = session.batchStartTime || Date.now();
        totalProcessedDuration = session.totalProcessedDuration || 0;
        totalProcessTime = session.totalProcessTime || 0;
        batchProcessedCount = session.batchProcessedCount || 0;
        batchTotalFiles =
            session.batchTotalFiles || restoredTasks.length + batchProcessedCount;
        batchETA = session.batchETA ?? null;
        batchProcessingSpeed = session.batchProcessingSpeed || 0;
        stopAfterCurrentRequested = false;
        manualQueuePaused = false;
        lastUsedCleaningParams = session.lastUsedCleaningParams || lastUsedCleaningParams;
        activeQueueTaskPath = null;
        isApplyingBatchRestore = false;

        showTransientToast(
            `Recovered batch queue: ${restoredTasks.length} file(s) pending.`,
            "info",
            2600,
        );
        return true;
    }

    async function restoreBatchSessionIfNeeded() {
        if (
            !isLiveOptimizerInstance() ||
            hasAttemptedBatchRestore ||
            !folderPath ||
            files.length === 0 ||
            isProcessingQueue ||
            activeQueueTaskPath ||
            conversionQueue.length > 0
        ) {
            return;
        }
        hasAttemptedBatchRestore = true;

        const session = pendingBatchRestore || loadBatchSession();
        pendingBatchRestore = null;
        if (!session) return;

        const status = await fetchCleanStatus();
        if (status.active && session.activeQueueTaskPath) {
            pendingBatchRestore = session;
            hasAttemptedBatchRestore = false;
            showTransientToast(
                "Optimization is still running in the backend. Resume will continue after the next reload or restart.",
                "info",
                4200,
            );
            return;
        }

        applyRestoredBatchSession(session, true);
    }

    $effect(() => {
        localStorage.setItem("optimizer-folder-path", folderPath);
    });

    $effect(() => {
        folderPath;
        hasAttemptedBatchRestore = false;
        pendingBatchRestore = null;
        activeQueueTaskPath = null;
    });

    $effect(() => {
        if (!folderPath) {
            clearBatchSession();
            return;
        }

        if (
            isApplyingBatchRestore ||
            (!activeQueueTaskPath && conversionQueue.length === 0 && !isProcessingQueue)
        ) {
            if (
                !isProcessingQueue &&
                conversionQueue.length === 0 &&
                !activeQueueTaskPath
            ) {
                clearBatchSession();
            }
            return;
        }

        const session = {
            folderPath,
            conversionQueue: conversionQueue
                .map(serializeQueueTask)
                .filter(Boolean),
            activeQueueTaskPath,
            selectedPaths: Array.from(selectedPaths),
            batchStartTime,
            totalProcessedDuration,
            totalProcessTime,
            batchProcessedCount,
            batchTotalFiles,
            batchETA,
            batchProcessingSpeed,
            lastUsedCleaningParams,
        };
        localStorage.setItem(BATCH_SESSION_KEY, JSON.stringify(session));
    });

    $effect(() => {
        localStorage.setItem(
            "optimizer-compare-start-time",
            String(compareStartTime),
        );
    });

    $effect(() => {
        localStorage.setItem(
            "optimizer-compare-duration",
            String(compareDuration),
        );
    });

    $effect(() => {
        localStorage.setItem(
            "optimizer-compare-bitrates",
            JSON.stringify(compareBitrates),
        );
    });

    $effect(() => {
        localStorage.setItem(
            "optimizer-flagged-paths",
            JSON.stringify(Array.from(flaggedPaths)),
        );
    });

    $effect(() => {
        localStorage.setItem(
            "optimizer-denoised-paths",
            JSON.stringify(Array.from(denoisedPaths)),
        );
    });

    $effect(() => {
        localStorage.setItem(
            "optimizer-bad-quality-paths",
            JSON.stringify(Array.from(badQualityPaths)),
        );
    });

    $effect(() => {
        localStorage.setItem("optimizer-file-notes", JSON.stringify(fileNotes));
    });

    // Scroll Restoration
    $effect(() => {
        if (!rememberScroll || !scrollContainer || hasRestoredOptimizerScroll) return;
        // Wait until file list is present; otherwise the browser may clamp scroll to 0.
        if (folderPath && files.length === 0) return;

        const saved = parseInt(localStorage.getItem(OPTIMIZER_SCROLL_KEY) || "", 10);
        hasRestoredOptimizerScroll = true;
        if (!Number.isFinite(saved) || saved < 0) return;

        isRestoringOptimizerScroll = true;
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                if (scrollContainer) {
                    scrollContainer.scrollTop = saved;
                }
                isRestoringOptimizerScroll = false;
            });
        });
    });

    // Cleanup Settings Persistence
    $effect(() => {
        localStorage.setItem("optimizer-clean-method", cleanMethod);
    });
    $effect(() => {
        localStorage.setItem("optimizer-volume-gain", String(volumeGain));
    });
    $effect(() => {
        localStorage.setItem("optimizer-resemble-mix", String(resembleMix));
    });
    $effect(() => {
        localStorage.setItem("optimizer-vf-mode", String(vfMode));
    });
    $effect(() => {
        localStorage.setItem(
            "optimizer-echo-reduction",
            String(echoReduction),
        );
    });

    $effect(() => {
        if (showCompareModal && !DEMO_MODE) {
            generateComparison();
        }
    });

    onMount(() => {
        loadEtaHistory();
        const unsubscribe = subscribeToGlobalTrack((track) => {
            if (!isLiveOptimizerInstance()) return;
            globalActiveTrack = track;
        });

        const unsubscribePlayback = subscribeToPlaybackState((playing) => {
            if (!isLiveOptimizerInstance()) return;
            isGlobalPlaying = playing;
        });

        const unsubscribeCommands = subscribeToAudioCommands(
            (command, payload) => {
                if (!isLiveOptimizerInstance()) return;
                if (command === "TOGGLE_SELECT" && payload) {
                    if (selectedPaths.has(payload)) {
                        selectedPaths.delete(payload);
                    } else {
                        // Check if file exists in current list to avoid selecting random paths
                        if (files.some((f) => f.path === payload)) {
                            selectedPaths.add(payload);
                        }
                    }
                    selectedPaths = new Set(selectedPaths);
                }
            },
        );

        // Auto-scan on load only after the bridge is reachable.
        if (DEMO_MODE) {
            if (files.length === 0) {
                loadDemoFiles();
            }
        } else if (folderPath) {
            waitForBridgeReady(25000).then((ready) => {
                if (ready && isLiveOptimizerInstance()) {
                    scanFolder();
                }
            });
        }

        const handleKeys = (e) => {
            // Only handle if not in an input/textarea or if a modal is open
            const target = e.target;
            if (
                ["INPUT", "TEXTAREA", "SELECT"].includes(target?.tagName) ||
                target?.isContentEditable ||
                globalUiState?.isModalOpen
            )
                return;

            const isModifier = e.metaKey || e.ctrlKey || e.altKey || e.shiftKey;

            const navigate = (newIndex) => {
                if (newIndex === lastFocusedIndex) return;

                // Auto-switch page if needed
                const targetPage = Math.floor(newIndex / pageSize) + 1;
                if (targetPage !== currentPage) {
                    currentPage = targetPage;
                }

                lastFocusedIndex = newIndex;

                const file = files[lastFocusedIndex];
                if (file) {
                    setGlobalTrack(
                        {
                            path: file.path,
                            title: file.originalName,
                            optimizedPath: file.finalPath,
                            duration: file.duration,
                            isOptimized:
                                !!file.finalPath && file.status === "completed",
                            btnId: `btn-play-${lastFocusedIndex}`,
                            shouldPlay: isGlobalPlaying,
                        },
                        null,
                    );
                }
            };

            if (e.key === "ArrowUp") {
                if (!isModifier) {
                    e.preventDefault();
                    const newIndex =
                        lastFocusedIndex === null
                            ? 0
                            : Math.max(0, lastFocusedIndex - 1);
                    navigate(newIndex);
                }
            } else if (e.key === "ArrowDown") {
                if (!isModifier) {
                    e.preventDefault();
                    const newIndex =
                        lastFocusedIndex === null
                            ? 0
                            : Math.min(files.length - 1, lastFocusedIndex + 1);
                    navigate(newIndex);
                }
            } else if (e.key === "ArrowLeft") {
                if (!isModifier) {
                    e.preventDefault();
                    dispatchAudioCommand("seek", -10);
                }
            } else if (e.key === "ArrowRight") {
                if (!isModifier) {
                    e.preventDefault();
                    dispatchAudioCommand("seek", 10);
                }
            } else if (e.key.toLowerCase() === "z") {
                if (!isModifier) {
                    e.preventDefault();
                    dispatchAudioCommand("seek", -60);
                }
            } else if (e.key.toLowerCase() === "x") {
                if (!isModifier) {
                    e.preventDefault();
                    dispatchAudioCommand("seek", 60);
                }
            } else if (e.key.toLowerCase() === "o" || e.key === "щ") {
                if (!isModifier) {
                    e.preventDefault();
                    dispatchAudioCommand("toggle-version");
                }
            } else if (e.key.toLowerCase() === "l" || e.key === "д") {
                if (!isModifier) {
                    e.preventDefault();
                    if (lastFocusedIndex !== null) openCompareModal(lastFocusedIndex);
                }
            } else if (e.key.toLowerCase() === "r" || e.key === "к") {
                if (!isModifier) {
                    e.preventDefault();
                    if (lastFocusedIndex !== null) openReoptimizeModal(lastFocusedIndex);
                }
            } else if (e.key.toLowerCase() === "c") {
                // IMPORTANT: Only trigger if NO modifiers are pressed (allows Cmd+C for copy)
                if (!isModifier) {
                    e.preventDefault();
                    // Toggle selection for focused row, or fallback to active track
                    let targetPath = null;
                    if (lastFocusedIndex !== null && files[lastFocusedIndex]) {
                        targetPath = files[lastFocusedIndex].path;
                    } else if (globalActiveTrack) {
                        targetPath = globalActiveTrack.path;
                    }

                    if (targetPath) {
                        if (selectedPaths.has(targetPath)) {
                            selectedPaths.delete(targetPath);
                        } else {
                            selectedPaths.add(targetPath);
                        }
                        selectedPaths = new Set(selectedPaths);
                    }
                }
            } else if (e.key === " ") {
                if (!isModifier) {
                    e.preventDefault();
                    dispatchAudioCommand("toggle");
                }
            }
        };

        window.addEventListener("keydown", handleKeys);

        return () => {
            unsubscribe();
            unsubscribePlayback();
            unsubscribeCommands();
            window.removeEventListener("keydown", handleKeys);
        };
    });

    // Auto-Scroll to active track in Optimizer
    $effect(() => {
        if (globalActiveTrack && globalActiveTrack.btnId) {
            setTimeout(() => {
                const el = document.getElementById(globalActiveTrack.btnId);
                if (el) {
                    el.scrollIntoView({ behavior: "smooth", block: "center" });
                }
            }, 50);
        }
    });

    // Poll CPU Temperature when in Focus Mode
    $effect(() => {
        globalUiState.isModalOpen =
            showCompareModal ||
            showSpectrogramModal ||
            showBatchSettingsModal ||
            showHelp;
    });

    $effect(() => {
        if (showCompareModal) {
            // Automatically pause background recording when entering the lab
            dispatchAudioCommand("PAUSE_ALL");
        }
    });

    $effect(() => {
        if (DEMO_MODE) {
            if (!isFocusMode) {
                cpuTemp = null;
                cpuUsage = null;
            }
            return;
        }
        if (!isFocusMode) {
            cpuTemp = null;
            return;
        }

        const pollTemp = async () => {
            try {
                const res = await bridgeFetch("/cpu-temp", undefined, {
                    silentInDemo: true,
                });
                if (!res.ok) {
                    throw new Error(`HTTP ${res.status}`);
                }
                const data = await res.json();
                if (data.temp !== undefined) {
                    cpuTemp = data.temp;
                }
                if (data.usage !== undefined) {
                    cpuUsage = data.usage;
                }

                // Reset error toast throttle on successful poll
                lastCpuTempErrorToastAt = 0;

                if (cpuTemp !== null) {
                    // Support for Thermal Throttling
                    if (!thermalThrottling && cpuTemp > 92 && (Date.now() - lastThrottlingClosedAt > 60000)) {
                        thermalThrottling = true;
                        thermalThrottlingRemaining = 120; // 2 minutes
                        console.warn(
                            `[THERMAL] CPU temp reached ${cpuTemp}°C. Throttling for 2 minutes.`,
                        );
                    }
                }
            } catch (e) {
                console.error("Failed to fetch CPU temp", e);
                const now = Date.now();
                if (now - lastCpuTempErrorToastAt > 30000) {
                    showTransientToast(
                        "CPU monitor error: temperature unavailable",
                        "error",
                    );
                    lastCpuTempErrorToastAt = now;
                }
            }
        };

        pollTemp();
        const interval = setInterval(pollTemp, 5000);
        return () => clearInterval(interval);
    });

    let prevDemoFocusMode = false;
    $effect(() => {
        if (!DEMO_MODE) return;
        if (prevDemoFocusMode && !isFocusMode) {
            resetDemoFocusState();
            loadDemoFiles();
        }
        prevDemoFocusMode = isFocusMode;
    });

    // Thermal Throttling Timer
    $effect(() => {
        if (!thermalThrottling) return;

        const timer = setInterval(() => {
            if (thermalThrottlingRemaining > 0) {
                thermalThrottlingRemaining -= 1;
            } else {
                // Time is up, check temperature
                if (cpuTemp !== null && cpuTemp <= 80) {
                    thermalThrottling = false;
                    console.info(
                        `[THERMAL] CPU cooled down to ${cpuTemp}°C. Resuming.`,
                    );
                } else {
                    // Still too hot, reset timer for another 2 minutes
                    thermalThrottlingRemaining = 120;
                    console.warn(
                        `[THERMAL] CPU still too hot (${cpuTemp}°C). Waiting another 2 minutes.`,
                    );
                }
            }
        }, 1000);
        return () => clearInterval(timer);
    });

    // MediaSession updates for Lock Screen visibility
    $effect(() => {
        if (!isProcessingQueue && !isInterFilePausing) {
            if ("mediaSession" in navigator) {
                navigator.mediaSession.metadata = null;
            }
            return;
        }

        const currentFile =
            files.find((f) => f.path === activeQueueTaskPath) ||
            files.find((f) => f.status === "converting");
        const title = currentFile ? currentFile.name : "Waiting...";
        const progress = currentFile ? `${currentFile.progress}%` : "Paused";
        const progressText = `${batchProcessedCount}/${batchTotalFiles} done`;
        const etaText = batchETA
            ? `ETA: ${formatDurationHmsShort(batchETA)}`
            : "Calculating ETA...";

        if ("mediaSession" in navigator) {
            navigator.mediaSession.metadata = new MediaMetadata({
                title: `${progress} | ${title}`,
                artist: `${progressText} • ${etaText}`,
                album: "Prabhupada Lecture Audit",
                artwork: [
                    {
                        src: "https://vani.guru/wp-content/uploads/2014/11/logo.png",
                        sizes: "512x512",
                        type: "image/png",
                    },
                ],
            });
        }
    });

    // --- Actions ---
    async function revealInFinder(path) {
        if (!path) return;
        if (isDemoBlocked("Reveal in Finder")) return;
        try {
            await bridgeFetch("/reveal", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ file: path }),
            });
        } catch (e) {
            console.error("Reveal failed", e);
        }
    }

    async function openInAudacity(path) {
        if (!path) return;
        if (isDemoBlocked("Open in Audacity")) return;
        try {
            const res = await bridgeFetch("/open-audacity", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ file: path }),
            });
            const data = await res.json();
            if (data.error) {
                showTransientToast(data.error, "error");
            }
        } catch (e) {
            console.error("Audacity open failed", e);
            showTransientToast("Failed to open Audacity: " + e.message, "error");
        }
    }
    async function openInRX(path) {
        if (!path) return;
        if (isDemoBlocked("Open in iZotope RX")) return;
        try {
            const res = await bridgeFetch("/open-rx", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ file: path }),
            });
            const data = await res.json();
            if (data.error) {
                showTransientToast(data.error, "error");
            }
        } catch (e) {
            console.error("RX open failed", e);
            showTransientToast(
                "Failed to open iZotope RX 11: " + e.message,
                "error",
            );
        }
    }
    async function pickFolder() {
        if (isDemoBlocked("Folder picker")) return;
        try {
            const res = await bridgeFetch("/pick-folder", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ initialPath: folderPath }),
            });
            const data = await res.json();
            if (data.status === "success" && data.path) {
                folderPath = data.path;
                scanFolder();
            }
        } catch (e) {
            error = "Failed to open folder picker: " + e.message;
        }
    }

    async function scanFolder() {
        if (DEMO_MODE) {
            await loadDemoFiles({ withDelay: true });
            return;
        }
        if (!isLiveOptimizerInstance() || !folderPath) return;
        if (isBatchActive()) {
            console.warn("[scanFolder] Ignored because batch queue is active.");
            return;
        }
        isScanning = true;
        error = null;
        try {
            await refreshFilesFromBridge({ restoreBatch: true });
        } catch (e) {
            error = e.message;
        } finally {
            isScanning = false;
        }
    }

    async function analyzeFile(index, full = false, force = false) {
        if (isDemoBlocked("Audio analysis")) return;
        lastFocusedIndex = index;
        const file = files[index];
        if (!file) return;

        // Reset state, preserving completed status if already optimized
        const isOptimized = !!file.finalPath;
        files[index].status = isOptimized ? "completed" : "analyzing";
        files[index].isReanalyzing = true; // Flag for UI spinner
        files[index].progress = 0;
        files[index].progressMessage = "Connecting...";
        files[index].error = null;

        // Sync with modal if open
        if (selectedFileForChart && selectedFileForChart.path === file.path) {
            selectedFileForChart.status = "analyzing";
            selectedFileForChart.progress = 0;
            selectedFileForChart.error = null;
        }

        try {
            console.log(
                `[Frontend] Starting ${full ? "Full" : "Preview"} Analysis for: ${file.name}${force ? " (Forced Re-scan)" : ""}`,
            );
            const res = await bridgeFetch("/analyze-audio", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    path: file.path,
                    full: !!full,
                    force: !!force,
                }),
            });

            if (!res.ok) {
                const msg = await res.text();
                throw new Error(msg || `HTTP ${res.status}`);
            }
            if (!res.body) {
                throw new Error("No analysis stream received");
            }

            const reader = res.body.getReader();
            const decoder = new TextDecoder();
            let resultData = null;
            let buffer = "";

            while (true) {
                const { done, value } = await reader.read();

                if (value) {
                    buffer += decoder.decode(value, { stream: true });
                    // Split on both newline and carriage return for tqdm/ffmpeg progress
                    const lines = buffer.split(/[\n\r]/);
                    buffer = lines.pop() || ""; // Keep last potential incomplete line

                    for (const line of lines) {
                        if (!line.trim()) continue;
                        try {
                            // Robust JSON parsing: find the start of the JSON object
                            let jsonStr = line;
                            const firstBrace = line.indexOf("{");
                            if (firstBrace !== -1) {
                                jsonStr = line.substring(firstBrace);
                            }

                            const data = JSON.parse(jsonStr);
                            if (data.status === "progress") {
                                files[index] = {
                                    ...files[index],
                                    progress: data.progress,
                                    progressMessage: data.message,
                                    status: files[index].finalPath
                                        ? "completed"
                                        : "analyzing",
                                    isReanalyzing: true,
                                };

                                // SYNC with selected file if this is the one we are looking at
                                if (
                                    selectedFileForChart &&
                                    selectedFileForChart.path === file.path
                                ) {
                                    selectedFileForChart = {
                                        ...selectedFileForChart,
                                        progress: data.progress,
                                        progressMessage: data.message,
                                        status: files[index].finalPath
                                            ? "completed"
                                            : "analyzing",
                                        isReanalyzing: true,
                                    };
                                }
                            } else if (data.status === "success") {
                                resultData = data;
                            } else if (data.status === "error") {
                                throw new Error(data.error);
                            }
                        } catch (e) {
                            // Robust percentage fallback: Check for numeric% in the raw line
                            const percentMatch = line.match(/(\d+)%/);
                            if (percentMatch) {
                                const val = parseInt(percentMatch[1]);
                                files[index] = {
                                    ...files[index],
                                    progress: val,
                                };
                                if (
                                    selectedFileForChart &&
                                    selectedFileForChart.path === file.path
                                ) {
                                    selectedFileForChart = {
                                        ...selectedFileForChart,
                                        progress: val,
                                    };
                                }
                            }
                        }
                    }
                }

                if (done) {
                    // Process any remaining data in buffer
                    if (buffer.trim()) {
                        try {
                            const firstBrace = buffer.indexOf("{");
                            let jsonStr =
                                firstBrace !== -1
                                    ? buffer.substring(firstBrace)
                                    : buffer;

                            const data = JSON.parse(jsonStr);
                            if (data.status === "success") resultData = data;
                            else if (data.status === "error")
                                throw new Error(data.error);
                        } catch (e) {
                            console.error("Final parse error", buffer, e);
                        }
                    }
                    break;
                }
            }

            if (resultData) {
                const result = resultData;

                // Construct a clean update object
                const update = {
                    currentBitrate:
                        result.current_bitrate || files[index].currentBitrate,
                    channels: result.channels || files[index].channels,
                    maxFreq: result.max_frequency || files[index].maxFreq,
                    avgMaxFreq: result.avg_max_frequency,
                    noiseFloor: result.noise_floor,
                    samplePoints: result.sample_points,
                    quality: result.quality || files[index].quality,
                    recommended_bitrate:
                        result.recommended_bitrate ||
                        files[index].recommended_bitrate,
                    is_full_scan: !!(
                        result.is_full_scan ||
                        (full && result.status === "success")
                    ),
                    duration: result.duration || files[index].duration,
                    status: files[index].finalPath ? "completed" : "analyzed",
                    progress: 100,
                    progressMessage: "Done",
                };

                if (
                    update.currentBitrate &&
                    update.recommended_bitrate &&
                    !files[index].finalPath
                ) {
                    // Only project optimized size if not already optimized (preserve actual size)
                    update.optimizedSize = Math.round(
                        files[index].size *
                            (update.recommended_bitrate /
                                update.currentBitrate),
                    );
                }

                // Clear reanalyzing flag
                update.isReanalyzing = false;

                // ATOMIC UPDATE FOR SVELTE 5 REACTIVITY
                files[index] = { ...files[index], ...update };

                // Sync with the modal view if open
                if (
                    selectedFileForChart &&
                    selectedFileForChart.path === files[index].path
                ) {
                    selectedFileForChart = {
                        ...selectedFileForChart,
                        ...update,
                    };
                }
            } else {
                throw new Error("No analysis data received");
            }
        } catch (e) {
            const errMsg = e?.message || "Analysis failed";
            if (files[index]) {
                files[index] = {
                    ...files[index],
                    status: "error",
                    error: errMsg,
                    isReanalyzing: false,
                };
            }
            if (
                selectedFileForChart &&
                selectedFileForChart.path === file.path
            ) {
                selectedFileForChart.status = "error";
                selectedFileForChart.error = errMsg;
            }
            showTransientToast(`Quick scan failed: ${errMsg}`, "error");
        }
    }

    function setSelectedFileForChart(file) {
        selectedFileForChart = file;
    }

    function toggleSelect(index, event, pathOverride = null) {
        const path = pathOverride || files[index]?.path;
        if (!path) return;
        const actualIndex = files.findIndex((f) => f.path === path);
        const startIndex = actualIndex >= 0 ? actualIndex : index;
        const isMetaRangeSelect = Boolean(
            event?.metaKey ||
                event?.ctrlKey ||
                event?.getModifierState?.("Meta") ||
                event?.getModifierState?.("Control"),
        );

        if (isMetaRangeSelect) {
            event?.preventDefault?.();
            const lastCountValue = localStorage.getItem(
                OPTIMIZER_SELECT_COUNT_KEY,
            );
            const defaultCount =
                lastCountValue && /^\d+$/.test(lastCountValue)
                    ? lastCountValue
                    : "10";
            const input = window.prompt(
                "How many files to select from this track?",
                defaultCount,
            );
            if (input === null) return;

            const count = parseInt(String(input).trim(), 10);
            if (!Number.isFinite(count) || count <= 0) {
                showTransientToast("Enter a valid positive number.", "error");
                return;
            }
            localStorage.setItem(OPTIMIZER_SELECT_COUNT_KEY, String(count));

            // Always include the clicked file first, then select following files.
            selectedPaths.add(path);
            const remainingCount = Math.max(0, count - 1);
            const end = Math.min(files.length - 1, startIndex + remainingCount);
            for (let i = startIndex + 1; i <= end; i++) {
                selectedPaths.add(files[i].path);
            }
            lastSelectedIndex = startIndex;
            selectedPaths = new Set(selectedPaths);
            // Some browsers may emit an additional plain click; ignore that follow-up.
            skipNextPlainToggle = { index: startIndex, until: Date.now() + 350 };
            showTransientToast(
                `Selected ${end - startIndex + 1} file(s).`,
                "info",
                1400,
            );
            return;
        }

        if (
            skipNextPlainToggle.index === startIndex &&
            Date.now() < skipNextPlainToggle.until
        ) {
            return;
        }

        if (event?.shiftKey && lastSelectedIndex !== null) {
            const start = Math.min(lastSelectedIndex, index);
            const end = Math.max(lastSelectedIndex, index);
            const isRemoving = selectedPaths.has(path);

            for (let i = start; i <= end; i++) {
                if (isRemoving) {
                    selectedPaths.delete(files[i].path);
                } else {
                    selectedPaths.add(files[i].path);
                }
            }
        } else {
            if (selectedPaths.has(path)) {
                selectedPaths.delete(path);
            } else {
                selectedPaths.add(path);
            }
        }
        lastSelectedIndex = index;
        selectedPaths = new Set(selectedPaths);
    }

    function selectAll() {
        const newSelected = new Set(selectedPaths);
        if (isAllOnPageSelected) {
            // Deselect all on current page
            paginatedFiles.forEach((f) => newSelected.delete(f.path));
        } else {
            // Select all on current page
            paginatedFiles.forEach((f) => newSelected.add(f.path));
        }
        selectedPaths = newSelected;
    }

    async function optimizeSelected() {
        if (isDemoBlocked("Batch optimization")) return;
        showBatchSettingsModal = false; // Close modal if open

        // Initialize batch stats
        batchStartTime = Date.now();
        totalProcessedDuration = 0;
        totalProcessTime = 0;
        batchProcessedCount = 0;
        batchTotalFiles = selectedPaths.size;
        batchETA = null;
        batchProcessingSpeed = 0;
        stopAfterCurrentRequested = false;
        manualQueuePaused = false;

        for (let i = 0; i < files.length; i++) {
            if (selectedPaths.has(files[i].path)) {
                await convertFile(i, lastUsedCleaningParams);
            }
        }
        updateBatchEtaEstimate();
    }

    async function optimizeAll() {
        if (isDemoBlocked("Optimize all")) return;
        showBatchSettingsModal = false; // Close modal if open
        stopAfterCurrentRequested = false;
        manualQueuePaused = false;
        for (let i = 0; i < files.length; i++) {
            if (files[i].status !== "completed") {
                await convertFile(i, lastUsedCleaningParams);
            }
        }
    }

    function requestStopAfterCurrent() {
        if (
            !isProcessingQueue &&
            !isInterFilePausing &&
            !activeQueueTaskPath &&
            conversionQueue.length === 0
        ) {
            return;
        }
        stopAfterCurrentRequested = true;
        showTransientToast(
            "Stop requested. Finishing current file, then stopping queue.",
            "info",
            2200,
        );

        // If we're already between files, nothing is converting now, so stop immediately.
        if (isInterFilePausing || !isProcessingQueue) {
            conversionQueue = [];
            activeQueueTaskPath = null;
            isInterFilePausing = false;
            interFilePauseRemaining = 0;
            manualQueuePaused = false;
            stopAfterCurrentRequested = false;
            updateBatchEtaEstimate();
            showTransientToast("Queue stopped.", "info");
        }
    }

    function toggleManualQueuePause() {
        if (manualQueuePaused) {
            manualQueuePaused = false;
            showTransientToast("Queue resumed.", "info");
            return;
        }

        manualQueuePaused = true;
        if (isInterFilePausing) {
            isInterFilePausing = false;
            interFilePauseRemaining = 0;
            showTransientToast("Queue paused.", "info");
            return;
        }

        showTransientToast(
            "Pause requested. Finishing current file, then pausing queue.",
            "info",
            2200,
        );
    }

    function openBatchSettings(mode) {
        batchTargetMode = mode;
        showBatchSettingsModal = true;
    }

    async function convertFile(
        index,
        sampleOrBitrate = null,
        customInputPath = null,
    ) {
        console.log(`[convertFile] Called for index ${index}`, { sampleOrBitrate, customInputPath });
        const file = files[index];
        if (!file) return;
        const allowReprocess =
            customInputPath !== null ||
            sampleOrBitrate !== null;

        if (
            (!allowReprocess &&
                (file.finalPath || file.status === "completed")) ||
            (Number.isFinite(file.lastOptimized) &&
                !allowReprocess &&
                Date.now() - file.lastOptimized < 60_000)
        ) {
            console.warn(
                `[convertFile] Skipping already optimized file at index ${index}`,
                { path: file.path, status: file.status, finalPath: file.finalPath },
            );
            return;
        }
        
        // Don't add if already in queue or converting
        if (
            files[index].status === "queued" ||
            files[index].status === "converting"
        ) {
            console.warn(`[convertFile] File at index ${index} is already ${files[index].status}`);
            return;
        }

        files[index] = {
            ...files[index],
            status: "queued",
            progress: 0,
        };
        conversionQueue = [
            ...conversionQueue,
            {
                filePath: files[index].path,
                sampleOrBitrate,
                customInputPath,
                allowReprocess,
            },
        ];
        console.log(`[convertFile] Added to queue. Queue length: ${conversionQueue.length}`);
    }

    $effect(() => {
        if (!isLiveOptimizerInstance()) return;
        if (
            !isProcessingQueue &&
            conversionQueue.length > 0 &&
            !thermalThrottling &&
            !isInterFilePausing &&
            !manualQueuePaused
        ) {
            processNextInQueue();
        }
    });

    $effect(() => {
        if (!isLiveOptimizerInstance()) return;
        if (
            conversionQueue.length === 0 ||
            isProcessingQueue ||
            cleanStatusCheckInFlight ||
            thermalThrottling ||
            isInterFilePausing ||
            manualQueuePaused
        ) {
            return;
        }

        if (optimizerRuntime.queueWatchdogTimeout) {
            clearTimeout(optimizerRuntime.queueWatchdogTimeout);
        }

        optimizerRuntime.queueWatchdogTimeout = setTimeout(async () => {
            optimizerRuntime.queueWatchdogTimeout = null;
            if (!isLiveOptimizerInstance()) {
                return;
            }
            if (
                conversionQueue.length === 0 ||
                isProcessingQueue ||
                cleanStatusCheckInFlight ||
                thermalThrottling ||
                isInterFilePausing ||
                manualQueuePaused
            ) {
                return;
            }

            const status = await fetchCleanStatus();
            if (status.active) {
                return;
            }

            console.warn("[Queue Watchdog] Queue is idle with pending items. Retrying next task.", {
                queueLength: conversionQueue.length,
                activeQueueTaskPath,
            });
            processNextInQueue();
        }, 4000);

        return () => {
            if (optimizerRuntime.queueWatchdogTimeout) {
                clearTimeout(optimizerRuntime.queueWatchdogTimeout);
                optimizerRuntime.queueWatchdogTimeout = null;
            }
        };
    });

    // Inter-file Pause Timer
    $effect(() => {
        if (!isInterFilePausing) return;

        const timer = setInterval(() => {
            if (interFilePauseRemaining > 0) {
                interFilePauseRemaining -= 1;
            } else {
                isInterFilePausing = false;
                console.info("[PAUSE] Inter-file pause ended. Resuming.");
            }
        }, 1000);
        return () => clearInterval(timer);
    });

    async function processNextInQueue() {
        if (!isLiveOptimizerInstance()) return;
        if (
            isProcessingQueue ||
            cleanStatusCheckInFlight ||
            conversionQueue.length === 0 ||
            thermalThrottling ||
            isInterFilePausing
        )
            return;

        cleanStatusCheckInFlight = true;
        try {
            const status = await fetchCleanStatus();
            if (status.active) {
                console.warn("[processNextInQueue] Backend still busy, waiting before retry.", {
                    queueLength: conversionQueue.length,
                    activeQueueTaskPath,
                });
                return;
            }
        } finally {
            cleanStatusCheckInFlight = false;
        }

        isProcessingQueue = true;
        const task = conversionQueue[0];
        const taskIndex = findFileIndexByPath(task?.filePath);

        if (taskIndex === -1) {
            console.warn("[processNextInQueue] Task file no longer exists in current list:", task?.filePath);
            conversionQueue = conversionQueue.slice(1);
            isProcessingQueue = false;
            return;
        }

        if (
            (files[taskIndex]?.finalPath ||
                files[taskIndex]?.status === "completed") &&
            !task?.allowReprocess
        ) {
            console.warn(
                "[processNextInQueue] Skipping task because file is already completed:",
                task?.filePath,
            );
            conversionQueue = conversionQueue.slice(1);
            isProcessingQueue = false;
            return;
        }

        activeQueueTaskPath = task.filePath;
        normalizeConvertingStatuses(task.filePath);
        let shouldAdvanceQueue = true;

        try {
            await performConversion(
                taskIndex,
                task.sampleOrBitrate,
                task.customInputPath,
            );
        } catch (e) {
            console.error("Queue process error:", e);
            if (e?.code === "BACKEND_BUSY") {
                shouldAdvanceQueue = false;
            }
        } finally {
            if (shouldAdvanceQueue) {
                const remaining = conversionQueue.slice(1);
                conversionQueue = remaining;
                activeQueueTaskPath = null;
            }

            console.log(`[processNextInQueue] Finished task. Remaining: ${conversionQueue.length}`);

            if (!shouldAdvanceQueue) {
                console.warn("[processNextInQueue] Queue retained current task because backend reported busy.", {
                    queueLength: conversionQueue.length,
                    activeQueueTaskPath,
                });
                isProcessingQueue = false;
                return;
            }

            if (stopAfterCurrentRequested) {
                conversionQueue = [];
                activeQueueTaskPath = null;
                isInterFilePausing = false;
                interFilePauseRemaining = 0;
                manualQueuePaused = false;
                stopAfterCurrentRequested = false;
                updateBatchEtaEstimate();
                showTransientToast("Queue stopped after current file.", "info");
                isProcessingQueue = false;
                return;
            }

            if (manualQueuePaused) {
                isInterFilePausing = false;
                interFilePauseRemaining = 0;
                updateBatchEtaEstimate();
                showTransientToast("Queue paused.", "info");
                isProcessingQueue = false;
                return;
            }

            let startedInterFilePause = false;

            // Trigger inter-file pause if enabled and there are more items
            if (interFilePauseEnabled && conversionQueue.length > 0) {
                if (shouldSkipInterFilePause()) {
                    console.info(
                        `[PAUSE] Skipping inter-file pause because CPU temp is ${cpuTemp}°C (< ${INTER_FILE_PAUSE_SKIP_TEMP_C}°C).`,
                    );
                } else {
                    startedInterFilePause = true;
                    isInterFilePausing = true;
                    interFilePauseRemaining = interFilePauseDuration * 60;
                    console.info(
                        `[PAUSE] File finished. Pausing for ${interFilePauseDuration} min.`,
                    );
                }
            }
            
            isProcessingQueue = false;
            if (
                conversionQueue.length > 0 &&
                (!interFilePauseEnabled || !startedInterFilePause) &&
                !manualQueuePaused &&
                !thermalThrottling
            ) {
                queueMicrotask(() => {
                    if (isLiveOptimizerInstance()) {
                        processNextInQueue();
                    }
                });
            }
        }
    }

    async function performConversion(
        index,
        sampleOrBitrate = null,
        customInputPath = null,
    ) {
        if (!isLiveOptimizerInstance()) return;
        const file = files[index];
        console.log(`[performConversion] Starting for ${file?.name}`, { sampleOrBitrate, customInputPath });
        
        if (!file) {
            console.error("[Optimizer] File not found at index:", index);
            return;
        }

        let targetBitrate = null;
        let cleaningParams = null;

        const inferMethodFromTag = (tag) => {
            if (typeof tag !== "string" || !tag.startsWith("cleaned_"))
                return null;
            if (tag.startsWith("cleaned_resemble_denoise"))
                return "resemble_denoise";
            if (tag.startsWith("cleaned_lavasr")) return "lavasr";
            if (tag.startsWith("cleaned_voicefixer")) return "voicefixer";
            if (tag.startsWith("cleaned_remove_echo")) return "remove_echo";
            if (tag.startsWith("cleaned_manual")) return "manual";
            return null;
        };

        if (sampleOrBitrate && typeof sampleOrBitrate === "object") {
            // Priority 1: Explicit params object attached
            if (sampleOrBitrate.params) {
                targetBitrate =
                    sampleOrBitrate.params.bitrate ||
                    sampleOrBitrate.bitrate ||
                    null;
                const inferredMethod =
                    sampleOrBitrate.params.method ||
                    sampleOrBitrate.method ||
                    inferMethodFromTag(sampleOrBitrate.bitrate);
                if (inferredMethod) {
                    cleaningParams = {
                        ...sampleOrBitrate.params,
                        method: inferredMethod,
                    };
                }
            }
            // Priority 2: It's a cleaning params object itself (e.g. from Batch settings)
            else if (sampleOrBitrate.method) {
                cleaningParams = sampleOrBitrate;
                targetBitrate = cleaningParams.bitrate;
            }
            // Priority 3: Simple sample object with bitrate property (from Laboratory preview buttons)
            else if (sampleOrBitrate.bitrate) {
                targetBitrate = sampleOrBitrate.bitrate;
            }
        } else {
            // Simple bitrate number passed directly
            targetBitrate = sampleOrBitrate;
        }

        console.log(`[performConversion] Resolved bitrate: ${targetBitrate}, cleaningParams:`, cleaningParams);

        // Validate we have enough info to proceed
        if (!targetBitrate && !cleaningParams && file.status !== "analyzed") {
            console.warn("[Optimizer] Missing target bitrate/params for non-analyzed file.");
            files[index] = { ...files[index], status: "error", error: "Please scan the file first or select a bitrate." };
            return;
        }

        // Force status change to move from "QUEUED" to "CONVERTING"
        files[index] = {
            ...files[index],
            status: "converting",
            progress: 0,
            progressTarget: 0,
            optimizationStartTime: Date.now(),
            optimizationDuration: null,
        };

        let receivedTerminalEvent = false;

        try {
            const currentFilePath = (file.path || "").normalize('NFC');
            const fileDir = currentFilePath.substring(0, currentFilePath.lastIndexOf('/'));
            const fileName = currentFilePath.substring(currentFilePath.lastIndexOf('/') + 1);
            
            // Logic: Always save to a folder ending in _OPTIMIZED. 
            // If the file's parent is already _OPTIMIZED, stay there.
            let outputDir;
            if (fileDir.endsWith("_OPTIMIZED")) {
                outputDir = fileDir;
            } else {
                outputDir = fileDir + "_OPTIMIZED";
            }
            const outputPath = outputDir + "/" + fileName;
            const inputPathToUse = (customInputPath || file.path || "").normalize('NFC');
            const currentBadQuality = badQualityPaths.has(file.path);
            const currentNote = fileNotes[file.path] || "";

            console.log(`[performConversion] Paths:`, { 
                input: inputPathToUse, 
                output: outputPath,
                bitrate: targetBitrate
            });

            let response;

            if (cleaningParams) {
                // Perform FULL CLEANING
                response = await bridgeFetch("/clean-audio", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        inputPath: inputPathToUse,
                        outputPath: outputPath,
                        mode: "full",
                        method: cleaningParams.method || "manual",
                        noiseStart: cleaningParams.noiseStart,
                        noiseEnd: cleaningParams.noiseEnd,
                        nrAmount: cleaningParams.nrAmount,
                        nrSensitivity: cleaningParams.nrSensitivity,
                        volume: cleaningParams.volume,
                        gain: cleaningParams.gain,
                        mix: cleaningParams.mix,
                        lavasr_denoise: cleaningParams.lavasr_denoise,
                        lavasr_superres: cleaningParams.lavasr_superres,
                        lavasr_mix: cleaningParams.lavasr_mix,
                        lavasr_gain: cleaningParams.lavasr_gain,
                        lavasr_input_sr: cleaningParams.lavasr_input_sr,
                        lavasr_batch: cleaningParams.lavasr_batch,
                        vf_mode: cleaningParams.vf_mode, // VoiceFixer mode
                        echo_strength: cleaningParams.echo_strength,
                        bitrate: cleaningParams.bitrate || 96, // Use user selected bitrate or default 96
                        badQuality: currentBadQuality,
                        note: currentNote,
                    }),
                });
            } else {
                // Standard bitrate conversion
                response = await bridgeFetch("/convert-audio", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        inputPath: inputPathToUse,
                        outputPath: outputPath,
                        bitrate: targetBitrate || file.recommended_bitrate,
                        badQuality: currentBadQuality,
                        note: currentNote,
                    }),
                });
            }

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                if (response.status === 409) {
                    const busyError = new Error(
                        errorData.error ||
                            errorData.message ||
                            "Another optimization is already running",
                    );
                    busyError.code = "BACKEND_BUSY";
                    throw busyError;
                }
                throw new Error(
                    errorData.error ||
                        errorData.message ||
                        `Server error: ${response.status}`,
                );
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = "";

            function processMessage(data) {
                console.log("[Optimization Progress]", data);
                if (data.status === "processing") {
                    console.log("[Optimizer] Backend started processing...");
                }
                if (
                    data.status === "progress" ||
                    data.status === "processing"
                ) {
                    const newProgress = Number(data.progress);
                    if (
                        shouldApplyProgressUpdate(
                            files[index]?.progress,
                            newProgress,
                        )
                    ) {
                        files[index] = {
                            ...files[index],
                            progress: Math.max(0, Math.min(100, newProgress)),
                        };
                        updateBatchEtaEstimate();
                    }
                } else if (
                    data.status === "success" ||
                    data.status === "completed"
                ) {
                    receivedTerminalEvent = true;
                    // Update batch stats
                    const fileDuration = files[index].duration;
                    const processDuration =
                        (Date.now() -
                            files[index].optimizationStartTime) /
                        1000;

                    totalProcessedDuration += fileDuration;
                    totalProcessTime += processDuration;
                    batchProcessedCount++;
                    recordEtaSample(fileDuration, processDuration);

                    // Calculate Speed ( Audio Seconds / Real Seconds )
                    if (totalProcessTime > 0) {
                        batchProcessingSpeed =
                            totalProcessedDuration / totalProcessTime;
                    }

                    // Calculate ETA with duration-aware history fallback.
                    updateBatchEtaEstimate();

                    files[index] = {
                        ...files[index],
                        status: "completed",
                        progress: 100,
                        optimizationDuration:
                            processDuration.toFixed(1),
                        optimizedSize: data.new_size || 0,
                        finalPath: data.output_path || outputPath,
                        optimizedMetadata: data.metadata || null,
                        manualSamples: data.manualSamples
                            ? data.manualSamples
                            : files[index].manualSamples,
                        actualOptimizedBitrate: data.bitrate,
                        lastOptimized: Date.now(), // Cache buster for player
                    };

                    // Keep Bad Quality / Note tags in sync on newly written optimized file.
                    syncFileTags(files[index].path, {
                        optimizedPath: files[index].finalPath,
                    });

                    // If this file is currently active in the player, refresh it to load new version
                    if (
                        globalActiveTrack &&
                        globalActiveTrack.path === files[index].path
                    ) {
                        const updatedTrack = {
                            ...globalActiveTrack,
                            optimizedPath: files[index].finalPath,
                            isOptimized: true,
                            lastOptimized: files[index].lastOptimized,
                            shouldPlay: isGlobalPlaying, // Preserve current play/pause state
                        };
                        setGlobalTrack(updatedTrack);
                    }

                    // Auto-deselect successfully processed file
                    if (selectedPaths.has(files[index].path)) {
                        const newSelected = new Set(selectedPaths);
                        newSelected.delete(files[index].path);
                        selectedPaths = newSelected;
                    }
                } else if (data.status === "error") {
                    receivedTerminalEvent = true;
                    throw new Error(
                        data.error || data.message || "Unknown error",
                    );
                }
            }

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split(/[\n\r]/);
                buffer = lines.pop() || "";

                for (const line of lines) {
                    if (!line.trim()) continue;
                    try {
                        let jsonStr = line;
                        const firstBrace = line.indexOf("{");
                        if (firstBrace !== -1)
                            jsonStr = line.substring(firstBrace);

                        const data = JSON.parse(jsonStr);
                        processMessage(data);
                    } catch (e) {
                        // If processMessage threw an error (e.g. status: "error"), we MUST handle it here
                        // to break out of the loop and mark the file as error.
                        if (e.message && !line.includes("%")) {
                            throw e; 
                        }

                        const percentMatch = line.match(/(\d+)%/);
                        if (percentMatch) {
                            const val = parseInt(percentMatch[1]);
                            if (
                                shouldApplyProgressUpdate(
                                    files[index]?.progress,
                                    val,
                                )
                            ) {
                                files[index] = {
                                    ...files[index],
                                    progress: Math.max(0, Math.min(100, val)),
                                };
                            }
                        }
                    }
                }
            }

            // Process any remaining tail in buffer (crucial for single-line JSON or non-LF terminated responses)
            if (buffer.trim()) {
                try {
                    let jsonStr = buffer.trim();
                    const firstBrace = jsonStr.indexOf("{");
                    if (firstBrace !== -1)
                        jsonStr = jsonStr.substring(firstBrace);

                    const data = JSON.parse(jsonStr);
                    processMessage(data);
                } catch (e) {
                    if (e.message) throw e;
                    console.warn("[Optimization] Could not parse remaining buffer:", buffer);
                }
            }

            if (!receivedTerminalEvent) {
                await recoverConversionAfterStreamClose(file.path);
            }
        } catch (e) {
            console.error("[Optimizer] Conversion failed:", e);
            files[index] = {
                ...files[index],
                status: "error",
                error: e.message || "Conversion failed",
            };
        } finally {
            // Cleanup
        }
    }

    async function analyzeAll() {
        if (isDemoBlocked("Analyze all")) return;
        const count = files.filter((f) => f.status === "idle").length;
        if (count === 0) return;

        if (!confirm(`Start analysis for ${count} files?`)) return;

        isProcessing = true;
        try {
            for (let i = 0; i < files.length; i++) {
                if (files[i]?.status === "idle") {
                    await analyzeFile(i);
                }
            }
        } finally {
            isProcessing = false;
        }
    }

    // optimizeAll function removed

    function showChart(index) {
        lastFocusedIndex = index;
        selectedFileForChart = files[index];
        console.log("Showing chart for:", selectedFileForChart.name);

        tick().then(() => {
            if (!chartContainer) return;
            if (chartInstance) chartInstance.destroy();

            const ctx = chartContainer.getContext("2d");

            // Normalize magnitudes for better visualization
            const magnitudes = selectedFileForChart.spectralData.magnitudes;
            const maxMag = Math.max(...magnitudes, 0.0001);
            const normalizedMags = magnitudes.map((m) => m / maxMag);

            chartInstance = new Chart(ctx, {
                type: "line",
                data: {
                    labels: selectedFileForChart.spectralData.frequencies.map(
                        (f) => (f / 1000).toFixed(1) + "k",
                    ),
                    datasets: [
                        {
                            label: "Spectral Magnitude",
                            data: normalizedMags,
                            borderColor: "#3b82f6",
                            backgroundColor: "rgba(59, 130, 246, 0.2)",
                            fill: true,
                            tension: 0.4,
                            pointRadius: 0,
                            borderWidth: 2,
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    animation: { duration: 400 },
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            backgroundColor: "#1e293b",
                            callbacks: {
                                label: () => "",
                            },
                        },
                    },
                    scales: {
                        y: {
                            display: false,
                            min: 0,
                            max: 1.1,
                        },
                        x: {
                            grid: { color: "rgba(255, 255, 255, 0.05)" },
                            ticks: {
                                color: "#64748b",
                                maxRotation: 0,
                                autoSkip: true,
                                maxTicksLimit: 12,
                                font: { size: 10 },
                            },
                        },
                    },
                },
            });
        });
    }

    // --- Comparison Logic ---
    let compareAudioElement = $state(null);

    function openReoptimizeModal(index) {
        const originalFile = files[index];
        if (!originalFile.finalPath) return;

        error = null; // Clear any previous errors
        // proxy object for the optimizer UI
        selectedFileForCompare = {
            ...originalFile,
            path: originalFile.finalPath, // SOURCE is now the optimized file
            name: "⚡️ " + originalFile.name, // Visual indicator
            isProxy: true,
            originalIndex: index,
            manualSamples: [], // Reset history for this new session
        };

        lastFocusedIndex = index;
        if (files[index].compareSamples) files[index].compareSamples = [];
        if (files[index].manualSamples) files[index].manualSamples = [];
        activeSampleUrl = null;
        comparePlaybackTime = 0;
        zoomedSpectrogramUrl = null;
        showSpectrogramModal = false;

        dispatchAudioCommand("pause-all", null);
        showCompareModal = true;
    }

    async function restoreOriginalSegment(startTime, endTime, bitrateConfig = null) {
        if (isDemoBlocked("Restore from original")) return;
        if (!selectedFileForCompare) return;

        // Find index of the selected file
        const index = files.findIndex(
            (f) => f.path === selectedFileForCompare.path,
        );
        if (index === -1) return;

        const file = files[index];
        if (!file.finalPath) return;

        files[index].status = "analyzing"; // Use analyzing as a busy state
        files[index].progress = 50;
        files[index].progressMessage = "Restoring segment from original...";

        try {
            const res = await bridgeFetch("/restore-original", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    originalPath: file.path,
                    optimizedPath: file.finalPath,
                    startTime,
                    endTime,
                    bitrateConfig
                }),
            });

            const reader = res.body.getReader();
            const decoder = new TextDecoder();
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                const chunk = decoder.decode(value);
                const lines = chunk.split("\n");
                for (const line of lines) {
                    if (!line.trim()) continue;
                    try {
                        const data = JSON.parse(line);
                        if (data.status === "done" || data.status === "completed") {
                            files[index] = {
                                ...files[index],
                                status: "completed",
                                progress: 100,
                                progressMessage: "Restoration Done!",
                                optimizedSize: data.new_size || files[index].optimizedSize,
                                actualOptimizedBitrate: data.bitrate || files[index].actualOptimizedBitrate,
                                optimizedMetadata: data.metadata || files[index].optimizedMetadata,
                                lastOptimized: Date.now(), // Cache buster for UI/player
                                shouldPlay: isGlobalPlaying,
                            };
                            // Refresh the file list if needed, but status update should be enough for UI
                            if (
                                globalActiveTrack &&
                                globalActiveTrack.path === files[index].path
                            ) {
                                setGlobalTrack(files[index]);
                            }
                        } else if (data.status === "error") {
                            files[index].status = "error";
                            files[index].error = data.error;
                        }
                    } catch (e) {
                        console.error("Failed to parse restore progress", e);
                    }
                }
            }
        } catch (e) {
            files[index].status = "error";
            files[index].error = e.message;
        }
    }

    function openCompareModal(index) {
        lastFocusedIndex = index;
        selectedFileForCompare = files[index];
        error = null; // Clear any previous errors
        // Load existing manual samples for this file if they exist
        // derived comparisonSamples will auto-update
        if (!selectedFileForCompare.manualSamples) {
            selectedFileForCompare.manualSamples = [];
        }
        activeSampleUrl = selectedFileForCompare.path; // Set to original path
        comparePlaybackTime = 0;
        zoomedSpectrogramUrl = null;
        showSpectrogramModal = false;

        // Initialize empty manual samples if not exist
        if (!selectedFileForCompare.manualSamples) {
            selectedFileForCompare.manualSamples = [];
        }

        // Sync to first sample if it exists for consistency
        if (comparisonSamples.length > 0) {
            const first = comparisonSamples[0];
            if (first.params) {
                cleanMethod = first.params.method || cleanMethod;
                if (first.params.bitrate !== undefined)
                    targetBitrateForClean = first.params.bitrate;
            }
        }

        // Pause global player if it's playing
        dispatchAudioCommand("pause-all", null);

        showCompareModal = true;
    }

    async function generateComparison() {
        if (isDemoBlocked("Comparison sample generation")) return;
        if (!selectedFileForCompare) return;

        // Validation
        if (compareStartTime >= selectedFileForCompare.duration) {
            error = `Start time (${(compareStartTime / 60).toFixed(1)}m) exceeds lecture duration (${(selectedFileForCompare.duration / 60).toFixed(1)}m)`;
            return;
        }

        if (
            compareStartTime + compareDuration >
            selectedFileForCompare.duration
        ) {
            const possibleDuration = Math.floor(
                selectedFileForCompare.duration - compareStartTime,
            );
            if (possibleDuration < 5) {
                error =
                    "Not enough audio left at this start time (need at least 5s).";
                return;
            }
            // Auto-adjust or warn? Let's warn and stop.
            error = `Selected range (${(compareStartTime / 60).toFixed(1)}m to ${((compareStartTime + compareDuration) / 60).toFixed(1)}m) exceeds lecture length. Max duration from here: ${possibleDuration}s`;
            return;
        }

        // Fetch samples
        isFetchingSpectrogram = true;

        isComparing = true;
        error = null;
        try {
            const res = await bridgeFetch("/compare-samples", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    filePath: selectedFileForCompare.path,
                    startTime: compareStartTime,
                    duration: compareDuration,
                    bitrates: compareBitrates,
                }),
            });
            const respData = await res.json();
            if (respData.status === "success") {
                // Merge manual samples with new auto-generated ones
                if (!selectedFileForCompare.compareSamples) {
                    selectedFileForCompare.compareSamples = [];
                }
                selectedFileForCompare.compareSamples = respData.samples;
                if (comparisonSamples.length > 0) {
                    // Start with 96kbps if available, otherwise default to first (Original)
                    const preferredSample =
                        comparisonSamples.find((s) => s.bitrate === 96) ||
                        comparisonSamples[0];
                    activeSampleUrl = preferredSample.url;
                    pendingCompareSeek = { time: 0, shouldPlay: true };
                }
            } else {
                throw new Error(respData.error);
            }
        } catch (e) {
            error = "Comparison failed: " + e.message;
        } finally {
            isComparing = false;
        }
    }

    function switchSample(url) {
        if (!url || url === activeSampleUrl) return;

        const wasPaused = compareAudioElement
            ? compareAudioElement.paused
            : false;
        const time = compareAudioElement
            ? compareAudioElement.currentTime
            : comparePlaybackTime;

        // Sync parameters if this sample has them
        const sample = comparisonSamples.find((s) => s.url === url);
        if (sample && sample.params) {
            cleanMethod = sample.params.method || cleanMethod;
            if (sample.params.volume !== undefined)
                volumeGain = sample.params.volume;
            if (sample.params.bitrate !== undefined)
                targetBitrateForClean = sample.params.bitrate;
            if (sample.params.nrAmount !== undefined)
                noiseReductionAmount = sample.params.nrAmount;
            if (sample.params.nrSensitivity !== undefined)
                noiseSensitivity = sample.params.nrSensitivity;
            if (sample.params.gain !== undefined)
                resembleGain = sample.params.gain;
            if (sample.params.mix !== undefined)
                resembleMix = sample.params.mix;
            if (sample.params.lavasr_denoise !== undefined)
                lavasrDenoise = sample.params.lavasr_denoise;
            if (sample.params.lavasr_superres !== undefined)
                lavasrSuperres = sample.params.lavasr_superres;
            if (sample.params.lavasr_mix !== undefined)
                lavasrMix = sample.params.lavasr_mix;
            if (sample.params.lavasr_gain !== undefined)
                lavasrGain = sample.params.lavasr_gain;
            if (sample.params.lavasr_input_sr !== undefined)
                lavasrInputSr = sample.params.lavasr_input_sr;
            if (sample.params.lavasr_batch !== undefined)
                lavasrBatch = sample.params.lavasr_batch;
            if (sample.params.vf_mode !== undefined)
                vfMode = sample.params.vf_mode;
            if (sample.params.echo_strength !== undefined)
                echoReduction = sample.params.echo_strength;
        }

        // Use pending compare seek to ensure it applies AFTER metadata loads
        pendingCompareSeek = {
            time: time,
            shouldPlay: !wasPaused,
        };

        activeSampleUrl = url;
    }

    function handleCompareMetadata() {
        if (pendingCompareSeek && compareAudioElement) {
            compareAudioElement.currentTime = pendingCompareSeek.time;
            if (pendingCompareSeek.shouldPlay) {
                dispatchAudioCommand("PAUSE_ALL");
                compareAudioElement
                    .play()
                    .catch((e) => console.error("Sync play failed:", e));
            }
            pendingCompareSeek = null;
        }
    }

    async function fetchZoomedSpectrogram() {
        if (isDemoBlocked("Spectrogram generation")) return;
        if (!selectedFileForCompare) return;
        isFetchingSpectrogram = true;
        spectrogramProgress = "Initializing...";
        zoomedSpectrogramUrl = null;
        error = null;
        try {
            console.log("🔍 [DEBUG] Spectrogram fetch started:", {
                filePath: selectedFileForCompare.path,
                offset: compareStartTime,
                duration: compareDuration,
            });
            console.log(
                "%c🌐 [FETCH] Sending request to:",
                "color: #a855f7; font-weight: bold;",
                "http://localhost:3000/zoomed-spectrogram",
            );
            const res = await bridgeFetch("/zoomed-spectrogram", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    filePath: selectedFileForCompare.path,
                    offset: compareStartTime,
                    duration: compareDuration,
                }),
            });

            console.log(
                "📡 [DEBUG] Response received:",
                res.status,
                res.statusText,
            );

            if (!res.ok) {
                const errText = await res.text();
                console.error("❌ [DEBUG] Fetch failed:", errText);
                throw new Error(
                    errText || `Server responded with ${res.status}`,
                );
            }

            const reader = res.body.getReader();
            const decoder = new TextDecoder();
            let resultData = null;
            let lastError = null;
            let buffer = "";

            while (true) {
                console.log("⏳ [DEBUG] Waiting for stream chunk...");
                const { done, value } = await reader.read();
                console.log(
                    "📥 [DEBUG] Chunk received. done:",
                    done,
                    "value length:",
                    value?.length,
                );
                if (done) {
                    console.log("🛑 [DEBUG] Reader done signal received.");
                    break;
                }

                const chunk = decoder.decode(value, { stream: true });
                console.log(
                    "🧩 [DEBUG] Raw chunk string (first 100 char):",
                    chunk.substring(0, 100),
                );

                buffer += chunk;
                const lines = buffer.split("\n");
                buffer = lines.pop() || "";

                for (const line of lines) {
                    const trimmed = line.trim();
                    if (!trimmed) continue;
                    try {
                        console.log(
                            "%c📄 [SPECTROGRAM] Raw Data:",
                            "color: #3b82f6; font-weight: bold;",
                            trimmed.substring(0, 100),
                        );
                        const data = JSON.parse(trimmed);
                        if (
                            data.status === "progress" ||
                            data.status === "processing"
                        ) {
                            const pct = data.progress || 0;
                            console.log(
                                `%c📊 [PROGRESS] ${pct}% - ${data.message}`,
                                "color: #10b981; font-weight: bold;",
                            );
                            spectrogramProgress =
                                data.message || `Analyzing... ${pct}%`;
                        } else if (
                            data.status === "success" ||
                            data.status === "completed"
                        ) {
                            console.log(
                                "%c✅ [SUCCESS] Spectrogram analysis complete!",
                                "color: #059669; font-size: 14px; font-weight: bold;",
                            );
                            resultData = data;
                            spectrogramProgress = "";
                        } else if (data.status === "error") {
                            console.error(
                                "%c❌ [SERVER-ERROR] Analysis failed:",
                                "color: #dc2626; font-size: 14px; font-weight: bold;",
                                data,
                            );
                            spectrogramProgress = "";
                            const err = data.error || "";
                            const det = data.details || "";
                            lastError =
                                err && det && err !== det
                                    ? `${err}: ${det}`
                                    : det || err || "Analysis failed";
                        }
                    } catch (e) {
                        console.error(
                            "%c⚠️ [NDJSON-PARSE-ERROR]",
                            "color: #f59e0b; font-weight: bold;",
                            e,
                            "Line content:",
                            trimmed,
                        );
                    }
                }
            }

            console.log(
                "🏁 [DEBUG] Stream loop exited. Buffer left:",
                buffer.trim(),
            );
            // Parse any remaining data in buffer after stream ends
            if (buffer.trim()) {
                try {
                    console.log(
                        "📄 [DEBUG] Parsing final buffer segment:",
                        buffer.trim(),
                    );
                    const data = JSON.parse(buffer.trim());
                    if (data.status === "success") {
                        resultData = data;
                        spectrogramProgress = "";
                    } else if (data.status === "error") {
                        spectrogramProgress = "";
                        const err = data.error || "";
                        const det = data.details || "";
                        lastError =
                            err && det && err !== det
                                ? `${err}: ${det}`
                                : det || err || "Analysis failed";
                    }
                } catch (e) {
                    console.warn(
                        "⚠️ [DEBUG] Could not parse final buffer as JSON:",
                        e,
                    );
                }
            }

            if (resultData && resultData.status === "success") {
                console.log("🖼️ [DEBUG] Displaying spectrogram modal...");
                zoomedSpectrogramUrl = resultData.spectrogram_image;
                showSpectrogramModal = true;
            } else {
                console.warn(
                    "⚠️ [DEBUG] Finish reached without success object. resultData:",
                    resultData,
                    "lastError:",
                    lastError,
                );
                throw new Error(
                    lastError ||
                        "No spectrogram data received from analysis script",
                );
            }
        } catch (e) {
            console.error("❌ [DEBUG] fetchZoomedSpectrogram catch block:", e);
            error = "Spectrogram Error: " + e.message;
        } finally {
            console.log(
                "🔚 [DEBUG] fetchZoomedSpectrogram finally block. Current progress:",
                spectrogramProgress,
            );
            isFetchingSpectrogram = false;
        }
    }

    let isDraggingSpec = $state(false);
    let spectrogramZoom = $state(1);

    // Manual noise reduction settings
    let noiseReductionAmount = $state(0.7); // 70% reduction
    let noiseSensitivity = $state(1.5); // 1.5 sensitivity

    // Ensure minimum duration (0.1s)

    function playNoiseSegment() {
        if (!compareAudioElement) return;

        // Pause and seek
        compareAudioElement.pause();
        compareAudioElement.currentTime = noiseStart;
        dispatchAudioCommand("PAUSE_ALL");
        compareAudioElement.play();
        isPlayingNoise = true;

        const checkEnd = () => {
            if (compareAudioElement.currentTime >= noiseEnd) {
                compareAudioElement.pause();
                isPlayingNoise = false;
                compareAudioElement.removeEventListener("timeupdate", checkEnd);
            }
        };
        compareAudioElement.addEventListener("timeupdate", checkEnd);
    }

    async function runCleanup() {
        if (isDemoBlocked("Preview cleanup")) return;
        if (!selectedFileForCompare) return;
        isCleaning = true;
        cleanProgress = 0;
        cleanProgressTarget = 0;

        // Clear any existing interval
        if (cleanProgressInterval) {
            clearInterval(cleanProgressInterval);
            cleanProgressInterval = null;
        }

        // Start smooth progress animation
        cleanProgressInterval = setInterval(() => {
            if (cleanProgress < cleanProgressTarget) {
                cleanProgress = Math.min(
                    cleanProgress + 1,
                    cleanProgressTarget,
                );
            }
        }, 50);

        // Find current bitrate context - default to safe numeric value
        const activeSample = comparisonSamples.find(
            (s) => s.url === activeSampleUrl,
        );
        let targetBitrate = 128;
        if (activeSample) {
            if (activeSample.bitrate === "original") {
                targetBitrate = 320;
            } else if (typeof activeSample.bitrate === "number") {
                targetBitrate = activeSample.bitrate;
            } else if (typeof activeSample.bitrate === "string") {
                const parsed = parseInt(activeSample.bitrate);
                if (!isNaN(parsed)) {
                    targetBitrate = parsed;
                } else {
                    // It's likely a cleaned_manual_... tag, use high quality default
                    targetBitrate = 320;
                }
            }
        }

        try {
            const res = await bridgeFetch("/clean-audio", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    inputPath: selectedFileForCompare.path,
                    mode: "preview",
                    method: cleanMethod,
                    offset: compareStartTime,
                    duration: compareDuration,
                    noiseStart:
                        cleanMethod === "manual" ? noiseStart : undefined,
                    noiseEnd: cleanMethod === "manual" ? noiseEnd : undefined,
                    nrAmount:
                        cleanMethod === "manual"
                            ? noiseReductionAmount
                            : undefined,
                    nrSensitivity:
                        cleanMethod === "manual" ? noiseSensitivity : undefined,
                    volume: volumeGain,
                    gain: resembleGain,
                    mix: resembleMix,
                    lavasr_denoise: lavasrDenoise,
                    lavasr_superres: lavasrSuperres,
                    lavasr_mix: lavasrMix,
                    lavasr_gain: lavasrGain,
                    lavasr_input_sr: lavasrInputSr,
                    lavasr_batch: lavasrBatch,
                    vf_mode: vfMode,
                    echo_strength: echoReduction,
                    bitrate: targetBitrate,
                }),
            });

            if (!res.ok) {
                throw new Error(`HTTP ${res.status} while generating preview`);
            }
            if (!res.body) {
                throw new Error("Preview stream is empty");
            }

            const reader = res.body.getReader();
            const decoder = new TextDecoder();
            let buffer = "";
            let completedReceived = false;
            let backendError = null;

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split(/[\n\r]/);
                buffer = lines.pop() || "";

                for (const line of lines) {
                    if (!line.trim()) continue;

                    let data = null;
                    try {
                        let jsonStr = line;
                        const firstBrace = line.indexOf("{");
                        if (firstBrace !== -1)
                            jsonStr = line.substring(firstBrace);
                        data = JSON.parse(jsonStr);
                    } catch (_e) {
                        const percentMatch = line.match(/(\d+)%/);
                        if (percentMatch) {
                            cleanProgressTarget = parseInt(percentMatch[1]);
                        }
                        continue;
                    }

                    if (data.status === "processing") {
                        cleanProgressTarget = data.progress;
                        continue;
                    }

                    if (data.status === "error") {
                        backendError =
                            data.message || data.error || "Preview failed";
                        continue;
                    }

                    if (data.status === "completed") {
                        completedReceived = true;
                        const isManual = cleanMethod === "manual";
                        const cleanMethodLabel = cleanMethod
                            .replace("_denoise", "")
                            .toUpperCase();
                        const uniqueBitrate = isManual
                            ? `cleaned_${cleanMethod}_${Date.now()}`
                            : `cleaned_${cleanMethod}`;

                        const label = isManual
                            ? `Manual (Str:${(noiseReductionAmount * 100).toFixed(0)}% / Sens:${noiseSensitivity.toFixed(1)} / Gain:${volumeGain.toFixed(1)}x)`
                            : cleanMethod === "lavasr"
                              ? `(LAVASR / Gain:${lavasrGain.toFixed(1)}x / In:${Math.round(lavasrInputSr / 1000)}k / DN:${lavasrDenoise ? "On" : "Off"} / SR:${lavasrSuperres ? "48k" : "Off"} / Mix:${Math.round(lavasrMix * 100)}%${lavasrBatch ? " / Batch" : ""})`
                            : cleanMethod === "voicefixer"
                              ? `(VOICEFIXER / Mode:${vfMode})`
                              : cleanMethod === "remove_echo"
                                ? `(REMOVE ECHO / Strength:${(
                                      echoReduction * 100
                                  ).toFixed(0)}%)`
                              : `(${cleanMethodLabel}${cleanMethod.includes("resemble") ? ` / Gain:${resembleGain.toFixed(1)}x / Mix:${resembleMix.toFixed(2)}` : ` / Gain:${volumeGain.toFixed(1)}x`})`;

                        const newSample = {
                            bitrate: uniqueBitrate,
                            label: label,
                            url: data.url,
                            isCleaned: true,
                            isManual: isManual,
                            params: {
                                method: cleanMethod,
                                noiseStart,
                                noiseEnd,
                                nrAmount: noiseReductionAmount,
                                nrSensitivity: noiseSensitivity,
                                volume: volumeGain,
                                gain: resembleGain,
                                mix: resembleMix,
                                lavasr_denoise: lavasrDenoise,
                                lavasr_superres: lavasrSuperres,
                                lavasr_mix: lavasrMix,
                                lavasr_gain: lavasrGain,
                                lavasr_input_sr: lavasrInputSr,
                                lavasr_batch: lavasrBatch,
                                vf_mode: vfMode,
                                echo_strength: echoReduction,
                            },
                        };

                        if (
                            isManual ||
                            cleanMethod === "resemble_denoise" ||
                            cleanMethod === "lavasr" ||
                            cleanMethod === "voicefixer" ||
                            cleanMethod === "remove_echo"
                        ) {
                            if (!selectedFileForCompare.manualSamples) {
                                selectedFileForCompare.manualSamples = [];
                            }

                            if (!isManual) {
                                selectedFileForCompare.manualSamples =
                                    selectedFileForCompare.manualSamples.filter(
                                        (s) => s.bitrate !== uniqueBitrate,
                                    );
                            }

                            selectedFileForCompare.manualSamples.push(newSample);
                        }

                        lastUsedCleaningParams = {
                            method: cleanMethod,
                            noiseStart,
                            noiseEnd,
                            nrAmount: noiseReductionAmount,
                            nrSensitivity: noiseSensitivity,
                            volume: volumeGain,
                            gain: resembleGain,
                            mix: resembleMix,
                            lavasr_denoise: lavasrDenoise,
                            lavasr_superres: lavasrSuperres,
                            lavasr_mix: lavasrMix,
                            lavasr_gain: lavasrGain,
                            lavasr_input_sr: lavasrInputSr,
                            lavasr_batch: lavasrBatch,
                            vf_mode: vfMode,
                            echo_strength: echoReduction,
                            bitrate: targetBitrate,
                        };

                        switchSample(data.url);
                        cleanProgressTarget = 100;
                        cleanProgress = 100;
                    }
                }
            }

            if (backendError) {
                throw new Error(backendError);
            }
            if (!completedReceived) {
                throw new Error(
                    "Preview did not return a completed result. Check backend logs.",
                );
            }
        } catch (e) {
            console.error("Cleanup failed:", e);
            error = "Cleaning failed: " + e.message;
            showTransientToast(`Optimization Failed: ${e.message}`, "error");
        } finally {
            isCleaning = false;
            if (cleanProgressInterval) {
                clearInterval(cleanProgressInterval);
                cleanProgressInterval = null;
            }
        }
    }

    function removeBitrate(br) {
        compareBitrates = compareBitrates.filter((b) => b !== br);
    }

    function addBitrate(e) {
        if (e.key === "Enter") {
            const val = parseInt(e.target.value);
            if (val && !compareBitrates.includes(val)) {
                compareBitrates = [...compareBitrates, val].sort(
                    (a, b) => b - a,
                );
                e.target.value = "";
            }
        }
    }

    function toggleFlag(path) {
        if (flaggedPaths.has(path)) {
            flaggedPaths.delete(path);
        } else {
            flaggedPaths.add(path);
        }
        // Force reactivity for Set
        flaggedPaths = new Set(flaggedPaths);
    }

    function toggleDenoised(path) {
        if (denoisedPaths.has(path)) {
            denoisedPaths.delete(path);
        } else {
            denoisedPaths.add(path);
        }
        // Force reactivity for Set
        denoisedPaths = new Set(denoisedPaths);
    }

    function toggleBadQuality(path) {
        if (badQualityPaths.has(path)) {
            badQualityPaths.delete(path);
        } else {
            badQualityPaths.add(path);
        }
        // Force reactivity for Set
        badQualityPaths = new Set(badQualityPaths);
        syncFileTags(path, { badQuality: badQualityPaths.has(path) });
    }
    function handleKeydown(e) {
        if (e.key === "Escape") {
            if (showSpectrogramModal) {
                showSpectrogramModal = false;
                return;
            }
            selectedFileForChart = null;
            selectedFileForCompare = null;
            showCompareModal = false;
            showBatchSettingsModal = false;
            showHelp = false;
        }

        // Comparison Player Controls
        if (selectedFileForCompare && compareAudioElement) {
            if (e.key === "ArrowRight") {
                e.preventDefault();
                e.stopPropagation();
                compareAudioElement.currentTime = Math.min(
                    compareAudioElement.duration,
                    compareAudioElement.currentTime + 2,
                );
            } else if (e.key === "ArrowLeft") {
                e.preventDefault();
                e.stopPropagation();
                compareAudioElement.currentTime = Math.max(
                    0,
                    compareAudioElement.currentTime - 2,
                );
            } else if (e.key === "ArrowUp") {
                // Only prevent default if we are actually handling the sample switch
                // This local trainer is for switching bitrates INSIDE the compare modal
                const currentIndex = comparisonSamples.findIndex(
                    (s) => s.url === activeSampleUrl,
                );
                if (currentIndex > 0) {
                    e.preventDefault();
                    e.stopPropagation();
                    switchSample(comparisonSamples[currentIndex - 1].url);
                }
            } else if (e.key === "ArrowDown") {
                const currentIndex = comparisonSamples.findIndex(
                    (s) => s.url === activeSampleUrl,
                );
                if (
                    currentIndex !== -1 &&
                    currentIndex < comparisonSamples.length - 1
                ) {
                    e.preventDefault();
                    e.stopPropagation();
                    switchSample(comparisonSamples[currentIndex + 1].url);
                }
            } else if (e.key === " ") {
                e.preventDefault();
                e.stopPropagation();
                if (compareAudioElement.paused) {
                    dispatchAudioCommand("PAUSE_ALL");
                    compareAudioElement.play().catch(() => {});
                } else {
                    compareAudioElement.pause();
                }
            }
        }
    }
</script>

<svelte:window onkeydown={handleKeydown} />

<div
    class="flex flex-col flex-grow h-full min-h-0 bg-slate-50 dark:bg-[#0f172a] text-slate-900 dark:text-slate-200 overflow-hidden font-sans w-full"
>
    <!-- Header/Controls -->
    <div
        class="p-6 border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/50 backdrop-blur-xl relative z-50 shadow-sm dark:shadow-none"
    >
        <div class="flex flex-wrap items-center gap-4 justify-between">
            <div class="flex items-center gap-3">
                <div
                    class="p-2 bg-blue-600 rounded-lg shadow-lg shadow-blue-500/20"
                >
                    <Activity size={24} class="text-white" />
                </div>
                <div>
                    <div class="flex items-center gap-2">
                        <h1
                            class="text-2xl font-black tracking-tight text-slate-900 dark:text-white"
                        >
                            Audio Optimizer
                        </h1>
                        {#if globalUiState.isProcessing}
                            <div
                                class="w-4 h-4 rounded-full border-2 border-blue-200 border-t-blue-600 animate-spin"
                                title="Processing"
                            ></div>
                        {/if}
                    </div>
                    <HelpModal bind:showHelp />
                    <p
                        class="text-slate-500 dark:text-slate-400 text-sm font-medium"
                    >
                        Analyze quality and optimize bitrate
                    </p>
                </div>
            </div>

            {#if thermalThrottling || isInterFilePausing}
                <div
                    class="mx-auto flex items-center gap-3 px-4 py-2 bg-rose-500/10 dark:bg-rose-500/5 border border-rose-500/20 rounded-2xl animate-in fade-in slide-in-from-top-4 duration-500 shadow-sm"
                >
                    <div class="flex items-center gap-2">
                        {#if thermalThrottling}
                            <div class="p-1.5 bg-rose-500/20 rounded-lg shrink-0">
                                <Thermometer
                                    size={15}
                                    class="text-rose-500 animate-pulse"
                                />
                            </div>
                            <div class="flex items-baseline gap-2">
                                <span
                                    class="text-[11px] font-black text-rose-500 uppercase tracking-[0.14em] leading-none"
                                    >Cooling</span
                                >
                                <span
                                    class="text-xs font-black tabular-nums text-slate-700 dark:text-slate-300"
                                >
                                    {Math.floor(
                                        thermalThrottlingRemaining / 60,
                                    )}:{String(
                                        thermalThrottlingRemaining % 60,
                                    ).padStart(2, "0")}
                                </span>
                            </div>
                        {:else}
                            <div class="p-1.5 bg-blue-500/20 rounded-lg">
                                <Coffee
                                    size={16}
                                    class="text-blue-500 animate-pulse"
                                />
                            </div>
                            <div class="flex flex-col">
                                <span
                                    class="text-[10px] font-black text-blue-500 uppercase tracking-widest leading-none mb-1"
                                    >Inter-file Pause</span
                                >
                                <span
                                    class="text-xs font-black tabular-nums text-slate-700 dark:text-slate-300"
                                >
                                    {Math.floor(
                                        interFilePauseRemaining / 60,
                                    )}:{String(
                                        interFilePauseRemaining % 60,
                                    ).padStart(2, "0")} left
                                </span>
                            </div>
                        {/if}
                    </div>

                    <button
                        onclick={() => {
                            thermalThrottling = false;
                            isInterFilePausing = false;
                            showTransientToast(
                                "Resuming work manually...",
                                "info",
                            );
                        }}
                        class="px-4 py-1.5 bg-slate-900 dark:bg-white text-white dark:text-slate-900 text-[9px] font-black uppercase tracking-widest rounded-xl hover:scale-105 active:scale-95 transition-all shadow-md"
                    >
                        Resume now
                    </button>
                </div>
            {/if}

            <div class="flex items-center gap-3">
                <div class="relative group flex-1 md:flex-none">
                    <input
                        type="text"
                        bind:value={folderPath}
                        placeholder="Path to audio folder..."
                        class="w-full md:w-64 lg:w-96 bg-white dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 rounded-xl px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-blue-500/50 transition-all text-slate-800 dark:text-slate-200 placeholder:text-slate-400 dark:placeholder:text-slate-500 shadow-sm dark:shadow-inner"
                    />

                    <button
                        onclick={pickFolder}
                        disabled={DEMO_MODE}
                        class="absolute right-2 top-2 p-1.5 bg-slate-100 dark:bg-slate-700 hover:bg-slate-200 dark:hover:bg-slate-600 rounded-lg text-slate-400 dark:text-slate-400 hover:text-blue-600 dark:hover:text-blue-400 transition-all active:scale-95"
                        title="Pick Folder (macOS)"
                    >
                        <FolderOpen size={18} />
                    </button>
                </div>
                <button
                    onclick={scanFolder}
                    disabled={isScanning}
                    class="flex items-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 dark:disabled:bg-slate-700 text-white rounded-xl font-medium shadow-lg shadow-blue-500/20 hover:shadow-blue-500/30 transition-all active:scale-95 disabled:cursor-not-allowed"
                >
                    Scan
                </button>

                <!-- Settings Button -->
                <div class="relative">
                    <button
                        onclick={() => (showSettingsPopup = !showSettingsPopup)}
                        class="p-2.5 bg-white dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 hover:border-blue-400 dark:hover:border-blue-500/50 rounded-xl text-slate-400 dark:text-slate-500 hover:text-blue-600 dark:hover:text-blue-400 transition-all active:scale-95 shadow-sm"
                        title="Application Settings"
                    >
                        <Settings2
                            size={20}
                            class={showSettingsPopup ? "text-blue-500" : ""}
                        />
                    </button>

                    {#if showSettingsPopup}
                        <!-- Settings Popup Backdrop -->
                        <button
                            class="fixed inset-0 z-[60] cursor-default"
                            aria-label="Close settings"
                            title="Close settings"
                            onclick={() => (showSettingsPopup = false)}
                        ></button>

                        <div
                            class="absolute right-0 mt-3 w-72 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-2xl z-[70] p-4 animate-in fade-in zoom-in-95 duration-200 origin-top-right"
                        >
                            <div class="flex items-center gap-2 mb-4">
                                <Settings2 size={16} class="text-blue-500" />
                                <span
                                    class="text-xs font-black uppercase tracking-widest text-slate-400"
                                    >General Settings</span
                                >
                            </div>

                            <div class="space-y-4">
                                <label
                                    class="flex items-center justify-between cursor-pointer group"
                                >
                                    <div class="flex flex-col">
                                        <span
                                            class="text-[11px] font-bold text-slate-700 dark:text-slate-300 group-hover:text-blue-500 transition-colors"
                                            >Remember Scroll</span
                                        >
                                        <span class="text-[9px] text-slate-400"
                                            >Restore list position when reopening</span
                                        >
                                    </div>
                                    <input
                                        type="checkbox"
                                        bind:checked={rememberScroll}
                                        class="w-4 h-4 rounded border-slate-300 dark:border-slate-700 text-blue-600 focus:ring-blue-500 cursor-pointer"
                                    />
                                </label>

                                <button
                                    onclick={restartBridge}
                                    disabled={isRestartingBridge || DEMO_MODE}
                                    class="w-full flex items-center justify-between px-3 py-3 rounded-xl border border-amber-200 dark:border-amber-900/40 bg-amber-50 dark:bg-amber-950/20 hover:bg-amber-100 dark:hover:bg-amber-950/30 disabled:opacity-60 transition-all"
                                >
                                    <div class="flex flex-col items-start text-left">
                                        <span
                                            class="text-[11px] font-bold text-amber-700 dark:text-amber-300"
                                            >Reload Bridge</span
                                        >
                                        <span class="text-[9px] text-amber-600/80 dark:text-amber-400/80"
                                            >Restart backend bridge and reload page</span
                                        >
                                    </div>
                                    <div class="text-amber-500 font-black text-xs">
                                        {#if isRestartingBridge}...{:else}↻{/if}
                                    </div>
                                </button>
                            </div>
                        </div>
                    {/if}
                </div>
            </div>
        </div>

    </div>

    {#if isRestartingBridge}
        <div class="fixed inset-0 z-[20000] bg-slate-950/70 backdrop-blur-md flex items-center justify-center p-6">
            <div class="w-full max-w-md rounded-3xl border border-slate-700/70 bg-slate-900/90 shadow-2xl px-8 py-7 text-center">
                <div class="mx-auto mb-5 w-12 h-12 rounded-full border-4 border-slate-700 border-t-blue-400 animate-spin"></div>
                <div class="text-lg font-black text-white tracking-tight">
                    Идет перезагрузка моста
                </div>
                <div class="mt-2 text-sm text-slate-300">
                    {restartBridgeMessage}
                </div>
                <div class="mt-4 text-[10px] uppercase tracking-[0.2em] text-slate-500">
                    Страница обновится автоматически
                </div>
            </div>
        </div>
    {/if}

    <!-- Main Content -->
    <div
        bind:this={scrollContainer}
        onscroll={(e) => {
            if (rememberScroll && !isRestoringOptimizerScroll) {
                localStorage.setItem(
                    OPTIMIZER_SCROLL_KEY,
                    String(e.currentTarget.scrollTop),
                );
            }
        }}
        class="flex-1 overflow-auto p-4 lg:p-6 scrollbar-thin scrollbar-thumb-slate-300 dark:scrollbar-thumb-slate-700 scrollbar-track-transparent pb-32"
    >
        <StatsHeader
            {stats}
            selectedPathsCount={selectedPaths.size}
            filesCount={files.length}
            {isProcessing}
            {analyzeAll}
            {openBatchSettings}
        />

        {#if DEMO_MODE}
            <div
                class="mb-6 p-4 bg-amber-500/10 border border-amber-500/30 rounded-2xl text-amber-700 dark:text-amber-300"
            >
                <div class="text-sm font-bold uppercase tracking-wide">
                    Public Demo Mode
                </div>
                <div class="text-sm mt-1">
                    This is a frontend-only demo build.
                </div>
                <div class="text-sm mt-1">
                    Local file access and audio processing are disabled here because they require the desktop bridge backend (Node + Python + FFmpeg).
                </div>
                <div class="text-sm mt-1">
                    To use full functionality on your computer, install and run the project locally using the setup guide in README.md (or environment restore steps in RESTORE.md).
                </div>
                <div class="mt-3">
                    <button
                        onclick={openFocusModeDemo}
                        class="px-3 py-1.5 rounded-lg border border-amber-500/40 bg-amber-500/10 hover:bg-amber-500/20 text-amber-800 dark:text-amber-200 text-xs font-bold uppercase tracking-wide transition-colors"
                    >
                        Open Batch Optimization Demo
                    </button>
                </div>
            </div>
        {/if}

        {#if error}
            <div
                class="mb-6 p-4 bg-red-500/10 border border-red-500/20 rounded-2xl flex items-center justify-between text-red-400 animate-in zoom-in-95 duration-300"
            >
                <div class="flex items-center gap-3">
                    <AlertCircle size={20} />
                    <span>{error}</span>
                </div>
                <button
                    onclick={() => (error = null)}
                    class="p-1 hover:bg-red-500/10 rounded-full transition-colors"
                >
                    <X size={16} />
                </button>
            </div>
        {/if}

        <EmptyState filesCount={files.length} {isScanning} />

        <div class="space-y-3">
            {#if files.length > 0}
                <div
                    class="flex items-center justify-between gap-3 px-6 py-2 mb-2 bg-slate-50 dark:bg-slate-900/50 rounded-xl border border-slate-200 dark:border-slate-800"
                >
                    <div class="flex items-center gap-3">
                        <input
                            type="checkbox"
                            checked={isAllOnPageSelected}
                            onchange={selectAll}
                            class="w-4 h-4 rounded border-slate-300 dark:border-slate-700 text-blue-600 focus:ring-blue-500 cursor-pointer"
                        />
                        <span
                            class="text-sm font-extrabold text-slate-600 dark:text-slate-300"
                            >Select All on Page ({paginatedFiles.filter((f) =>
                                selectedPaths.has(f.path),
                            ).length} / {paginatedFiles.length})</span
                        >

                        {#if selectedPaths.size > 0}
                            <div
                                class="w-px h-3 bg-slate-200 dark:bg-slate-800"
                            ></div>
                            <span
                                class="text-[10px] font-black text-blue-600 dark:text-blue-400 uppercase tracking-widest"
                                >Total Selected: {selectedPaths.size}</span
                            >
                        {/if}
                    </div>

                    <span
                        class="text-sm font-black text-slate-500 dark:text-slate-400 uppercase tracking-widest"
                    >
                        Page {currentPage} of {totalPages || 1}
                    </span>
                </div>
            {/if}
            {#each paginatedFiles as file, i (file.path || file.relPath || `${currentPage}-${i}`)}
                {@const globalIndex = (currentPage - 1) * pageSize + i}
                <FileRow
                    {file}
                    index={globalIndex}
                    totalFiles={files.length}
                    {folderPath}
                    {globalActiveTrack}
                    bind:lastFocusedIndex
                    {selectedPaths}
                    {flaggedPaths}
                    {denoisedPaths}
                    {badQualityPaths}
                    {currentTime}
                    {setGlobalTrack}
                    {toggleSelect}
                    {revealInFinder}
                    {openInAudacity}
                    {openInRX}
                    {openReoptimizeModal}
                    {openCompareModal}
                    {analyzeFile}
                    {toggleFlag}
                    {toggleDenoised}
                    {toggleBadQuality}
                    {fileNotes}
                    {setFileNote}
                    {getFileNote}
                />
            {/each}

            <Pagination
                totalFiles={files.length}
                bind:pageSize
                bind:currentPage
            />
        </div>
    </div>

    <!-- Comparison Modal -->
    <CompareModal
        bind:selectedFileForCompare
        bind:compareStartTime
        bind:compareDuration
        {compareBitrates}
        {removeBitrate}
        {addBitrate}
        bind:error
        bind:cleanMethod
        bind:resembleGain
        bind:resembleMix
        bind:lavasrDenoise
        bind:lavasrSuperres
        bind:lavasrMix
        bind:lavasrGain
        bind:lavasrInputSr
        bind:lavasrBatch
        bind:vfMode
        bind:echoReduction
        bind:volumeGain
        {isPlayingNoise}
        {playNoiseSegment}
        {runCleanup}
        {cleanProgress}
        {isCleaning}
        {comparisonSamples}
        bind:comparePlaybackTime
        {activeSampleUrl}
        {switchSample}
        bind:targetBitrateForClean
        {restoreOriginalSegment}
        {files}
        bind:lastUsedCleaningParams
        {convertFile}
        bind:compareAudioElement
        {handleCompareMetadata}
        bind:noiseReductionAmount
        bind:noiseSensitivity
        {isFetchingSpectrogram}
        {spectrogramProgress}
        {fetchZoomedSpectrogram}
        {zoomedSpectrogramUrl}
        {showTransientToast}
    />

    {#if toast.show}
        <div
            class="fixed bottom-20 right-6 max-w-sm px-4 py-3 rounded-xl shadow-2xl text-sm font-black text-white transition-all z-[12000] animate-in {toast.type === 'error'
                ? 'bg-rose-600 ring-2 ring-rose-300'
                : 'bg-emerald-600 ring-2 ring-emerald-300'}"
        >
            {toast.message}
        </div>
    {/if}

    <!-- Spectrogram Modal for Manual Noise Selection -->
    <SpectrogramModal
        bind:show={showSpectrogramModal}
        url={zoomedSpectrogramUrl}
        startTime={compareStartTime}
        duration={compareDuration}
        bind:noiseStart
        bind:noiseEnd
        isPlaying={isPlayingNoise}
        onPlay={playNoiseSegment}
        onClose={() => (showSpectrogramModal = false)}
        onApply={(start, end) => {
            noiseStart = start;
            noiseEnd = end;
        }}
    />

    <!-- Batch Settings Modal -->
    <!-- Batch Settings Modal -->
    <BatchSettingsModal
        bind:showBatchSettingsModal
        {batchTargetMode}
        {selectedPaths}
        bind:cleanMethod
        bind:resembleGain
        bind:resembleMix
        bind:lavasrDenoise
        bind:lavasrSuperres
        bind:lavasrMix
        bind:lavasrGain
        bind:lavasrInputSr
        bind:lavasrBatch
        bind:vfMode
        bind:echoReduction
        bind:noiseReductionAmount
        bind:noiseSensitivity
        bind:targetBitrateForClean
        {compareBitrates}
        bind:volumeGain
        bind:lastUsedCleaningParams
        {noiseStart}
        {noiseEnd}
        {optimizeSelected}
        {optimizeAll}
    />

    <!-- Sticky Optimize Button -->
    <!-- Sticky Optimize Button or Progress Panel -->
    <BatchProgressBar
        {isProcessingQueue}
        {isBatchSessionActive}
        {batchProcessedCount}
        {batchTotalFiles}
        {batchETA}
        {queuePendingCount}
        {activeQueueTaskPath}
        selectedPathsCount={selectedPaths.size}
        bind:isFocusMode
        {openBatchSettings}
    />
</div>

<!-- Focus Mode Overlay -->
<FocusModeOverlay
    bind:isFocusMode
    {isProcessingQueue}
    {isBatchSessionActive}
    {batchProcessedCount}
    {batchTotalFiles}
    {activeQueueTaskPath}
    {files}
    {batchETA}
    {batchProcessingSpeed}
    {cpuTemp}
    {cpuUsage}
    bind:thermalThrottling
    {thermalThrottlingRemaining}
    bind:interFilePauseEnabled
    bind:interFilePauseDuration
    bind:skipInterFilePauseWhenCool
    bind:isInterFilePausing
    bind:interFilePauseRemaining
    {stopAfterCurrentRequested}
    {requestStopAfterCurrent}
    {manualQueuePaused}
    {toggleManualQueuePause}
    {showTransientToast}
/>

<audio
    bind:this={silentAudio}
    src="data:audio/wav;base64,UklGRigAAABXQVZFRm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQQAAAD//w=="
    loop
></audio>

<style>
    /* Custom Scrollbar */
    .scrollbar-thin::-webkit-scrollbar {
        width: 6px;
    }
    .scrollbar-track-transparent::-webkit-scrollbar-track {
        background-color: transparent;
    }
</style>
