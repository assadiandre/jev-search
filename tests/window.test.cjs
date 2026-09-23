// Exercise real native resizing + production preload without Keychain or APIs.
const { app, BrowserWindow, ipcMain, screen } = require('electron');
const { createWindowLayout } = require('../electron/window-layout.cjs');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const assert = require('node:assert/strict');
app.setPath('userData', fs.mkdtempSync(path.join(os.tmpdir(), 'jev-window-test-')));
app.whenReady().then(async () => {
  const window = new BrowserWindow({ show: false, width: 760, height: 112, titleBarStyle: 'hiddenInset', backgroundColor: '#faf9f6', webPreferences: { preload: path.resolve(__dirname, '../electron/preload.cjs'), contextIsolation: true, sandbox: true, backgroundThrottling: false } });
  const applyLayout = createWindowLayout(window, screen);
  const layouts = [];
  let searches = 0;
  ipcMain.handle('window:layout', (_, layout) => { applyLayout(layout); layouts.push(layout); });
  ipcMain.handle('window:hide', () => {});
  ipcMain.handle('settings:get', () => ({ root: '/demo/Desktop', hasKey: true, includeGenerated: false, readContents: true, concurrency: 12 }));
  ipcMain.handle('search:start', () => { searches++; return 'preview'; });
  ipcMain.handle('search:cancel', () => {});
  const evaluate = code => window.webContents.executeJavaScript(code);
  const settle = () => new Promise(resolve => setTimeout(resolve, 80));
  const waitForHeight = async height => {
    const deadline = Date.now() + 3000;
    while (window.getBounds().height !== height && Date.now() < deadline) await settle();
    assert.equal(window.getBounds().height, height);
  };
  const screenshot = async name => {
    if (!process.env.JEV_UI_SCREENSHOTS) return;
    fs.mkdirSync(path.resolve(__dirname, '../build/qa'), { recursive: true });
    fs.writeFileSync(path.resolve(__dirname, '../build/qa/' + name + '.png'), (await window.webContents.capturePage()).toPNG());
  };
  try {
    await window.loadFile(path.resolve(__dirname, '../ui/index.html'));
    await settle();
    assert.equal(window.getBounds().height, 112);
    assert.equal(searches, 0);
    assert.equal(await evaluate('document.querySelector(".sidebar")'), null);
    assert.equal(await evaluate('document.querySelector("#query").getBoundingClientRect().bottom < innerHeight'), true);
    await screenshot('modern-search-bar');
    const y = window.getBounds().y;
    await evaluate('startSearch("rental agreement")');
    await settle();
    assert.equal(layouts.at(-1), 'results');
    assert.equal(window.getBounds().height, 580);
    assert.equal(window.getBounds().y, y);
    window.webContents.send('search-event', { id: 'preview', type: 'results', phase: 'complete', matchCount: 3, stats: { mode: 'fast', scanned: 21513, sampled: 114, evaluated: 128, selected: 128, scanComplete: true, cost: .0012, costReports: 4, requests: 4, elapsed: 1.1, unverifiedMatches: 1 }, hits: [
      { path: '/demo/scan_0042.pdf', relative: 'Documents / Archive / scan_0042.pdf', name: 'scan_0042.pdf', kind: 'document', size: 94211, modified: 1790000000, probability: .97, rank: .97, localScore: 0, matchSource: 'semantic', excerpt: 'Residential lease agreement. Terms of the tenancy, monthly rent, and the security deposit.', coverage: 'PDF text · 2 of 8 pages sampled' },
      { path: '/demo/rental-agreement.docx', relative: 'Home / rental-agreement.docx', name: 'rental-agreement.docx', kind: 'document', size: 43322, modified: 1790000000, probability: .92, rank: .92, localScore: .91, matchSource: 'name', excerpt: 'Rental agreement for the apartment.', coverage: 'Office text · bounded excerpt' },
      { path: '/demo/lease-notes.txt', relative: 'Home / lease-notes.txt', name: 'lease-notes.txt', kind: 'document', size: null, modified: null, probability: null, rank: .86, localScore: .86, matchSource: 'content', excerpt: 'Notes for the rental agreement and next renewal.', coverage: 'Text excerpt' },
    ] });
    await settle();
    assert.equal(await evaluate('document.querySelector("#search-cost-value").textContent'), '$0.0012');
    assert.equal(await evaluate('document.querySelector("#widen-button").getBoundingClientRect().bottom < innerHeight'), true);
    await screenshot('modern-compact-results');
    await evaluate('showSettings()'); await settle();
    assert.equal(layouts.at(-1), 'settings');
    assert.equal(window.getBounds().height, 680);
    await screenshot('modern-settings');
    await evaluate('document.querySelector("#settings-dialog").close()'); await waitForHeight(580);
    assert.equal(window.getBounds().height, 580);
    await evaluate('document.querySelector("#layout-toggle").click()'); await settle();
    assert.equal(layouts.at(-1), 'workspace');
    assert.ok(window.getBounds().width >= 940);
    await screenshot('modern-workspace-results');
    await evaluate('clearSearch()'); await settle();
    assert.equal(layouts.at(-1), 'workspace');
    await screenshot('modern-workspace-welcome');
    await evaluate('document.querySelector("#layout-toggle").click()'); await settle();
    assert.equal(window.getBounds().height, 112);
    assert.equal(searches, 1, 'Layout changes triggered additional searches');
    assert.throws(() => applyLayout('invalid'), /Unknown/);
    console.log('Native UI passed: 112px bar, downward expansion, production IPC, results and cost, settings resize and restore, workspace, collapse, no extra searches.');
  } catch(error) { console.error(error); process.exitCode = 1; }
  window.destroy(); app.exit(process.exitCode || 0);
});
