const { chromium } = require('playwright');
const sharp = require('sharp');
const { pathToFileURL } = require('node:url');
const fs = require('node:fs/promises');

(async () => {
  const browser = await chromium.launch({channel: 'msedge', headless: true});
  try {
    await fs.mkdir('logs', {recursive: true});
    for (const viewport of [{width: 1280, height: 800}, {width: 390, height: 844}]) {
      const page = await browser.newPage({viewport});
      const errors = [];
      page.on('pageerror', e => errors.push(e.message));
      await page.goto(pathToFileURL(process.argv[2]).href);
      await page.waitForFunction(() => typeof osr !== 'undefined' && osr && document.querySelector('canvas'));
      await page.evaluate(() => osr.write('L01500I100 R01500I100\n'));
      await page.waitForTimeout(250);
      const before = await page.locator('canvas').screenshot();
      await page.evaluate(() => osr.write('L08500I100 R08500I100\n'));
      await page.waitForTimeout(250);
      const after = await page.locator('canvas').screenshot();
      const pixels = await sharp(after).removeAlpha().raw().toBuffer();
      const colors = new Set();
      for (let i = 0; i < pixels.length; i += 150) colors.add(pixels.subarray(i, i + 3).toString('hex'));
      if (colors.size < 20 || before.equals(after)) throw new Error('Blank or static 3D canvas');
      const bounds = await page.locator('#deviceContext').boundingBox();
      const canvasBounds = await page.locator('canvas').boundingBox();
      if (canvasBounds.y < bounds.y + bounds.height || canvasBounds.y + canvasBounds.height > viewport.height + 2) {
        throw new Error('Notice overlaps or clips the 3D canvas');
      }
      if (!(await page.locator('#deviceNote').innerText()).includes('differs from the actual device')) throw new Error('Missing shape notice');
      await page.screenshot({path: `logs/preview-${viewport.width}.png`});
      if (errors.length) throw new Error(errors.join('\n'));
      console.log(JSON.stringify({viewport, colors: colors.size, moving: true, bounds, canvasBounds}));
      await page.close();
    }
  } finally {
    await browser.close();
  }
})().catch(error => {console.error(error); process.exitCode = 1;});
