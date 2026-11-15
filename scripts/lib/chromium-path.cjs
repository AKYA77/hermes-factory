// Resolve a Chromium executable for the dashboard browser-acceptance smokes.
//
// Five of the six smoke scripts hardcoded /usr/bin/chromium, which does not exist
// on this host, so they could never launch. Resolve in order: an explicit
// FACTORY_CHROMIUM, the known tool path, playwright's bundled browser, then a
// small list of system locations. Fail loudly if none is present rather than
// letting playwright fall back to a path that does not exist.
const fs = require('fs');
const path = require('path');

const CANDIDATES = [
  '/root/.hermes/tools/chromium-1208/chrome-linux64/chrome',
  '/usr/bin/chromium',
  '/usr/bin/chromium-browser',
  '/usr/bin/google-chrome',
  '/usr/bin/google-chrome-stable',
];

function resolveChromium() {
  const explicit = process.env.FACTORY_CHROMIUM;
  if (explicit) {
    if (!fs.existsSync(explicit)) {
      throw new Error(`FACTORY_CHROMIUM set but missing: ${explicit}`);
    }
    return explicit;
  }
  for (const candidate of CANDIDATES) {
    if (fs.existsSync(candidate)) return candidate;
  }
  try {
    const registry = require('playwright-core/lib/server/registry/index.js');
    const browser = registry.findExecutable('chromium');
    if (browser && browser.executablePath() && fs.existsSync(browser.executablePath())) {
      return browser.executablePath();
    }
  } catch {
    // playwright-core registry unavailable; fall through to the error below
  }
  throw new Error(
    'No Chromium executable found. Set FACTORY_CHROMIUM to a chromium binary, ' +
      `or install one. Checked: ${CANDIDATES.join(', ')}`,
  );
}

module.exports = { resolveChromium, CANDIDATES };
