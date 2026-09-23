const { _electron: electron } = require('playwright');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const assert = require('node:assert/strict');
const project = path.resolve(__dirname, '..');

async function main() {
  const userData = fs.mkdtempSync(path.join(os.tmpdir(), 'jev-smoke-settings-'));
  const fixture = fs.mkdtempSync(path.join(os.tmpdir(), 'jev-ui-'));
  fs.writeFileSync(path.join(fixture, 'budget-plan.txt'), 'Planning next year’s spending and revenue.');
  fs.writeFileSync(path.join(fixture, 'holiday.jpg'), 'image placeholder');
  const args = process.env.JEV_PACKAGED ? [] : [project];
  if (process.env.JEV_KEY_FILE) args.push(`--import-key=${process.env.JEV_KEY_FILE}`);
  const instance = await electron.launch({ args, cwd: project, env: { ...process.env, JEV_USER_DATA_DIR: userData }, executablePath: process.env.JEV_PACKAGED || undefined });
  try {
    const page = await instance.firstWindow();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.waitForSelector('#query');
    const original = await page.evaluate(() => window.jev.settings());
    if (process.env.JEV_KEY_FILE) assert.equal(original.hasKey, true);
    assert.equal(await page.locator('#query').isVisible(), true);
    assert.equal(await page.locator('.sidebar').isVisible(), false);
    assert.equal(await page.locator('#welcome').isVisible(), false);
    assert.equal(await page.locator('#results-area').isVisible(), false);
    fs.mkdirSync(path.join(project, 'build/qa'), { recursive: true });
    await page.screenshot({ path: path.join(project, 'build/qa/welcome.png') });
    await instance.evaluate(({ dialog }, fixture) => { dialog.showOpenDialog = async () => ({ canceled: false, filePaths: [fixture] }); }, fixture);
    await page.locator('#compact-folder').click();
    await page.locator('#query').fill('budget');
    await page.locator('#query').press('Enter');
    await page.waitForFunction(() => document.querySelector('#results-title').textContent === 'Fast results');
    assert.equal(await page.locator('.result-row').count(), 1);
    assert.match(await page.locator('#detail').innerText(), /budget-plan\.txt/);
    if (process.env.JEV_KEY_FILE) assert.match(await page.locator('#detail').innerText(), /JEV relevance/);
    await page.locator('[data-action="copy"]').click();
    const copied = await instance.evaluate(({ clipboard }) => clipboard.readText());
    assert.equal(copied, path.join(fixture, 'budget-plan.txt'));
    await page.locator('[data-filter="image"]').click();
    assert.match(await page.locator('#results-list').innerText(), /No matches/);
    await page.locator('[data-filter="all"]').click();
    assert.equal(await page.locator('.result-row').count(), 1);
    // No stale inventory: adding and deleting files must be visible next search.
    fs.unlinkSync(path.join(fixture, 'budget-plan.txt'));
    fs.writeFileSync(path.join(fixture, 'budget-updated.txt'), 'New spending plan');
    await page.locator('#query').press('Enter');
    await page.waitForFunction(() => document.querySelector('#results-title').textContent === 'Fast results' && document.querySelector('.result-name')?.textContent === 'budget-updated.txt');
    await page.screenshot({ path: path.join(project, 'build/qa/results.png') });
    await page.locator('#compact-settings').click();
    await page.waitForFunction(() => innerHeight >= 600);
    assert.equal(await page.locator('#settings-dialog').isVisible(), true);
    await page.locator('#include-generated').check();
    await page.locator('.primary-button').click();
    assert.equal((await page.evaluate(() => window.jev.settings())).includeGenerated, true);
    await page.evaluate(settings => window.jev.saveSettings(settings), original);
    await instance.evaluate(({ dialog }, folder) => { dialog.showOpenDialog = async () => ({ canceled: false, filePaths: [folder] }); }, original.root);
    await page.locator('#compact-folder').click();
    assert.equal(errors.length, 0, errors.join('\n'));
    console.log('Electron smoke passed: startup, live search, preview, copy path, filters, fresh re-scan, settings.');
  } finally {
    await instance.close();
    fs.rmSync(userData, { recursive: true, force: true });
    fs.rmSync(fixture, { recursive: true, force: true });
  }
}
main().catch(error => { console.error(error); process.exit(1); });
