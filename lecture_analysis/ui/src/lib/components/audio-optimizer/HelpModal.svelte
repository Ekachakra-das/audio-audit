<script>
    import { X } from "lucide-svelte";

    /**
     * @type {{ showHelp: boolean }}
     */
    let { showHelp = $bindable() } = $props();
</script>

{#if showHelp}
    <div
        class="fixed inset-0 z-[9998] bg-transparent"
        onclick={() => (showHelp = false)}
        role="button"
        tabindex="0"
        onkeydown={(e) => e.key === "Escape" && (showHelp = false)}
        aria-label="Close help"
    ></div>
    <div
        class="fixed z-[9999] left-10 top-32 w-[560px] bg-slate-900 border border-slate-700 p-6 rounded-3xl shadow-2xl animate-in zoom-in-95 duration-200"
        role="dialog"
        aria-modal="true"
        tabindex="-1"
    >
        <div class="flex justify-between items-start mb-4">
            <h4 class="font-bold text-blue-400 text-lg">Optimization Guide</h4>
            <button
                onclick={() => (showHelp = false)}
                class="text-slate-500 hover:text-white transition-colors"
                aria-label="Close"
            >
                <X size={18} />
            </button>
        </div>
        <div class="space-y-3 text-[13px] leading-relaxed">
            <p
                class="text-slate-300 font-semibold pb-2 border-b border-slate-700"
            >
                Bitrate & Quality Mapping:
            </p>
            <div class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 font-mono">
                <span class="text-blue-400 font-bold">4 kHz</span>
                <span class="text-slate-400"
                    >→ 64 kbps (только речь, качество уровня телефона)</span
                >
                <span class="text-blue-400 font-bold">8 kHz</span>
                <span class="text-slate-400"
                    >→ 96 kbps (лекции и диктофон, оптимум для узкого спектра)</span
                >
                <span class="text-blue-400 font-bold">10 kHz</span>
                <span class="text-slate-400"
                    >→ 112 kbps (речь с лёгкой музыкой или фоном)</span
                >
                <span class="text-blue-400 font-bold">12 kHz</span>
                <span class="text-slate-400"
                    >→ 128 kbps (стандартный подкаст, разборчивый звук)</span
                >
                <span class="text-blue-400 font-bold">14 kHz</span>
                <span class="text-slate-400"
                    >→ 160 kbps (музыка с обрезанным верхом)</span
                >
                <span class="text-blue-400 font-bold">16 kHz</span>
                <span class="text-slate-400"
                    >→ 192 kbps (почти полный диапазон, хорошая музыка)</span
                >
                <span class="text-blue-400 font-bold">20 kHz</span>
                <span class="text-slate-400"
                    >→ 256–320 kbps (полный hi-fi диапазон)</span
                >
            </div>
        </div>
    </div>
{/if}
