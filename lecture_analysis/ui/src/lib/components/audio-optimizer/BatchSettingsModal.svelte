<script>
    import { X, Zap } from "lucide-svelte";
    import { onMount } from "svelte";

    /**
     * @type {{
     *   showBatchSettingsModal: boolean,
     *   batchTargetMode: "selected" | "all",
     *   selectedPaths: Set<string>,
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
     *   noiseReductionAmount: number,
     *   noiseSensitivity: number,
     *   targetBitrateForClean: number,
     *   compareBitrates: number[],
     *   volumeGain: number,
     *   lastUsedCleaningParams: any,
     *   noiseStart: number,
     *   noiseEnd: number,
     *   optimizeSelected: () => void,
     *   optimizeAll: () => void
     * }}
     */
    let {
        showBatchSettingsModal = $bindable(),
        batchTargetMode,
        selectedPaths,
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
        noiseReductionAmount = $bindable(),
        noiseSensitivity = $bindable(),
        targetBitrateForClean = $bindable(),
        compareBitrates,
        volumeGain = $bindable(),
        lastUsedCleaningParams = $bindable(),
        noiseStart,
        noiseEnd,
        optimizeSelected,
        optimizeAll,
    } = $props();

    // Bitrate Mode State
    let bitrateMode = $state("cbr");
    let targetVbrLevel = $state("v6");

    const vbrLevels = [
        { id: "v4", label: "VBR 4", desc: "~165 kbps" },
        { id: "v6", label: "VBR 6", desc: "~120 kbps" },
        { id: "v8", label: "VBR 8", desc: "~85 kbps" },
        { id: "v9", label: "VBR 9", desc: "~65 kbps" },
    ];

    onMount(() => {
        const savedMode = localStorage.getItem("optimizer-batch-bitrate-mode");
        if (savedMode === "cbr" || savedMode === "vbr") {
            bitrateMode = savedMode;
        }
        const savedVbr = localStorage.getItem("optimizer-batch-vbr-level");
        if (savedVbr && vbrLevels.some((v) => v.id === savedVbr)) {
            targetVbrLevel = savedVbr;
        }
    });

    $effect(() => {
        localStorage.setItem("optimizer-batch-bitrate-mode", bitrateMode);
    });

    $effect(() => {
        localStorage.setItem("optimizer-batch-vbr-level", targetVbrLevel);
    });
</script>

{#if showBatchSettingsModal}
    <div class="fixed inset-0 z-[10000] flex items-center justify-center p-6">
        <button
            type="button"
            class="fixed inset-0 z-0 appearance-none border-0 p-0 m-0 rounded-none shadow-none bg-slate-950/40 backdrop-blur-md animate-in fade-in duration-300"
            onclick={() => (showBatchSettingsModal = false)}
            aria-label="Close batch settings"
            title="Close batch settings"
        ></button>
        <div
            class="relative z-10 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 w-full max-w-[600px] rounded-3xl shadow-3xl mx-auto flex flex-col overflow-hidden"
            role="dialog"
            aria-modal="true"
            tabindex="-1"
        >
            <div class="p-8 space-y-6">
                <div class="flex justify-between items-start">
                    <div>
                        <h2
                            class="text-2xl font-black text-slate-800 dark:text-white tracking-tight"
                        >
                            Batch Settings
                        </h2>
                        <p
                            class="text-slate-500 text-[10px] font-black uppercase tracking-[0.2em] mt-1.5 opacity-70"
                        >
                            {batchTargetMode === "selected"
                                ? `Apply to ${selectedPaths.size} selected files`
                                : "Apply to EVERY scanned file"}
                        </p>
                    </div>
                    <button
                        onclick={() => (showBatchSettingsModal = false)}
                        class="p-2 hover:bg-slate-200 dark:hover:bg-slate-800 rounded-full transition-colors text-slate-400 hover:text-slate-900 dark:hover:text-white"
                        aria-label="Close"
                    >
                        <X size={24} />
                    </button>
                </div>

                <!-- General Settings -->

                <!-- Method Selection -->
                <div class="space-y-6">
                    <div class="flex items-center justify-between">
                        <span
                            class="text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]"
                        >
                            Enhancement
                        </span>
                        <div
                            class="flex gap-1 bg-slate-100 dark:bg-slate-950 rounded-xl p-1 border border-slate-200 dark:border-slate-800 shadow-inner"
                        >
                            {#each ["manual", "resemble_denoise", "lavasr", "remove_echo", "voicefixer"] as method}
                                <button
                                    onclick={() => (cleanMethod = method)}
                                    class="px-3 py-1.5 rounded-lg text-[10px] font-black uppercase tracking-wider transition-all
                                {cleanMethod === method
                                        ? 'bg-blue-600 text-white shadow-sm'
                                        : 'text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'}"
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

                    <!-- Method Parameters -->
                    <div
                        class="p-6 bg-slate-50 dark:bg-slate-950/50 rounded-2xl border border-slate-200 dark:border-slate-800 space-y-5 shadow-inner"
                    >
                        {#if cleanMethod === "resemble_denoise"}
                            <div class="space-y-3">
                                <div class="flex justify-between items-center">
                                    <span
                                        class="text-[10px] font-black text-slate-500 uppercase tracking-widest"
                                        >Input Gain</span
                                    >
                                    <span
                                        class="text-[10px] font-mono font-bold text-blue-500 bg-blue-500/10 px-2 py-0.5 rounded"
                                        >{resembleGain.toFixed(1)}x</span
                                    >
                                </div>
                                <input
                                    type="range"
                                    bind:value={resembleGain}
                                    min="0.5"
                                    max="3"
                                    step="0.1"
                                    class="w-full h-1.5 bg-slate-200 dark:bg-slate-800 rounded-lg appearance-none cursor-pointer accent-blue-500"
                                />
                            </div>
                            <div class="space-y-3">
                                <div class="flex justify-between items-center">
                                    <span
                                        class="text-[10px] font-black text-slate-500 uppercase tracking-widest"
                                        >Strength (Mix)</span
                                    >
                                    <span
                                        class="text-[10px] font-mono font-bold text-blue-500 bg-blue-500/10 px-2 py-0.5 rounded"
                                        >{Math.round(resembleMix * 100)}%</span
                                    >
                                </div>
                                <input
                                    type="range"
                                    bind:value={resembleMix}
                                    min="0"
                                    max="1"
                                    step="0.05"
                                    class="w-full h-1.5 bg-slate-200 dark:bg-slate-800 rounded-lg appearance-none cursor-pointer accent-blue-500"
                                />
                            </div>
                        {:else if cleanMethod === "lavasr"}
                            <div class="space-y-3">
                                <div class="flex justify-between items-center">
                                    <span
                                        class="text-[10px] font-black text-slate-500 uppercase tracking-widest"
                                        >Pipeline</span
                                    >
                                    <span
                                        class="text-[10px] font-mono font-bold text-orange-500 bg-orange-500/10 px-2 py-0.5 rounded"
                                        >HF-style</span
                                    >
                                </div>
                                <div class="grid gap-3 md:grid-cols-3">
                                    <div class="space-y-3">
                                        <div class="flex justify-between items-center">
                                            <span
                                                class="text-[10px] font-black text-slate-500 uppercase tracking-widest"
                                                >Input Gain</span
                                            >
                                            <span
                                                class="text-[10px] font-mono font-bold text-orange-500 bg-orange-500/10 px-2 py-0.5 rounded"
                                                >{lavasrGain.toFixed(1)}x</span
                                            >
                                        </div>
                                        <input
                                            type="range"
                                            bind:value={lavasrGain}
                                            min="0.5"
                                            max="3"
                                            step="0.1"
                                            class="w-full h-1.5 bg-slate-200 dark:bg-slate-800 rounded-lg appearance-none cursor-pointer accent-orange-500"
                                        />
                                    </div>
                                    <div class="space-y-3">
                                        <div class="flex justify-between items-center gap-2">
                                            <span
                                                class="text-[10px] font-black text-slate-500 uppercase tracking-widest"
                                                >Input Sampling Rate (Hz)</span
                                            >
                                            <div class="flex items-center gap-2">
                                                <span
                                                    class="text-[10px] font-mono font-bold text-orange-500 bg-orange-500/10 px-2 py-0.5 rounded"
                                                    >{lavasrInputSr}</span
                                                >
                                                <button
                                                    class="text-[10px] font-mono font-bold text-orange-500 bg-orange-500/10 px-2 py-0.5 rounded"
                                                    onclick={() => (lavasrInputSr = 16000)}
                                                    >↺ 16000</button
                                                >
                                            </div>
                                        </div>
                                        <input
                                            type="range"
                                            bind:value={lavasrInputSr}
                                            min="8000"
                                            max="48000"
                                            step="1000"
                                            class="w-full h-1.5 bg-slate-200 dark:bg-slate-800 rounded-lg appearance-none cursor-pointer accent-orange-500"
                                        />
                                        <div class="flex justify-between text-[10px] font-mono text-slate-400">
                                            <span>8000</span>
                                            <span>{lavasrInputSr}</span>
                                            <span>48000</span>
                                        </div>
                                        <p class="text-[10px] text-slate-500 italic leading-relaxed">
                                            Match this to your source audio&apos;s quality.
                                        </p>
                                    </div>
                                    <div class="space-y-3">
                                        <div class="flex justify-between items-center">
                                            <span
                                                class="text-[10px] font-black text-slate-500 uppercase tracking-widest"
                                                >Mix</span
                                            >
                                            <span
                                                class="text-[10px] font-mono font-bold text-orange-500 bg-orange-500/10 px-2 py-0.5 rounded"
                                                >{Math.round(lavasrMix * 100)}%</span
                                            >
                                        </div>
                                        <input
                                            type="range"
                                            bind:value={lavasrMix}
                                            min="0"
                                            max="1"
                                            step="0.05"
                                            class="w-full h-1.5 bg-slate-200 dark:bg-slate-800 rounded-lg appearance-none cursor-pointer accent-orange-500"
                                        />
                                    </div>
                                </div>
                                <div class="grid gap-3 md:grid-cols-3">
                                    <button
                                        class="rounded-xl border bg-white dark:bg-slate-900 px-4 py-3 text-left transition-all {lavasrDenoise
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
                                        class="rounded-xl border bg-white dark:bg-slate-900 px-4 py-3 text-left transition-all {lavasrSuperres
                                            ? 'border-orange-300 dark:border-orange-700 shadow-sm ring-1 ring-orange-200/60 dark:ring-orange-800/50'
                                            : 'border-slate-200 dark:border-slate-800 opacity-70'}"
                                        onclick={() => (lavasrSuperres = !lavasrSuperres)}
                                    >
                                        <div class="text-[9px] font-black uppercase tracking-widest text-slate-400">
                                            Output
                                        </div>
                                        <div class="mt-1 text-xs font-bold text-slate-700 dark:text-slate-200">
                                            {lavasrSuperres ? "48 kHz speech restore" : "16 kHz denoise / passthrough"}
                                        </div>
                                    </button>
                                    <label class="rounded-xl border border-orange-100 dark:border-orange-900/30 bg-white dark:bg-slate-900 px-4 py-3 cursor-pointer flex items-center justify-between transition-all">
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
                            </div>
                        {:else if cleanMethod === "remove_echo"}
                            <div class="space-y-3">
                                <div class="flex justify-between items-center">
                                    <span
                                        class="text-[10px] font-black text-slate-500 uppercase tracking-widest"
                                        >Echo Reduction</span
                                    >
                                    <span
                                        class="text-[10px] font-mono font-bold text-blue-500 bg-blue-500/10 px-2 py-0.5 rounded"
                                        >{Math.round(echoReduction * 100)}%</span
                                    >
                                </div>
                                <input
                                    type="range"
                                    bind:value={echoReduction}
                                    min="0"
                                    max="1"
                                    step="0.05"
                                    class="w-full h-1.5 bg-slate-200 dark:bg-slate-800 rounded-lg appearance-none cursor-pointer accent-blue-500"
                                />
                                <p
                                    class="text-[10px] text-slate-500 italic leading-relaxed"
                                >
                                    Dedicated de-echo pass with mild room-tail suppression.
                                </p>
                            </div>
                        {:else if cleanMethod === "voicefixer"}
                            <div class="space-y-4">
                                <div class="flex items-center justify-between">
                                    <span
                                        class="text-[10px] font-black text-slate-500 uppercase tracking-widest"
                                        >Processing Mode</span
                                    >
                                    <div
                                        class="flex gap-1 bg-white dark:bg-slate-900 rounded-lg p-1 border border-slate-200 dark:border-slate-800"
                                    >
                                        {#each [0, 1, 2] as mode}
                                            <button
                                                onclick={() => (vfMode = mode)}
                                                class="px-4 py-1.5 rounded-md text-[10px] font-black uppercase tracking-wider transition-all
                                            {vfMode === mode
                                                    ? 'bg-indigo-600 text-white shadow-sm'
                                                    : 'text-slate-500 hover:text-slate-900 dark:hover:text-slate-200'}"
                                            >
                                                {mode === 0
                                                    ? "Std"
                                                    : mode === 1
                                                      ? "Hybrid"
                                                      : "Deep"}
                                            </button>
                                        {/each}
                                    </div>
                                </div>
                                <p
                                    class="text-[10px] text-slate-500 italic leading-relaxed"
                                >
                                    {vfMode === 0
                                        ? "Standard VoiceFixer (Balanced)"
                                        : vfMode === 1
                                          ? "Hybrid (Mixes original for clarity)"
                                          : "Deep (Aggressive restoration)"}
                                </p>
                            </div>
                        {:else}
                            <div class="space-y-3">
                                <div class="flex justify-between items-center">
                                    <span
                                        class="text-[10px] font-black text-slate-500 uppercase tracking-widest"
                                        >NR Intensity</span
                                    >
                                    <span
                                        class="text-[10px] font-mono font-bold text-blue-500 bg-blue-500/10 px-2 py-0.5 rounded"
                                        >{Math.round(
                                            noiseReductionAmount * 100,
                                        )}%</span
                                    >
                                </div>
                                <input
                                    type="range"
                                    bind:value={noiseReductionAmount}
                                    min="0.1"
                                    max="1"
                                    step="0.05"
                                    class="w-full h-1.5 bg-slate-200 dark:bg-slate-800 rounded-lg appearance-none cursor-pointer accent-blue-500"
                                />
                            </div>
                            <div class="space-y-3">
                                <div class="flex justify-between items-center">
                                    <span
                                        class="text-[10px] font-black text-slate-500 uppercase tracking-widest"
                                        >NR Sensitivity</span
                                    >
                                    <span
                                        class="text-[10px] font-mono font-bold text-blue-500 bg-blue-500/10 px-2 py-0.5 rounded"
                                        >{noiseSensitivity.toFixed(1)}</span
                                    >
                                </div>
                                <input
                                    type="range"
                                    bind:value={noiseSensitivity}
                                    min="0.5"
                                    max="5"
                                    step="0.1"
                                    class="w-full h-1.5 bg-slate-200 dark:bg-slate-800 rounded-lg appearance-none cursor-pointer accent-blue-500"
                                />
                            </div>
                        {/if}
                    </div>

                    <!-- Common Settings -->
                    <div class="space-y-4">
                        <div class="flex items-center justify-between">
                            <span
                                class="text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]"
                            >
                                Bitrate Mode
                            </span>
                            <div
                                class="flex bg-slate-100 dark:bg-slate-950 rounded-lg p-1 border border-slate-200 dark:border-slate-800 shadow-inner"
                            >
                                <button
                                    onclick={() => (bitrateMode = "cbr")}
                                    class="px-3 py-1 rounded text-[10px] font-black uppercase transition-all
                                {bitrateMode === 'cbr'
                                        ? 'bg-white dark:bg-slate-800 text-blue-600 shadow-sm'
                                        : 'text-slate-500'}"
                                >
                                    CBR
                                </button>
                                <button
                                    onclick={() => (bitrateMode = "vbr")}
                                    class="px-3 py-1 rounded text-[10px] font-black uppercase transition-all
                                {bitrateMode === 'vbr'
                                        ? 'bg-white dark:bg-slate-800 text-blue-600 shadow-sm'
                                        : 'text-slate-500'}"
                                >
                                    VBR
                                </button>
                            </div>
                        </div>

                        <div class="grid grid-cols-2 gap-5">
                            <div class="space-y-2">
                                <span
                                    class="text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]"
                                >
                                    {bitrateMode === "cbr"
                                        ? "Target Bitrate"
                                        : "VBR Quality"}
                                </span>
                                {#if bitrateMode === "cbr"}
                                    <select
                                        bind:value={targetBitrateForClean}
                                        class="w-full bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-2xl px-4 py-3 text-sm font-bold text-slate-700 dark:text-slate-200 focus:outline-none focus:ring-4 focus:ring-blue-500/10 transition-all appearance-none cursor-pointer"
                                        style="background-image: url('data:image/svg+xml;charset=US-ASCII,%3Csvg%20xmlns%3D%22http%3A//www.w3.org/2000/svg%22%20width%3D%2224%22%20height%3D%2224%22%20viewBox%3D%220%200%2024%2024%22%20fill%3D%22none%22%20stroke%3D%22%2364748b%22%20stroke-width%3D%222%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%3E%3Cpolyline%20points%3D%226%209%2012%2015%2018%209%22%3E%3C/polyline%3E%3C/svg%3E'); background-repeat: no-repeat; background-position: right 1rem center; background-size: 1em;"
                                    >
                                        {#each compareBitrates as br}
                                            <option value={br}>{br} kbps</option
                                            >
                                        {/each}
                                    </select>
                                {:else}
                                    <select
                                        bind:value={targetVbrLevel}
                                        class="w-full bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-2xl px-4 py-3 text-sm font-bold text-slate-700 dark:text-slate-200 focus:outline-none focus:ring-4 focus:ring-blue-500/10 transition-all appearance-none cursor-pointer"
                                        style="background-image: url('data:image/svg+xml;charset=US-ASCII,%3Csvg%20xmlns%3D%22http%3A//www.w3.org/2000/svg%22%20width%3D%2224%22%20height%3D%2224%22%20viewBox%3D%220%200%2024%2024%22%20fill%3D%22none%22%20stroke%3D%22%2364748b%22%20stroke-width%3D%222%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%3E%3Cpolyline%20points%3D%226%209%2012%2015%2018%209%22%3E%3C/polyline%3E%3C/svg%3E'); background-repeat: no-repeat; background-position: right 1rem center; background-size: 1em;"
                                    >
                                        {#each vbrLevels as vbr}
                                            <option value={vbr.id}
                                                >{vbr.label} ({vbr.desc})</option
                                            >
                                        {/each}
                                    </select>
                                {/if}
                            </div>
                            <div class="space-y-2">
                                <span
                                    class="text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]"
                                >
                                    Output Vol.
                                </span>
                                <div
                                    class="flex items-center gap-3 bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-2xl px-4 py-2.5"
                                >
                                    <input
                                        type="range"
                                        bind:value={volumeGain}
                                        min="0.5"
                                        max="3"
                                        step="0.1"
                                        class="flex-1 h-1 bg-slate-200 dark:bg-slate-800 rounded-lg appearance-none cursor-pointer accent-blue-500"
                                    />
                                    <span
                                        class="text-xs font-mono font-bold text-slate-600 dark:text-slate-400 w-10 text-right"
                                        >{volumeGain.toFixed(1)}x</span
                                    >
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="pt-6">
                    <button
                        onclick={() => {
                            // Save current settings to lastUsedCleaningParams
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
                                bitrate:
                                    bitrateMode === "cbr"
                                        ? targetBitrateForClean
                                        : targetVbrLevel,
                                isCleaned: true,
                            };

                            if (batchTargetMode === "selected") {
                                optimizeSelected();
                            } else {
                                optimizeAll();
                            }
                        }}
                        class="w-full py-5 bg-blue-600 hover:bg-blue-500 text-white rounded-[2rem] font-black uppercase tracking-[0.2em] text-sm shadow-2xl shadow-blue-500/30 transition-all hover:scale-[1.02] active:scale-95 flex items-center justify-center gap-4 group"
                    >
                        <Zap
                            size={24}
                            class="text-blue-200 group-hover:scale-125 transition-transform"
                        />
                        Start Processing
                    </button>
                </div>
            </div>
        </div>
    </div>
{/if}

<style>
    .shadow-3xl {
        box-shadow:
            0 32px 64px -12px rgb(0 0 0 / 0.14),
            0 0 0 1px rgb(0 0 0 / 0.02);
    }
</style>
