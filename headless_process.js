const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

/**
 * Usage: node headless_process.js <imagePath> <label> [stockpileName] [version]
 * Example: node headless_process.js sample_pictures/tine.png "Tine North" "" airborne-63
 */
const args = process.argv.slice(2);
const inputImagePath = args[0] || path.join('sample_pictures', 'tine.png');
const inputLabel = args[1] || 'Default Label';

// Fallback to 'Public' if the argument is missing, empty "", or a dash "-"
let inputStockpileName = args[2];
if (!inputStockpileName || inputStockpileName === "" || inputStockpileName === "-") {
  inputStockpileName = 'Public';
}

const inputVersion = args[3] || 'airborne-63';

(async () => {
  const browser = await chromium.launch({ 
    headless: true,
    args: [
      '--use-gl=angle',
      '--use-angle=gl',        // Use actual OpenGL/Hardware
      '--enable-features=Vulkan', // Enable Vulkan for better TF.js support
      '--disable-webgl-sandbox',
      '--ignore-gpu-blocklist'    // Force GPU usage even if driver is "unsupported"
    ]
  });
  const page = await browser.newPage();
  
  page.on('console', msg => console.log(`[BROWSER]: ${msg.text()}`));

  const url = `http://localhost:8005?v=${inputVersion}`;
  console.log(`Connecting to ${url}...`);

  try {
    await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 });
  } catch (e) {
    console.error('ERROR: Could not reach the FIR server. Ensure the Python process is running on 8005.');
    await browser.close();
    process.exit(1);
  }

  const imagePath = path.resolve(__dirname, inputImagePath);
  const outputDir = path.resolve(__dirname, 'sample_output');
  if (!fs.existsSync(outputDir)) fs.mkdirSync(outputDir);

  if (!fs.existsSync(imagePath)) {
    console.error(`ERROR: Image file not found at ${imagePath}`);
    await browser.close();
    process.exit(1);
  }

  console.log(`\nProcessing: ${inputImagePath}`);
  await page.setInputFiles('input[type="file"]', imagePath);

  process.stdout.write('OCR Status: Processing...');
  await page.waitForFunction(() => {
    const status = document.querySelector('li span').textContent;
    return status.includes('1 of 1');
  }, { timeout: 120000 });
  process.stdout.write(' Complete!\n');

  await page.evaluate(({ label, stockpileName }) => {
    const labelElem = document.querySelector('div.render span[contenteditable]');
    if (labelElem) {
      labelElem.textContent = label;
      labelElem.dispatchEvent(new Event('input', { bubbles: true }));
    }

    if (window.stockpiles && window.stockpiles[0]) {
      window.stockpiles[0].header.name = stockpileName;
    }
  }, { label: inputLabel, stockpileName: inputStockpileName });

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
