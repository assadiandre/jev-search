const { contextBridge, ipcRenderer } = require('electron');
const subscribe = (channel, callback) => {
  const handler = (_, value) => callback(value);
  ipcRenderer.on(channel, handler);
  return () => ipcRenderer.removeListener(channel, handler);
};
contextBridge.exposeInMainWorld('jev', {
  settings: () => ipcRenderer.invoke('settings:get'),
  setLayout: layout => ipcRenderer.invoke('window:layout', layout),
  hideWindow: () => ipcRenderer.invoke('window:hide'),
  saveSettings: value => ipcRenderer.invoke('settings:save', value),
  chooseFolder: () => ipcRenderer.invoke('folder:choose'),
  search: (query, mode = 'fast') => ipcRenderer.invoke('search:start', query, mode),
  cancel: () => ipcRenderer.invoke('search:cancel'),
  fileAction: (action, file) => ipcRenderer.invoke('file:action', action, file),
  onSearch: callback => subscribe('search-event', callback),
  onFocus: callback => subscribe('focus-search', callback),
  onSettings: callback => subscribe('show-settings', callback),
});
