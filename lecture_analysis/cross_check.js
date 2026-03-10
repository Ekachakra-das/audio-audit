const fs = require('fs');
const path = require('path');

const OUTPUT_DIR = __dirname;
const DATA_FILE_1 = path.join(OUTPUT_DIR, 'analysis_folder1.json');
const DATA_FILE_2 = path.join(OUTPUT_DIR, 'analysis_folder2.json');
const CROSS_CHECK_OUTPUT = path.join(OUTPUT_DIR, 'global_conflicts.json');

console.log("Starting Global Cross-Check...");

try {
    const data1 = JSON.parse(fs.readFileSync(DATA_FILE_1, 'utf8'));
    const data2 = JSON.parse(fs.readFileSync(DATA_FILE_2, 'utf8'));

    const reg1 = data1.registry;
    const reg2 = data2.registry;

    const crossConflicts = [];

    // Iterate through Registry 1 and check if ID exists in Registry 2
    for (const key in reg1) {
        if (reg2[key]) {
            // MATCH FOUND! 
            // We combine files from both sources into one "Global Duplicate Cluster"
            const files = [
                ...reg1[key].map(f => ({ ...f, source: data1.source })),
                ...reg2[key].map(f => ({ ...f, source: data2.source }))
            ];

            // Deep Equality Check:
            // All files in this global group must have the same size and duration (rounded)
            let isIdentical = false;
            if (files.length > 1) {
                const first = files[0];
                const cleanDuration = (d) => Math.round(d);

                isIdentical = files.every(f =>
                    f.size === first.size &&
                    cleanDuration(f.duration) === cleanDuration(first.duration)
                );
            }

            crossConflicts.push({
                key: key,
                isIdentical: isIdentical,
                files: files
            });
        }
    }

    // Sort: IDENTICAL ONES FIRST
    crossConflicts.sort((a, b) => {
        if (a.isIdentical && !b.isIdentical) return -1;
        if (!a.isIdentical && b.isIdentical) return 1;
        return 0;
    });

    fs.writeFileSync(CROSS_CHECK_OUTPUT, JSON.stringify(crossConflicts, null, 2));
    console.log(`Global Cross-Check complete. Found ${crossConflicts.length} shared lectures.`);
    console.log(`Results exported to: ${CROSS_CHECK_OUTPUT}`);

} catch (e) {
    console.error("Cross-check error:", e.message);
}
