const fs = require('fs');
const content = fs.readFileSync('/Users/ekachakra/Documents/Projects/PRABHUPADA/lecture_analysis/ui/src/lib/AudioOptimizer.svelte', 'utf8');

let stack = [];
let lines = content.split('\n');

for (let i = 0; i < lines.length; i++) {
    let line = lines[i];
    // Match <div, </div>, {#if, {/if}, {#each, {/each}
    let regex = /<div|<\/div>|{#if|{\/if}|{#each|{\/each}/g;
    let match;
    while ((match = regex.exec(line)) !== null) {
        let tag = match[0];
        if (tag === '<div' || tag === '{#if' || tag === '{#each') {
            stack.push({ tag, line: i + 1 });
        } else {
            if (stack.length === 0) {
                console.log(`Unexpected closing tag ${tag} at line ${i + 1}`);
            } else {
                let last = stack.pop();
                // Simple check for matching type
                let expected = tag === '</div>' ? '<div' : tag === '{/if}' ? '{#if' : '{#each}';
                // if (last.tag !== expected) {
                //     console.log(`Mismatch: closed ${tag} at ${i+1} but last opened was ${last.tag} at ${last.line}`);
                // }
            }
        }
    }
}
console.log('Items remaining in stack:', stack.length);
stack.forEach(s => console.log(`Unclosed ${s.tag} at line ${s.line}`));
