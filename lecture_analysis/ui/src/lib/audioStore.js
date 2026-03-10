/**
 * Global Audio Store
 * Manages which audio player is currently active.
 * When a new player starts, all others should pause.
 */

// Using a simple event-based approach for Svelte 5 compatibility
let activePlayerId = null;
let currentTrack = null; // { path, title, ... }
let currentPlaylist = [];
let currentIndex = -1;
let isFullPlayerVisible = false;
let isPlaying = false;

const listeners = new Set();
const trackListeners = new Set();
const playlistListeners = new Set();
const commandListeners = new Set();
const visibilityListeners = new Set();
const playingListeners = new Set();

export function setActivePlayer(id) {
    activePlayerId = id;
    listeners.forEach(callback => callback(id));
}

export function setPlaybackState(playing) {
    isPlaying = playing;
    playingListeners.forEach(callback => callback(playing));
}

export function subscribeToPlaybackState(callback) {
    playingListeners.add(callback);
    callback(isPlaying);
    return () => playingListeners.delete(callback);
}

export function setGlobalTrack(track, playlist = null) {
    currentTrack = track;
    if (playlist) {
        currentPlaylist = playlist;
        if (track) {
            currentIndex = playlist.findIndex(t => t.path === track.path || t.optimizedPath === track.path);
        } else {
            currentIndex = -1;
        }
    } else if (currentPlaylist.length > 0 && track) {
        currentIndex = currentPlaylist.findIndex(t => t.path === track.path || t.optimizedPath === track.path);
    } else {
        currentIndex = -1;
    }
    trackListeners.forEach(callback => callback(track));
    playlistListeners.forEach(callback => callback({ playlist: currentPlaylist, index: currentIndex }));
}

export function setPlaylist(playlist) {
    currentPlaylist = playlist;
    if (currentTrack) {
        currentIndex = playlist.findIndex(t => t.path === currentTrack.path || t.optimizedPath === currentTrack.path);
    }
    playlistListeners.forEach(callback => callback({ playlist: currentPlaylist, index: currentIndex }));
}

export function setFullPlayerVisibility(visible) {
    isFullPlayerVisible = visible;
    visibilityListeners.forEach(callback => callback(visible));
}

export function subscribeToFullPlayerVisibility(callback) {
    visibilityListeners.add(callback);
    callback(isFullPlayerVisible);
    return () => visibilityListeners.delete(callback);
}

export function subscribeToPlaylist(callback) {
    playlistListeners.add(callback);
    callback({ playlist: currentPlaylist, index: currentIndex });
    return () => playlistListeners.delete(callback);
}

export function subscribeToGlobalTrack(callback) {
    trackListeners.add(callback);
    return () => trackListeners.delete(callback);
}

export function getActivePlayer() {
    return activePlayerId;
}

export function subscribeToActivePlayer(callback) {
    listeners.add(callback);
    // Return unsubscribe function
    return () => listeners.delete(callback);
}

// Helper: Pause all except the given ID
export function pauseOthers(currentId) {
    setActivePlayer(currentId);
}

// --- Global Command System ---

export function subscribeToAudioCommands(callback) {
    commandListeners.add(callback);
    return () => commandListeners.delete(callback);
}

export function dispatchAudioCommand(command, payload) {
    commandListeners.forEach(cb => cb(command, payload));
}

