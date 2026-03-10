<script>
    import {
        X,
        XCircle,
        AlertCircle,
        Info,
        Loader2,
        Activity,
        Sparkles,
        Play,
        Save,
        Music,
        Minus,
        Plus,
        ChevronRight,
        ChevronsLeft,
        ChevronsRight,
        FileAudio,
        Scissors,
    } from "lucide-svelte";
    import { formatDuration } from "../../utils/formatters.js";
    import { dispatchAudioCommand } from "../../audioStore.js";
    import { globalUiState } from "../../globalState.svelte.js";

    /**
     * @type {{
     *   selectedFileForCompare: any,
     *   compareStartTime: number,
     *   compareDuration: number,
     *   compareBitrates: number[],
     *   removeBitrate: (br: number) => void,
     *   addBitrate: (e: KeyboardEvent) => void,
     *   error: string | null,
     *   cleanMethod: string,
     *   resembleGain: number,
     *   resembleMix: number,
     *   lavasrDenoise: boolean,
     *   lavasrSuperres: boolean,
     *   lavasrMix: number,
     *   lavasrGain: number,
     *   lavasrInputSr: number,
     *   lavasrBatch: boolean,
     *   echoReduction: number,
     *   vfMode: number,
     *   volumeGain: number,
     *   isPlayingNoise: boolean,
     *   playNoiseSegment: () => void,
     *   runCleanup: () => void,
     *   cleanProgress: number,
     *   isCleaning: boolean,
     *   comparisonSamples: any[],
     *   comparePlaybackTime: number,
     *   activeSampleUrl: string | null,
     *   switchSample: (url: string) => void,
     *   targetBitrateForClean: number,
     *   files: any[],
     *   lastUsedCleaningParams: any,
     *   convertFile: (index: number, params: any, inputPath?: string) => Promise<void>,
     *   compareAudioElement: HTMLAudioElement | null,
     *   handleCompareMetadata: () => void,
     *   restoreOriginalSegment: (start: number, end: number, bitrateConfig?: any) => Promise<void>,
     *   noiseReductionAmount: number,
     *   noiseSensitivity: number,
     *   isFetchingSpectrogram: boolean,
     *   showTransientToast?: (message: string, type?: string, duration?: number) => void,
     *   fetchZoomedSpectrogram: () => void,
     *   spectrogramProgress: string,
     *   zoomedSpectrogramUrl: string | null
     * }}
     */
    let {
        selectedFileForCompare = $bindable(),
        compareStartTime = $bindable(),
        compareDuration = $bindable(),
        compareBitrates,
        removeBitrate,
        addBitrate,
        error = $bindable(),
        cleanMethod = $bindable(),
        resembleGain = $bindable(),
        resembleMix = $bindable(),
        lavasrDenoise = $bindable(),
        lavasrSuperres = $bindable(),
        lavasrMix = $bindable(),
        lavasrGain = $bindable(),
        lavasrInputSr = $bindable(),
        lavasrBatch = $bindable(),
        echoReduction = $bindable(),
        vfMode = $bindable(),
        volumeGain = $bindable(),
        isPlayingNoise,
        playNoiseSegment,
        runCleanup,
        cleanProgress,
        isCleaning,
        comparisonSamples,
        comparePlaybackTime = $bindable(),
        activeSampleUrl,
        switchSample,
        targetBitrateForClean = $bindable(),
        files,
        lastUsedCleaningParams = $bindable(),
        convertFile,
        compareAudioElement = $bindable(),
        handleCompareMetadata,
        restoreOriginalSegment,
        noiseReductionAmount = $bindable(),
        noiseSensitivity = $bindable(),
        isFetchingSpectrogram,
        showTransientToast = () => {},
        spectrogramProgress,
        fetchZoomedSpectrogram,
        zoomedSpectrogramUrl,
    } = $props();

    let restoreStart = $state(0);
    let restoreEnd = $state(0);
    let isRestoring = $state(false);
    let restorationAudioLoading = $state(false);
    let restorationAudioElement = $state(null); // Dedicated element for restoration
    let restorationPlayerMode = $state("original"); // "original" or "optimized"
    let isComparePlaying = $state(false); // Track playing state for custom UI
    let splicingProgress = $state(0); // Progress for splicing (0-100)

    // Splicing Bitrate Configuration
    let useCustomRestoreBitrate = $state(false);
    let restoreBitrateMode = $state("cbr");
    let restoreTargetBitrate = $state(128);
    let restoreTargetVbrLevel = $state("v6");

    // Bitrate Mode State (CBR vs VBR)
    let bitrateMode = $state("cbr");
    let targetVbrLevel = $state("v6"); // Default VBR level

    // Load from localStorage on mount
    import { onMount, tick } from "svelte";
    onMount(() => {
        const savedMode = localStorage.getItem("last_bitrate_mode");
        if (savedMode) bitrateMode = savedMode;

        const savedVbr = localStorage.getItem("last_vbr_level");
        if (savedVbr) targetVbrLevel = savedVbr;

        // Restore custom restoration settings
        useCustomRestoreBitrate = localStorage.getItem("last_use_custom_restore_bitrate") === "true";
        const savedRestoreMode = localStorage.getItem("last_restore_bitrate_mode");
        if (savedRestoreMode) restoreBitrateMode = savedRestoreMode;
        
        const savedRestoreBr = localStorage.getItem("last_restore_target_bitrate");
        if (savedRestoreBr) restoreTargetBitrate = parseInt(savedRestoreBr);

        const savedRestoreVbr = localStorage.getItem("last_restore_target_vbr_level");
        if (savedRestoreVbr) restoreTargetVbrLevel = savedRestoreVbr;
    });

    // Save settings when they change
    $effect(() => {
        localStorage.setItem("last_bitrate_mode", bitrateMode);
        localStorage.setItem("last_vbr_level", targetVbrLevel);
        localStorage.setItem("last_use_custom_restore_bitrate", useCustomRestoreBitrate.toString());
        localStorage.setItem("last_restore_bitrate_mode", restoreBitrateMode);
        localStorage.setItem("last_restore_target_bitrate", restoreTargetBitrate.toString());
        localStorage.setItem("last_restore_target_vbr_level", restoreTargetVbrLevel);
    });

    // Reset restoration points when the selected file changes
    $effect(() => {
        if (selectedFileForCompare?.path) {
            restoreStart = 0;
            restoreEnd = 0;
            comparePlaybackTime = 0;
        }
    });

    // Manage Global Modal State to prevent keyboard conflicts
    $effect(() => {
        globalUiState.isModalOpen = !!selectedFileForCompare;

        // Keyboard handler for the modal
        const handleModalKeys = (e) => {
            if (!selectedFileForCompare) return;

            // Only handle if we aren't in an input (though inputs usually stop prop, good safety)
            const target = e.target;
            const isRangeInput = target?.tagName === "INPUT" && target?.type === "range";
            if (
                !isRangeInput && (
                    ["INPUT", "TEXTAREA", "SELECT"].includes(target?.tagName) ||
                    target?.isContentEditable
                )
            )
                return;

            // Restoration Player Controls
            if (cleanMethod === "restoration" && restorationAudioElement) {
                if (e.key === "ArrowLeft") {
                    e.preventDefault();
                    restorationAudioElement.currentTime = Math.max(
                        0,
                        restorationAudioElement.currentTime - 5,
                    );
                } else if (e.key === "ArrowRight") {
                    e.preventDefault();
                    restorationAudioElement.currentTime = Math.min(
                        restorationAudioElement.duration || selectedFileForCompare.duration || 10000,
                        restorationAudioElement.currentTime + 5,
                    );
                } else if (e.key === " ") {
                    e.preventDefault();
                    if (restorationAudioLoading) return;
                    if (restorationAudioElement.paused) {
                        restorationAudioElement.play();
                        dispatchAudioCommand("PAUSE_ALL");
                    } else {
                        restorationAudioElement.pause();
                    }
                } else if (e.key.toLowerCase() === "o" || e.key.toLowerCase() === "щ" || e.code === "KeyO") {
                    e.preventDefault();
                    if (restorationAudioElement) {
                        const newMode = restorationPlayerMode === "original" ? "optimized" : "original";
                        // If switching to optimized, check if finalPath exists
                        if (newMode === "optimized" && !selectedFileForCompare.finalPath) return;
                        toggleRestorationVersion(newMode);
                    }
                }
            } else if (
                cleanMethod !== "restoration" &&
                compareAudioElement
            ) {
                if (e.key === "ArrowLeft") {
                    e.preventDefault();
                    compareAudioElement.currentTime = Math.max(
                        0,
                        compareAudioElement.currentTime - 5,
                    );
                } else if (e.key === "ArrowRight") {
                    e.preventDefault();
                    compareAudioElement.currentTime = Math.min(
                        compareAudioElement.duration || selectedFileForCompare.duration || 10000,
                        compareAudioElement.currentTime + 5,
                    );
                } else if (e.key === " ") {
                    e.preventDefault();
                    if (compareAudioElement.paused) {
                        compareAudioElement.play();
                        dispatchAudioCommand("PAUSE_ALL");
                    } else {
                        compareAudioElement.pause();
                    }
                }
            }
        };

        if (selectedFileForCompare) {
            window.addEventListener("keydown", handleModalKeys);
        }

        return () => {
            globalUiState.isModalOpen = false;
            window.removeEventListener("keydown", handleModalKeys);
        };
    });

    const vbrLevels = [
        { id: "v2", label: "VBR 2", desc: "~190 kbps (High)" },
        { id: "v4", label: "VBR 4", desc: "~165 kbps" },
        { id: "v6", label: "VBR 6", desc: "~120 kbps" },
        { id: "v7", label: "VBR 7", desc: "~100 kbps" },
        { id: "v8", label: "VBR 8", desc: "~85 kbps" },
        { id: "v9", label: "VBR 9", desc: "~65 kbps (Low)" },
    ];
    let audioNonce = $state(Date.now());
    $effect(() => {
        // Refresh local audio URLs when selected file or its optimized revision changes.
        if (selectedFileForCompare?.path || selectedFileForCompare?.lastOptimized) {
            audioNonce = Date.now();
        }
    });

    function getAudioSrc(pathOrUrl) {
        if (!pathOrUrl) return "";
        if (pathOrUrl.startsWith("http")) {
            const sep = pathOrUrl.includes("?") ? "&" : "?";
            return `${pathOrUrl}${sep}t=${audioNonce}`;
        }
        return `http://127.0.0.1:3000/audio?path=${encodeURIComponent(pathOrUrl)}&t=${audioNonce}`;
    }

    async function toggleRestorationVersion(mode) {
        if (restorationPlayerMode === mode) return;

        if (restorationAudioElement) {
            const currentTime = restorationAudioElement.currentTime;
            const wasPlaying = !restorationAudioElement.paused;

            // 1. Pause immediately
            restorationAudioElement.pause();

            // 2. Define restoration handler
            const onAudioLoaded = () => {
                restorationAudioElement.currentTime = currentTime;
                if (wasPlaying) {
                    restorationAudioElement.play().catch(console.warn);
                    dispatchAudioCommand("PAUSE_ALL"); // Ensure global exclusivity
                }
            };

            // 3. Attach one-time listener BEFORE changing src
            // 'loadeddata' is usually the earliest we can seek safely
            restorationAudioElement.addEventListener(
                "loadeddata",
                onAudioLoaded,
                { once: true },
            );

            // 4. Change mode (triggers src update via Svelte)
            restorationPlayerMode = mode;
        } else {
            restorationPlayerMode = mode;
        }
    }
</script>

{#if selectedFileForCompare}
    <div class="fixed inset-0 z-[10000] flex items-center justify-center p-6">
        <button
            type="button"
            class="fixed inset-0 z-0 appearance-none border-0 p-0 m-0 rounded-none shadow-none bg-slate-950/40 backdrop-blur-md animate-in fade-in duration-300"
            onclick={() => (selectedFileForCompare = null)}
            aria-label="Close compare modal"
            title="Close compare modal"
        ></button>
        <div
            class="relative z-10 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 w-full max-w-[1000px] max-h-[90vh] rounded-2xl shadow-3xl mx-auto flex flex-col overflow-hidden"
            role="dialog"
            aria-modal="true"
            tabindex="-1"
        >
            <!-- Inner scrollable container with padding -->
            <div
                class="overflow-y-auto scrollbar-thin scrollbar-thumb-slate-200 dark:scrollbar-thumb-slate-800 scrollbar-track-transparent p-8 flex-1 space-y-6"
            >
                <div class="flex justify-between items-start">
                    <div class="min-w-0 pr-4">
                        <h2
                            class="text-2xl font-black text-slate-800 dark:text-white tracking-tight flex items-center gap-3"
                        >
                            Audio Enhancement Lab
                            {#if selectedFileForCompare.isProxy}
                                <span class="px-2 py-0.5 rounded-lg bg-red-500 text-white text-[10px] uppercase font-black tracking-widest animate-pulse shadow-lg shadow-red-500/20">
                                    Re-Optimize Mode
                                </span>
                            {/if}
                        </h2>
                        <p
                            class="text-slate-500 text-sm truncate font-medium flex items-center gap-2 mt-2"
                        >
                            <span
                                >{selectedFileForCompare?.name ||
                                    "Unknown File"}</span
                            >
                            {#if selectedFileForCompare.currentBitrate}
                                <span
                                    class="px-1.5 py-0.5 rounded-md bg-slate-100 dark:bg-slate-800 text-xs font-bold text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-700"
                                >
                                    {selectedFileForCompare.currentBitrate}k
                                </span>
                            {/if}
                        </p>
                    </div>
                    <button
                        onclick={() => (selectedFileForCompare = null)}
                        class="p-2 hover:bg-slate-200 dark:hover:bg-slate-800 rounded-full transition-colors text-slate-400 hover:text-slate-900 dark:hover:text-white"
                        aria-label="Close"
                    >
                        <X size={24} />
                    </button>
                </div>

                <div
                    class="flex flex-wrap items-start gap-6 p-5 bg-slate-50 dark:bg-slate-900/40 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm"
                >
                    <!-- Start Time -->
                    <div class="space-y-1.5 w-32 shrink-0">
                        <span
                            class="text-[10px] font-black {compareStartTime >=
                            selectedFileForCompare.duration
                                ? 'text-red-500'
                                : 'text-slate-400'} uppercase tracking-widest"
                            >Start (min)</span
                        >
                        <div class="relative">
                            <input
                                type="number"
                                value={Math.round(
                                    (compareStartTime / 60) * 10,
                                ) / 10}
                                oninput={(e) => {
                                    const val = parseFloat(
                                        e.currentTarget.value,
                                    );
                                    if (!isNaN(val)) {
                                        compareStartTime = Math.round(val * 60);
                                    }
                                }}
                                step="0.1"
                                min="0"
                                max={selectedFileForCompare.duration / 60}
                                class="w-full bg-white dark:bg-slate-950 border {compareStartTime >=
                                selectedFileForCompare.duration
                                    ? 'border-red-300 dark:border-red-900/50'
                                    : 'border-slate-200 dark:border-slate-800'} rounded-xl pl-3 pr-10 py-2 text-sm font-bold focus:outline-none focus:ring-2 focus:ring-blue-500/20 text-slate-700 dark:text-slate-200 shadow-sm transition-all"
                            />
                            <div
                                class="absolute right-3 top-1/2 -translate-y-1/2 text-[10px] font-bold text-slate-400 pointer-events-none"
                            >
                                / {(
                                    selectedFileForCompare.duration / 60
                                ).toFixed(0)}m
                            </div>
                        </div>
                    </div>

                    <!-- Duration -->
                    <div class="space-y-1.5 w-24 shrink-0">
                        <span
                            class="text-[10px] font-black text-slate-400 uppercase tracking-widest"
                            >Dur (sec)</span
                        >
                        <input
                            type="number"
                            bind:value={compareDuration}
                            min="5"
                            max="300"
                            class="w-full bg-white dark:bg-slate-950 border {compareStartTime +
                                compareDuration >
                            selectedFileForCompare.duration
                                ? 'border-red-300 dark:border-red-900/50'
                                : 'border-slate-200 dark:border-slate-800'} rounded-xl px-3 py-2 text-sm font-bold focus:outline-none focus:ring-2 focus:ring-blue-500/20 text-slate-700 dark:text-slate-200 shadow-sm transition-all"
                        />
                    </div>

                    <!-- Divider -->
                    <div
                        class="w-px h-10 bg-slate-200 dark:bg-slate-800 self-center hidden sm:block mx-1"
                    ></div>

                    <!-- Bitrates -->
                    <div class="space-y-1.5 flex-grow min-w-[200px]">
                        <span
                            class="text-[10px] font-black text-slate-400 uppercase tracking-widest"
                            >Bitrates (kbps)</span
                        >
                        <div
                            class="flex flex-wrap items-center gap-2 min-h-[38px]"
                        >
                            {#each compareBitrates as br}
                                <span
                                    class="bg-white dark:bg-slate-950 text-blue-600 dark:text-blue-400 px-2.5 py-1.5 rounded-lg text-xs font-bold flex items-center gap-2 border border-blue-100 dark:border-blue-900/30 shadow-sm animate-in zoom-in-90 duration-200"
                                >
                                    {br}
                                    <button
                                        onclick={() => removeBitrate(br)}
                                        class="text-slate-400 hover:text-red-500 transition-colors"
                                        aria-label={`Remove ${br} kbps`}
                                        ><XCircle size={12} /></button
                                    >
                                </span>
                            {/each}
                            <input
                                type="number"
                                placeholder="+ Add"
                                onkeydown={addBitrate}
                                class="bg-transparent border-none outline-none text-xs w-16 p-1.5 font-medium text-slate-600 dark:text-slate-400 placeholder:text-slate-400 focus:placeholder:text-blue-400 transition-all"
                            />
                        </div>
                    </div>
                </div>

                {#if error && error.includes("time")}
                    <div
                        class="mt-2 p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-xs flex items-center gap-2 animate-in slide-in-from-top-1"
                    >
                        <AlertCircle size={14} />
                        {error}
                    </div>
                {/if}

                <!-- Speech Enhancement Section -->
                <div
                    class="space-y-4 p-6 bg-slate-50 dark:bg-slate-800/40 rounded-2xl border border-slate-200 dark:border-slate-700/50 shadow-sm"
                >
                    <div class="flex items-center justify-between">
                        <span
                            class="text-[10px] font-black text-slate-400 uppercase tracking-widest"
                            >Speech Enhancement</span
                        >

                        <div
                            class="flex gap-1 bg-slate-100 dark:bg-slate-900/50 rounded-lg p-1 border border-slate-200 dark:border-slate-800"
                        >
                            <div
                                class="flex gap-1 mr-1 pr-1 border-r border-slate-200 dark:border-slate-700"
                            >
                                <button
                                    onclick={() =>
                                        (cleanMethod = "restoration")}
                                    class="px-2 py-1 rounded text-[10px] font-black uppercase transition-all
                                {cleanMethod === 'restoration'
                                        ? 'bg-amber-500 text-white shadow-sm'
                                        : 'text-amber-600/70 hover:text-amber-600 hover:bg-amber-50 dark:hover:bg-amber-950/30'}"
                                >
                                    Restoration
                                </button>
                            </div>
                            {#each ["manual", "resemble_denoise", "lavasr", "remove_echo", "voicefixer"] as method}
                                <button
                                    onclick={() => (cleanMethod = method)}
                                    class="px-2 py-1 rounded text-[10px] font-bold uppercase transition-all
                                {cleanMethod === method
                                        ? 'bg-blue-600 text-white shadow-sm'
                                        : 'text-slate-500 hover:text-slate-700'}"
                                >
                                    {method === "lavasr"
                                        ? "lava sr"
                                        : method === "remove_echo"
                                        ? "remove echo"
                                        : method.replace("_denoise", "")}
                                </button>
                            {/each}
                        </div>
                    </div>

                    {#if cleanMethod === "restoration"}
                        <div
                            class="space-y-4 animate-in slide-in-from-top-2 duration-300"
                        >
                            <div
                                class="bg-amber-50/50 dark:bg-amber-950/10 border border-amber-100 dark:border-amber-900/30 p-5 rounded-2xl space-y-5"
                            >
                                <div class="flex items-center justify-between">
                                    <div
                                        class="flex items-center gap-2 text-[10px] font-black uppercase tracking-widest text-amber-600 dark:text-amber-500"
                                    >
                                        <Activity size={14} />
                                        Full-Track Restoration
                                    </div>
                                    <div
                                        class="flex gap-1 bg-white/50 dark:bg-black/20 p-1 rounded-lg border border-amber-200/50 dark:border-amber-900/30"
                                    >
                                        <button
                                            onclick={() =>
                                                toggleRestorationVersion(
                                                    "original",
                                                )}
                                            class="px-3 py-1 rounded text-[9px] font-black uppercase transition-all {restorationPlayerMode ===
                                            'original'
                                                ? 'bg-amber-500 text-white'
                                                : 'text-slate-500'}"
                                            >Original</button
                                        >
                                        <button
                                            onclick={() =>
                                                toggleRestorationVersion(
                                                    "optimized",
                                                )}
                                            class="px-3 py-1 rounded text-[9px] font-black uppercase transition-all {restorationPlayerMode ===
                                            'optimized'
                                                ? 'bg-green-600 text-white'
                                                : 'text-slate-500'}"
                                            disabled={!selectedFileForCompare.finalPath}
                                            >Optimized</button
                                        >
                                    </div>
                                </div>

                                <!-- Integrated Player for Restoration -->
                                <div
                                    class="bg-amber-100 dark:bg-amber-900/30 rounded-xl p-3 border border-amber-200 dark:border-amber-900/50"
                                >
                                    <div
                                        class="flex items-center justify-between mb-2 px-1"
                                    >
                                        <div
                                            class="flex items-center gap-2 text-[10px] font-bold uppercase tracking-widest text-amber-700 dark:text-amber-400"
                                        >
                                            Preview {restorationPlayerMode}
                                        </div>
                                        <span
                                            class="font-mono text-[10px] font-bold text-amber-600/70 dark:text-amber-500/70"
                                        >
                                            {formatDuration(
                                                comparePlaybackTime,
                                            )} / {formatDuration(
                                                selectedFileForCompare.duration,
                                            )}
                                        </span>
                                    </div>
                                    <div class="flex items-center gap-3">
                                        <button
                                            class="w-8 h-8 flex items-center justify-center rounded-full bg-amber-500 text-white hover:bg-amber-600 transition-colors shadow-sm focus:outline-none"
                                            onclick={(e) => {
                                                e.stopPropagation();
                                                if (restorationAudioElement) {
                                                    if (
                                                        restorationAudioElement.paused
                                                    ) {
                                                        restorationAudioElement.play();
                                                        dispatchAudioCommand(
                                                            "PAUSE_ALL",
                                                        );
                                                    } else {
                                                        restorationAudioElement.pause();
                                                    }
                                                }
                                            }}
                                        >
                                            {#if isComparePlaying}
                                                <div
                                                    class="w-3 h-3 bg-white rounded-sm"
                                                ></div>
                                            {:else}
                                                <Play
                                                    size={14}
                                                    class="fill-white ml-0.5"
                                                />
                                            {/if}
                                        </button>

                                        <div class="flex-1 relative h-6 flex items-center">
                                            <!-- Track Background with Highlight -->
                                            <div class="absolute left-0 right-0 h-2 bg-amber-200/50 dark:bg-amber-900/50 rounded-full overflow-hidden">
                                                {#if restoreEnd > restoreStart}
                                                    <div 
                                                        class="absolute h-full bg-amber-500/40 dark:bg-amber-400/30 transition-all duration-300 pointer-events-none"
                                                        style="
                                                            left: {(restoreStart / (selectedFileForCompare.duration || 1)) * 100}%; 
                                                            width: {((restoreEnd - restoreStart) / (selectedFileForCompare.duration || 1)) * 100}%;
                                                        "
                                                    ></div>
                                                {/if}
                                            </div>
                                            
                                            <input
                                                type="range"
                                                min="0"
                                                max={selectedFileForCompare.duration ||
                                                    100}
                                                step="0.01"
                                                value={comparePlaybackTime}
                                                oninput={(e) => {
                                                    const val = parseFloat(
                                                        e.currentTarget.value,
                                                    );
                                                    comparePlaybackTime = val;
                                                    if (restorationAudioElement) {
                                                        restorationAudioElement.currentTime =
                                                            val;
                                                    }
                                                }}
                                                class="absolute inset-0 w-full h-full bg-transparent appearance-none cursor-pointer accent-amber-600 focus:outline-none z-10"
                                            />
                                        </div>
                                    </div>

                                    <audio
                                        bind:this={restorationAudioElement}
                                        src={getAudioSrc(
                                            restorationPlayerMode === "original"
                                                ? selectedFileForCompare.path
                                                : selectedFileForCompare.finalPath,
                                        )}
                                        ontimeupdate={(e) =>
                                            (comparePlaybackTime =
                                                e.currentTarget.currentTime)}
                                        oncanplay={handleCompareMetadata}
                                        onplay={() => {
                                            isComparePlaying = true;
                                            dispatchAudioCommand("PAUSE_ALL");
                                        }}
                                        onpause={() =>
                                            (isComparePlaying = false)}
                                        preload="auto"
                                        class="hidden"
                                    ></audio>
                                </div>

                                <div class="grid grid-cols-2 gap-3">
                                    <div class="space-y-2">
                                        <span
                                            class="text-[9px] uppercase font-bold text-slate-400 block"
                                            >Start Point</span
                                        >
                                        <div class="flex gap-1.5">
                                            <button
                                                onclick={() => (restoreStart = 0)}
                                                class="px-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg text-slate-400 hover:text-amber-500 hover:border-amber-400 focus:outline-none transition-all active:scale-90"
                                                title="Set to start of track (0:00)"
                                            >
                                                <ChevronsLeft size={14} />
                                            </button>
                                            <button
                                                onclick={() =>
                                                    (restoreStart =
                                                        comparePlaybackTime)}
                                                class="flex-1 px-3 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg text-xs font-mono font-bold hover:border-amber-400 focus:outline-none transition-colors"
                                            >
                                                {formatDuration(restoreStart)}
                                            </button>
                                        </div>
                                    </div>
                                    <div class="space-y-2">
                                        <span
                                            class="text-[9px] uppercase font-bold text-slate-400 block"
                                            >End Point</span
                                        >
                                        <div class="flex gap-1.5">
                                            <button
                                                onclick={() =>
                                                    (restoreEnd =
                                                        comparePlaybackTime)}
                                                class="flex-1 px-3 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg text-xs font-mono font-bold hover:border-amber-400 focus:outline-none transition-colors"
                                            >
                                                {formatDuration(restoreEnd)}
                                            </button>
                                            <button
                                                onclick={() => (restoreEnd = selectedFileForCompare.duration)}
                                                class="px-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg text-slate-400 hover:text-amber-500 hover:border-amber-400 focus:outline-none transition-all active:scale-90"
                                                title="Set to end of track"
                                            >
                                                <ChevronsRight size={14} />
                                            </button>
                                        </div>
                                    </div>
                                </div>

                                <div class="space-y-3 pt-2">
                                    <label class="flex items-center gap-2 cursor-pointer group">
                                        <input
                                            type="checkbox"
                                            bind:checked={useCustomRestoreBitrate}
                                            class="w-3.5 h-3.5 rounded border-slate-300 text-amber-500 focus:ring-amber-500"
                                        />
                                        <span class="text-[10px] font-bold text-slate-500 uppercase tracking-tight group-hover:text-slate-700 transition-colors">
                                            Custom Bitrate / Quality
                                        </span>
                                    </label>

                                    {#if useCustomRestoreBitrate}
                                        <div class="space-y-2 p-3 rounded-xl bg-slate-50 dark:bg-slate-900/50 border border-slate-200 dark:border-slate-800 animate-in fade-in slide-in-from-top-1">
                                            <!-- Mode Toggle -->
                                            <div class="flex items-center justify-between">
                                                <span class="text-[9px] font-black text-slate-400 uppercase">Mode</span>
                                                <div class="flex bg-white dark:bg-slate-800 rounded-lg p-0.5 border border-slate-200 dark:border-slate-700">
                                                    <button
                                                        onclick={() => (restoreBitrateMode = "cbr")}
                                                        class="px-2 py-1 rounded text-[9px] font-black uppercase transition-all
                                                        {restoreBitrateMode === 'cbr' ? 'bg-amber-100 dark:bg-amber-900/30 text-amber-600' : 'text-slate-500'}"
                                                    >CBR</button>
                                                    <button
                                                        onclick={() => (restoreBitrateMode = "vbr")}
                                                        class="px-2 py-1 rounded text-[9px] font-black uppercase transition-all
                                                        {restoreBitrateMode === 'vbr' ? 'bg-amber-100 dark:bg-amber-900/30 text-amber-600' : 'text-slate-500'}"
                                                    >VBR</button>
                                                </div>
                                            </div>

                                            <!-- Value Selector -->
                                            <div class="flex flex-wrap gap-1">
                                                {#if restoreBitrateMode === "cbr"}
                                                    {#each [64, 96, 128, 192, 256, 320] as br}
                                                        <button
                                                            onclick={() => (restoreTargetBitrate = br)}
                                                            class="px-2 py-1 rounded-md text-[9px] font-bold border transition-all
                                                            {restoreTargetBitrate === br
                                                                ? 'bg-amber-500 border-amber-500 text-white shadow-sm'
                                                                : 'bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-500 hover:border-amber-300'}"
                                                        >{br}k</button>
                                                    {/each}
                                                {:else}
                                                    {#each vbrLevels as vbr}
                                                        <button
                                                            onclick={() => (restoreTargetVbrLevel = vbr.id)}
                                                            title={vbr.desc}
                                                            class="px-2 py-1 rounded-md text-[9px] font-bold border transition-all
                                                            {restoreTargetVbrLevel === vbr.id
                                                                ? 'bg-amber-500 border-amber-500 text-white shadow-sm'
                                                                : 'bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-500 hover:border-amber-300'}"
                                                        >{vbr.label}</button>
                                                    {/each}
                                                {/if}
                                            </div>
                                        </div>
                                    {/if}
                                </div>

                                <button
                                    onclick={async () => {
                                        if (restoreEnd <= restoreStart) {
                                            error =
                                                "End point must be after start point";
                                            return;
                                        }
                                        isRestoring = true;
                                        splicingProgress = 0; // Reset

                                        // Fake progress animation since it's a single await
                                        const progressInterval = setInterval(
                                            () => {
                                                splicingProgress = Math.min(
                                                    splicingProgress + 5,
                                                    95,
                                                );
                                            },
                                            300,
                                        );

                                        try {
                                            await restoreOriginalSegment(
                                                restoreStart,
                                                restoreEnd,
                                                useCustomRestoreBitrate ? {
                                                    mode: restoreBitrateMode,
                                                    value: restoreBitrateMode === "cbr" ? restoreTargetBitrate : restoreTargetVbrLevel
                                                } : null
                                            );

                                            clearInterval(progressInterval);
                                            splicingProgress = 100;

                                            // Brief delay to show 100%
                                            await new Promise((r) =>
                                                setTimeout(r, 500),
                                            );

                                            showTransientToast(
                                                "Track Restoration segment spliced successfully!",
                                                "success",
                                                1800,
                                            );
                                            selectedFileForCompare = null;
                                        } catch (e) {
                                            error =
                                                "Restoration failed: " +
                                                e.message;
                                        } finally {
                                            clearInterval(progressInterval);
                                            isRestoring = false;
                                            splicingProgress = 0;
                                        }
                                    }}
                                    disabled={isRestoring ||
                                        !selectedFileForCompare.finalPath}
                                    class="w-full py-3 rounded-xl bg-amber-500 text-white font-black text-[10px] uppercase tracking-widest flex items-center justify-center gap-2 hover:bg-amber-600 transition-all active:scale-95 disabled:opacity-50 shadow-lg shadow-amber-500/20 relative overflow-hidden"
                                >
                                    {#if isRestoring}
                                        <!-- Progress Bar Background -->
                                        <div
                                            class="absolute left-0 top-0 bottom-0 bg-amber-700/20 transition-all duration-300"
                                            style="width: {splicingProgress}%"
                                        ></div>

                                        <div
                                            class="relative z-10 flex items-center gap-2"
                                        >
                                            <Loader2
                                                size={14}
                                                class="animate-spin"
                                            />
                                            Splicing... {splicingProgress}%
                                        </div>
                                    {:else}
                                        <Activity size={14} />
                                        Splicing Segment from Original
                                    {/if}
                                </button>
                                <p
                                    class="text-[9px] text-slate-500 italic text-center"
                                >
                                    This will surgically replace the {formatDuration(
                                        restoreStart,
                                    )} - {formatDuration(restoreEnd)} period in the
                                    optimized file with the original version.
                                </p>
                            </div>
                        </div>
                    {/if}

                    {#if cleanMethod === "resemble_denoise"}
                        <div
                            class="space-y-4 animate-in slide-in-from-top-2 duration-300"
                        >
                            <div class="grid grid-cols-2 gap-4">
                                <div class="space-y-2">
                                    <div
                                        class="flex justify-between items-center"
                                    >
                                        <div
                                            class="flex items-center gap-1.5 group relative"
                                        >
                                            <span
                                                class="text-[10px] font-bold text-slate-500 uppercase"
                                                >Input Gain</span
                                            >
                                            <button
                                                type="button"
                                                class="cursor-help text-slate-400 hover:text-blue-500 transition-colors"
                                                aria-label="Input gain help"
                                            >
                                                <Info size={10} />
                                            </button>
                                            <!-- Tooltip -->
                                            <div
                                                class="absolute bottom-full left-0 mb-3 w-72 p-4 bg-slate-900 border border-slate-700 rounded-xl shadow-2xl text-base leading-snug text-slate-100 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-[10010]"
                                            >
                                                Increase if the original audio
                                                is too quiet. Resemble works
                                                best with strong signal input
                                                (0.8x - 1.5x recommended).
                                            </div>
                                        </div>
                                        <span
                                            class="text-[10px] font-mono text-blue-400"
                                            >{resembleGain.toFixed(1)}x</span
                                        >
                                    </div>
                                    <input
                                        type="range"
                                        bind:value={resembleGain}
                                        min="0.5"
                                        max="3"
                                        step="0.1"
                                        class="w-full h-1.5 bg-slate-200 dark:bg-slate-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
                                    />
                                </div>
                                <div class="space-y-2">
                                    <div
                                        class="flex justify-between items-center"
                                    >
                                        <div
                                            class="flex items-center gap-1.5 group relative"
                                        >
                                            <span
                                                class="text-[10px] font-bold text-slate-500 uppercase"
                                                >Denoise Mix</span
                                            >
                                            <button
                                                type="button"
                                                class="cursor-help text-slate-400 hover:text-blue-500 transition-colors"
                                                aria-label="Denoise mix help"
                                            >
                                                <Info size={10} />
                                            </button>
                                            <!-- Tooltip -->
                                            <div
                                                class="absolute bottom-full left-0 mb-3 w-72 p-4 bg-slate-900 border border-slate-700 rounded-xl shadow-2xl text-base leading-snug text-slate-100 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-[10010]"
                                            >
                                                Balance between AI Denoised and
                                                Original audio. 100% is full AI
                                                processing, lower values bring
                                                back some original character.
                                            </div>
                                        </div>
                                        <span
                                            class="text-[10px] font-mono text-blue-400"
                                            >{Math.round(
                                                resembleMix * 100,
                                            )}%</span
                                        >
                                    </div>
                                    <input
                                        type="range"
                                        bind:value={resembleMix}
                                        min="0"
                                        max="1"
                                        step="0.05"
                                        class="w-full h-1.5 bg-slate-200 dark:bg-slate-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
                                    />
                                </div>
                            </div>
                            <p class="text-[10px] text-slate-500 italic">
                                Resemble Denoise uses AI to remove noise while
                                preserving voice character.
                            </p>
                        </div>
                    {/if}

                    {#if cleanMethod === "lavasr"}
                        <div
                            class="space-y-5 animate-in slide-in-from-top-2 duration-300"
                        >
                            <div
                                class="p-5 rounded-2xl border border-orange-200 dark:border-orange-900/40 bg-orange-50/60 dark:bg-orange-950/10 space-y-4"
                            >
                                <div class="flex items-center gap-2">
                                    <span
                                        class="text-[10px] font-black tracking-widest text-orange-700 dark:text-orange-400 uppercase"
                                    >
                                        LavaSR
                                    </span>
                                    <div class="group relative flex items-center">
                                        <button
                                            type="button"
                                            class="text-slate-400 transition-colors hover:text-orange-500 focus:text-orange-500"
                                            aria-label="About LavaSR"
                                        >
                                            <Info size={11} />
                                        </button>
                                        <div
                                            class="pointer-events-none absolute left-0 top-full z-[10010] mt-2 w-72 rounded-xl border border-slate-700 bg-slate-900 p-4 text-[12px] leading-snug text-slate-100 opacity-0 invisible shadow-2xl transition-all group-hover:visible group-hover:opacity-100 group-focus-within:visible group-focus-within:opacity-100"
                                        >
                                            LavaSR runs speech denoising plus
                                            bandwidth extension in one pass.
                                            This tab uses the model default
                                            pipeline tuned for speech
                                            restoration.
                                        </div>
                                    </div>
                                </div>
                                <div class="grid gap-3 md:grid-cols-3">
                                    <button
                                        class="rounded-xl bg-white/80 dark:bg-slate-900/70 border px-4 py-3 text-left transition-all {lavasrDenoise
                                            ? 'border-orange-300 dark:border-orange-700 shadow-sm ring-1 ring-orange-200/60 dark:ring-orange-800/50'
                                            : 'border-slate-200 dark:border-slate-800 opacity-70'}"
                                        onclick={() => (lavasrDenoise = !lavasrDenoise)}
                                    >
                                        <div class="text-[9px] font-black uppercase tracking-widest text-slate-400">
                                            Denoise
                                        </div>
                                        <div class="mt-1 text-xs font-bold text-slate-700 dark:text-slate-200">
                                            {lavasrDenoise ? "Enabled" : "Disabled"}
                                        </div>
                                    </button>
                                    <button
                                        class="rounded-xl bg-white/80 dark:bg-slate-900/70 border px-4 py-3 text-left transition-all {lavasrSuperres
                                            ? 'border-orange-300 dark:border-orange-700 shadow-sm ring-1 ring-orange-200/60 dark:ring-orange-800/50'
                                            : 'border-slate-200 dark:border-slate-800 opacity-70'}"
                                        onclick={() => (lavasrSuperres = !lavasrSuperres)}
                                    >
                                        <div class="text-[9px] font-black uppercase tracking-widest text-slate-400">
                                            Super-Res
                                        </div>
                                        <div class="mt-1 text-xs font-bold text-slate-700 dark:text-slate-200">
                                            {lavasrSuperres ? "To 48 kHz" : "Off"}
                                        </div>
                                    </button>
                                    <label class="rounded-xl border border-orange-100 dark:border-orange-900/30 bg-white/70 dark:bg-slate-900/50 px-4 py-3 cursor-pointer flex items-center justify-between transition-all">
                                        <div>
                                            <div class="text-[9px] font-black uppercase tracking-widest text-slate-400">
                                                Enable Batching
                                            </div>
                                            <div class="mt-1 text-xs font-bold text-slate-700 dark:text-slate-200">
                                                {lavasrBatch ? "Enabled" : "Disabled"}
                                            </div>
                                            <div class="text-[10px] text-slate-500 mt-1">
                                                Use for very long audio files.
                                            </div>
                                        </div>
                                        <input
                                            type="checkbox"
                                            bind:checked={lavasrBatch}
                                            class="h-4 w-4 rounded border-slate-300 text-orange-500 focus:ring-orange-500"
                                        />
                                    </label>
                                </div>
                                <div class="grid gap-3 pt-1 md:grid-cols-3">
                                    <div class="space-y-2">
                                        <div class="flex justify-between items-center">
                                            <span class="text-[10px] font-bold text-slate-500 uppercase">
                                                Input Gain
                                            </span>
                                            <span class="text-[10px] font-mono text-orange-500">
                                                {lavasrGain.toFixed(1)}x
                                            </span>
                                        </div>
                                        <input
                                            type="range"
                                            bind:value={lavasrGain}
                                            min="0.5"
                                            max="3"
                                            step="0.1"
                                            class="w-full h-1.5 bg-slate-200 dark:bg-slate-700 rounded-lg appearance-none cursor-pointer accent-orange-500"
                                        />
                                    </div>
                                    <div class="space-y-2">
                                        <div class="flex justify-between items-center gap-2">
                                            <span class="text-[10px] font-bold text-slate-500 uppercase">
                                                Input Sampling Rate (Hz)
                                            </span>
                                            <div class="flex items-center gap-2">
                                                <span class="text-[10px] font-mono text-orange-500">
                                                    {lavasrInputSr}
                                                </span>
                                                <button
                                                    class="text-[10px] font-mono text-orange-500 hover:text-orange-600"
                                                    onclick={() => (lavasrInputSr = 16000)}
                                                    title="Reset to 16000 Hz"
                                                >
                                                    ↺ 16000
                                                </button>
                                            </div>
                                        </div>
                                        <input
                                            type="range"
                                            bind:value={lavasrInputSr}
                                            min="8000"
                                            max="48000"
                                            step="1000"
                                            class="w-full h-1.5 bg-slate-200 dark:bg-slate-700 rounded-lg appearance-none cursor-pointer accent-orange-500"
                                        />
                                        <div class="flex justify-between text-[10px] font-mono text-slate-400">
                                            <span>8000</span>
                                            <span>{lavasrInputSr}</span>
                                            <span>48000</span>
                                        </div>
                                        <p class="text-[10px] text-slate-500">
                                            Match this to your source audio&apos;s quality.
                                        </p>
                                    </div>
                                    <div class="space-y-2">
                                        <div class="flex justify-between items-center">
                                            <span class="text-[10px] font-bold text-slate-500 uppercase">
                                                LavaSR Mix
                                            </span>
                                            <span class="text-[10px] font-mono text-orange-500">
                                                {Math.round(lavasrMix * 100)}%
                                            </span>
                                        </div>
                                        <input
                                            type="range"
                                            bind:value={lavasrMix}
                                            min="0"
                                            max="1"
                                            step="0.05"
                                            class="w-full h-1.5 bg-slate-200 dark:bg-slate-700 rounded-lg appearance-none cursor-pointer accent-orange-500"
                                        />
                                    </div>
                                </div>
                            </div>
                            <p class="text-[10px] text-slate-500 italic">
                                Best suited for speech that sounds narrow,
                                dull, or low-bandwidth and needs a more open
                                top end. If both are off, LavaSR acts as a passthrough.
                            </p>
                        </div>
                    {/if}

                    {#if cleanMethod === "voicefixer"}
                        <div
                            class="space-y-6 animate-in slide-in-from-top-2 duration-300"
                        >
                            <div class="space-y-4">
                                <div class="flex items-center justify-between">
                                    <span
                                        class="text-[10px] font-black tracking-widest text-slate-400 uppercase"
                                    >
                                        Quality Mode
                                    </span>
                                    <span
                                        class="text-xs font-mono font-bold text-blue-500"
                                    >
                                        {#if vfMode === 0}Standard (0){/if}
                                        {#if vfMode === 1}Enhanced (1){/if}
                                        {#if vfMode === 2}Deep (2){/if}
                                    </span>
                                </div>

                                <div class="flex gap-2">
                                    <button
                                        class="flex-1 py-3 rounded-xl text-[10px] font-black uppercase tracking-wider border transition-all {vfMode ===
                                        0
                                            ? 'bg-blue-600 text-white shadow-md border-blue-500'
                                            : 'bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-700 text-slate-500 hover:bg-slate-50 dark:hover:bg-slate-800'}"
                                        onclick={() => (vfMode = 0)}
                                    >
                                        Standard
                                    </button>
                                    <button
                                        class="flex-1 py-3 rounded-xl text-[10px] font-black uppercase tracking-wider border transition-all {vfMode ===
                                        1
                                            ? 'bg-blue-600 text-white shadow-md border-blue-500'
                                            : 'bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-700 text-slate-500 hover:bg-slate-50 dark:hover:bg-slate-800'}"
                                        onclick={() => (vfMode = 1)}
                                    >
                                        Enhanced
                                    </button>
                                    <button
                                        class="flex-1 py-3 rounded-xl text-[10px] font-black uppercase tracking-wider border transition-all {vfMode ===
                                        2
                                            ? 'bg-blue-600 text-white shadow-md border-blue-500'
                                            : 'bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-700 text-slate-500 hover:bg-slate-50 dark:hover:bg-slate-800'}"
                                        onclick={() => (vfMode = 2)}
                                    >
                                        Deep
                                    </button>
                                </div>
                            </div>
                            <p class="text-[10px] text-slate-500 italic">
                                VoiceFixer restoration models: 0 is balanced, 1
                                adds harmonics (good for dull audio), 2 is
                                aggressive removal (good for heavy noise).
                            </p>
                        </div>
                    {/if}

                    {#if cleanMethod === "remove_echo"}
                        <div
                            class="space-y-4 animate-in slide-in-from-top-2 duration-300"
                        >
                            <div class="space-y-2">
                                <div class="flex justify-between items-center">
                                    <span
                                        class="text-[10px] font-bold text-slate-500 uppercase"
                                        >Echo Reduction</span
                                    >
                                    <span
                                        class="text-[10px] font-mono text-blue-400"
                                        >{Math.round(echoReduction * 100)}%</span
                                    >
                                </div>
                                <input
                                    type="range"
                                    bind:value={echoReduction}
                                    min="0"
                                    max="1"
                                    step="0.05"
                                    class="w-full h-1.5 bg-slate-200 dark:bg-slate-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
                                />
                            </div>
                            <p class="text-[10px] text-slate-500 italic">
                                Remove Echo is focused on suppressing short room
                                reflections with minimal extra denoise.
                            </p>
                        </div>
                    {/if}

                    {#if cleanMethod === "manual"}
                        <div
                            class="space-y-6 animate-in slide-in-from-top-2 duration-300"
                        >
                            <div class="space-y-3">
                                <div class="flex items-center justify-between">
                                    <span
                                        class="text-[10px] font-black tracking-widest text-slate-400 uppercase"
                                        >Noise Profile</span
                                    >
                                    {#if isFetchingSpectrogram}
                                        <div
                                            class="flex items-center gap-1 text-blue-500 animate-pulse"
                                        >
                                            <Activity size={12} />
                                            <span
                                                class="text-[9px] font-black uppercase"
                                                >Analyzing...</span
                                            >
                                        </div>
                                    {:else if isPlayingNoise}
                                        <div
                                            class="flex items-center gap-1.5 text-blue-500 animate-pulse"
                                        >
                                            <Play
                                                size={10}
                                                fill="currentColor"
                                            />
                                            <span
                                                class="text-[9px] font-black uppercase"
                                                >Monitoring...</span
                                            >
                                        </div>
                                    {/if}
                                </div>

                                {#if !isFetchingSpectrogram && !zoomedSpectrogramUrl}
                                    <button
                                        onclick={fetchZoomedSpectrogram}
                                        class="w-full py-6 rounded-2xl border-2 border-dashed border-slate-200 dark:border-slate-800 hover:border-blue-500 dark:hover:border-blue-400 bg-white dark:bg-slate-900 hover:bg-blue-50/50 dark:hover:bg-blue-500/5 transition-all group flex flex-col items-center justify-center gap-3 active:scale-[0.98] shadow-sm hover:shadow-md"
                                    >
                                        <div
                                            class="w-12 h-12 rounded-full bg-slate-50 dark:bg-slate-800 flex items-center justify-center group-hover:bg-blue-100 dark:group-hover:bg-blue-900/30 group-hover:text-blue-600 transition-all"
                                        >
                                            <Sparkles
                                                size={24}
                                                class="text-slate-400 group-hover:scale-110 transition-transform"
                                            />
                                        </div>
                                        <div class="text-center">
                                            <span
                                                class="text-xs font-black text-slate-700 dark:text-slate-200 uppercase tracking-wider block mb-1"
                                                >Create Noise Profile</span
                                            >
                                            <p
                                                class="text-[10px] text-slate-400 font-medium"
                                            >
                                                Click to analyze the selected {compareDuration}s
                                                segment
                                            </p>
                                        </div>
                                    </button>
                                {:else if isFetchingSpectrogram}
                                    <div
                                        class="w-full p-6 rounded-2xl bg-blue-50/50 dark:bg-blue-500/5 border border-blue-100 dark:border-blue-500/20 space-y-4 animate-in fade-in zoom-in duration-300"
                                    >
                                        <div
                                            class="flex items-center justify-between mb-1"
                                        >
                                            <div
                                                class="flex items-center gap-2"
                                            >
                                                <div
                                                    class="w-2 h-2 rounded-full bg-blue-500 animate-ping"
                                                ></div>
                                                <span
                                                    class="text-[10px] font-black text-blue-600 dark:text-blue-400 uppercase tracking-widest"
                                                >
                                                    {spectrogramProgress ||
                                                        (error
                                                            ? "Failed"
                                                            : "Initializing...")}
                                                </span>
                                            </div>
                                            {#if spectrogramProgress?.includes("%")}
                                                <span
                                                    class="text-xs font-black text-blue-600 dark:text-blue-400"
                                                >
                                                    {spectrogramProgress.match(
                                                        /\d+/,
                                                    ) || "0"}%
                                                </span>
                                            {/if}
                                        </div>

                                        <div
                                            class="w-full h-2.5 bg-slate-200 dark:bg-slate-800 rounded-full overflow-hidden p-0.5"
                                        >
                                            <div
                                                class="h-full bg-gradient-to-r from-blue-400 to-blue-600 rounded-full transition-all duration-500 ease-out relative"
                                                style="width: {spectrogramProgress?.match(
                                                    /\d+/,
                                                ) || 2}%"
                                            >
                                                <div
                                                    class="absolute inset-0 bg-white/20 animate-sparkle"
                                                ></div>
                                            </div>
                                        </div>

                                        <p
                                            class="text-[9px] text-slate-400 text-center font-medium italic"
                                        >
                                            Please wait while we generate the
                                            high-resolution spectrogram
                                        </p>
                                    </div>
                                {:else if zoomedSpectrogramUrl}
                                    <!-- Keep existing result view here if any, or just show complete -->
                                    <div
                                        class="w-full p-4 rounded-xl bg-green-50/30 dark:bg-green-500/5 border border-green-100/50 dark:border-green-500/10 flex items-center justify-between"
                                    >
                                        <div class="flex items-center gap-3">
                                            <div
                                                class="w-10 h-10 rounded-lg bg-green-100 dark:bg-green-900/30 flex items-center justify-center text-green-600"
                                            >
                                                <Activity size={20} />
                                            </div>
                                            <div>
                                                <span
                                                    class="text-[10px] font-black text-green-700 dark:text-green-400 uppercase block tracking-wider"
                                                    >Profile Active</span
                                                >
                                                <span
                                                    class="text-[9px] text-slate-400 uppercase font-bold"
                                                    >Ready for reduction</span
                                                >
                                            </div>
                                        </div>
                                        <button
                                            onclick={fetchZoomedSpectrogram}
                                            class="text-[9px] font-black text-slate-400 hover:text-blue-500 uppercase tracking-widest px-3 py-1.5 border border-slate-200 dark:border-slate-800 rounded-lg hover:border-blue-500 transition-all"
                                        >
                                            Re-Analyze
                                        </button>
                                    </div>
                                {/if}
                            </div>

                            <!-- Manual Controls -->
                            <div class="grid grid-cols-2 gap-4">
                                <div class="space-y-2">
                                    <div
                                        class="flex justify-between items-center"
                                    >
                                        <span
                                            class="text-[10px] font-bold text-slate-500 uppercase"
                                            >Reduction</span
                                        >
                                        <span
                                            class="text-[10px] font-mono text-blue-400"
                                            >{Math.round(
                                                noiseReductionAmount * 100,
                                            )}%</span
                                        >
                                    </div>
                                    <input
                                        type="range"
                                        bind:value={noiseReductionAmount}
                                        min="0"
                                        max="1"
                                        step="0.05"
                                        class="w-full h-1.5 bg-slate-200 dark:bg-slate-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
                                    />
                                </div>
                                <div class="space-y-2">
                                    <div
                                        class="flex justify-between items-center"
                                    >
                                        <span
                                            class="text-[10px] font-bold text-slate-500 uppercase"
                                            >Sensitivity</span
                                        >
                                        <span
                                            class="text-[10px] font-mono text-blue-400"
                                            >{noiseSensitivity.toFixed(1)}</span
                                        >
                                    </div>
                                    <input
                                        type="range"
                                        bind:value={noiseSensitivity}
                                        min="0.5"
                                        max="4"
                                        step="0.1"
                                        class="w-full h-1.5 bg-slate-200 dark:bg-slate-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
                                    />
                                </div>
                            </div>

                            <p class="text-[10px] text-slate-500 italic">
                                Manual mode uses Spectral Subtraction. Profiling
                                a clean noise segment is required for best
                                results.
                            </p>
                        </div>
                    {/if}

                    {#if cleanMethod !== "restoration"}
                        <button
                            onclick={runCleanup}
                            disabled={isCleaning}
                            class="w-full py-4 rounded-xl border border-blue-200 dark:border-blue-900/50 bg-blue-50 dark:bg-blue-950 hover:bg-blue-100 dark:hover:bg-blue-900/30 text-blue-600 dark:text-blue-400 font-black text-sm uppercase tracking-widest flex items-center justify-center gap-3 transition-all active:scale-95 shadow-lg shadow-blue-500/10"
                        >
                            {#if isCleaning}
                                <Loader2 size={18} class="animate-spin" />
                                Generating Preview...
                            {:else}
                                <Sparkles size={18} />
                                Preview Optimization
                            {/if}
                        </button>
                    {/if}
                </div>

                {#if cleanMethod !== "restoration"}
                    {#if comparisonSamples.length > 0}
                        <div
                            class="space-y-4 pt-6 border-t border-slate-100 dark:border-slate-800 animate-in slide-in-from-bottom-4 duration-500"
                        >
                            <div
                                class="bg-blue-50/50 dark:bg-blue-900/10 border border-blue-100 dark:border-blue-900/30 p-5 rounded-2xl shadow-sm dark:shadow-none"
                            >
                                <div
                                    class="flex items-center justify-between mb-3 text-[10px] font-bold uppercase tracking-widest"
                                >
                                    <div
                                        class="flex items-center gap-2 text-blue-600"
                                    >
                                        <div
                                            class="w-1.5 h-1.5 bg-blue-500 rounded-full animate-pulse"
                                        ></div>
                                        Synchronized Player
                                    </div>
                                    <span class="font-mono text-slate-400"
                                        >{formatDuration(comparePlaybackTime)} /
                                        {formatDuration(compareDuration)}</span
                                    >
                                </div>
                                <audio
                                    bind:this={compareAudioElement}
                                    src={getAudioSrc(activeSampleUrl)}
                                    ontimeupdate={(e) =>
                                        (comparePlaybackTime =
                                            e.currentTarget.currentTime)}
                                    oncanplay={handleCompareMetadata}
                                    onplay={() =>
                                        dispatchAudioCommand("PAUSE_ALL")}
                                    controls
                                    preload="auto"
                                    class="w-full h-10 opacity-90 rounded-lg overflow-hidden"
                                ></audio>
                            </div>

                            {#if comparisonSamples.length > 0}
                                <div class="flex flex-col gap-2">
                                    {#each comparisonSamples as sample}
                                        <button
                                            onclick={() =>
                                                switchSample(sample.url)}
                                            class="flex items-center justify-between p-4 rounded-xl border transition-all active:scale-[0.98] {activeSampleUrl ===
                                            sample.url
                                                ? 'bg-blue-600 border-blue-500 text-white shadow-lg translate-x-1'
                                                : 'bg-white dark:bg-slate-800/80 border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 hover:border-slate-300 dark:hover:border-slate-600 shadow-sm'}"
                                        >
                                            <div
                                                class="flex items-center gap-3"
                                            >
                                                <Music
                                                    size={18}
                                                    class={activeSampleUrl ===
                                                    sample.url
                                                        ? "text-blue-100"
                                                        : "text-slate-400"}
                                                />

                                                <div class="text-left">
                                                    <span
                                                        class="block font-bold leading-none"
                                                        >{sample.label}</span
                                                    >
                                                </div>
                                            </div>
                                        </button>
                                    {/each}
                                </div>
                            {/if}
                        </div>
                    {/if}

                    <div class="pt-4 flex flex-col gap-3">
                        {#if comparisonSamples.length > 0}
                            {@const activeSample = comparisonSamples.find(
                                (s) => s.url === activeSampleUrl,
                            )}
                            {#if activeSample}
                                {#if activeSample.bitrate === "original" || (typeof activeSample.bitrate === "string" && activeSample.bitrate.startsWith("cleaned_"))}
                                    <!-- Bitrate Mode Toggle -->
                                    <div
                                        class="flex items-center justify-between mb-2"
                                    >
                                        <span
                                            class="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-3"
                                            >Bitrate Mode</span
                                        >
                                        <div
                                            class="flex bg-slate-100 dark:bg-slate-900 rounded-lg p-1 border border-slate-200 dark:border-slate-800"
                                        >
                                            <button
                                                onclick={() =>
                                                    (bitrateMode = "cbr")}
                                                class="px-3 py-1 rounded text-[10px] font-black uppercase transition-all
                                            {bitrateMode === 'cbr'
                                                    ? 'bg-white dark:bg-slate-800 text-blue-600 shadow-sm'
                                                    : 'text-slate-500'}"
                                            >
                                                Constant (CBR)
                                            </button>
                                            <button
                                                onclick={() =>
                                                    (bitrateMode = "vbr")}
                                                class="px-3 py-1 rounded text-[10px] font-black uppercase transition-all
                                            {bitrateMode === 'vbr'
                                                    ? 'bg-white dark:bg-slate-800 text-blue-600 shadow-sm'
                                                    : 'text-slate-500'}"
                                            >
                                                Variable (VBR)
                                            </button>
                                        </div>
                                    </div>

                                    <!-- Target Bitrate Selector -->
                                    <div
                                        class="flex items-center justify-between bg-slate-50 dark:bg-slate-900/50 p-1.5 rounded-xl border border-slate-200 dark:border-slate-800 mb-2 shadow-inner"
                                    >
                                        <span
                                            class="text-xs font-bold text-slate-500 uppercase tracking-wider ml-3"
                                            >{bitrateMode === "cbr"
                                                ? "Output Bitrate"
                                                : "Output Quality"}</span
                                        >
                                        <div class="flex items-center gap-1">
                                            {#if bitrateMode === "cbr"}
                                                {#each compareBitrates as bitrate}
                                                    <button
                                                        onclick={() =>
                                                            (targetBitrateForClean =
                                                                bitrate)}
                                                        class="px-3 py-1.5 rounded-lg text-xs font-bold transition-all {targetBitrateForClean ===
                                                        bitrate
                                                            ? 'bg-blue-600 text-white shadow-md'
                                                            : 'text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-white dark:hover:bg-slate-700'}"
                                                    >
                                                        {bitrate}k
                                                    </button>
                                                {/each}
                                            {:else}
                                                {#each vbrLevels as vbr}
                                                    <button
                                                        onclick={() =>
                                                            (targetVbrLevel =
                                                                vbr.id)}
                                                        title={vbr.desc}
                                                        class="px-3 py-1.5 rounded-lg text-xs font-bold transition-all {targetVbrLevel ===
                                                        vbr.id
                                                            ? 'bg-blue-600 text-white shadow-md'
                                                            : 'text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-white dark:hover:bg-slate-700'}"
                                                    >
                                                        {vbr.label}
                                                    </button>
                                                {/each}
                                            {/if}
                                        </div>
                                    </div>

                                    <button
                                        onclick={async () => {
                                            // 1. Capture data BEFORE closing anything
                                            const capturedSample = $state.snapshot(activeSample);
                                            const currentFile = $state.snapshot(selectedFileForCompare);
                                            const finalBitrate = bitrateMode === "cbr" ? targetBitrateForClean : targetVbrLevel;

                                            console.log("[Modal] Original Save starting...", { capturedSample, finalBitrate });

                                            // Ensure params exist and attach selected bitrate
                                            if (!capturedSample.params) {
                                                capturedSample.params = {};
                                            }
                                            if (
                                                capturedSample.bitrate !==
                                                    "original" &&
                                                !capturedSample.params.method
                                            ) {
                                                capturedSample.params.method =
                                                    cleanMethod;
                                            }
                                            capturedSample.params.bitrate = finalBitrate;
                                            capturedSample.params.vf_mode = vfMode;
                                            capturedSample.params.echo_strength = echoReduction;

                                            const idx = files.findIndex(
                                                (f) => f.path.normalize('NFC') === currentFile.path.normalize('NFC')
                                            );

                                            if (idx !== -1) {
                                                await convertFile(idx, capturedSample);
                                                selectedFileForCompare = null;
                                            } else if (
                                                currentFile.isProxy &&
                                                currentFile.originalIndex !== undefined
                                            ) {
                                                const origIdx = currentFile.originalIndex;
                                                const inputPath = currentFile.path;
                                                await convertFile(origIdx, capturedSample, inputPath);
                                                selectedFileForCompare = null;
                                            } else {
                                                console.error("Could not find file for optimization");
                                                selectedFileForCompare = null;
                                            }
                                        }}
                                        class="w-full bg-green-50 dark:bg-green-950 hover:bg-green-100 dark:hover:bg-green-900/30 text-green-700 dark:text-green-400 font-black py-4 rounded-2xl flex items-center justify-center gap-3 transition-all active:scale-95 border border-green-200 dark:border-green-900/50 group"
                                    >
                                        <Save
                                            size={20}
                                            class="text-green-500 group-hover:text-white"
                                        />
                                        <span
                                            >Optimize with {activeSample.label} ({bitrateMode ===
                                            "cbr"
                                                ? targetBitrateForClean + "kbps"
                                                : targetVbrLevel.toUpperCase()})</span
                                        >
                                    </button>
                                {:else}
                                    <!-- Simplified Button for Non-Original Samples -->
                                    <button
                                        onclick={async () => {
                                            // 1. Capture data IMMEDIATELY before closing anything
                                            const capturedSample = $state.snapshot(activeSample);
                                            const currentFile = $state.snapshot(selectedFileForCompare);

                                            console.log("[Modal] Simplified Save starting...", capturedSample);

                                            if (!capturedSample.params) {
                                                capturedSample.params = {};
                                            }
                                            if (
                                                capturedSample.bitrate !==
                                                    "original" &&
                                                !capturedSample.params.method
                                            ) {
                                                capturedSample.params.method =
                                                    cleanMethod;
                                            }

                                            const idx = files.findIndex(
                                                (f) => f.path.normalize('NFC') === currentFile.path.normalize('NFC')
                                            );

                                            if (idx !== -1) {
                                                console.log("[Modal] Simplified Save for index:", idx, capturedSample);
                                                // 2. Queue the action
                                                await convertFile(idx, capturedSample);
                                                // 3. Close modal ONLY after action is queued
                                                selectedFileForCompare = null;
                                            } else if (
                                                currentFile.isProxy &&
                                                currentFile.originalIndex !== undefined
                                            ) {
                                                const origIdx = currentFile.originalIndex;
                                                const proxyInputPath = currentFile.path;
                                                console.log("[Modal] Simplified Proxy Save for index:", origIdx, capturedSample);
                                                await convertFile(origIdx, capturedSample, proxyInputPath);
                                                selectedFileForCompare = null;
                                            } else {
                                                console.warn("[Modal] Could not find file index for:", currentFile.path);
                                                selectedFileForCompare = null;
                                            }
                                        }}
                                        class="w-full bg-green-50 dark:bg-green-950 hover:bg-green-100 dark:hover:bg-green-900/30 text-green-700 dark:text-green-400 font-black py-4 rounded-2xl flex items-center justify-center gap-3 transition-all active:scale-95 border border-green-200 dark:border-green-900/50 group"
                                    >
                                        <Save
                                            size={20}
                                            class="text-green-500 group-hover:text-white"
                                        />
                                        <span
                                            >Optimize with {activeSample.label}</span
                                        >
                                    </button>
                                {/if}
                            {/if}
                        {/if}
                    </div>
                {/if}
            </div>
        </div>
    </div>
{/if}

<style>
    /* Custom Scrollbar */
    .scrollbar-thin::-webkit-scrollbar {
        width: 6px;
    }
    .scrollbar-track-transparent::-webkit-scrollbar-track {
        background-color: transparent;
    }
</style>
