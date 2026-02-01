/**
 * Headless FIR processing (DIRECT MODE)
 *
 * - No file input upload to Chromium
 * - Loads image bytes in Node, passes data URL into page
 * - Creates canvas in page and calls Screenshot.process(...) directly
 * - Sets window.stockpiles so TSV extraction works unchanged
 */

const {chromium} = require('playwright');
const path = require('path');
const fs = require('fs');

const OCR_BACKEND = process.env.FIR_OCR_BACKEND || 'browser';

const args = process.argv.slice(2);
const inputImagePath = args[0] || path.join('sample_pictures', 'tine.png');
const inputLabel = args[1] || 'Default Label';

let inputStockpileName = args[2];
if (!inputStockpileName || inputStockpileName === '' || inputStockpileName === '-') {
    inputStockpileName = 'Public';
}

const inputVersion = args[3] || 'airborne-63';

function buildLaunchArgs() {
    // Keep Chromium CPU-only so it doesn't compete with Ollama/Plex GPU usage.
    const common = [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--ignore-gpu-blocklist',
    ];

    const cpuOnly = [
        '--disable-gpu',
        '--use-gl=swiftshader',
    ];

    console.log(`Launching Chromium (OCR backend = ${OCR_BACKEND})`);
    return [...common, ...cpuOnly];
}

function fileToDataUrl(absPath) {
    const buf = fs.readFileSync(absPath);
    // Basic mime inference from extension (good enough for PNG/JPG)
    const ext = path.extname(absPath).toLowerCase();
    const mime =
        ext === '.png' ? 'image/png' :
            (ext === '.jpg' || ext === '.jpeg') ? 'image/jpeg' :
                'application/octet-stream';

    return `data:${mime};base64,${buf.toString('base64')}`;
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
        // Runs BEFORE FIR JS executes
        await page.addInitScript((backend) => {
            window.FIR_OCR_BACKEND = backend;

            if (backend === 'gpu') {
                // Prevent browser OCR workers from launching
                window.launchOCRWorkers = () => {
                    console.log('[FIR] Browser OCR disabled (GPU backend)');
                };

                // Hard block tesseract fallback
                window.Tesseract = {
                    createWorker: () => {
                        throw new Error('Browser OCR disabled — GPU backend active');
                    }
                };

                // Soft-disable TFJS backend selection
                if (window.tf && window.tf.setBackend) {
                    try {
                        window.tf.setBackend('cpu');
                    } catch {
                    }
                }
            }
        }, OCR_BACKEND);

        await page.goto(url, {waitUntil: 'networkidle', timeout: 30000});
    } catch (e) {
        console.error('ERROR: Could not reach FIR frontend on port 8005');
        await browser.close();
        process.exit(1);
    }

    // Resolve image and convert to data URL
    const absImagePath = path.resolve(__dirname, inputImagePath);
    if (!fs.existsSync(absImagePath)) {
        console.error(`ERROR: Image file not found: ${absImagePath}`);
        await browser.close();
        process.exit(1);
    }
    const dataUrl = fileToDataUrl(absImagePath);

    // -----------------------------
    // DIRECT processing inside page:
    // - create Image -> canvas
    // - call Screenshot.process
    // - build window.stockpiles (same shape FIR expects)
    // - update "1 of 1" status so your existing wait checks still work
    // -----------------------------
    process.stdout.write('OCR Status: Processing...');

    const ok = await page.evaluate(async ({dataUrl, labelText, stockpileName, version}) => {
        // Load modules fresh (same instances; browser caches ES modules)
        const Screenshot = (await import('./includes/screenshot.mjs')).default;

        // Resource URLs match includes/main.js logic
        const ICON_MODEL_URL = `./foxhole/${version}/classifier/model.json`;
        const QUANTITY_MODEL_URL = './includes/quantities/model.json';

        const [iconClassNames, quantityClassNames] = await Promise.all([
            fetch(`./foxhole/${version}/classifier/class_names.json`).then(r => r.json()),
            fetch('./includes/quantities/class_names.json').then(r => r.json()),
        ]);

        // Create image from data URL
        const img = new Image();
        img.src = dataUrl;

        await new Promise((resolve, reject) => {
            img.onload = resolve;
            img.onerror = () => reject(new Error('Failed to load image data URL'));
        });

        // Draw to canvas
        const canvas = document.createElement('canvas');
        canvas.width = img.naturalWidth || img.width;
        canvas.height = img.naturalHeight || img.height;

        const ctx = canvas.getContext('2d', {alpha: false, willReadFrequently: true});
        ctx.drawImage(img, 0, 0);

        // Run FIR detection pipeline
        const stockpile = await Screenshot.process(
            canvas,
            ICON_MODEL_URL,
            iconClassNames,
            QUANTITY_MODEL_URL,
            quantityClassNames
        );

        // If FIR couldn't find the stockpile box, bail
        if (!stockpile) {
            return {ok: false, reason: 'Screenshot.process returned undefined (no stockpile detected)'};
        }

        // Create a label element so TSV code can do: stockpile.label.textContent.trim()
        const labelEl = document.createElement('span');
        labelEl.textContent = labelText;
        labelEl.contentEditable = true;
        labelEl.spellcheck = false;

        // Match FIR's structure
        stockpile.label = labelEl;
        stockpile.lastModified = Date.now();
        stockpile.header = stockpile.header || {};
        stockpile.header.name = stockpileName;

        // Publish globals FIR uses
        window.stockpiles = [stockpile];
        window.stockpilesJSON = JSON.stringify([{
            file: labelEl.textContent.trim(),
            version: window.FIR_CATALOG_VERSION,
            box: {x: stockpile.box.x, y: stockpile.box.y, width: stockpile.box.width, height: stockpile.box.height},
            header: {type: stockpile.header.type || null, name: stockpile.header.name || null},
            contents: stockpile.contents.map(e => ({
                CodeName: e.CodeName,
                quantity: e.quantity,
                isCrated: e.isCrated,
            })),
        }], undefined, 2);

        // Update the UI progress span so existing "1 of 1" waits work
        const progress = document.querySelector('li span');
        if (progress) progress.textContent = '1 of 1';

        return {ok: true};
    }, {
        dataUrl,
        labelText: inputLabel,
        stockpileName: inputStockpileName,
        version: inputVersion,
    });

    if (!ok.ok) {
        process.stdout.write(' Failed!\n');
        console.error(`ERROR: ${ok.reason}`);
        await browser.close();
        process.exit(1);
    }

    process.stdout.write(' Complete!\n');

    // Inject label & stockpile name (optional; already set in direct mode)
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

    // TSV extraction: unchanged logic
    const tsvData = await page.evaluate(async () => {
        const stockpiles = window.stockpiles;
        const version = window.FIR_CATALOG_VERSION || 'airborne-63';
        const catalog = await fetch(`./foxhole/${version}/catalog.json`).then(r => r.json());

        const rows = [[
            'Stockpile Title', 'Stockpile Name', 'Structure Type', 'Quantity', 'Name',
            'Crated?', 'Per Crate', 'Total', 'Description', 'CodeName'
        ].join('\t')];

        for (const stockpile of stockpiles) {
            for (const element of stockpile.contents) {
                if (element.quantity === 0) continue;
                const details = catalog.find(e => e.CodeName === element.CodeName);
                if (!details) continue;

                const perCrate =
                    ((details.ItemDynamicData || {}).QuantityPerCrate || 3) +
                    (details.VehiclesPerCrateBonusQuantity || 0);

                const perUnit = element.isCrated ? perCrate : 1;

                rows.push([
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

        return rows.join('\n');
    });

    const outputDir = path.resolve(__dirname, 'sample_output');
    if (!fs.existsSync(outputDir)) fs.mkdirSync(outputDir, {recursive: true});

    const safeFileName = inputLabel.replace(/[^a-z0-9]/gi, '_').toLowerCase();
    const outputPath = path.join(outputDir, `${safeFileName}_report.tsv`);

    fs.writeFileSync(outputPath, tsvData);
    console.log(`SUCCESS: Report generated at ${outputPath}`);

    await browser.close();
})();
