const path = require('node:path');

function createMenuBar({ Tray, Menu, nativeImage, app, getWindow, focusSearch }) {
  const icon = nativeImage.createFromPath(path.join(__dirname, 'assets/searchTemplate.png'));
  icon.setTemplateImage(true);
  const tray = new Tray(icon);
  tray.setToolTip('JEV Streaming');
  tray.on('click', () => {
    const window = getWindow();
    if (window?.isVisible()) window.hide();
    else focusSearch();
  });
  const menu = Menu.buildFromTemplate([
    { label: 'Search…', click: focusSearch },
    { label: 'Settings…', click: () => { focusSearch(); getWindow()?.webContents.send('show-settings'); } },
    { type: 'separator' },
    { label: 'Quit JEV Streaming', click: () => app.quit() },
  ]);
  tray.on('right-click', () => tray.popUpContextMenu(menu));
  return tray;
}
module.exports = { createMenuBar };
