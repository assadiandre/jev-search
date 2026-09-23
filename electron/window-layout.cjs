// Native window sizing is kept separate so the compact UI can be tested without
// starting the search worker or accessing the user's Keychain.
function createWindowLayout(window, screen) {
  let previous = null;
  return function applyLayout(layout) {
    if (!['bar', 'results', 'workspace', 'settings'].includes(layout)) throw new Error('Unknown window layout.');
    if (layout === previous) return;
    const current = window.getBounds();
    const area = screen.getDisplayMatching(current).workArea;
    const workspace = layout === 'workspace';
    const width = Math.min(workspace ? 1220 : 760, area.width - 32);
    const height = Math.min({ bar: 112, results: 580, workspace: 820, settings: 680 }[layout], area.height - 32);
    const recenter = previous === null || workspace || previous === 'workspace';
    const x = recenter ? area.x + (area.width - width) / 2 : current.x;
    const y = recenter ? area.y + (workspace ? (area.height - height) / 2 : area.height * .2) : current.y;
    window.setMinimumSize(workspace ? Math.min(940, width) : Math.min(600, width), workspace ? Math.min(650, height) : 112);
    window.setResizable(workspace);
    if (process.platform === 'darwin') window.setWindowButtonVisibility(workspace);
    window.setBounds({
      x: Math.round(Math.max(area.x + 16, Math.min(x, area.x + area.width - width - 16))),
      y: Math.round(Math.max(area.y + 16, Math.min(y, area.y + area.height - height - 16))),
      width, height,
    });
    previous = layout;
  };
}
module.exports = { createWindowLayout };
