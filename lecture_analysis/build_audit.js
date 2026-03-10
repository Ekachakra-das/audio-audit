const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

console.log("🚀 STARTING FULL AUDIT BUILD (INJECTION MODE)...");

try {
    // 1. Run Data Extractors
    console.log("--- 1/5 Scanning Folder 1 (Classes)...");
    execSync('node standardize_audit.js', { stdio: 'inherit' });

    console.log("--- 2/5 Scanning Folder 2 (Vani)...");
    execSync('node standardize_vani.js', { stdio: 'inherit' });

    console.log("--- 3/5 Cross-Checking Folders...");
    execSync('node cross_check.js', { stdio: 'inherit' });

    // 2. Build Svelte UI (WITHOUT DATA)
    console.log("--- 4/5 Building Svelte UI Shell...");
    process.chdir('ui');
    execSync('npm run build', { stdio: 'inherit' });
    process.chdir('..');

    // 3. Inject Data & Move
    console.log("--- 5/5 Injecting Data into HTML...");
    const builtHtmlPath = path.join(__dirname, 'ui', 'dist', 'index.html');
    let html = fs.readFileSync(builtHtmlPath, 'utf8');

    // Load JSON Content
    const data1 = fs.readFileSync(path.join(__dirname, 'analysis_folder1.json'), 'utf8');
    const data2 = fs.readFileSync(path.join(__dirname, 'analysis_folder2.json'), 'utf8');
    const globalData = fs.readFileSync(path.join(__dirname, 'global_conflicts.json'), 'utf8');

    // Create Injection Script
    const injection = `
    <script>
      window.auditData = {
        folder1: ${data1},
        folder2: ${data2},
        global: ${globalData}
      };
    </script>
    `;

    // Inject before </head> or <body>
    html = html.replace('</head>', `${injection}</head>`);

    // Save Final
    const targetHtml = path.join(__dirname, 'index.html');
    fs.writeFileSync(targetHtml, html);

    console.log(`\n✅ SUCCESS! Final report generated: ${targetHtml}`);
    console.log(`Final Size: ${(fs.statSync(targetHtml).size / 1024 / 1024).toFixed(2)} MB`);

} catch (e) {
    console.error("\n❌ FATAL ERROR DURING BUILD:", e.message);
    process.exit(1);
}
