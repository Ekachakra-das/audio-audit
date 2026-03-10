const fs = require('fs');
const path = require('path');

// Read global conflicts
const globalPath = path.join(__dirname, 'global_conflicts.json');
const globalData = JSON.parse(fs.readFileSync(globalPath, 'utf8'));

console.log(`Loaded ${globalData.length} groups from global_conflicts.json`);

// Separate files by source
const folder1Files = []; // !Prabhupada classes
const folder2Files = []; // Prabhupada Vani

globalData.forEach(group => {
    group.files.forEach(file => {
        if (file.source === '!Prabhupada classes') {
            folder1Files.push({
                key: group.key,
                isIdentical: group.isIdentical,
                files: [file]
            });
        } else if (file.source === 'Prabhupada Vani') {
            folder2Files.push({
                key: group.key,
                isIdentical: group.isIdentical,
                files: [file]
            });
        }
    });
});

// Create folder data structure
const folder1Data = {
    stats: {
        total: folder1Files.length,
        standardized: folder1Files.filter(f => f.isIdentical).length,
        conflicts: folder1Files.filter(f => !f.isIdentical).length
    },
    files: folder1Files
};

const folder2Data = {
    stats: {
        total: folder2Files.length,
        standardized: folder2Files.filter(f => f.isIdentical).length,
        conflicts: folder2Files.filter(f => !f.isIdentical).length
    },
    files: folder2Files
};

// Write to files
const folder1Path = path.join(__dirname, 'analysis_folder1.json');
const folder2Path = path.join(__dirname, 'analysis_folder2.json');

fs.writeFileSync(folder1Path, JSON.stringify(folder1Data, null, 2));
fs.writeFileSync(folder2Path, JSON.stringify(folder2Data, null, 2));

console.log(`✅ Created ${folder1Path} with ${folder1Files.length} files`);
console.log(`✅ Created ${folder2Path} with ${folder2Files.length} files`);
console.log('\nFolder 1 (!Prabhupada classes):');
console.log(`  Total: ${folder1Data.stats.total}`);
console.log(`  Standardized: ${folder1Data.stats.standardized}`);
console.log(`  Conflicts: ${folder1Data.stats.conflicts}`);
console.log('\nFolder 2 (Prabhupada Vani):');
console.log(`  Total: ${folder2Data.stats.total}`);
console.log(`  Standardized: ${folder2Data.stats.standardized}`);
console.log(`  Conflicts: ${folder2Data.stats.conflicts}`);
