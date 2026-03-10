<script>
    import {
        Activity,
        Play,
        Folder,
        Music,
        Waves,
        Sparkles,
        ChevronRight,
        CheckCircle2,
        FlaskConical,
        Loader2,
        Clock,
        Flag,
        AlertTriangle,
        MessageSquare,
        Tag,
        Info,
    } from "lucide-svelte";
    import {
        formatDuration,
        formatSize,
        getSavingsPercent,
        getRowColor,
    } from "../../utils/formatters.js";

    /**
     * @typedef {Object} AudioFile
     * @property {string} path
     * @property {string} name
     * @property {string} originalName
     * @property {number} size
     * @property {number} duration
     * @property {number} [channels]
    * @property {Record<string, any>} [allTags]
    * @property {{ allTags?: Record<string, any> }} [optimizedMetadata]
     * @property {number} [maxFreq]
     * @property {number} [currentBitrate]
     * @property {number} [recommended_bitrate]
     * @property {string} status
     * @property {string} [error]
     * @property {number} [progress]
     * @property {number} [optimizationStartTime]
     * @property {number} [optimizationDuration]
     * @property {string} [finalPath]
     * @property {number} [optimizedSize]
     * @property {number} [actualOptimizedBitrate]
     * @property {string} [quality] - "good", "bad", etc.
     * @property {number} [avgMaxFreq]
     * @property {number} [noiseFloor]
     * @property {Array<number>} [samplePoints]
     * @property {boolean} [isReanalyzing]
     */

    /**
     * @type {{
     *   file: AudioFile,
     *   index: number,
     *   folderPath: string,
     *   globalActiveTrack: any,
     *   lastFocusedIndex: number,
     *   selectedPaths: Set<string>,
     *   flaggedPaths: Set<string>,
     *   denoisedPaths: Set<string>,
     *   badQualityPaths: Set<string>,
     *   currentTime: number,
     *   setGlobalTrack: (track: any, playlist?: any[]) => void,
     *   toggleSelect: (index: number, event: Event, pathOverride?: string) => void,
     *   revealInFinder: (path: string) => void,
     *   openInAudacity: (path: string) => void,
     *   openInRX: (path: string) => void,
     *   openReoptimizeModal: (index: number) => void,
     *   openCompareModal: (index: number) => void,
     *   analyzeFile: (index: number, full?: boolean, force?: boolean) => void,
     *   toggleFlag: (path: string) => void,
     *   toggleDenoised: (path: string) => void,
     *   toggleBadQuality: (path: string) => void,
     *   fileNotes: any,
     *   setFileNote: (path: string, note: string) => void,
     *   getFileNote: (path: string) => string,
     *   totalFiles?: number,
     *   showAnalysisColumn?: boolean
     * }}
     */
    let {
        file,
        index,
        totalFiles = 0,
        folderPath,
        globalActiveTrack,
        lastFocusedIndex = $bindable(),
        selectedPaths,
        flaggedPaths,
        denoisedPaths,
        badQualityPaths,
        currentTime,
        setGlobalTrack,
        toggleSelect,
        revealInFinder,
        openInAudacity,
        openInRX,
        openReoptimizeModal,
        openCompareModal,
        analyzeFile,
        toggleFlag,
        toggleDenoised,
        toggleBadQuality,
        fileNotes,
        setFileNote,
        getFileNote,
        showAnalysisColumn = true,
    } = $props();

    let noteInput = $state("");
    let showNoteInput = $state(false);
    let showMetadata = $state(false);

    let isPlaying = $derived(globalActiveTrack?.path === file.path);
    $effect(() => {
        // Keep local note state bound to current row when file identity changes.
        if (!showNoteInput) {
            noteInput = getFileNote(file.path);
        }
    });

    function handleNoteKeyDown(e) {
        if (e.key === "Enter") {
            setFileNote(file.path, noteInput);
            showNoteInput = false;
        }
    }

    function getVisibleTagEntries(tags) {
        if (!tags || typeof tags !== "object") return [];
        return Object.entries(tags).filter(([key]) => {
            const normalized = String(key || "").toLowerCase();
            if (normalized === "encoder") return false;
            if (normalized.startsWith("id3v2_priv.xmp")) return false;
            return true;
        });
    }
</script>

<div
    class="group relative rounded-2xl border p-4 transition-all hover:shadow-xl dark:hover:shadow-black/20
    {isPlaying
        ? 'bg-blue-50 dark:bg-blue-900/20 border-blue-500 ring-2 ring-inset ring-blue-400 dark:ring-blue-400/50 shadow-lg dark:shadow-blue-900/30 scale-[1.005] z-20'
        : getRowColor(file)} 
    {lastFocusedIndex === index && !isPlaying
        ? 'ring-1 ring-blue-500/50 scale-[1.01] shadow-lg shadow-blue-500/10'
        : ''}"
>
    <div class="flex items-center gap-4 flex-wrap lg:flex-nowrap">
        <!-- Play / Icon Button -->
        <div class="flex items-center gap-3 min-w-0 flex-1">
            <button
                id="btn-play-{index}"
                onclick={() => {
                    lastFocusedIndex = index;
                    setGlobalTrack(
                        {
                            path: file.path,
                            title: file.originalName,
                            optimizedPath: file.finalPath,
                            duration: file.duration,
                            isOptimized:
                                !!file.finalPath && file.status === "completed",
                            btnId: `btn-play-${index}`,
                        },
                        null,
                    );
                }}
                class="p-2 rounded-xl transition-all shadow-lg active:scale-90
                    {globalActiveTrack?.path === file.path
                    ? 'bg-blue-600 text-white shadow-blue-500/20'
                    : 'bg-white dark:bg-slate-800 text-slate-400 hover:text-blue-600 dark:hover:text-white hover:bg-blue-50 dark:hover:bg-slate-700 border border-slate-100 dark:border-transparent shadow-sm dark:shadow-none'}"
                title="Play file"
            >
                {#if globalActiveTrack?.path === file.path}
                    <Activity size={20} />
                {:else}
                    <Play size={20} fill="currentColor" />
                {/if}
            </button>
            <div class="flex items-center gap-3 min-w-0">
                {#key `${file.path}:${selectedPaths.has(file.path)}`}
                    <input
                        type="checkbox"
                        checked={selectedPaths.has(file.path)}
                        onclick={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            toggleSelect(index, e, file.path);
                        }}
                        class="w-4 h-4 rounded border-slate-300 dark:border-slate-700 text-blue-600 focus:ring-blue-500 cursor-pointer"
                    />
                {/key}
                <div class="min-w-0 flex-1">
                    <div class="flex items-center gap-3">
                        <h3
                            class="font-semibold text-slate-800 dark:text-slate-200 truncate"
                        >
                            {file.name || file.originalName}
                        </h3>
                        {#if isPlaying && totalFiles > 0}
                            <span
                                class="flex-shrink-0 px-2 py-0.5 rounded-lg bg-blue-600 dark:bg-blue-500 text-white text-[10px] font-black shadow-lg shadow-blue-500/30 animate-in zoom-in-90 duration-300"
                            >
                                {index + 1} / {totalFiles}
                            </span>
                        {/if}
                    </div>
                    <div
                        class="flex items-center gap-1.5 opacity-50 hover:opacity-100 transition-opacity"
                    >
                        <div class="flex items-center gap-1">
                            <button
                                onclick={(e) => {
                                    e.stopPropagation();
                                    revealInFinder(file.path);
                                }}
                                class="text-slate-500 hover:text-blue-400 p-0.5 rounded transition-colors"
                                title="Show Original in Finder"
                            >
                                <Folder size={12} />
                            </button>

                            <button
                                onclick={(e) => {
                                    e.stopPropagation();
                                    openInAudacity(file.path);
                                }}
                                class="text-indigo-400 hover:text-indigo-300 p-0.5 rounded transition-colors"
                                title="Open Original in Audacity"
                            >
                                <Music size={16} />
                            </button>

                            <!-- Single Tag Icon for Metadata -->
                            <div class="relative">
                                <button
                                    onclick={(e) => {
                                        e.stopPropagation();
                                        showMetadata = !showMetadata;
                                    }}
                                    class="p-0.5 rounded transition-all active:scale-95 {showMetadata
                                        ? 'text-blue-500 bg-blue-500/10'
                                        : 'text-slate-400 hover:text-blue-400'}"
                                    title="View File Metadata (ID3 Tags)"
                                >
                                    <Tag size={16} />
                                </button>

                                {#if showMetadata}
                                    <button
                                        type="button"
                                        class="fixed inset-0 z-[100] cursor-default appearance-none border-0 p-0 m-0 rounded-none shadow-none bg-transparent"
                                        aria-label="Close metadata"
                                        title="Close metadata"
                                        onclick={(e) => {
                                            e.stopPropagation();
                                            showMetadata = false;
                                        }}
                                    ></button>
                                    <div
                                        class="absolute left-0 mt-2 w-80 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-2xl z-[101] p-3 animate-in fade-in zoom-in-95 duration-200 origin-top-left overflow-hidden flex flex-col"
                                    >
                                        <div
                                            class="grid grid-cols-1 md:grid-cols-2 gap-4 max-h-[450px] overflow-y-auto pr-1 scrollbar-thin scrollbar-thumb-slate-200 dark:scrollbar-thumb-slate-800"
                                        >
                                            <!-- Original Metadata -->
                                            <div class="min-w-0">
                                                <div
                                                    class="flex items-center gap-1.5 mb-2"
                                                >
                                                    <div
                                                        class="w-1 h-3 bg-slate-400 rounded-full"
                                                    ></div>
                                                    <span
                                                        class="text-[10px] uppercase font-black tracking-widest text-slate-500"
                                                        >Original File</span
                                                    >
                                                </div>
                                                <div class="space-y-2 pl-2">
                                                    {#if getVisibleTagEntries(file.allTags).length > 0}
                                                        {#each getVisibleTagEntries(file.allTags) as [key, value]}
                                                            <div
                                                                class="flex flex-col border-b border-slate-50 dark:border-slate-800/50 pb-1 last:border-0"
                                                            >
                                                                <span
                                                                    class="text-[9px] text-slate-400 uppercase font-black tracking-tighter"
                                                                    >{key}</span
                                                                >
                                                                <span
                                                                    class="text-xs text-slate-700 dark:text-slate-300 font-medium break-words leading-tight"
                                                                    >{value}</span
                                                                >
                                                            </div>
                                                        {/each}
                                                    {:else}
                                                        <span
                                                            class="text-[10px] text-slate-500 italic"
                                                            >No metadata tags
                                                            found</span
                                                        >
                                                    {/if}
                                                </div>
                                            </div>

                                            <!-- Optimized Metadata -->
                                            <div class="min-w-0">
                                                <div
                                                    class="flex items-center gap-1.5 mb-2"
                                                >
                                                    <div
                                                        class="w-1 h-3 bg-emerald-500 rounded-full"
                                                    ></div>
                                                    <span
                                                        class="text-[10px] uppercase font-black tracking-widest text-emerald-500"
                                                        >Optimized File</span
                                                    >
                                                </div>
                                                <div class="space-y-2 pl-2">
                                                    {#if file.finalPath && file.optimizedMetadata}
                                                        {#if getVisibleTagEntries(file.optimizedMetadata.allTags).length > 0}
                                                            {#each getVisibleTagEntries(file.optimizedMetadata.allTags) as [key, value]}
                                                                <div
                                                                    class="flex flex-col border-b border-slate-50 dark:border-slate-800/50 pb-1 last:border-0"
                                                                >
                                                                    <span
                                                                        class="text-[9px] text-emerald-600/50 uppercase font-black tracking-tighter"
                                                                        >{key}</span
                                                                    >
                                                                    <span
                                                                        class="text-xs text-slate-700 dark:text-slate-300 font-medium break-words leading-tight"
                                                                        >{value}</span
                                                                    >
                                                                </div>
                                                            {/each}
                                                        {:else}
                                                            <span
                                                                class="text-[10px] text-slate-500 italic"
                                                                >No metadata
                                                                tags found</span
                                                            >
                                                        {/if}
                                                    {:else}
                                                        <span
                                                            class="text-[10px] text-slate-500 italic"
                                                            >No optimized file
                                                            yet</span
                                                        >
                                                    {/if}
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                {/if}
                            </div>

                            {#if file.finalPath}
                                <button
                                    onclick={(e) => {
                                        e.stopPropagation();
                                        revealInFinder(file.finalPath);
                                    }}
                                    class="text-green-500/70 hover:text-green-400 p-0.5 rounded transition-colors"
                                    title="Show Optimized in Finder"
                                >
                                    <Folder size={12} />
                                </button>

                                <button
                                    onclick={(e) => {
                                        e.stopPropagation();
                                        openInAudacity(file.finalPath);
                                    }}
                                    class="text-indigo-400/80 hover:text-indigo-300 p-0.5 rounded transition-colors"
                                    title="Open Optimized in Audacity"
                                >
                                    <Music size={16} />
                                </button>
                            {/if}
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Stats Grid -->
        <div class="flex items-center gap-4 lg:gap-8 text-sm shrink-0">
            <!-- Bitrate & Mode -->
            <!-- Bitrate & Mode -->
            <div class="flex flex-col items-end w-24 lg:w-28 shrink min-w-0">
                <span
                    class="text-slate-500 text-[10px] uppercase font-bold tracking-widest text-right truncate w-full"
                    >Bitrate</span
                >
                <div class="flex flex-col items-end font-mono">
                    {#if file.currentBitrate}
                        <div class="flex items-center gap-1.5">
                            <span
                                class="font-bold text-slate-700 dark:text-slate-300"
                            >
                                {file.currentBitrate}k
                            </span>

                            {#if file.status === "completed" && file.actualOptimizedBitrate}
                                <div class="flex items-center gap-1">
                                    <ChevronRight
                                        size={12}
                                        class="text-slate-600"
                                    />
                                    <span
                                        class="font-bold text-emerald-600 dark:text-emerald-400"
                                    >
                                        {file.actualOptimizedBitrate}k
                                    </span>
                                </div>
                            {/if}
                        </div>
                    {:else}
                        <span class="text-slate-600 italic">...</span>
                    {/if}

                    <div class="mt-0.5">
                        {#if file.channels === 1}
                            <span
                                class="text-slate-800 dark:text-white text-[10px] font-bold uppercase"
                                >Mono</span
                            >
                        {:else if file.channels === 2}
                            <span
                                class="text-blue-400/80 text-[10px] font-bold uppercase"
                                >Stereo</span
                            >
                        {:else if file.channels > 2}
                            <span
                                class="text-purple-400/80 text-[10px] font-bold uppercase"
                                >{file.channels}ch</span
                            >
                        {/if}
                    </div>
                </div>
            </div>

            <!-- Analysis Results Column -->
            <!-- Analysis Results Column -->
            {#if showAnalysisColumn}
                <div
                    class="flex flex-col items-end w-28 lg:w-32 gap-1 animate-in fade-in zoom-in-95 duration-300 shrink min-w-0"
                >
                    <span
                        class="text-slate-500 text-[10px] uppercase font-bold tracking-widest text-right truncate w-full"
                        >Analysis</span
                    >
                    {#if file.avgMaxFreq !== undefined}
                        <div class="flex flex-col items-end gap-0.5">
                            <!-- Max Freq & Quality -->
                            <div
                                class="flex flex-col items-end"
                                title="Highest frequency found. Higher usually means better quality."
                            >
                                <div class="flex items-center gap-1.5">
                                    <span
                                        class="text-[9px] text-slate-400 font-bold uppercase"
                                        >Max</span
                                    >
                                    <span
                                        class="font-mono font-bold text-slate-600 dark:text-slate-400 text-xs"
                                        >{file.avgMaxFreq}k</span
                                    >
                                </div>
                                {#if file.quality}
                                    <span
                                        class="text-[9px] text-slate-500 font-bold leading-none dark:text-slate-500 text-right -mt-0.5"
                                        >{file.quality}</span
                                    >
                                {/if}
                            </div>

                            <!-- Noise -->
                            <div
                                class="flex flex-col items-end mt-1"
                                title="Background noise level: <-60dB (Silent), -60 to -50dB (Clean), -50 to -40dB (Normal), >-40dB (Noisy)"
                            >
                                <div
                                    class="flex items-center justify-end gap-1.5"
                                >
                                    <span
                                        class="text-[9px] text-slate-400 font-bold uppercase"
                                        >Noise</span
                                    >
                                    <span
                                        class="font-mono font-bold text-slate-600 dark:text-slate-400 text-xs"
                                        >{file.noiseFloor}dB</span
                                    >
                                </div>
                                <span
                                    class="text-[9px] text-slate-400 font-normal text-right -mt-0.5"
                                    >({file.noiseFloor < -60
                                        ? "Silent"
                                        : file.noiseFloor < -50
                                          ? "Clean"
                                          : file.noiseFloor < -40
                                            ? "Normal"
                                            : "Noisy"})</span
                                >
                            </div>

                            <!-- Recommended -->
                            {#if file.recommended_bitrate}
                                <div
                                    class="flex items-center justify-end gap-1.5 mt-1"
                                    title="Recommended Bitrate based on analysis"
                                >
                                    <span
                                        class="text-[9px] text-blue-400 font-bold uppercase"
                                        >Rec</span
                                    >
                                    <span
                                        class="font-mono font-bold text-blue-600 dark:text-blue-400 text-xs"
                                        >{file.recommended_bitrate}k</span
                                    >
                                </div>
                            {/if}
                        </div>
                    {:else if file.status === "analyzing"}
                        <span
                            class="text-xs text-blue-500 font-bold animate-pulse"
                            >Scanning...</span
                        >
                    {:else}
                        <!-- Empty state when analysis column is shown but file hasn't been analyzed -->
                        <span
                            class="text-xs text-slate-300 dark:text-slate-700 font-bold"
                            >-</span
                        >
                    {/if}
                </div>
            {/if}

            <!-- Duration -->
            <div class="flex flex-col items-end w-16 lg:w-20 shrink min-w-0">
                <span
                    class="text-xs font-bold text-slate-500 uppercase tracking-tighter mb-0.5 text-right truncate w-full"
                    >Duration</span
                >
                <span
                    class="font-mono text-slate-700 dark:text-slate-300 truncate"
                >
                    {formatDuration(file.duration)}
                </span>
            </div>

            <!-- Size Display Vertical -->
            <div
                class="flex flex-col items-end w-32 lg:w-40 gap-1.5 shrink min-w-0"
            >
                <div class="flex flex-col items-end w-full">
                    <span
                        class="text-slate-500 text-[9px] uppercase font-bold tracking-widest text-right truncate w-full"
                        >Original</span
                    >
                    <span
                        class="font-mono text-slate-700 dark:text-slate-300 font-bold leading-none truncate"
                    >
                        {formatSize(file.size)}
                    </span>
                </div>

                {#if file.status === "completed" && file.optimizedSize}
                    <div
                        class="flex flex-col items-end animate-in slide-in-from-top-1"
                    >
                        <span
                            class="text-emerald-500 dark:text-emerald-400 text-[9px] uppercase font-black tracking-widest"
                            >Optimized</span
                        >
                        <div
                            class="flex items-center gap-1.5 font-mono leading-none"
                        >
                            <span
                                class="text-slate-500 dark:text-slate-400 font-bold"
                                style="font-size: 1.3em;"
                            >
                                (-{getSavingsPercent(
                                    file.size,
                                    file.optimizedSize,
                                )}%)
                            </span>
                            <span
                                class="text-green-600 dark:text-green-400 font-bold"
                            >
                                {formatSize(file.optimizedSize)}
                            </span>
                        </div>
                    </div>
                {/if}
            </div>
        </div>

        <!-- Actions -->
        <div
            class="flex items-center justify-end gap-2 pl-4 w-40 lg:w-52 shrink-0"
        >
            {#if file.status === "completed" || (file.status === "analyzing" && file.finalPath)}
                <div class="flex items-center gap-2">
                    <!-- Analyze Button for Done State -->
                    <button
                        onclick={() => analyzeFile(index, false, true)}
                        disabled={file.status === "analyzing" ||
                            file.isReanalyzing}
                        class="p-2 rounded-xl transition-all active:scale-90 flex items-center justify-center hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400"
                        title="Quick Scan"
                    >
                        {#if file.status === "analyzing" || file.isReanalyzing}
                            <Loader2
                                size={18}
                                class="animate-spin text-blue-400"
                            />
                        {:else}
                            <Activity size={18} />
                        {/if}
                    </button>

                    <div class="flex flex-col items-center gap-2">
                        <div
                            class="p-2.5 rounded-xl bg-green-500 text-white flex items-center gap-2 px-4 shadow-lg shadow-green-500/20"
                        >
                            <CheckCircle2 size={18} />
                            <span class="text-xs font-bold uppercase">Done</span
                            >
                        </div>
                        {#if file.optimizationDuration}
                            <span
                                class="text-[10px] text-green-600 dark:text-green-400 font-mono font-bold"
                            >
                                {Math.floor(
                                    file.optimizationDuration / 60,
                                )}:{String(
                                    Math.floor(file.optimizationDuration % 60),
                                ).padStart(2, "0")}
                            </span>
                        {/if}
                        <button
                            onclick={() => openCompareModal(index)}
                            class="text-[10px] uppercase font-black text-indigo-400 hover:text-indigo-300 transition-colors flex items-center gap-1.5"
                            title="Open Audio Laboratory"
                        >
                            <FlaskConical size={12} />
                            Laboratory
                        </button>

                        <button
                            onclick={(e) => {
                                e.stopPropagation();
                                openReoptimizeModal(index);
                            }}
                            class="text-[10px] uppercase font-black text-amber-500 hover:text-amber-400 transition-colors flex items-center gap-1.5"
                            title="Re-optimize (Double Pass)"
                        >
                            <Sparkles size={12} />
                            Re-optimize
                        </button>
                    </div>
                </div>
            {:else if (file.status === "idle" || file.status === "error" || file.status === "analyzing") && !file.finalPath}
                <div class="flex items-center gap-2">
                    <!-- Smaller Analyze Button -->
                    <button
                        onclick={() => analyzeFile(index, false, true)}
                        disabled={file.status === "analyzing" ||
                            file.isReanalyzing}
                        class="p-2 rounded-xl transition-all active:scale-90 flex items-center justify-center hover:bg-slate-100 dark:hover:bg-slate-800
                        {file.status === 'error'
                            ? 'text-red-400'
                            : 'text-slate-400'}"
                        title={file.status === "error"
                            ? "Retry Scan"
                            : "Quick Scan"}
                    >
                        {#if file.status === "analyzing" || file.isReanalyzing}
                            <Loader2
                                size={18}
                                class="animate-spin text-blue-400"
                            />
                        {:else}
                            <Activity size={18} />
                        {/if}
                    </button>

                    <!-- Main Laboratory Button (Always shown as primary) -->
                    <button
                        onclick={() => openCompareModal(index)}
                        class="p-2.5 rounded-xl bg-indigo-50 dark:bg-indigo-600/10 hover:bg-indigo-600 text-indigo-600 dark:text-indigo-400 hover:text-white transition-all active:scale-90 flex items-center gap-2 px-4 border border-indigo-100 dark:border-transparent"
                        title="Open Audio Laboratory"
                    >
                        <FlaskConical size={18} />
                        <span class="text-xs font-bold uppercase"
                            >Laboratory</span
                        >
                    </button>
                </div>
                {#if file.error}
                    <div class="mt-1 text-right">
                        <span
                            class="text-[9px] text-red-500 font-bold uppercase max-w-[150px] truncate"
                            >{file.error}</span
                        >
                    </div>
                {/if}
            {:else if file.status === "analyzed" || file.status === "converting" || file.status === "queued"}
                {#if file.status === "converting"}
                    {@const elapsedMs =
                        currentTime -
                        (file.optimizationStartTime || currentTime)}
                    {@const elapsedMin = Math.floor(elapsedMs / 60000)}
                    {@const elapsedSec = Math.floor((elapsedMs % 60000) / 1000)}
                    <div class="flex flex-col items-center gap-2 py-2">
                        <Loader2
                            size={48}
                            class="animate-spin text-blue-500 dark:text-blue-400"
                            strokeWidth={2}
                        />
                        <div class="flex flex-col items-center gap-1">
                            <span
                                class="text-lg font-black text-blue-600 dark:text-blue-400"
                            >
                                {file.progress || 0}%
                            </span>
                            <span
                                class="text-xs text-blue-500 dark:text-blue-400 font-mono font-bold"
                            >
                                {elapsedMin}:{String(elapsedSec).padStart(
                                    2,
                                    "0",
                                )}
                            </span>
                            <span
                                class="text-sm text-blue-600 dark:text-blue-400 font-black uppercase tracking-wide animate-pulse"
                                >Optimizing...</span
                            >
                        </div>
                    </div>
                {:else if file.status === "queued"}
                    <div class="flex flex-col items-center gap-2 py-4">
                        <Clock size={32} class="text-slate-400 animate-pulse" />
                        <span
                            class="text-[10px] font-black text-slate-500 uppercase tracking-widest"
                            >Queued</span
                        >
                    </div>
                {:else}
                    <div class="flex items-center gap-2">
                        <!-- Analyze Button for Analyzed State -->
                        <button
                            onclick={() => analyzeFile(index, false, true)}
                            disabled={file.status === "analyzing" ||
                                file.isReanalyzing}
                            class="p-2 rounded-xl transition-all active:scale-90 flex items-center justify-center hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400"
                            title="Quick Scan"
                        >
                            {#if file.status === "analyzing" || file.isReanalyzing}
                                <Loader2
                                    size={18}
                                    class="animate-spin text-blue-400"
                                />
                            {:else}
                                <Activity size={18} />
                            {/if}
                        </button>

                        <button
                            onclick={() => openCompareModal(index)}
                            class="p-2.5 rounded-xl bg-indigo-50 dark:bg-indigo-600/10 hover:bg-indigo-600 text-indigo-600 dark:text-indigo-400 hover:text-white transition-all active:scale-90 flex items-center gap-2 px-4 border border-indigo-100 dark:border-transparent"
                            title="Open Audio Laboratory"
                        >
                            <FlaskConical size={18} />
                            <span class="text-xs font-bold uppercase"
                                >Laboratory</span
                            >
                        </button>
                    </div>
                {/if}
            {/if}
        </div>
    </div>

    <!-- Quality Badge (removed text, keeping actions) -->
    <div class="mt-3 flex items-center gap-2">
        <button
            onclick={(e) => {
                e.stopPropagation();
                toggleFlag(file.path);
            }}
            class="flex items-center gap-1.5 px-2 py-0.5 rounded-full border transition-all active:scale-90
            {flaggedPaths.has(file.path)
                ? 'bg-red-100 dark:bg-red-600/30 border-2 border-red-500 dark:border-red-500 text-red-700 dark:text-red-400 font-black shadow-md dark:shadow-red-900/30'
                : 'bg-slate-50 dark:bg-slate-800 border-2 border-slate-200 dark:border-slate-700 text-slate-400 dark:text-slate-500 hover:text-red-600 dark:hover:text-red-400 hover:border-red-200 dark:hover:border-red-900/50'}"
            title="Flag for review"
        >
            <Flag
                size={10}
                fill={flaggedPaths.has(file.path) ? "currentColor" : "none"}
            />
            <span class="text-[10px] font-bold uppercase tracking-tighter"
                >Flag</span
            >
        </button>

        <button
            onclick={(e) => {
                e.stopPropagation();
                toggleDenoised(file.path);
            }}
            class="flex items-center gap-1.5 px-2 py-0.5 rounded-full border transition-all active:scale-90
            {denoisedPaths.has(file.path)
                ? 'bg-emerald-100 dark:bg-emerald-600/30 border-2 border-emerald-500 dark:border-emerald-500 text-emerald-700 dark:text-emerald-400 font-black shadow-md dark:shadow-emerald-900/30'
                : 'bg-slate-50 dark:bg-slate-800 border-2 border-slate-200 dark:border-slate-700 text-slate-400 dark:text-slate-500 hover:text-emerald-600 dark:hover:text-emerald-400 hover:border-emerald-200 dark:hover:border-emerald-900/50'}"
            title="Mark as Denoised"
        >
            <Sparkles
                size={10}
                fill={denoisedPaths.has(file.path) ? "currentColor" : "none"}
            />
            <span class="text-[10px] font-bold uppercase tracking-tighter"
                >Denoised</span
            >
        </button>

        <button
            onclick={(e) => {
                e.stopPropagation();
                toggleBadQuality(file.path);
            }}
            class="flex items-center gap-1.5 px-2 py-0.5 rounded-full border transition-all active:scale-90
            {badQualityPaths.has(file.path)
                ? 'bg-orange-100 dark:bg-orange-600/30 border-2 border-orange-500 dark:border-orange-500 text-orange-700 dark:text-orange-400 font-black shadow-md dark:shadow-orange-900/30'
                : 'bg-slate-50 dark:bg-slate-800 border-2 border-slate-200 dark:border-slate-700 text-slate-400 dark:text-slate-500 hover:text-orange-600 dark:hover:text-orange-400 hover:border-orange-200 dark:hover:border-orange-900/50'}"
            title="Flag as Bad Quality"
        >
            <AlertTriangle
                size={10}
                fill={badQualityPaths.has(file.path) ? "currentColor" : "none"}
            />
            <span class="text-[10px] font-bold uppercase tracking-tighter"
                >Bad Quality</span
            >
        </button>

        <!-- Notes Input -->
        <div class="flex items-center gap-2 w-48">
            {#if noteInput === "" && !showNoteInput}
                <button
                    onclick={(e) => {
                        e.stopPropagation();
                        showNoteInput = true;
                    }}
                    class="flex items-center gap-1.5 px-2 py-0.5 rounded-full border transition-all active:scale-90 bg-slate-50 dark:bg-slate-800 border-2 border-slate-200 dark:border-slate-700 text-slate-400 dark:text-slate-500 hover:text-orange-600 dark:hover:text-orange-400 hover:border-orange-200 dark:hover:border-orange-900/50"
                    title="Add a note for this file"
                >
                    <MessageSquare size={10} fill="none" />
                    <span
                        class="text-[10px] font-bold uppercase tracking-tighter"
                        >Add Note</span
                    >
                </button>
            {:else if noteInput !== "" && !showNoteInput}
                <button
                    type="button"
                    class="flex items-center gap-1.5 px-2 py-0.5 rounded-full border transition-all active:scale-90 bg-orange-100 dark:bg-orange-600/30 border-2 border-orange-500 dark:border-orange-500 text-orange-700 dark:text-orange-400 font-black shadow-md dark:shadow-orange-900/30 cursor-pointer hover:bg-orange-200 dark:hover:bg-orange-600/40 transition-colors"
                    onclick={(e) => {
                        e.stopPropagation();
                        showNoteInput = true;
                    }}
                    title="Click to edit note"
                    aria-label="Edit note"
                >
                    <MessageSquare size={10} fill="currentColor" />
                    <span
                        class="text-[10px] font-bold uppercase tracking-tighter"
                        >{noteInput}</span
                    >
                </button>
            {:else}
                <input
                    type="text"
                    bind:value={noteInput}
                    onkeydown={handleNoteKeyDown}
                    onblur={() => {
                        setFileNote(file.path, noteInput);
                        showNoteInput = false;
                    }}
                    placeholder="Enter note..."
                    class="w-full px-2 py-0.5 text-xs rounded-full border border-orange-500 dark:border-orange-500 bg-orange-50 dark:bg-orange-600/20 text-orange-700 dark:text-orange-400 placeholder:text-orange-500/60 focus:outline-none focus:ring-1 focus:ring-orange-500 dark:focus:ring-orange-400 transition-all"
                />
            {/if}
        </div>
    </div>
</div>
