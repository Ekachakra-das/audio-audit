const path = require('path');
const fs = require('fs');
const { TRASH_DIR } = require('../config');

/**
 * Resolves a file path that might be broken due to folder moving.
 * @param {string} filePath The stored absolute path from JSON
 * @returns {string} The resolved existing path or the original if nothing found
 */
function resolveSafePath(filePath) {
    if (!filePath) return filePath;

    // 1. If it exists as-is, great.
    if (fs.existsSync(filePath)) return filePath;

    // 2. Try to resolve relative to project root.
    // In JSON, paths often look like /Users/.../PRABHUPADA/!Prabhupada classes/...
    // We try to find the part after the root folder name.
    const projectRootName = 'PRABHUPADA';
    const parts = filePath.split(path.sep);
    const rootIndex = parts.indexOf(projectRootName);

    if (rootIndex !== -1) {
        const relativePart = parts.slice(rootIndex + 1).join(path.sep);
        // __dirname is .../lecture_analysis/utils, so '..' is .../lecture_analysis.
        // We need to go up one more level to reach the PRABHUPADA root.
        const resolvedPath = path.resolve(__dirname, '..', '..', relativePart);
        if (fs.existsSync(resolvedPath)) {
            return resolvedPath;
        }
        // If the file is missing (maybe deleted), but its parent folder in the project 
        // exists, return this path so 'Reveal' can open the folder.
        if (fs.existsSync(path.dirname(resolvedPath))) {
            return resolvedPath;
        }
    }

    // 3. Try to find it in the Trash
    try {
        const trashPath = path.join(TRASH_DIR, path.basename(filePath));
        if (fs.existsSync(trashPath)) return trashPath;
    } catch (e) { }

    // 4. Try to resolve if it's already a relative-looking path
    const simpleResolved = path.resolve(__dirname, filePath.replace(/^\.\.\//, '../'));
    if (fs.existsSync(simpleResolved)) return simpleResolved;

    return filePath;
}

module.exports = {
    resolveSafePath
};
