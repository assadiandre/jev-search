const { app, BrowserWindow, ipcMain, dialog, shell, Menu, globalShortcut, clipboard, screen, Tray, nativeImage } = require('electron');
const { createMenuBar } = require('./menu-bar.cjs');
const { createWindowLayout } = require('./window-layout.cjs');
const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const readline = require('node:readline');
const crypto = require('node:crypto');

app.setName('JEV SEARCH Streaming');
app.setPath('userData', process.env.JEV_USER_DATA_DIR ? path.resolve(process.env.JEV_USER_DATA_DIR) : path.join(app.getPath('appData'), 'JEV SEARCH Streaming'));
let window, worker, settings, key = '', activeId = '', quitting = false;
let applyWindowLayout, tray;
let nativeDialogOpen = false;
let allowedPaths = new Set();
let readyResolve, readyReject;
const workerReady = new Promise((resolve, reject) => { readyResolve = resolve; readyReject = reject; });
workerReady.catch(() => {});
const dataDir = app.getPath('userData');
const configPath = path.join(dataDir, 'settings.json');


function saveKey(value) { key = value; }

function publicSettings() { return { ...settings, hasKey: Boolean(key), model: '~typesafe/jev-latest', version: app.getVersion() }; }
function persistSettings() {
  fs.mkdirSync(dataDir, { recursive: true, mode: 0o700 });
  fs.writeFileSync(configPath, JSON.stringify(settings, null, 2), { mode: 0o600 });
}
function send(message) {
  if (!worker?.stdin.writable) throw new Error('The Python search service is unavailable. Restart the app.');
  worker.stdin.write(JSON.stringify(message) + '\n');
}
function focusSearch() {
  if (!window) createWindow();
  window.show(); window.focus();
  window.webContents.send('focus-search');
}
function createWindow() {
  window = new BrowserWindow({
    width: 760, height: 112, minWidth: 600, minHeight: 112,
    title: 'JEV SEARCH Streaming', titleBarStyle: 'hiddenInset', trafficLightPosition: { x: 22, y: 23 },
    backgroundColor: '#faf9f6', show: false,
    webPreferences: { preload: path.join(__dirname, 'preload.cjs'), contextIsolation: true, nodeIntegration: false, sandbox: true, spellcheck: false },
  });
  applyWindowLayout = createWindowLayout(window, screen);
  applyWindowLayout('bar');
  window.loadFile(path.join(__dirname, '../ui/index.html'));
  window.once('ready-to-show', () => window.show());
  let blurTimer;
  window.on('blur', () => {
    clearTimeout(blurTimer);
    // Let menu-bar clicks finish toggling visibility before dismissing.
    blurTimer = setTimeout(() => {
      if (window && !window.isDestroyed() && !window.isFocused() && !nativeDialogOpen) window.hide();
    }, 120);
  });
  window.on('focus', () => clearTimeout(blurTimer));
  window.on('closed', () => clearTimeout(blurTimer));
  window.on('close', event => { if (!quitting) { event.preventDefault(); window.hide(); } });
  window.on('closed', () => { window = null; });
  window.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  window.webContents.on('will-navigate', event => event.preventDefault());
  window.webContents.session.setPermissionRequestHandler((webContents, permission, callback) => callback(false));
}

app.whenReady().then(async () => {
  settings = { root: path.join(app.getPath('home'), 'Desktop'), includeGenerated: false, readContents: true, concurrency: 4 };
  try { settings = { ...settings, ...JSON.parse(fs.readFileSync(configPath, 'utf8')) }; } catch {}
  // Use the existing user-provided key file in memory; no Keychain access.
  try {
    if (process.env.JEV_DISABLE_KEY_LOAD !== '1') key = process.env.OPENROUTER_API_KEY || fs.readFileSync(process.env.JEV_KEY_FILE || path.join(app.getPath('desktop'), 'jev.txt'), 'utf8').trim();
  } catch {}
  const importArgument = process.argv.find(arg => arg.startsWith('--import-key='));
  if (importArgument) saveKey(fs.readFileSync(importArgument.slice('--import-key='.length), 'utf8').trim());

  const project = path.resolve(__dirname, '..');
  const binary = app.isPackaged ? path.join(process.resourcesPath, 'python', 'jev-core', 'jev-core') : path.join(project, '.venv', 'bin', 'python');
  const args = app.isPackaged ? [] : ['-u', path.join(project, 'backend', 'server.py')];
  worker = spawn(binary, args, { detached: true, stdio: ['pipe', 'pipe', 'pipe'], env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1', PYTHONUNBUFFERED: '1' } });
  const lines = readline.createInterface({ input: worker.stdout });
  lines.on('line', line => {
    try {
      const event = JSON.parse(line);
      if (event.type === 'ready') { readyResolve(event); return; }
      if (event.id && event.id !== activeId) return;
      if (event.type === 'results' && Array.isArray(event.hits)) allowedPaths = new Set(event.hits.map(hit => hit.path));
      window?.webContents.send('search-event', event);
    } catch { /* Invalid worker output is not displayed as HTML or logged with contents. */ }
  });
  worker.stderr.on('data', () => {});
  worker.on('error', error => {
    readyReject(error);
    window?.webContents.send('search-event', { type: 'error', message: 'Could not start the Python search core. Rebuild or restart the app.' });
  });
  worker.on('exit', () => {
    if (!quitting) {
      readyReject(new Error('The Python search service stopped.'));
      window?.webContents.send('search-event', { type: 'error', message: 'The Python search core stopped. Restart the app to continue.' });
    }
  });

  ipcMain.handle('settings:get', () => publicSettings());
  ipcMain.handle('window:layout', (_, layout) => applyWindowLayout?.(layout));
  ipcMain.handle('window:hide', () => window?.hide());
  ipcMain.handle('settings:save', async (_, value) => {
    if (typeof value.apiKey === 'string' && value.apiKey.trim()) saveKey(value.apiKey.trim());
    settings.includeGenerated = Boolean(value.includeGenerated);
    settings.readContents = Boolean(value.readContents);
    settings.concurrency = Math.max(1, Math.min(4, Number(value.concurrency) || 4));
    persistSettings();
    return publicSettings();
  });
  ipcMain.handle('folder:choose', async () => {
    nativeDialogOpen = true;
    try {
      const result = await dialog.showOpenDialog(window, { title: 'Choose a folder to search live', defaultPath: settings.root, properties: ['openDirectory'] });
      if (!result.canceled) { settings.root = result.filePaths[0]; persistSettings(); }
      return publicSettings();
    } finally {
      nativeDialogOpen = false;
      focusSearch();
    }
  });
  ipcMain.handle('search:start', async (_, query, mode = 'streaming') => {
    if (typeof query !== 'string' || !query.trim()) throw new Error('Enter a search query.');
    await Promise.race([workerReady, new Promise((_, reject) => { const timer = setTimeout(() => reject(new Error('Python is taking too long to start. Restart the app.')), 15000); timer.unref(); })]);
    activeId = crypto.randomUUID();
    allowedPaths.clear();
    send({ action: 'search', id: activeId, root: settings.root, query: query.trim().slice(0, 2000), key, options: { ...settings, mode: 'streaming' } });
    return activeId;
  });
  ipcMain.handle('search:cancel', () => send({ action: 'cancel' }));
  ipcMain.handle('file:action', async (_, action, file) => {
    if (typeof file !== 'string' || !allowedPaths.has(file)) throw new Error('Select a current search result first.');
    if (!fs.existsSync(file)) throw new Error('This file has moved or was deleted. Search again to refresh.');
    if (action === 'open') { const error = await shell.openPath(file); if (error) throw new Error(error); }
    else if (action === 'reveal') shell.showItemInFolder(file);
    else if (action === 'copy') clipboard.writeText(file);
    else throw new Error('Unknown file action.');
  });

  Menu.setApplicationMenu(Menu.buildFromTemplate([
    { label: 'JEV SEARCH Streaming', submenu: [{ role: 'about' }, { type: 'separator' }, { label: 'Settings…', accelerator: 'CmdOrCtrl+,', click: () => window?.webContents.send('show-settings') }, { type: 'separator' }, { role: 'hide' }, { role: 'hideOthers' }, { type: 'separator' }, { role: 'quit' }] },
    { label: 'File', submenu: [{ label: 'New Search', accelerator: 'CmdOrCtrl+K', click: focusSearch }, { role: 'close' }] },
    { label: 'Edit', submenu: [{ role: 'undo' }, { role: 'redo' }, { type: 'separator' }, { role: 'cut' }, { role: 'copy' }, { role: 'paste' }, { role: 'selectAll' }] },
    { label: 'View', submenu: [{ role: 'resetZoom' }, { role: 'zoomIn' }, { role: 'zoomOut' }, { type: 'separator' }, { role: 'togglefullscreen' }] },
    { label: 'Window', submenu: [{ role: 'minimize' }, { role: 'zoom' }, { role: 'front' }] },
  ]));
  globalShortcut.register('CommandOrControl+Alt+Space', focusSearch);
  createWindow();
  tray = createMenuBar({ Tray, Menu, nativeImage, app, getWindow: () => window, focusSearch });
  if (process.platform === 'darwin') app.dock.hide();
});
app.on('activate', focusSearch);
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });
app.on('before-quit', () => { quitting = true; tray?.destroy(); globalShortcut.unregisterAll(); if (worker) { try { process.kill(-worker.pid, 'SIGTERM'); } catch { worker.kill('SIGTERM'); } worker = null; } });
