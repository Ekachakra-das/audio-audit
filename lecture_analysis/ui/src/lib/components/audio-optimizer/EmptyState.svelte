<script>
    import { FileAudio } from "lucide-svelte";

    /**
     * @type {{
     *   filesCount: number,
     *   isScanning: boolean
     * }}
     */
    let { filesCount, isScanning } = $props();
</script>

{#if filesCount === 0 && !isScanning}
    <div
        class="h-full flex flex-col items-center justify-center text-slate-400 dark:text-slate-500 space-y-4"
    >
        <div class="p-6 bg-slate-50 dark:bg-slate-800/40 rounded-full border border-slate-100 dark:border-transparent shadow-inner">
            <FileAudio size={48} strokeWidth={1.5} />
        </div>
        <p class="text-lg font-medium text-slate-500 dark:text-slate-400">
            No files scanned yet. Enter a path and click Scan.
        </p>
    </div>
{/if}
