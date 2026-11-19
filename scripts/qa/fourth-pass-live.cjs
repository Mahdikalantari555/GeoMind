// Fourth-pass live check: production Studio build + stubbed gateway.
// Run: LD_LIBRARY_PATH=/tmp/al/lib NODE_PATH=/tmp/qa/node_modules node scripts/qa/fourth-pass-live.cjs before|after
// STUDIO_HTML overrides the bundle (used for the pristine baseline build).
const fs = require('node:fs');
const assert = require('node:assert/strict');
const path = require('node:path');
const puppeteer = require('puppeteer-core');
const chromium = require('@sparticuz/chromium');

(async () => {
  const phase = process.argv[2];
  assert(['before', 'after'].includes(phase), 'pass before|after');
  const dir = path.join('docs/qa/fourth-pass', phase);
  fs.mkdirSync(dir, { recursive: true });
  const html = fs.readFileSync(process.env.STUDIO_HTML || 'apps/studio/dist/index.html');
  const browser = await puppeteer.launch({
    args: chromium.args,
    executablePath: await chromium.executablePath(),
    headless: true,
  });
  const observations = {};
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1440, height: 900 });
    const base = 'https://studio.test';
    const errors = [];
    const nonGet = [];
    page.on('pageerror', (e) => errors.push(e.message));
    await page.setRequestInterception(true);
    page.on('request', (r) => {
      if (r.isNavigationRequest()) return r.respond({ contentType: 'text/html', body: html });
      if (!r.url().startsWith(base + '/api/')) return r.abort();
      const p = new URL(r.url()).pathname.replace('/api/v1', '');
      if (r.method() !== 'GET') nonGet.push({ p, body: r.postData() });
      const json = (d, status = 200) => r.respond({ status, contentType: 'application/json', body: JSON.stringify(d) });
      // Two sub-regions sharing version 1, plus a (crop, region) pair.
      if (p === '/models/versions')
        return json({
          versions: [
            { key: ['sugarcane', 'karkheh', 'north'], version: 2, timestamp: '2026-02-01T00:00:00Z', n_samples: 40, sha256: 'aa', active: true },
            { key: ['sugarcane', 'karkheh', 'north'], version: 1, timestamp: '2026-01-01T00:00:00Z', n_samples: 20, sha256: 'bb', active: false },
            { key: ['sugarcane', 'karkheh', 'south'], version: 1, timestamp: '2026-01-01T00:00:00Z', n_samples: 20, sha256: 'cc', active: true },
          ],
        });
      if (p === '/rois')
        return json({ rois: [{ id: 'A', name: 'Parcel A', kind: 'bbox', coords: [[47.9, 32.3], [48.1, 32.3], [48.1, 32.5], [47.9, 32.5]], areaHa: 12, centroid: [-34.6, -58.4], createdAt: 0 }] });
      if (p === '/health') return json({ workspace: { status: 'open' }, llm: { key_configured: true } });
      if (p === '/workspace') return json({ path: '/qa/ws', settings: { name: 'ws' } });
      if (p === '/events') return r.respond({ contentType: 'text/event-stream', body: ': ping\n\n' });
      if (p === '/agent/playbooks') return json({ playbooks: [] });
      if (p === '/models/rollback') return json({ rolled_back: true });
      return json([]);
    });

    // 1) Training lab uses the stub data without unmounting.
    await page.goto(base + '/#/training');
    await page.waitForSelector('main');
    await page.waitForFunction(() => document.querySelector('main').innerText.includes('north'), { timeout: 15000 });
    await page.screenshot({ path: path.join(dir, 'training-subregions.jpg') });
    await page.reload();
    await page.waitForFunction(() => document.querySelector('main').innerText.includes('north'), { timeout: 15000 });
    observations.versionRows = await page.evaluate(() =>
      Array.from(document.querySelectorAll('main li')).filter((li) => li.innerText.includes('@v')).map((li) => li.innerText.split('\n')[0]),
    );
    // Click "Rollback" on the sub-region v1 row and capture the request body.
    await page.evaluate(() => {
      const rows = Array.from(document.querySelectorAll('main li')).filter((li) => li.innerText.includes('sugarcane-karkheh-north@v1'));
      const btn = rows[0] && Array.from(rows[0].querySelectorAll('button')).find((b) => /Rollback/i.test(b.innerText));
      if (btn) btn.click();
    });
    await sleep(700);

    // 2) Map view: negative latitude/longitude must be labelled S/W.
    await page.goto(base + '/#/map');
    await page.waitForSelector('main canvas');
    await sleep(900);
    // The cursor readout only fills after a real pointer move inside the map.
    const view = page.viewport();
    for (const [fx, fy] of [[0.45, 0.55], [0.6, 0.4], [0.3, 0.7]]) {
      await page.mouse.move(view.width * fx, view.height * fy);
      await sleep(180);
    }
    await page.screenshot({ path: path.join(dir, 'map-hemisphere.jpg') });
    const readout = () =>
      page.evaluate(() => {
        const box = Array.from(document.querySelectorAll('main div')).find(
          (d) => d.textContent.includes('EPSG:4326') && d.className.includes('font-mono'),
        );
        return box ? box.innerText : null;
      });
    observations.hemisphereLabels = await readout();
    // Fly to the southern/western stub ROI, then sample the cursor readout.
    await page.evaluate(() => {
      const btn = Array.from(document.querySelectorAll('main button')).find((b) => /Parcel A/.test(b.innerText));
      if (btn) btn.click();
    });
    await sleep(1600);
    await page.mouse.move(view.width * 0.55, view.height * 0.45);
    await sleep(300);
    observations.hemisphereLabelsAlt = await readout();
    // The ROI card prints the stored centroid; a southern/western ROI must show
    // S/W, not a bare negative number or the wrong hemisphere.
    // Draw a bounding box around the known southern/western ROI: two clicks.
    await page.evaluate(() => {
      const btn = Array.from(document.querySelectorAll('main button')).find((b) => /Bounding Box/.test(b.innerText));
      if (btn) btn.click();
    });
    await sleep(250);
    const canvasBox = await page.evaluate(() => {
      const c = document.querySelector('main canvas');
      const r = c.getBoundingClientRect();
      return { x: r.x, y: r.y, w: r.width, h: r.height };
    });
    await page.mouse.click(canvasBox.x + canvasBox.w * 0.3, canvasBox.y + canvasBox.h * 0.55);
    await sleep(200);
    await page.mouse.click(canvasBox.x + canvasBox.w * 0.45, canvasBox.y + canvasBox.h * 0.7);
    await sleep(400);
    observations.drawnRoiCentroid = await page.evaluate(() => {
      const mono = Array.from(document.querySelectorAll('main span'))
        .filter((el) => el.children.length === 0 && /°[NSEW]/.test(el.textContent || ''))
        .map((el) => el.textContent.trim());
      return mono.slice(0, 3);
    });
    await page.screenshot({ path: path.join(dir, 'map-drawn-roi-centroid.jpg') });
    observations.roiCentroidRow = await page.evaluate(() => {
      const btn = Array.from(document.querySelectorAll('main button')).find((b) => /Parcel A/.test(b.innerText));
      if (btn) btn.click();
      const mono = Array.from(document.querySelectorAll('main span, main div')).filter(
        (el) => el.children.length === 0 && /°[NSEW]/.test(el.textContent || ''),
      );
      return mono.map((el) => el.textContent.trim()).slice(0, 4);
    });
    await page.screenshot({ path: path.join(dir, 'map-hemisphere-south-west.jpg') });
    observations.badHemispherePairs = await page.evaluate(() => {
      const text = document.querySelector('main').innerText;
      // A southern/western coordinate pair rendered with N/E suffixes.
      return (text.match(/-\d+\.\d+°[NE]/g) || []).length + (text.match(/-\d+\.\d+,? -?\d+\.\d+/g) || []).length;
    });

    // 3) Acquire / knowledge / settings sections still mount.
    const sections = {};
    for (const view of ['acquire', 'knowledge', 'ops', 'settings', 'resources']) {
      await page.goto(base + `/#/${view}`);
      await page.waitForSelector('main');
      await sleep(350);
      sections[view] = await page.evaluate(() => (document.querySelector('main') || {}).innerText?.length ?? 0);
      await page.screenshot({ path: path.join(dir, `view-${view}.jpg`) });
    }
    observations.sectionChars = sections;
    observations.rollbackPosts = nonGet.filter((r) => r.p === '/models/rollback').map((r) => JSON.parse(r.body || '{}'));
    observations.errors = errors;
    fs.writeFileSync(path.join(dir, 'observations.json'), JSON.stringify(observations, null, 2));

    for (const [view, chars] of Object.entries(sections)) assert.ok(chars > 200, `${view} rendered ${chars} chars`);
    if (phase === 'after') {
      assert.ok(
        observations.versionRows.some((r) => r.includes('north')) && observations.versionRows.some((r) => r.includes('south')),
        'sub-region versions are not distinguished',
      );
      assert.equal(observations.badHemispherePairs, 0, 'a coordinate kept the wrong hemisphere or a raw negative sign');
      assert.equal(observations.rollbackPosts.length, 1, 'the Rollback button never posted to /models/rollback');
      assert.deepEqual(
        observations.rollbackPosts[0].key,
        ['sugarcane', 'karkheh', 'north'],
        `rollback sent ${JSON.stringify(observations.rollbackPosts[0].key)} instead of the full sub-region key`,
      );
      assert.ok(
        /°[NS]/.test(observations.hemisphereLabels || ''),
        `cursor readout has no hemisphere suffix: ${observations.hemisphereLabels}`,
      );
      assert.ok(
        (observations.drawnRoiCentroid || []).length > 0,
        'drawing a bbox never produced a centroid readout',
      );
      assert.ok(
        !/-\d+\.\d+°/.test(observations.hemisphereLabels || ''),
        `cursor readout prints a raw negative latitude: ${observations.hemisphereLabels}`,
      );
    }
  } finally {
    await browser.close();
  }
})();
