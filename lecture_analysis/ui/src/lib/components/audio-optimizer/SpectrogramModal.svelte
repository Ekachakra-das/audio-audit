<script>
    import { X, Play, Volume2, Save, Scissors, Loader2 } from "lucide-svelte";
    import { onMount } from "svelte";

    /**
     * @type {{
     *   show: boolean,
     *   url: string,
     *   startTime: number,
     *   duration: number,
     *   noiseStart: number,
     *   noiseEnd: number,
     *   isPlaying: boolean,
     *   onPlay: () => void,
     *   onClose: () => void,
     *   onApply: (start: number, end: number) => void
     * }}
     */
    let {
        show = $bindable(),
        url,
        startTime,
        duration,
        noiseStart = $bindable(),
        noiseEnd = $bindable(),
        isPlaying,
        onPlay,
        onClose,
        onApply,
    } = $props();

    let container = $state(null);
    let isDragging = $state(false);
    let startX = $state(0);
    let currentX = $state(0);

    // Derived values for UI selection overlay
    let selectionLeft = $derived.by(() => {
        if (!container) return 0;
        const s = Math.min(noiseStart, noiseEnd);
        const rel = (s - startTime) / duration;
        return rel * 100;
    });

    let selectionWidth = $derived.by(() => {
        if (!container) return 0;
        const width = Math.abs(noiseEnd - noiseStart);
        const rel = width / duration;
        return rel * 100;
    });

    function handleMouseDown(e) {
        if (!container) return;
        isDragging = true;
        const rect = container.getBoundingClientRect();
        startX = e.clientX - rect.left;
        currentX = startX;

        const time = startTime + (startX / rect.width) * duration;
        noiseStart = time;
        noiseEnd = time;
    }

    function handleMouseMove(e) {
        if (!isDragging || !container) return;
        const rect = container.getBoundingClientRect();
        currentX = Math.max(0, Math.min(rect.width, e.clientX - rect.left));

        const time = startTime + (currentX / rect.width) * duration;
        noiseEnd = time;
    }

    function handleMouseUp() {
        isDragging = false;
        // Ensure some min duration
        if (Math.abs(noiseEnd - noiseStart) < 0.1) {
            noiseEnd = noiseStart + 0.5;
        }
        // Normalize range
        if (noiseStart > noiseEnd) {
            const tmp = noiseStart;
            noiseStart = noiseEnd;
            noiseEnd = tmp;
        }
    }

    function formatTime(t) {
        const h = Math.floor(t / 3600);
        const m = Math.floor((t % 3600) / 60);
        const s = (t % 60).toFixed(2);
        if (h > 0) {
            return `${h}:${m.toString().padStart(2, "0")}:${s.padStart(5, "0")}`;
        }
        return `${m}:${s.padStart(5, "0")}`;
    }
</script>

{#if show}
    <div
        class="fixed inset-0 z-[10000] flex items-center justify-center p-8 backdrop-blur-md bg-slate-900/60 transition-all animate-in fade-in duration-300"
    >
        <div
            class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl shadow-2xl w-full max-w-6xl overflow-hidden flex flex-col max-h-[90vh] animate-in zoom-in-95 duration-300"
        >
            <!-- Header -->
            <div
                class="p-6 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between bg-slate-50/50 dark:bg-slate-800/20"
            >
                <div class="flex items-center gap-3">
                    <div
                        class="p-2 bg-blue-500 rounded-xl text-white shadow-lg shadow-blue-500/20"
                    >
                        <Scissors size={20} />
                    </div>
                    <div>
                        <h3
                            class="text-xl font-black text-slate-800 dark:text-white tracking-tight"
                        >
                            Manual Noise Profiling
                        </h3>
                        <p
                            class="text-xs font-bold text-slate-500 uppercase tracking-widest"
                        >
                            Select a clear segment of background noise
                        </p>
                    </div>
                </div>
                <button
                    onclick={onClose}
                    class="p-2 mr-[-8px] text-slate-400 hover:text-slate-600 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 rounded-full transition-all"
                >
                    <X size={24} />
                </button>
            </div>

            <!-- Body -->
            <div class="flex-1 p-8 overflow-auto">
                <div class="space-y-6">
                    <div
                        class="bg-slate-950 rounded-2xl border border-slate-800 overflow-hidden relative group"
                        style="aspect-ratio: 16/7;"
                    >
                        {#if url}
                            <!-- svelte-ignore a11y_no_static_element_interactions -->
                            <div
                                bind:this={container}
                                class="w-full h-full relative cursor-crosshair select-none"
                                onmousedown={handleMouseDown}
                                onmousemove={handleMouseMove}
                                onmouseup={handleMouseUp}
                                onmouseleave={handleMouseUp}
                            >
                                <img
                                    src={url}
                                    alt="Spectrogram"
                                    class="w-full h-full object-fill opacity-90 group-hover:opacity-100 transition-opacity"
                                />

                                <!-- Selection Overlay -->
                                <div
                                    class="absolute top-0 bottom-0 bg-blue-500/30 border-x-2 border-blue-400 backdrop-blur-[1px] pointer-events-none transition-[left,width] duration-75"
                                    style="left: {selectionLeft}%; width: {selectionWidth}%"
                                >
                                    <div
                                        class="absolute top-2 left-1/2 -translate-x-1/2 bg-blue-600 text-[10px] font-black text-white px-2 py-0.5 rounded shadow-lg uppercase tracking-tighter whitespace-nowrap"
                                    >
                                        Noise Profile
                                    </div>
                                </div>

                                <!-- Hover time indicator could go here -->
                            </div>
                        {:else}
                            <div
                                class="w-full h-full flex flex-col items-center justify-center gap-3 text-slate-500"
                            >
                                <Loader2
                                    size={32}
                                    class="animate-spin text-blue-500"
                                />
                                <span
                                    class="font-bold uppercase text-[10px] tracking-widest"
                                    >Generating Spectrogram...</span
                                >
                            </div>
                        {/if}
                    </div>

                    <div class="grid grid-cols-2 gap-6">
                        <div
                            class="bg-slate-50 dark:bg-slate-800/40 p-5 rounded-2xl border border-slate-100 dark:border-slate-700 shadow-inner"
                        >
                            <span
                                class="text-[10px] font-black text-slate-400 uppercase tracking-widest block mb-3"
                                >Selected Range</span
                            >
                            <div class="flex items-center gap-6">
                                <div>
                                    <span
                                        class="text-[9px] font-black text-slate-400 uppercase tracking-tighter block"
                                        >Start</span
                                    >
                                    <span
                                        class="text-2xl font-mono font-black text-blue-600 dark:text-blue-400"
                                        >{formatTime(noiseStart)}</span
                                    >
                                </div>
                                <div
                                    class="w-px h-8 bg-slate-200 dark:bg-slate-700"
                                ></div>
                                <div>
                                    <span
                                        class="text-[9px] font-black text-slate-400 uppercase tracking-tighter block"
                                        >End</span
                                    >
                                    <span
                                        class="text-2xl font-mono font-black text-blue-600 dark:text-blue-400"
                                        >{formatTime(noiseEnd)}</span
                                    >
                                </div>
                                <div
                                    class="w-px h-8 bg-slate-200 dark:bg-slate-700"
                                ></div>
                                <div>
                                    <span
                                        class="text-[9px] font-black text-slate-400 uppercase tracking-tighter block"
                                        >Duration</span
                                    >
                                    <span
                                        class="text-2xl font-mono font-black text-slate-700 dark:text-slate-300"
                                        >{(noiseEnd - noiseStart).toFixed(
                                            2,
                                        )}s</span
                                    >
                                </div>
                            </div>
                        </div>

                        <div class="flex flex-col justify-center gap-3">
                            <button
                                onclick={onPlay}
                                disabled={isPlaying}
                                class="w-full py-4 rounded-2xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 font-black text-xs uppercase tracking-widest flex items-center justify-center gap-3 transition-all active:scale-95 disabled:opacity-50 shadow-sm"
                            >
                                <Play
                                    size={18}
                                    fill={isPlaying ? "currentColor" : "none"}
                                    class={isPlaying ? "animate-pulse" : ""}
                                />
                                {isPlaying
                                    ? "Playing selection..."
                                    : "Preview Noise Selection"}
                            </button>
                            <p
                                class="text-[10px] text-slate-500 text-center italic"
                            >
                                Listen to the selected segment to ensure it
                                contains <b>only noise</b> (no voice).
                            </p>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Footer -->
            <div
                class="p-6 bg-slate-50 dark:bg-slate-800/50 border-t border-slate-100 dark:border-slate-800 flex gap-4"
            >
                <button
                    onclick={onClose}
                    class="flex-1 py-4 px-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 font-black text-sm uppercase tracking-widest hover:bg-slate-50 dark:hover:bg-slate-800 transition-all active:scale-95"
                >
                    Cancel
                </button>
                <button
                    onclick={() => {
                        onApply(noiseStart, noiseEnd);
                        onClose();
                    }}
                    class="flex-[2] py-4 px-6 rounded-2xl bg-blue-600 hover:bg-blue-700 text-white font-black text-sm uppercase tracking-widest shadow-lg shadow-blue-600/20 transition-all active:scale-95 flex items-center justify-center gap-3"
                >
                    <Save size={20} />
                    Apply Noise Profile
                </button>
            </div>
        </div>
    </div>
{/if}

<style>
    .cursor-crosshair {
        cursor: crosshair;
    }
</style>
