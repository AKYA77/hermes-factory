// Recorded performance evidence: the dashboard must show REAL past measurements with
// their provenance and declared limitations, and must not claim a live benchmark or
// the target envelope.
//
// Usage: FACTORY_BROWSER_STATE=<dir> FACTORY_BROWSER_URL=<url> node performance-browser-smoke.cjs
const fs = require('fs');
const path = require('path');

const state = process.env.FACTORY_BROWSER_STATE;
const base = process.env.FACTORY_BROWSER_URL;
if (!state || !base) {
  console.error('FACTORY_BROWSER_STATE and FACTORY_BROWSER_URL are required');
  process.exit(2);
}
const token = fs.readFileSync(path.join(state, 'operator-1.token'), 'utf8').trim();

(async () => {
  const { chromium } = require('playwright');
  const browser = await chromium.launch({executablePath:require('./lib/chromium-path.cjs').resolveChromium(),headless:true,args:['--no-sandbox']});
  const errors = [];
  try {
    const page = await browser.newPage();
    page.on('pageerror', (e) => errors.push(String(e)));
    await page.goto(base);
    await page.getByLabel('Access token').fill(token);
    await page.getByRole('button', { name: 'Connect / refresh', exact: true }).click();
    await page.getByRole('button', { name: 'Performance', exact: true }).click();

    const section = page.locator('section[aria-label="Recorded performance evidence"]');
    await section.waitFor({ timeout: 30000 });
    // Wait for THIS view's payload: either a measured artifact rendered, or the
    // panel stating that none are recorded. Waiting only for measurements would hang
    // forever on a fresh checkout, where benchmark reports legitimately do not exist.
    await page.waitForFunction(
      () => {
        const text = document.querySelector(
          'section[aria-label="Recorded performance evidence"]',
        )?.textContent ?? '';
        return text.includes('logical CPUs') || text.includes('not recorded');
      },
      null,
      { timeout: 30000 },
    );
    const body = await section.innerText();

    if (!/recorded measurements/i.test(body)) throw Error('Recorded-performance framing missing');
    // Benchmark reports are generated artifacts and are gitignored, so a fresh
    // checkout legitimately has none. When artifacts ARE present, verify the measured
    // facts; when they are not, require the panel to say so per artifact instead of
    // rendering an empty panel.
    if (/logical CPUs/.test(body)) {
      if (!/limitations/i.test(body)) throw Error('Declared limitations not rendered');
      if (!/[0-9a-f]{16}/.test(body)) throw Error('Artifact hash not rendered');
      var measured = 'measured hardware, limitations and hashes rendered';
    } else if (/not recorded/.test(body)) {
      var measured = 'absence of recorded artifacts stated explicitly';
    } else {
      throw Error('Panel shows neither measurements nor an explicit absence');
    }
    // A recorded number must never be presented as a current run.
    if (!/recorded measurements from past runs/i.test(body)) {
      throw Error('Panel does not state these are past measurements');
    }
    if (!/not live benchmarking/i.test(body)) {
      throw Error('Panel does not disclaim live benchmarking');
    }

    await page.setViewportSize({ width: 390, height: 844 });
    const overflow = await page.evaluate(() => ({
      document: document.documentElement.scrollWidth,
      viewport: innerWidth,
    }));
    if (overflow.document > overflow.viewport) {
      const widest = await page.evaluate(() => {
        const vw = innerWidth;
        const bad = [];
        document.querySelectorAll('*').forEach((el) => {
          const r = el.getBoundingClientRect();
          if (r.right > vw + 1 || r.left < -1) bad.push(`${el.tagName}.${el.className} l=${Math.round(r.left)} r=${Math.round(r.right)}`);
        });
        return { document: document.documentElement.scrollWidth, viewport: vw, widest: bad.slice(0, 6) };
      });
      throw Error('Mobile horizontal overflow ' + JSON.stringify(widest));
    }
    if (errors.length) throw Error('Browser page errors: ' + errors.join(';'));

    console.log(JSON.stringify({
      status: 'PASS',
      scope: 'recorded benchmark measurements in authenticated loopback Chromium; historical artifacts only, not live runs and not a target-envelope claim',
      browser: await browser.version(),
      state_directory: path.basename(state),
      checks: [
        'authenticated render',
        'recorded-not-live framing explicit',
        measured,
        'mobile no document overflow',
        'no page errors',
      ],
      mobile: overflow,
    }));
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(String(e));
  process.exit(1);
});
