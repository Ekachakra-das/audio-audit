<script>
    import { Loader2, CheckCircle2 } from "lucide-svelte";
    import { formatDurationHmsShort } from "../../utils/formatters.js";

    /**
     * @type {{
     *   isProcessingQueue: boolean,
     *   isBatchSessionActive: boolean,
     *   batchProcessedCount: number,
     *   batchTotalFiles: number,
     *   batchETA: number | null,
     *   queuePendingCount: number,
     *   activeQueueTaskPath: string | null,
     *   selectedPathsCount: number,
     *   isFocusMode: boolean,
     *   openBatchSettings: (mode: string) => void
     * }}
     */
    let {
        isProcessingQueue,
        isBatchSessionActive = false,
        batchProcessedCount,
        batchTotalFiles,
        batchETA,
        queuePendingCount = 0,
        activeQueueTaskPath = null,
        selectedPathsCount,
        isFocusMode = $bindable(),
        openBatchSettings,
    } = $props();

    let effectiveTotal = $derived(
        batchTotalFiles > 0
            ? batchTotalFiles
            : batchProcessedCount +
                  Math.max(0, Number(queuePendingCount) || 0) +
                  (activeQueueTaskPath ? 1 : 0),
    );
    let effectiveProcessed = $derived(Math.min(batchProcessedCount, effectiveTotal));
</script>

{#if isBatchSessionActive}
    <button
        onclick={() => (isFocusMode = true)}
        class="fixed top-24 right-8 z-[100] bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 px-5 py-3 rounded-2xl shadow-2xl flex flex-col items-end gap-1 transition-all duration-300 animate-in fade-in slide-in-from-top-4 hover:scale-[1.02] hover:border-blue-400 dark:hover:border-blue-500 group"
    >
        <div class="flex items-center gap-2 mb-1">
            <Loader2 size={16} class="animate-spin text-blue-500" />
            <span
                class="text-xs font-black uppercase tracking-widest text-slate-700 dark:text-slate-200"
            >
                Processing {effectiveProcessed} / {Math.max(1, effectiveTotal)}
            </span>
        </div>

        {#if batchETA !== null}
            <span class="text-[10px] font-mono font-bold text-slate-600 dark:text-slate-500">
                ~{formatDurationHmsShort(batchETA)} remaining
            </span>
        {:else}
            <span class="text-[10px] font-mono font-bold text-slate-500 dark:text-slate-400">
                Calculating time...
            </span>
        {/if}
        <div
            class="absolute -bottom-1 -left-1 -right-1 h-0.5 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden"
        >
            <div
                class="h-full bg-blue-500 transition-all duration-500"
                style="width: {effectiveTotal > 0 ? (effectiveProcessed / effectiveTotal) * 100 : 0}%"
            ></div>
        </div>
    </button>
{:else if selectedPathsCount > 0}
    <button
        onclick={() => openBatchSettings("selected")}
        class="fixed top-24 right-8 z-[220] bg-emerald-600 hover:bg-emerald-500 text-white px-5 py-2.5 rounded-2xl shadow-2xl shadow-emerald-500/40 flex items-center gap-3 transition-all duration-300 animate-in fade-in slide-in-from-top-4 active:scale-95 border border-emerald-400/30 group"
    >
        <div class="relative">
            <CheckCircle2
                size={18}
                class="group-hover:scale-110 transition-transform"
            />
            <span class="absolute -top-1 -right-1 flex h-3 w-3">
                <span
                    class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"
                ></span>
                <span
                    class="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"
                ></span>
            </span>
        </div>
        <span class="text-xs font-black uppercase tracking-widest">
            Optimize Selected ({selectedPathsCount})
        </span>
    </button>
{/if}
