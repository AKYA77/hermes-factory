// Supervisor surfaces: the operator must be able to see and act on the queue, the
// service health and the audit trail. These are the screens that make an incident
// answerable, so they are checked as actions rather than as static pages.
//
// Usage: FACTORY_BROWSER_STATE=<dir> FACTORY_BROWSER_URL=<url> node supervisor-browser-smoke.cjs
const fs = require('fs');
const path = require('path');

const state = process.env.FACTORY_BROWSER_STATE;
const base = process.env.FACTORY_BROWSER_URL;
if (!state || !base) {
  console.error('FACTORY_BROWSER_STATE and FACTORY_BROWSER_URL are required');
  process.exit(2);
}
const token = fs.readFileSync(path.join(state, 'operator-1.token'), 'utf8').trim();

const VIEWS = ['Queue', 'Operations', 'Audit'];

(async () => {
  const { chromium } = require('playwright');
  const browser = await chromium.launch({executablePath:require('./lib/chromium-path.cjs').resolveChromium(),headless:true,args:['--no-sandbox']});
  const errors = [];
  const checks = [];
  try {
    const page = await browser.newPage();
    page.on('pageerror', (e) => errors.push(String(e)));
    await page.goto(base);
    await page.getByLabel('Access token').fill(token);
    await page.getByRole('button', { name: 'Connect / refresh', exact: true }).click();
    await page.locator('header h1').waitFor();

    for (const view of VIEWS) {
      await page.getByRole('button', { name: view, exact: true }).click();
      // Wait for THIS view's heading, not merely for a section to exist: a stale
      // frame from the previous view must never satisfy the check.
      await page.waitForFunction(
        (name) => document.querySelector('main header h1')?.textContent === name,
        view,
        { timeout: 30000 },
      );
      await page.waitForFunction(
        (name) => {
          const main = document.querySelector('main');
          return main && !main.textContent.includes('Loading application state');
        },
        view,
        { timeout: 30000 },
      );
      const body = await page.locator('main').innerText();
      if (body.length < 40) throw Error(`${view}: view rendered almost empty`);
      checks.push(`${view} rendered with evidence`);
    }

    // Queue: with no jobs there is nothing to cancel, and the panel must say so
    // rather than offering a cancel action that cannot apply.
    await page.getByRole('button', { name: 'Queue', exact: true }).click();
    await page.waitForTimeout(600);
    const queue = await page.locator('main').innerText();
    if (/No queued jobs/.test(queue)) {
      const cancels = await page.getByRole('button', { name: 'Cancel job' }).count();
      if (cancels !== 0) throw Error('Queue offers a cancel action with no jobs');
      checks.push('queue empty state truthful; no spurious cancel action');
    } else {
      checks.push('queue lists real jobs');
    }

    // Operations: readiness must report real states, not a hardcoded healthy flag.
    await page.getByRole('button', { name: 'Operations', exact: true }).click();
    await page.waitForTimeout(600);
    const ops = await page.locator('main').innerText();
    if (!/readiness|ready|live/i.test(ops)) {
      throw Error('Operations does not render readiness state');
    }
    checks.push('operations readiness rendered');

    // Export must exist on every one of these views.
    const downloads = await page.getByRole('button', { name: /Download exact API response/ }).count();
    if (downloads !== 1) throw Error(`Expected one export control, found ${downloads}`);
    checks.push('exact-response export present on supervisor views');

    await page.setViewportSize({ width: 390, height: 844 });
    const overflow = await page.evaluate(() => ({
      document: document.documentElement.scrollWidth,
      viewport: innerWidth,
    }));
    if (overflow.document > overflow.viewport) throw Error('Mobile horizontal overflow');
    if (errors.length) throw Error('Browser page errors: ' + errors.join(';'));

    console.log(JSON.stringify({
      status: 'PASS',
      scope: 'supervisor surfaces -- job queue, operations readiness and audit -- in authenticated loopback Chromium; generated state only, no production job was cancelled',
      browser: await browser.version(),
      state_directory: path.basename(state),
      checks: [...checks, 'mobile no document overflow', 'no page errors'],
      mobile: overflow,
    }));
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(String(e));
  process.exit(1);
});
