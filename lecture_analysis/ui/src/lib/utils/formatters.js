/**
 * Shared utility functions for AudioOptimizer components
 */

/**
 * Format duration in seconds to H:MM:SS or M:SS format
 * @param {number} seconds
 * @returns {string}
 */
export function formatDuration(seconds) {
    if (!seconds && seconds !== 0) return "0:00";
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    if (h > 0) {
        return `${h}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
    }
    return `${m}:${s.toString().padStart(2, "0")}`;
}

/**
 * Format duration to compact English h/m style (no seconds).
 * Examples: "1h 05m", "27m", "1m"
 * @param {number} seconds
 * @returns {string}
 */
export function formatDurationHmsShort(seconds) {
    if (!seconds || Number.isNaN(seconds)) return "0m";
    const total = Math.max(0, Math.floor(seconds));
    const h = Math.floor(total / 3600);
    const m = Math.floor((total % 3600) / 60);

    if (h > 0) {
        return `${h}h ${m.toString().padStart(2, "0")}m`;
    }
    if (m > 0) return `${m}m`;
    return "1m";
}

/**
 * Format bytes to human-readable size
 * @param {number} bytes
 * @returns {string}
 */
export function formatSize(bytes) {
    if (!bytes && bytes !== 0) return "0 B";
    const units = ["B", "KB", "MB", "GB"];
    let i = 0;
    while (bytes >= 1024 && i < units.length - 1) {
        bytes /= 1024;
        i++;
    }
    return `${bytes.toFixed(1)} ${units[i]}`;
}

/**
 * Calculate savings percentage
 * @param {number} original
 * @param {number} optimized
 * @returns {number}
 */
export function getSavingsPercent(original, optimized) {
    if (!original || !optimized) return 0;
    return Math.round(((original - optimized) / original) * 100);
}

/**
 * Get row background color based on file status
 * @param {{ status: string, finalPath?: string }} file
 * @returns {string}
 */
export function getRowColor(file) {
    if (file.status === "error")
        return "bg-red-50 dark:bg-red-900/10 border-red-200 dark:border-red-900/50";
    if (file.status === "completed" || (file.finalPath && (file.status === "analyzing" || file.status === "converting")))
        return "bg-emerald-50 dark:bg-emerald-900/10 border-emerald-200 dark:border-emerald-900/50";
    if (file.status === "analyzing" || file.status === "converting")
        return "bg-blue-50 dark:bg-blue-900/10 border-blue-200 dark:border-blue-900/50";
    return "bg-white dark:bg-slate-800/40 border-slate-200 dark:border-slate-800";
}
