<script>
    import { onMount } from "svelte";
    import { globalUiState } from "./globalState.svelte.js";
    import {
        subscribeToGlobalTrack,
        setGlobalTrack,
        subscribeToAudioCommands,
        subscribeToPlaylist,
        dispatchAudioCommand,
        setPlaybackState,
    } from "./audioStore.js";
    import {
        Play,
        Pause,
        SkipBack,
        SkipForward,
        X,
        Zap,
        ZapOff,
    } from "lucide-svelte";

    let track = $state(null);
    let playlist = $state([]);
    let currentIndex = $state(-1);
    let audioEl = $state(null);
    let isPaused = $state(true);
    let currentTime = $state(0);
    let duration = $state(0);
    let isOptimized = $state(false);
    let pendingSeek = $state(null);

    $effect(() => {
        setPlaybackState(!isPaused);
    });

    onMount(() => {
        const unsubscribeTrack = subscribeToGlobalTrack((newTrack) => {
            if (newTrack) {
                // Determine if we should play the new track
                // If it's a manual click (e.g. from FileRow), shouldPlay won't be in the object, so we default to true.
                // If it's navigation via Arrow keys, it will reflect the current state.
                const shouldPlay =
                    newTrack.shouldPlay !== undefined
                        ? newTrack.shouldPlay
                        : true;

                // Mark for handleMetadata to play or stay paused
                pendingSeek = {
                    ...pendingSeek,
                    shouldPlay: shouldPlay,
                };

                // If it's a new track path, we'll reset
                if (
                    !track ||
                    (track.path !== newTrack.path &&
                        track.optimizedPath !== newTrack.path)
                ) {
                    track = newTrack;
                    isOptimized = !!newTrack.isOptimized;
                    currentTime = 0;
                    if (newTrack.duration) {
                        duration = newTrack.duration;
                    }
                } else {
                    // Same track, update metadata/info but handle playback carefully
                    track = newTrack;
                    isOptimized = !!newTrack.isOptimized;

                    if (newTrack.shouldPlay !== undefined) {
                        // Explicit play/pause command (e.g. from optimizer)
                        // handleMetadata will handle the actual play() call if shouldPlay is true
                        // after the src updates (since isOptimized might have changed).
                    } else {
                        // Manual click on same track in list -> Toggle
                        togglePlay();
                    }
                }
            } else {
                track = null;
            }
        });

        const unsubscribePlaylist = subscribeToPlaylist((data) => {
            playlist = data.playlist || [];
            currentIndex = data.index;
        });

        const unsubscribeCommands = subscribeToAudioCommands(
            (command, payload) => {
                if (command === "PAUSE_ALL") {
                    if (audioEl) {
                        audioEl.pause();
                        isPaused = true; // Force state sync
                    }
                } else if (command === "toggle") {
                    togglePlay();
                } else if (command === "seek") {
                    if (audioEl) {
                        const maxTime = Number.isFinite(audioEl.duration)
                            ? audioEl.duration
                            : duration;
                        audioEl.currentTime = Math.max(
                            0,
                            Math.min(maxTime, audioEl.currentTime + payload),
                        );
                    }
                } else if (command === "toggle-version") {
                    toggleVersion();
                }
            },
        );

        return () => {
            unsubscribeTrack();
            unsubscribePlaylist();
            unsubscribeCommands();
        };
    });

    function playNext(autoPlayNext = false) {
        if (playlist.length === 0 || currentIndex === -1) return;
        const nextIndex = (currentIndex + 1) % playlist.length;
        const nextTrack = playlist[nextIndex];
        // Preserve current state unless it's auto-advance after ending
        const shouldPlay = autoPlayNext || !isPaused;
        setGlobalTrack({ ...nextTrack, shouldPlay });
    }

    function playPrevious() {
        if (playlist.length === 0 || currentIndex === -1) return;
        const prevIndex =
            (currentIndex - 1 + playlist.length) % playlist.length;
        const nextTrack = playlist[prevIndex];
        // Preserve current state
        const shouldPlay = !isPaused;
        setGlobalTrack({ ...nextTrack, shouldPlay });
    }

    function togglePlay() {
        if (!audioEl) return;
        if (audioEl.paused) audioEl.play();
        else audioEl.pause();
    }

    function toggleVersion() {
        if (!track || !track.optimizedPath || !audioEl) return;

        const wasPlaying = !audioEl.paused;
        const savedTime = audioEl.currentTime; // Absolute seconds

        // 1. Pause immediately
        audioEl.pause();

        // 2. Define handler for seamless restoration
        const onAudioLoaded = () => {
            if (Number.isFinite(savedTime)) {
                audioEl.currentTime = savedTime;
            }
            if (wasPlaying) {
                audioEl.play().catch(console.warn);
            }
        };

        // 3. Attach one-time listener BEFORE changing src
        audioEl.addEventListener("loadeddata", onAudioLoaded, { once: true });

        // 4. Toggle state (will trigger src update)
        isOptimized = !isOptimized;
    }

    function handleMetadata() {
        const mediaDuration = audioEl?.duration;
        duration = Number.isFinite(mediaDuration)
            ? mediaDuration
            : (track?.duration || 0);

        // Handle pending seek (e.g. from new track selection or external commands)
        if (pendingSeek) {
            if (
                pendingSeek.progress !== undefined &&
                Number.isFinite(audioEl.duration)
            ) {
                audioEl.currentTime = pendingSeek.progress * audioEl.duration;
            } else if (pendingSeek.time !== undefined) {
                audioEl.currentTime = pendingSeek.time;
            }

            if (pendingSeek.shouldPlay) {
                audioEl
                    .play()
                    .catch((e) => console.error("Auto-play failed:", e));
            }
            pendingSeek = null;
        }
    }

    function skip(seconds) {
        if (audioEl) {
            const maxTime = Number.isFinite(audioEl.duration)
                ? audioEl.duration
                : duration;
            audioEl.currentTime = Math.min(
                Math.max(0, audioEl.currentTime + seconds),
                maxTime,
            );
        }
    }

    function formatTime(t) {
        if (!t || isNaN(t)) return "0:00";
        const h = Math.floor(t / 3600);
        const m = Math.floor((t % 3600) / 60);
        const s = Math.floor(t % 60);
        if (h > 0) {
            return `${h}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
        }
        return `${m}:${s.toString().padStart(2, "0")}`;
    }

    function closePlayer() {
        if (audioEl) audioEl.pause();
        setGlobalTrack(null);
    }
</script>

{#if track}
    <div class="fixed top-0 left-0 right-0 z-[1000] pointer-events-none">
        <div class="w-full pointer-events-auto">
            <div
                class="bg-white/95 dark:bg-slate-900/95 backdrop-blur-2xl border-b border-blue-200 dark:border-blue-900 shadow-sm pt-[28px] pb-[32px] px-6 flex items-center gap-6 animate-slide-down"
            >
                <!-- Controls (Left) -->
                <div class="flex items-center gap-1 shrink-0">
                    <button
                        onclick={() => skip(-10)}
                        class="p-1.5 text-slate-400 dark:text-slate-500 hover:text-slate-900 dark:hover:text-white transition-colors"
                        title="-10s"
                    >
                        <SkipBack size={18} />
                    </button>

                    <button
                        onclick={togglePlay}
                        class="w-10 h-10 rounded-full bg-slate-900 dark:bg-white text-white dark:text-slate-900 flex items-center justify-center hover:scale-105 active:scale-95 transition-all shadow-lg shadow-slate-900/10 dark:shadow-none shrink-0"
                    >
                        {#if isPaused}
                            <Play
                                size={20}
                                fill="currentColor"
                                class="ml-0.5"
                            />
                        {:else}
                            <Pause size={20} fill="currentColor" />
                        {/if}
                    </button>

                    <button
                        onclick={() => skip(10)}
                        class="p-1.5 text-slate-400 dark:text-slate-500 hover:text-slate-900 dark:hover:text-white transition-colors"
                        title="+10s"
                    >
                        <SkipForward size={18} />
                    </button>
                </div>

                <!-- Track Info (Mid-Left) -->
                <div
                    class="flex items-center gap-3 shrink-0 max-w-[220px] min-w-0"
                >
                    <div class="min-w-0">
                        <!-- h4 removed as per user request -->
                        {#if track.optimizedPath}
                            <button
                                onclick={toggleVersion}
                                class="text-[10px] font-black uppercase tracking-wider {isOptimized
                                    ? 'text-green-600 dark:text-green-400'
                                    : 'text-blue-600 dark:text-blue-400'}"
                            >
                                {isOptimized ? "Optimized" : "Original"}
                            </button>
                        {/if}
                    </div>
                </div>

                <!-- Progress (Center) -->
                <div class="flex items-center gap-4 flex-grow min-w-0">
                    <span
                        class="text-[10px] font-mono text-slate-400 dark:text-slate-500 w-14 text-right shrink-0"
                    >
                        {formatTime(currentTime)}
                    </span>

                    <div
                        class="flex-grow relative group h-2 flex items-center min-w-0"
                    >
                        <input
                            type="range"
                            min="0"
                            max={duration || 100}
                            bind:value={currentTime}
                            oninput={(e) => {
                                if (audioEl)
                                    audioEl.currentTime = Number(
                                        e.currentTarget.value,
                                    );
                            }}
                            onchange={(e) => e.currentTarget.blur()}
                            onmouseup={(e) => e.currentTarget.blur()}
                            onkeyup={(e) => {
                                if (e.key === "Enter" || e.key === " ")
                                    e.currentTarget.blur();
                            }}
                            class="w-full h-2 bg-slate-300 dark:bg-slate-600 rounded-full appearance-none cursor-pointer accent-blue-600 transition-all group-hover:h-2.5"
                        />
                    </div>
                    <span
                        class="text-[10px] font-mono text-slate-400 dark:text-slate-500 w-14 shrink-0"
                    >
                        {formatTime(duration)}
                    </span>
                </div>

                <!-- Volume & Actions (Right) -->
                <div class="flex items-center gap-4 shrink-0">
                    <button
                        onclick={closePlayer}
                        class="p-2 text-slate-400 dark:text-slate-500 hover:text-rose-500 dark:hover:text-rose-400 transition-colors"
                        title="Close Player"
                    >
                        <X size={20} />
                    </button>
                </div>

                <audio
                    bind:this={audioEl}
                    src={`http://localhost:3000/audio?path=${encodeURIComponent(isOptimized ? track.optimizedPath : track.path)}&t=${track.lastOptimized || 0}`}
                    onplay={() => (isPaused = false)}
                    onpause={() => (isPaused = true)}
                    onended={() => {
                        isPaused = true;
                        playNext(true);
                    }}
                    ontimeupdate={() => (currentTime = audioEl.currentTime)}
                    oncanplay={handleMetadata}
                    class="hidden"
                ></audio>
            </div>
        </div>
    </div>
{/if}

<style>
    .animate-slide-down {
        animation: slideDown 0.35s cubic-bezier(0.16, 1, 0.3, 1);
    }
    @keyframes slideDown {
        from {
            transform: translateY(-100%);
            opacity: 0;
        }
        to {
            transform: translateY(0);
            opacity: 1;
        }
    }

    /* Custom range input styling */
    input[type="range"]::-webkit-slider-runnable-track {
        height: 8px;
        border-radius: 9999px;
    }

    input[type="range"]::-webkit-slider-thumb {
        appearance: none;
        margin-top: -4px;
        width: 16px;
        height: 16px;
        background: #2563eb;
        border-radius: 50%;
        cursor: pointer;
        border: 2px solid rgba(255, 255, 255, 0.95);
        box-shadow: 0 2px 10px rgba(37, 99, 235, 0.45);
    }

    input[type="range"]::-moz-range-track {
        height: 8px;
        border-radius: 9999px;
        background: rgba(148, 163, 184, 0.55);
    }

    input[type="range"]::-moz-range-thumb {
        width: 16px;
        height: 16px;
        background: #2563eb;
        border-radius: 50%;
        border: 2px solid rgba(255, 255, 255, 0.95);
        box-shadow: 0 2px 10px rgba(37, 99, 235, 0.45);
    }
</style>
