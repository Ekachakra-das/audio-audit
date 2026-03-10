<script>
    import AudioOptimizer from "./lib/AudioOptimizer.svelte";
    import GlobalBottomPlayer from "./lib/GlobalBottomPlayer.svelte";
</script>

<div class="h-screen flex flex-col bg-slate-50 dark:bg-slate-950">
    <main class="flex-grow min-h-0 overflow-hidden">
        <AudioOptimizer />
    </main>

    <GlobalBottomPlayer />
</div>
