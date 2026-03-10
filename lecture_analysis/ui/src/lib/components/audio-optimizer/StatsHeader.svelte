<script>
    import { BarChart3, CheckCircle2, LayoutGrid } from "lucide-svelte";

    /**
     * @type {{
     *   stats: { 
     *     analyzed: number, 
     *     total: number, 
     *     completed: number, 
     *     totalOriginalMB: string,
     *     totalOptimizedMB: string,
     *     totalSavingsMB: string 
     *   },
     *   selectedPathsCount: number,
     *   filesCount: number,
     *   isProcessing: boolean,
     *   analyzeAll: () => void,
     *   openBatchSettings: (mode: string) => void
     * }}
     */
    let {
        stats,
        selectedPathsCount,
        filesCount,
        isProcessing,
        analyzeAll,
        openBatchSettings,
    } = $props();
</script>

<div
    class="mt-0 mb-5 flex flex-row items-stretch gap-4 overflow-x-auto pb-2 animate-in fade-in slide-in-from-top-4 duration-500"
>
    <!-- Optimized Stats -->
    <div
        class="bg-white dark:bg-slate-800/40 p-5 rounded-2xl border border-slate-200 dark:border-slate-700/50 flex flex-col justify-between relative overflow-hidden shadow-sm dark:shadow-none min-w-[200px] shrink-0"
    >
        <div class="flex justify-between items-start z-10 relative">
            <div class="flex flex-col">
                <span
                    class="text-slate-400 text-xs uppercase tracking-wider font-bold mb-1"
                    >Optimized</span
                >
                <div class="flex items-baseline gap-2">
                    <span
                        class="text-3xl font-bold text-emerald-600 dark:text-green-400"
                        >{stats.completed}</span
                    >
                    <span
                        class="text-xl font-medium text-slate-400 dark:text-slate-500"
                        >/ {stats.total}</span
                    >
                </div>
            </div>
        </div>

        <div class="mt-4">
            <div
                class="h-1.5 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden"
            >
                <div
                    class="h-full bg-blue-600 dark:bg-emerald-500 transition-all duration-500"
                    style="width: {(stats.completed / (stats.total || 1)) *
                        100}%"
                ></div>
            </div>
        </div>
    </div>

    <!-- Savings & Size Stats -->
    <div
        class="bg-white dark:bg-slate-800/40 p-4 rounded-2xl border border-slate-200 dark:border-slate-700/50 flex flex-row items-center gap-6 shadow-sm dark:shadow-none min-w-[360px] shrink-0"
    >
        <div class="flex flex-col border-r border-slate-100 dark:border-slate-700/50 pr-6">
            <span
                class="text-slate-500 dark:text-slate-400 text-[10px] uppercase tracking-wider font-extrabold mb-1"
                >Folder Weight</span
            >
            <div class="space-y-1.5 min-w-[140px]">
                <div class="flex items-center justify-between gap-4">
                    <span class="text-[10px] font-bold text-slate-400 uppercase">Original</span>
                    <span class="text-sm font-black text-slate-700 dark:text-slate-300">{stats.totalOriginalMB} <span class="text-[9px] font-normal opacity-60">MB</span></span>
                </div>
                <div class="flex items-center justify-between gap-4">
                    <span class="text-[10px] font-bold text-emerald-500 dark:text-green-500 uppercase">Optimized</span>
                    <span class="text-sm font-black text-emerald-600 dark:text-green-400">{stats.totalOptimizedMB} <span class="text-[9px] font-normal opacity-60">MB</span></span>
                </div>
            </div>
        </div>

        <div class="flex flex-col justify-center">
            <span
                class="text-slate-500 dark:text-slate-400 text-[10px] uppercase tracking-wider font-extrabold mb-1"
                >Total Savings</span
            >
            <div class="flex items-baseline gap-1.5">
                <span
                    class="text-3xl font-black text-blue-600 dark:text-blue-400"
                    >{stats.totalSavingsMB}</span
                >
                <span class="text-sm font-black text-blue-500/80">MB</span>
            </div>
            <span class="text-[9px] font-bold text-slate-400 dark:text-slate-500 mt-1 uppercase tracking-widest"
                >Space Recovered</span
            >
        </div>
    </div>

    <!-- Action Buttons -->
    <button
        onclick={analyzeAll}
        disabled={isProcessing}
        class="bg-white dark:bg-slate-800/40 hover:bg-blue-50 dark:hover:bg-blue-600/20 px-4 py-0 rounded-2xl border border-slate-200 dark:border-slate-700/50 flex flex-col items-center justify-center gap-1 transition-all active:scale-[0.98] group disabled:opacity-50 shadow-sm dark:shadow-none min-w-[80px]"
        title="Quick scan all idle files for quality"
    >
        <BarChart3
            size={18}
            class="text-slate-400 group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors shrink-0"
        />
        <span
            class="text-[9px] font-black uppercase tracking-widest text-slate-500 group-hover:text-blue-600 dark:group-hover:text-blue-300 whitespace-nowrap"
            >Analyze All</span
        >
    </button>

    <button
        onclick={() => openBatchSettings("selected")}
        disabled={selectedPathsCount === 0}
        class="bg-white dark:bg-slate-800/40 hover:bg-emerald-50 dark:hover:bg-emerald-600/20 px-6 py-0 rounded-2xl border border-slate-200 dark:border-slate-700/50 flex flex-col items-center justify-center gap-2 transition-all active:scale-[0.98] group disabled:opacity-50 shadow-sm dark:shadow-none flex-1 min-w-[200px]"
        title="Choose settings and optimize selected files"
    >
        <div class="flex items-center gap-3">
            <CheckCircle2
                size={28}
                class="text-emerald-500 group-hover:scale-110 transition-transform shrink-0"
            />
            <div class="flex flex-col items-start">
                <span
                    class="text-[11px] font-black uppercase tracking-widest text-emerald-600 dark:text-emerald-400 whitespace-nowrap"
                    >Optimize Selected</span
                >
                <span
                    class="text-[10px] font-bold text-slate-500 dark:text-slate-400"
                    >{selectedPathsCount} files ready</span
                >
            </div>
        </div>
    </button>

    <button
        onclick={() => openBatchSettings("all")}
        disabled={filesCount === 0}
        class="bg-white dark:bg-slate-800/40 hover:bg-blue-50 dark:hover:bg-blue-600/20 px-6 py-0 rounded-2xl border border-slate-200 dark:border-slate-700/50 flex flex-col items-center justify-center gap-2 transition-all active:scale-[0.98] group disabled:opacity-50 shadow-sm dark:shadow-none flex-1 min-w-[140px]"
        title="Choose settings and optimize all files"
    >
        <LayoutGrid
            size={24}
            class="text-slate-400 group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors shrink-0"
        />
        <span
            class="text-[10px] font-black uppercase tracking-widest text-slate-500 group-hover:text-blue-600 dark:group-hover:text-blue-300 whitespace-nowrap"
            >Optimize All</span
        >
    </button>
</div>
