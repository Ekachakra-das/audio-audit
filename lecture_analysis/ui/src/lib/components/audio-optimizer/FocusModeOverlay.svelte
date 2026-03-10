<script>
    import {
        X,
        Activity,
        Clock,
        Thermometer,
        Play,
        Pause,
        Square,
        Timer,
    } from "lucide-svelte";
    import { formatDuration, formatDurationHmsShort } from "../../utils/formatters.js";

    /**
     * @type {{
     *   isFocusMode: boolean,
     *   isProcessingQueue: boolean,
     *   isBatchSessionActive: boolean,
     *   batchProcessedCount: number,
     *   batchTotalFiles: number,
     *   activeQueueTaskPath: string | null,
     *   files: Array<any>,
     *   batchETA: number | null,
     *   batchProcessingSpeed: number,
     *   cpuTemp: number | null,
     *   thermalThrottling: boolean,
     *   thermalThrottlingRemaining: number,
     *   interFilePauseEnabled: boolean,
     *   interFilePauseDuration: number,
     *   skipInterFilePauseWhenCool: boolean,
     *   isInterFilePausing: boolean,
     *   interFilePauseRemaining: number,
     *   stopAfterCurrentRequested: boolean,
     *   requestStopAfterCurrent: () => void,
     *   manualQueuePaused: boolean,
     *   toggleManualQueuePause: () => void,
     *   showTransientToast: (msg: string, type?: string) => void
     * }}
     */
    let {
        isFocusMode = $bindable(),
        isProcessingQueue,
        isBatchSessionActive = false,
        batchProcessedCount,
        batchTotalFiles,
        activeQueueTaskPath = null,
        files,
        batchETA,
        batchProcessingSpeed,
        cpuTemp,
        thermalThrottling = $bindable(false),
        thermalThrottlingRemaining = 0,
        interFilePauseEnabled = $bindable(false),
        interFilePauseDuration = $bindable(1),
        skipInterFilePauseWhenCool = $bindable(false),
        isInterFilePausing = $bindable(false),
        interFilePauseRemaining = $bindable(0),
        stopAfterCurrentRequested = false,
        requestStopAfterCurrent = () => {},
        manualQueuePaused = false,
        toggleManualQueuePause = () => {},
        showTransientToast = () => {},
    } = $props();

    let currentQueueFile = $derived(
        files.find((f) => f.path === activeQueueTaskPath) ||
            files.find((f) => f.status === "converting") ||
            null,
    );
    let queueInFlightCount = $derived(
        files.filter(
            (f) => f.status === "queued" || f.status === "converting",
        ).length,
    );
    let queuedFiles = $derived(
        files.filter((f) => f.status === "queued").slice(0, 5),
    );
    let effectiveTotalFiles = $derived(
        batchTotalFiles > 0
            ? batchTotalFiles
            : batchProcessedCount + queueInFlightCount,
    );
    let effectiveProcessedCount = $derived(
        Math.min(batchProcessedCount, effectiveTotalFiles),
    );
    let effectiveCurrentFileIndex = $derived(
        currentQueueFile
            ? Math.min(batchProcessedCount + 1, Math.max(1, effectiveTotalFiles))
            : Math.min(batchProcessedCount, Math.max(1, effectiveTotalFiles)),
    );
    let effectiveProgressPercent = $derived(
        effectiveTotalFiles > 0
            ? (effectiveProcessedCount / effectiveTotalFiles) * 100
            : 0,
    );

    function formatTime(seconds) {
        const m = Math.floor(seconds / 60);
        const s = seconds % 60;
        return `${m}:${s.toString().padStart(2, "0")}`;
    }
</script>

<svelte:window
    onkeydown={(e) => {
        if (e.key === "Escape" && isFocusMode) {
            isFocusMode = false;
        }
    }}
/>

{#if isFocusMode && isBatchSessionActive}
    <div
        class={`fixed inset-0 z-[10000] bg-indigo-950 text-white flex flex-col overflow-hidden ${isInterFilePausing || thermalThrottling ? "" : "animate-in fade-in duration-500"}`}
    >
        <!-- Fullscreen Background with subtle gradient -->
        <div
            class="absolute inset-0 bg-gradient-to-br from-indigo-950 via-slate-950 to-indigo-950 z-0"
        ></div>

        {#if !isInterFilePausing && !thermalThrottling}
        <!-- Header Controls (Floating) -->
        <div class="relative z-20 flex justify-between items-start p-8">
            <div class="flex items-center gap-3">
                <!-- Pause Between Files (Top Left) -->
                <div class="group relative pb-5">
                    <div
                        class="bg-white/5 border border-white/10 rounded-2xl px-5 py-3 flex items-center gap-6 backdrop-blur-md"
                    >
                        <label class="flex items-center gap-3 cursor-pointer group">
                            <div class="relative">
                                <input
                                    type="checkbox"
                                    bind:checked={interFilePauseEnabled}
                                    class="peer sr-only"
                                />
                                <div
                                    class="w-10 h-5 bg-slate-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-blue-600"
                                ></div>
                            </div>
                            <span
                                class="text-[10px] font-black uppercase tracking-widest text-white/50 group-hover:text-white transition-colors"
                            >
                                Pause between files
                            </span>
                        </label>

                        {#if interFilePauseEnabled}
                            <div
                                class="flex items-center gap-2 border-l border-white/10 pl-5 animate-in slide-in-from-left-2 transition-all"
                            >
                                <Timer size={14} class="text-blue-400" />
                                <select
                                    bind:value={interFilePauseDuration}
                                    class="bg-transparent text-xs font-black text-blue-400 outline-none cursor-pointer appearance-none"
                                >
                                    <option value={1} class="bg-slate-900"
                                        >1 Min</option
                                    >
                                    <option value={2} class="bg-slate-900"
                                        >2 Min</option
                                    >
                                    <option value={3} class="bg-slate-900"
                                        >3 Min</option
                                    >
                                    <option value={5} class="bg-slate-900"
                                        >5 Min</option
                                    >
                                </select>
                                <div
                                    class="text-[9px] font-bold text-blue-400/50 uppercase ml-[-4px]"
                                >
                                    ▾
                                </div>
                            </div>
                        {/if}
                    </div>

                    {#if interFilePauseEnabled}
                        <label
                            class="absolute left-1/2 top-full mt-0 flex -translate-x-1/2 items-center cursor-pointer text-white/55 hover:text-white transition-all opacity-0 pointer-events-none group-hover:opacity-100 group-hover:pointer-events-auto focus-within:opacity-100 focus-within:pointer-events-auto"
                            aria-label="Skip pause when CPU temperature is below 75°C"
                        >
                            <input
                                type="checkbox"
                                bind:checked={skipInterFilePauseWhenCool}
                                class="h-3.5 w-3.5 rounded border-white/30 bg-transparent accent-blue-500"
                            />
                            <span
                                class="pointer-events-none absolute left-1/2 top-full z-10 mt-1 -translate-x-1/2 whitespace-nowrap rounded-lg border border-slate-700 bg-slate-950/95 px-3 py-1.5 text-[10px] font-black uppercase tracking-wide text-slate-100 opacity-0 shadow-xl transition-all group-hover:opacity-100 group-focus-within:opacity-100"
                            >
                                Skip pause if temp &lt; 75°C
                            </span>
                        </label>
                    {/if}
                </div>

            </div>

            <button
                onclick={() => (isFocusMode = false)}
                class="p-4 bg-white/5 hover:bg-white/10 border border-white/10 rounded-full transition-all active:scale-90 group backdrop-blur-md"
                aria-label="Close Focus Mode"
            >
                <X size={28} class="text-white/60 group-hover:text-white" />
            </button>
        </div>

        <!-- Main Content Area -->
        <div
            class="relative z-10 flex-1 overflow-y-auto scrollable-content px-6 pb-20"
        >
            <div class="max-w-5xl mx-auto space-y-16 py-8">
                <!-- Current File Info -->
                <div class="text-center space-y-4">
                    <div
                        class="inline-flex items-center gap-3 px-6 py-2 bg-blue-500/20 border border-blue-500/30 rounded-full text-blue-400 text-sm font-black uppercase tracking-widest"
                    >
                        <Activity size={18} />
                        Currently Optimizing
                        <span class="w-px h-4 bg-blue-300/30"></span>
                        <button
                            onclick={toggleManualQueuePause}
                            class="p-0.5 text-blue-300/80 hover:text-white transition-colors active:scale-95"
                            title={manualQueuePaused ? "Resume" : "Pause"}
                            aria-label={manualQueuePaused ? "Resume" : "Pause"}
                        >
                            {#if manualQueuePaused}
                                <Play size={15} />
                            {:else}
                                <Pause size={15} />
                            {/if}
                        </button>
                        <button
                            onclick={requestStopAfterCurrent}
                            disabled={stopAfterCurrentRequested}
                            class="p-0.5 text-blue-300/80 hover:text-white transition-colors active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed"
                            title={stopAfterCurrentRequested
                                ? "Stop requested"
                                : "Stop"}
                            aria-label={stopAfterCurrentRequested
                                ? "Stop requested"
                                : "Stop"}
                        >
                            <Square size={15} />
                        </button>
                    </div>

                    {#if currentQueueFile}
                        {@const currentFile = currentQueueFile}
                        <div
                            class="max-w-2xl mx-auto flex items-center justify-center gap-3"
                        >
                            <h2
                                class="text-lg font-black tracking-tight leading-tight opacity-80 truncate"
                                title={currentFile.name}
                            >
                                {currentFile.name}
                            </h2>
                            {#if currentFile.durationFormatted || currentFile.duration}
                                <span
                                    class="shrink-0 px-2.5 py-1 rounded-full border border-white/15 bg-white/5 text-[10px] font-bold uppercase tracking-widest text-white/70 tabular-nums"
                                >
                                    {currentFile.durationFormatted ||
                                        formatDuration(currentFile.duration)}
                                </span>
                            {/if}
                        </div>

                        {#if queuedFiles.length > 0}
                            <div class="max-w-3xl mx-auto pt-3">
                                <div class="text-[10px] font-bold uppercase tracking-widest text-white/45 mb-2">
                                    Queue ({queuedFiles.length} waiting)
                                </div>
                                <div class="flex flex-wrap items-center justify-center gap-2">
                                    {#each queuedFiles as queued (queued.path || queued.name)}
                                        <span
                                            class="max-w-[260px] truncate px-3 py-1.5 rounded-full border border-white/15 bg-white/5 text-[11px] font-bold text-white/70"
                                            title={queued.name}
                                        >
                                            {queued.name}
                                        </span>
                                    {/each}
                                </div>
                            </div>
                        {/if}

                        <div
                            class="flex items-center justify-center gap-8 pt-4"
                        >
                            <div class="flex flex-col items-center">
                                <span
                                    class="text-6xl font-black text-blue-400 tabular-nums"
                                >
                                    {currentFile.progress || 0}%
                                </span>
                                <span
                                    class="text-xs font-bold uppercase tracking-widest text-blue-400/60"
                                    >Progress</span
                                >
                            </div>

                            <div class="w-px h-16 bg-white/10"></div>

                            <div class="flex flex-col items-center">
                                <span
                                    class="text-6xl font-black text-emerald-400 tabular-nums"
                                >
                                    {effectiveCurrentFileIndex}/{Math.max(
                                        1,
                                        effectiveTotalFiles,
                                    )}
                                </span>
                                <span
                                    class="text-xs font-bold uppercase tracking-widest text-emerald-400/60"
                                    >Current File</span
                                >
                            </div>
                        </div>
                    {:else}
                        <h2
                            class="text-5xl font-black tracking-tight opacity-50"
                        >
                            Waiting for next file...
                        </h2>
                    {/if}
                </div>

                <!-- Global Progress Bar -->
                <div class="relative pt-12">
                    <div
                        class="h-4 bg-white/5 rounded-full overflow-hidden border border-white/10"
                    >
                        <div
                            class="h-full bg-gradient-to-r from-blue-600 via-indigo-500 to-emerald-500 transition-all duration-1000 ease-out relative"
                            style="width: {effectiveProgressPercent}%"
                        >
                            <div
                                class="absolute inset-0 bg-[image:linear-gradient(45deg,rgba(255,255,255,0.15)_25%,transparent_25%,transparent_50%,rgba(255,255,255,0.15)_50%,rgba(255,255,255,0.15)_75%,transparent_75%,transparent)] bg-[length:40px_40px] animate-[shimmer_2s_linear_infinite]"
                            ></div>
                        </div>
                    </div>

                    <!-- Floating Indicator -->
                    <div
                        class="absolute top-0 transition-all duration-1000 ease-out"
                        style="left: {effectiveProgressPercent}%"
                    >
                        <div
                            class="translate-x-[-50%] bg-white text-slate-900 px-3 py-1 rounded-lg font-black text-xs shadow-xl"
                        >
                            {Math.round(effectiveProgressPercent)}%
                        </div>
                    </div>
                </div>

                <!-- Bottom Stats -->
                <div class="flex flex-wrap justify-center gap-6">
                    <div
                        class="w-full sm:w-[280px] bg-white/5 border border-white/10 rounded-3xl p-8 flex flex-col items-center justify-center gap-2 group hover:bg-white/10 transition-all"
                    >
                        <Clock size={24} class="text-blue-400" />
                        <span class="text-3xl font-black tabular-nums">
                            {#if batchETA !== null}
                                ~{formatDurationHmsShort(batchETA)}
                            {:else}
                                --:--
                            {/if}
                        </span>
                        <span
                            class="text-[10px] font-bold uppercase tracking-widest text-white/40"
                            >Time Remaining</span
                        >
                    </div>

                    {#if cpuTemp && cpuTemp > 0}
                        <div
                            class="w-full sm:w-[280px] bg-white/5 border border-white/10 rounded-3xl p-8 flex flex-col items-center justify-center gap-2 group hover:bg-white/10 transition-all {cpuTemp >
                            90
                                ? 'ring-2 ring-rose-500 animate-pulse bg-rose-500/10'
                                : ''}"
                        >
                            <Thermometer
                                size={24}
                                class={cpuTemp > 90
                                    ? "text-rose-500"
                                    : cpuTemp > 80
                                      ? "text-red-400"
                                      : "text-orange-400"}
                            />
                            <span
                                class="text-3xl font-black tabular-nums {cpuTemp >
                                90
                                    ? 'text-rose-500'
                                    : ''}"
                            >
                                {Math.round(cpuTemp)}°C
                            </span>
                            <span
                                class="text-[10px] font-bold uppercase tracking-widest text-white/40"
                                >CPU Temperature</span
                            >
                        </div>
                    {/if}
                </div>
            </div>
        </div>
        {:else}
            <div class="relative z-10 flex-1 flex items-center justify-center px-6">
                <div
                    class={thermalThrottling
                        ? "bg-rose-500/12 border border-rose-500/35 rounded-2xl p-5 text-center w-full max-w-md shadow-lg"
                        : "bg-blue-500/20 border-2 border-blue-500/50 rounded-3xl p-8 text-center"}
                >
                    <div class="flex flex-col items-center">
                        {#if thermalThrottling}
                            <Thermometer size={28} class="text-rose-400 mb-3" />
                            <span class="text-lg font-black text-rose-300 uppercase tracking-[0.16em]">
                                Cooling
                            </span>
                            <div class="mt-3 rounded-2xl border border-rose-400/30 bg-rose-950/45 px-6 py-4 shadow-inner">
                                <div class="text-[10px] font-black uppercase tracking-[0.18em] text-rose-300/70">
                                    CPU Temperature
                                </div>
                                <div class="mt-2 text-5xl font-black text-rose-100 tabular-nums leading-none">
                                    {cpuTemp}°C
                                </div>
                            </div>
                            <span class="mt-3 text-5xl font-black text-white tabular-nums">
                                {formatTime(thermalThrottlingRemaining)}
                            </span>
                            {#if thermalThrottlingRemaining === 0 && cpuTemp > 80}
                                <span class="mt-2 text-xs text-rose-300/80 font-bold">
                                    Waiting for {cpuTemp}°C to drop
                                </span>
                            {/if}
                        {:else}
                            <span class="text-7xl font-black text-white tabular-nums">
                                {formatTime(interFilePauseRemaining)}
                            </span>
                            <span class="text-sm font-bold uppercase tracking-widest text-blue-500/60 mt-2">
                                Inter-file Cool Down
                            </span>
                        {/if}

                        <button
                            onclick={() => {
                                thermalThrottling = false;
                                isInterFilePausing = false;
                                interFilePauseRemaining = 0;
                                showTransientToast("Resuming work manually...", "info");
                            }}
                            class={thermalThrottling
                                ? "mt-5 inline-flex items-center gap-2 px-4 py-2 bg-white text-slate-950 rounded-xl text-xs font-black uppercase tracking-[0.16em] active:scale-95"
                                : "mt-6 px-5 py-2 bg-white text-slate-900 text-xs font-black uppercase tracking-widest rounded-xl shadow-lg"}
                        >
                            {#if thermalThrottling}
                                <Play size={15} fill="currentColor" />
                                Resume
                            {:else}
                                Resume now
                            {/if}
                        </button>
                    </div>
                </div>
            </div>
        {/if}
    </div>
{/if}

<style>
    @keyframes shimmer {
        from {
            background-position: 0 0;
        }
        to {
            background-position: 40px 0;
        }
    }

    .animate-in {
        animation: fadeIn 0.3s ease-out;
    }
    .scrollable-content::-webkit-scrollbar {
        width: 6px;
    }
    .scrollable-content::-webkit-scrollbar-track {
        background: transparent;
    }
    .scrollable-content::-webkit-scrollbar-thumb {
        background: rgba(255, 255, 255, 0.1);
        border-radius: 10px;
    }
    .scrollable-content::-webkit-scrollbar-thumb:hover {
        background: rgba(255, 255, 255, 0.2);
    }

    @keyframes fadeIn {
        from {
            opacity: 0;
            transform: scale(0.98);
        }
        to {
            opacity: 1;
            transform: scale(1);
        }
    }
</style>
