const {chromium} = require('playwright');
const path = require('path');
const fs = require('fs');

/**
 * Usage:
 *   node headless_process.js <imagePath> <label> [stockpileName] [version]
 *
 * Example:
 *   node headless_process.js sample_pictures/tine.png "Tine North" "" airborne-63
 */

const args = process.argv.slice(2);
const inputImagePath = args[0] || path.join('sample_pictures', 'tine.png');
const inputLabel = args[1] || 'Default Label';

// Fallback to 'Public' if missing, empty "", or "-"
let inputStockpileName = args[2];
if (!inputStockpileName || inputStockpileName === "" || inputStockpileName === "-") {
    inputStockpileName = 'Public';
}

const inputVersion = args[3] || 'airborne-63';

function buildLaunchArgs() {
    const mode = (process.env.FIR_GPU_MODE || 'gpu').toLowerCase();

    // Common container-safe args
    const common = [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--ignore-gpu-blocklist',
    ];

    // Best path for NVIDIA + Linux headless in containers
    const gpu = [
        '--use-gl=egl',
        '--enable-gpu',
        '--disable-software-rasterizer',
        // Optional: sometimes improves rendering paths
        '--enable-features=UseSkiaRenderer',
    ];

    // CPU fallback (keeps pipeline working if Ollama is camping VRAM)
    const cpu = [
        '--disable-gpu',
        '--use-gl=swiftshader',
    ];

    const launchArgs = mode === 'gpu'
        ? [...common, ...gpu]
        : [...common, ...cpu];

    console.log(`Launching Chromium in ${mode.toUpperCase()} mode`);
    return launchArgs;
}

(async () => {
    const browser = await chromium.launch({
        headless: true,
        args: buildLaunchArgs(),
    });

    const page = await browser.newPage();

    page.on('console', msg => console.log(`[BROWSER]: ${msg.text()}`));

    const url = `http://localhost:8005?v=${inputVersion}`;
    console.log(`Connecting to ${url}...`);

    try {
        await page.goto(url, {waitUntil: 'networkidle', timeout: 30000});
    } catch (e) {
        console.error('ERROR: Could not reach the FIR server. Ensure the Python process is running on 8005.');
        await browser.close();
        process.exit(1);
    }

    // Optional: print WebGL renderer to confirm GPU vs SwiftShader
    try {
        const glInfo = await page.evaluate(() => {
            const canvas = document.createElement('canvas');
            const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
            if (!gl) return {ok: false, reason: 'no webgl context'};
            const dbg = gl.getExtension('WEBGL_debug_renderer_info');
            if (!dbg) return {ok: true, renderer: gl.getParameter(gl.RENDERER)};
            return {
                ok: true,
                vendor: gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL),
                renderer: gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL),
            };
        });
        console.log('WebGL:', glInfo);
    } catch (e) {
        console.log('WebGL check skipped:', String(e));
    }

    const imagePath = path.resolve(__dirname, inputImagePath);
    const outputDir = path.resolve(__dirname, 'sample_output');
    if (!fs.existsSync(outputDir)) fs.mkdirSync(outputDir, {recursive: true});

    if (!fs.existsSync(imagePath)) {
        console.error(`ERROR: Image file not found at ${imagePath}`);
        await browser.close();
        process.exit(1);
    }

    console.log(`\nProcessing: ${inputImagePath}`);
    await page.setInputFiles('input[type="file"]', imagePath);

    process.stdout.write('OCR Status: Processing...');
    await page.waitForFunction(() => {
        const el = document.querySelector('li span');
        if (!el) return false;
        return el.textContent.includes('1 of 1');
    }, {timeout: 120000});
    process.stdout.write(' Complete!\n');

    await page.evaluate(({label, stockpileName}) => {
        const labelElem = document.querySelector('div.render span[contenteditable]');
        if (labelElem) {
            labelElem.textContent = label;
            labelElem.dispatchEvent(new Event('input', {bubbles: true}));
        }

        if (window.stockpiles && window.stockpiles[0]) {
            window.stockpiles[0].header.name = stockpileName;
        }
    }, {label: inputLabel, stockpileName: inputStockpileName});

    const tsvData = await page.evaluate(() => {
        return (async () => {
            const stockpiles = window.stockpiles;
            const version = window.FIR_CATALOG_VERSION || 'airborne-63';
            const catalog = await fetch(`./foxhole/${version}/catalog.json`).then(r => r.json());

            const items = [[
                'Stockpile Title', 'Stockpile Name', 'Structure Type', 'Quantity', 'Name',
                'Crated?', 'Per Crate', 'Total', 'Description', 'CodeName'
            ].join('\t')];

            for (const stockpile of stockpiles) {
                for (const element of stockpile.contents) {
                    if (element.quantity == 0) continue;
                    const details = catalog.find(e => e.CodeName == element.CodeName);
                    if (!details) continue;

                    const perCrate = ((details.ItemDynamicData || {}).QuantityPerCrate || 3)
                        + (details.VehiclesPerCrateBonusQuantity || 0);
                    const perUnit = element.isCrated ? perCrate : 1;

                    items.push([
                        stockpile.label.textContent.trim(),
                        stockpile.header.name || '',
                        stockpile.header.type || '',
                        element.quantity,
                        details.DisplayName,
                        element.isCrated,
                        element.isCrated ? perUnit : '',
                        element.quantity * perUnit,
                        details.Description,
                        element.CodeName,
                    ].join('\t'));
                }
            }
            return items.join('\n');
        })();
    });

    const safeFileName = inputLabel.replace(/[^a-z0-9]/gi, '_').toLowerCase();
    const outputPath = path.join(outputDir, `${safeFileName}_report.tsv`);
    fs.writeFileSync(outputPath, tsvData);

    console.log(`SUCCESS: Report generated at ${outputPath}`);
    await browser.close();
})();
