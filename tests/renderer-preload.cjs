const { contextBridge } = require('electron');
let onEvent;
let lastSearch;
let lastLayout, hidden = false, fileAction;
contextBridge.exposeInMainWorld('jev', {
  settings: async () => ({ root: '/demo/Desktop', hasKey: true, includeGenerated: false, readContents: true, concurrency: 12 }),
  setLayout: async layout => { lastLayout = layout; }, hideWindow: async () => { hidden = true; },
  fileAction: async (action, file) => { fileAction = { action, file }; },
  onSearch: callback => { onEvent = callback; },
  onFocus: () => {}, onSettings: () => {}, search: async (query, mode) => { lastSearch = { query, mode }; return 'fixture'; }, cancel: async () => {},
});
contextBridge.exposeInMainWorld('testSearch', { emit: event => onEvent(event), lastSearch: () => lastSearch, lastLayout: () => lastLayout, hidden: () => hidden, lastFileAction: () => fileAction });
