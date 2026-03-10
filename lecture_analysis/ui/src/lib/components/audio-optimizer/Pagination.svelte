<script>
    import {
        ChevronLeft,
        ChevronRight,
        ChevronsLeft,
        ChevronsRight,
    } from "lucide-svelte";

    /**
     * @type {{
     *   totalFiles: number,
     *   pageSize: number,
     *   currentPage: number,
     *   onPageSizeChange?: (size: number) => void,
     *   onPageChange?: (page: number) => void
     * }}
     */
    let {
        totalFiles,
        pageSize = $bindable(),
        currentPage = $bindable(),
        onPageSizeChange = null,
        onPageChange = null,
    } = $props();

    let totalPages = $derived(Math.ceil(totalFiles / pageSize));
    let customPageSizeInput = $state(String(pageSize || 20));
    let currentPageInput = $state(String(currentPage || 1));
    let lastSyncedPage = $state(0);
    let visiblePages = $derived.by(() => {
        if (totalPages <= 10) return [];

        /** @type {(number | string)[]} */
        const pages = [];
        const start = Math.max(2, currentPage - 1);
        const end = Math.min(totalPages - 1, currentPage + 1);

        pages.push(1);
        if (start > 2) pages.push("...");
        for (let p = start; p <= end; p += 1) pages.push(p);
        if (end < totalPages - 1) pages.push("...");
        pages.push(totalPages);

        return pages;
    });

    $effect(() => {
        customPageSizeInput = String(pageSize || 20);
    });

    $effect(() => {
        if (currentPage !== lastSyncedPage) {
            currentPageInput = String(currentPage || 1);
            lastSyncedPage = currentPage;
        }
    });

    function normalizePageSize(value) {
        const parsed = parseInt(String(value).trim(), 10);
        if (!Number.isFinite(parsed) || parsed <= 0) return null;
        return Math.min(parsed, 1000);
    }

    function applyPageSize(size) {
        const normalized = normalizePageSize(size);
        if (!normalized) return;
        pageSize = normalized;
        currentPage = 1;
        if (onPageSizeChange) onPageSizeChange(normalized);
    }

    function handlePageSizeClick(size) {
        applyPageSize(size);
    }

    function handleCustomPageSizeApply() {
        const normalized = normalizePageSize(customPageSizeInput);
        if (!normalized) {
            customPageSizeInput = String(pageSize || 20);
            return;
        }
        applyPageSize(normalized);
    }

    function handlePageChangeClick(page) {
        currentPage = page;
        if (onPageChange) onPageChange(page);
    }

    function normalizePage(value) {
        const parsed = parseInt(String(value).trim(), 10);
        if (!Number.isFinite(parsed)) return null;
        if (parsed < 1) return 1;
        if (parsed > totalPages) return totalPages;
        return parsed;
    }

    function handleCurrentPageApply() {
        const normalized = normalizePage(currentPageInput);
        if (!normalized) {
            currentPageInput = String(currentPage || 1);
            return;
        }
        handlePageChangeClick(normalized);
    }
</script>

{#if totalFiles > 20}
    <div
        class="mt-8 flex flex-col md:flex-row items-center justify-between gap-6 px-6 py-8 bg-white dark:bg-slate-900/30 border border-slate-200 dark:border-slate-800/50 rounded-3xl shadow-sm dark:shadow-none transition-colors"
    >
        <div class="flex items-center gap-6">
            <div class="flex flex-col">
                <span
                    class="text-[10px] font-black text-slate-400 dark:text-slate-500 uppercase tracking-widest mb-1"
                    >Files Per Page</span
                >
                <div class="flex items-center gap-2">
                    {#each [20, 40, 60, 100].filter((size) => {
                        const sizes = [0, 20, 40, 60, 100];
                        const idx = sizes.indexOf(size);
                        return totalFiles > sizes[idx - 1] || pageSize === size;
                    }) as size (size)}
                        <button
                            onclick={() => handlePageSizeClick(size)}
                            class="px-3 py-1.5 rounded-lg text-xs font-bold transition-all {pageSize ===
                            size
                                ? 'bg-blue-600 text-white shadow-md shadow-blue-600/20'
                                : 'bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700'}"
                        >
                            {size}
                        </button>
                    {/each}
                    <input
                        type="number"
                        min="1"
                        max="1000"
                        step="1"
                        bind:value={customPageSizeInput}
                        onblur={handleCustomPageSizeApply}
                        onkeydown={(e) => {
                            if (e.key === "Enter") {
                                e.preventDefault();
                                handleCustomPageSizeApply();
                            }
                        }}
                        class="w-16 px-2 py-1.5 rounded-lg text-xs font-bold bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                        aria-label="Custom files per page"
                        title="Custom files per page"
                    />
                </div>
            </div>

            <div class="w-px h-10 bg-slate-200 dark:bg-slate-800"></div>

            <div class="flex flex-col">
                <span
                    class="text-[10px] font-black text-slate-400 dark:text-slate-500 uppercase tracking-widest mb-1"
                    >Total Files</span
                >
                <span
                    class="text-lg font-black text-slate-900 dark:text-white leading-none"
                    >{totalFiles}</span
                >
            </div>
        </div>

        {#if totalPages > 1}
            <div class="flex items-center gap-3 flex-wrap justify-center">
                {#if totalPages <= 10}
                    <div class="flex items-center gap-1.5 flex-wrap justify-center">
                        {#each Array.from({ length: totalPages }, (_, i) => i + 1) as page (page)}
                            <button
                                onclick={() => handlePageChangeClick(page)}
                                class="min-w-10 px-3 py-2 rounded-xl text-sm font-black transition-all active:scale-95 {currentPage ===
                                page
                                    ? 'bg-blue-600 text-white shadow-md shadow-blue-600/20'
                                    : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-white hover:bg-slate-200 dark:hover:bg-slate-700'}"
                                aria-label={`Go to page ${page}`}
                                aria-current={currentPage === page ? "page" : undefined}
                            >
                                {page}
                            </button>
                        {/each}
                    </div>
                {:else}
                    <div class="flex items-center gap-1">
                        <button
                            onclick={() => handlePageChangeClick(1)}
                            disabled={currentPage === 1}
                            class="p-2 rounded-xl bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-white disabled:opacity-30 disabled:cursor-not-allowed hover:bg-slate-200 dark:hover:bg-slate-700 transition-all active:scale-90"
                            title="First Page"
                        >
                            <ChevronsLeft size={18} />
                        </button>
                        <button
                            onclick={() => handlePageChangeClick(currentPage - 1)}
                            disabled={currentPage === 1}
                            class="p-2 rounded-xl bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-white disabled:opacity-30 disabled:cursor-not-allowed hover:bg-slate-200 dark:hover:bg-slate-700 transition-all active:scale-90"
                            title="Previous Page"
                        >
                            <ChevronLeft size={18} />
                        </button>
                    </div>

                    <div class="flex items-center gap-1.5 mx-1">
                        {#each visiblePages as page, index (`${page}-${index}`)}
                            {#if page === "..."}
                                <span
                                    class="px-2 text-sm font-black text-slate-400 dark:text-slate-500"
                                    >...</span
                                >
                            {:else}
                                <button
                                    onclick={() => handlePageChangeClick(Number(page))}
                                    class="min-w-10 px-3 py-2 rounded-xl text-sm font-black transition-all active:scale-95 {currentPage ===
                                    Number(page)
                                        ? 'bg-blue-600 text-white shadow-md shadow-blue-600/20'
                                        : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-white hover:bg-slate-200 dark:hover:bg-slate-700'}"
                                    aria-label={`Go to page ${page}`}
                                    aria-current={currentPage === Number(page)
                                        ? "page"
                                        : undefined}
                                >
                                    {page}
                                </button>
                            {/if}
                        {/each}
                    </div>

                    <div class="flex items-center gap-1">
                        <button
                            onclick={() => handlePageChangeClick(currentPage + 1)}
                            disabled={currentPage >= totalPages}
                            class="p-2 rounded-xl bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-white disabled:opacity-30 disabled:cursor-not-allowed hover:bg-slate-200 dark:hover:bg-slate-700 transition-all active:scale-90"
                            title="Next Page"
                        >
                            <ChevronRight size={18} />
                        </button>
                        <button
                            onclick={() => handlePageChangeClick(totalPages)}
                            disabled={currentPage >= totalPages}
                            class="p-2 rounded-xl bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-white disabled:opacity-30 disabled:cursor-not-allowed hover:bg-slate-200 dark:hover:bg-slate-700 transition-all active:scale-90"
                            title="Last Page"
                        >
                            <ChevronsRight size={18} />
                        </button>
                    </div>

                    <div class="w-px h-10 bg-slate-200 dark:bg-slate-800 mx-1"></div>

                    <div class="flex items-center gap-2">
                        <span
                            class="text-[10px] font-black text-slate-400 dark:text-slate-500 uppercase tracking-widest"
                            >Go to</span
                        >
                        <input
                            type="number"
                            min="1"
                            max={totalPages}
                            step="1"
                            bind:value={currentPageInput}
                            onblur={handleCurrentPageApply}
                            onkeydown={(e) => {
                                if (e.key === "Enter") {
                                    e.preventDefault();
                                    handleCurrentPageApply();
                                }
                            }}
                            class="w-16 px-2 py-1.5 rounded-lg text-xs font-black bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500/50 text-center"
                            aria-label="Go to page"
                            title="Go to page"
                        />
                        <span
                            class="text-[10px] font-black text-slate-400 dark:text-slate-500 uppercase tracking-widest"
                            >of {totalPages}</span
                        >
                    </div>
                {/if}
            </div>
        {/if}
    </div>
{/if}
