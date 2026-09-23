const $ = selector => document.querySelector(selector);
const icons = {
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4 4"/>',
  desktop: '<rect x="3" y="4" width="18" height="13" rx="2"/><path d="M8 21h8m-4-4v4"/>',
  folder: '<path d="M3 7V5a1 1 0 0 1 1-1h5l2 3h9a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V7Z"/>',
  document: '<path d="M13 3H6a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V9Z"/><path d="M13 3v6h6M8 13h8m-8 4h6"/>',
  image: '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8" cy="8" r="1.5"/><path d="m3 17 5-5 4 4 4-6 5 7"/>',
  code: '<path d="m7 7-5 5 5 5m10-10 5 5-5 5M14 4l-4 16"/>',
  media: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="m10 8 6 4-6 4Z"/>',
  grid: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  settings: '<path d="M12 3 14 6l3-.3.3 3L21 11l-2 3 .3 3-3 .3L13 21l-3-2-3 .3-.3-3L3 13l2-3-.3-3 3-.3L11 3Z"/><circle cx="12" cy="12" r="3"/>',
  bolt: '<path d="m13 2-8 12h6l-1 8 9-13h-7Z"/>',
  spark: '<path d="m12 2 2.5 7.5L22 12l-7.5 2.5L12 22l-2.5-7.5L2 12l7.5-2.5Z"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10v.1"/>',
  arrow: '<path d="M7 17 17 7M7 7h10v10"/>',
};
function icon(name) { return `<svg viewBox="0 0 24 24" aria-hidden="true">${icons[name] || icons.document}</svg>`; }
document.querySelectorAll('[data-icon]').forEach(node => { node.innerHTML = icon(node.dataset.icon); });
function escape(value) { return String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }

const state = { settings: null, hits: [], filter: 'all', selected: null, phase: 'idle', count: 0, stats: {}, query: '', searchId: null, started: 0, message: '', detailSignature: '', workspace: false, resultNavigation: false };
let lastLayout = null;
function syncWindowLayout() {
  document.body.classList.toggle('compact', !state.workspace);
  document.body.classList.toggle('has-results', state.phase !== 'idle');
  const label = state.workspace ? 'Collapse to search bar' : 'Open workspace';
  $('#layout-toggle').title = label;
  $('#layout-toggle').setAttribute('aria-label', label);
  $('#layout-toggle').setAttribute('aria-expanded', String(state.workspace));
  $('#layout-toggle').innerHTML = state.workspace ? '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 3l6 6m0-6v6H3m18 12-6-6m0 6v-6h6"/></svg>' : icon('arrow');
  $('#search-button').innerHTML = `<span class="submit-label">${active() ? 'Search again' : 'Search'}</span><span class="submit-arrow" aria-hidden="true">↵</span>`;
  $('#search-button').setAttribute('aria-label', active() ? 'Search again' : 'Search');
  const layout = $('#settings-dialog').open ? 'settings' : state.workspace ? 'workspace' : state.phase === 'idle' ? 'bar' : 'results';
  if (layout !== lastLayout) {
    lastLayout = layout;
    window.jev.setLayout(layout).catch(error => notice(error.message));
  }
}
const resultRows = new Map();
let emptyResultsKey = '';
const active = () => ['scanning', 'thinking', 'starting'].includes(state.phase);
const visibleHits = () => state.hits.filter(hit => state.filter === 'all' || hit.kind === state.filter);
const number = value => Number(value || 0).toLocaleString();
const duration = seconds => seconds < 1 ? `${Math.round(seconds * 1000)} ms` : `${seconds.toFixed(1)} s`;
const size = bytes => bytes < 1024 ? `${bytes} bytes` : bytes < 1048576 ? `${(bytes / 1024).toFixed(1)} KB` : bytes < 1073741824 ? `${(bytes / 1048576).toFixed(1)} MB` : `${(bytes / 1073741824).toFixed(1)} GB`;
const typeName = kind => ({ folder: 'Folder', document: 'Document', image: 'Image', code: 'Code', media: 'Media', other: 'File' }[kind]);
let toastTimer;
function toast(message) { $('#toast').textContent = message; $('#toast').classList.remove('hidden'); clearTimeout(toastTimer); toastTimer = setTimeout(() => $('#toast').classList.add('hidden'), 4500); }
function notice(message) { $('#notice').textContent = message; $('#notice').classList.toggle('hidden', !message); }
function updateSettings(settings) {
  state.settings = settings;
  const name = settings.root.split('/').filter(Boolean).at(-1) || '/';
  $('#root-name').textContent = name;
  $('#root-name').title = settings.root;
  $('#compact-folder').title = `Search in ${settings.root} · click to change`;
  $('#mode-label').textContent = settings.hasKey ? 'Streaming · no saved index' : 'Local streaming · add a key';
}

async function startSearch(query = $('#query').value, mode = 'streaming') {
  if (!query.trim()) { $('#query').focus(); return; }
  $('#query').value = query; $('#clear-query').classList.remove('hidden');
  state.hits = []; state.selected = null; state.count = 0; state.query = query; state.phase = 'starting'; state.stats = {}; state.started = performance.now(); state.searchId = null; state.message = ''; state.detailSignature = '';
  state.mode = mode;
  state.resultNavigation = false;
  notice(mode === 'deep' ? 'Full search: a fresh pass through every eligible entry. This search has its own cost total and can take longer.' : ''); $('#welcome').classList.add('hidden'); $('#results-area').classList.remove('hidden');
  render();
  try { state.searchId = await window.jev.search(query, mode); }
  catch (error) { state.phase = 'error'; notice(error.message); render(); }
}

function render({ updateResults = true } = {}) {
  syncWindowLayout();
  const running = active(), stats = state.stats;
  const streaming = (stats.mode || state.mode) === 'streaming';
  const fast = (stats.mode || state.mode) === 'fast';
  $('#stop-button').classList.toggle('hidden', !running);
  const titles = { starting: 'Starting a fresh search', scanning: 'Looking through your files', thinking: 'Finding connections with JEV', complete: 'Search complete', partial: 'Partial results', stopped: 'Search stopped', error: 'Search needs attention' };
  $('#results-title').textContent = state.phase === 'complete' ? (streaming ? 'Streaming results' : fast ? 'Fast results' : 'Full search complete') : titles[state.phase] || 'Results';
  $('#widen-button').classList.toggle('hidden', running || !fast || !state.settings?.hasKey || !['complete', 'partial', 'stopped'].includes(state.phase));
  $('#coverage-summary').textContent = streaming ? `${number(stats.textFilesRead)} text files streamed · ${number(stats.documentsSampled)} documents sampled · ${number(stats.nameOnly)} names only` : `${fast ? 'Fast pass' : 'Full pass'} · ${stats.scanComplete ? 'Names checked across your search folder' : 'Checking names across your search folder'} · ${state.settings?.hasKey && state.settings?.readContents ? 'File contents sampled selectively' : 'Names and paths only'}`;
  const filtered = visibleHits();
  const unchecked = state.filter === 'all' && stats.unverifiedMatches != null ? stats.unverifiedMatches : filtered.filter(hit => hit.probability == null).length;
  $('#results-total').textContent = `${number(state.filter === 'all' ? state.count : filtered.length)} results${unchecked ? ` · ${number(unchecked)} not JEV-checked` : ''}${state.count > 500 ? ' · best 500 shown' : ''}`;
  $('#elapsed').textContent = duration(stats.elapsed || (performance.now() - state.started) / 1000);
  const cost = describeSearchCost(stats, state.phase);
  $('#search-cost-label').textContent = cost.label;
  $('#search-cost-value').textContent = cost.value;
  $('#search-cost').title = cost.detail;
  $('#search-cost').classList.toggle('incomplete', cost.incomplete);
  if (updateResults || !filtered.length) {
    if (!filtered.some(hit => hit.path === state.selected)) state.selected = filtered[0]?.path || null;
    renderResults(filtered, running);
    renderDetail();
  }
  let status = 'Ready when you are';
  if (state.phase === 'starting' || state.phase === 'scanning') status = `${number(stats.scanned)} entries discovered · reading the filesystem live`;
  else if (streaming && stats.scanned != null) status = `${number(stats.scanned)} entries · ${number(stats.textFilesRead)} text files streamed · ${number(stats.evaluated)} JEV checked`;
  else if (stats.scanned != null) status = `${number(stats.scanned)} names checked · ${number(stats.sampled)} files sampled · ${number(stats.evaluated)} JEV checked${stats.failed ? ` · ${number(stats.failed)} failed` : ''}`;
  $('#status-left').innerHTML = `${running ? '<span class="spinner"></span>' : '<span class="status-dot"></span>'}<span>${escape(status)}</span>`;
  $('#status-left').title = `${stats.excluded || 0} hidden, generated, or package folders excluded. ${stats.unreadable || 0} unreadable entries. ${stats.protected || 0} protected files excluded from JEV. ${stats.scanTime ? `Filesystem scan: ${duration(stats.scanTime)}.` : ''}`;
  $('#status-right').textContent = stats.requests ? `${number(stats.requests)} API requests${cost.incomplete ? ' · billing may be incomplete' : ''}` : '↑ ↓ to navigate · ↵ to open';
  const bar = $('#progress-bar');
  bar.classList.toggle('indeterminate', state.phase === 'starting' || state.phase === 'scanning');
  const total = (fast || streaming) ? (stats.selected || stats.candidateLimit || 128) : (stats.scanned || 0) - (stats.protected || 0);
  bar.style.width = state.phase === 'complete' ? '100%' : state.phase === 'idle' ? '0%' : `${total ? Math.min(100, 100 * ((stats.evaluated || 0) + (stats.failed || 0)) / total) : 0}%`;
}

function renderResults(hits, running) {
  const list = $('#results-list');
  if (!hits.length) {
    const key = `${running}|${state.filter}`;
    if (emptyResultsKey !== key || resultRows.size) {
      list.innerHTML = `<div class="empty-results"><span class="empty-symbol">${running ? '✳' : '⌕'}</span><strong>${running ? 'Following the clues…' : 'No matches here'}</strong>${running ? 'Results appear as soon as they’re found.' : state.filter !== 'all' ? 'Try Everything, or search for something else.' : 'Try a different description or include more files in Settings.'}</div>`;
      resultRows.clear(); emptyResultsKey = key;
    }
    return;
  }
  if (emptyResultsKey) { list.replaceChildren(); emptyResultsKey = ''; }
  const visible = new Set(hits.map(hit => hit.path));
  for (const [file, entry] of resultRows) {
    if (!visible.has(file)) { entry.node.remove(); resultRows.delete(file); }
  }
  let position = list.firstElementChild;
  for (let index = 0; index < hits.length; index++) {
    const hit = hits[index];
    const signature = JSON.stringify([hit.name, hit.relative, hit.kind, hit.probability, hit.matchSource]);
    let entry = resultRows.get(hit.path);
    if (!entry) {
      const node = document.createElement('button');
      node.className = 'result-row'; node.setAttribute('role', 'option');
      entry = { node, signature: null, selected: null };
      resultRows.set(hit.path, entry);
    }
    if (entry.signature !== signature) {
      entry.node.innerHTML = `<span class="file-icon ${hit.kind}">${icon(hit.kind)}</span><span class="result-text"><span class="result-name" title="${escape(hit.name)}">${escape(hit.name)}</span><span class="result-path" title="${escape(hit.relative)}">${escape(hit.relative)}</span></span>${hit.probability != null ? `<span class="score" title="JEV relevance probability">${icon('spark')}${Math.round(hit.probability * 100)}%</span>` : `<span class="score local" title="${hit.matchSource === 'content' ? 'Literal text match' : 'Filename word match'}; not evaluated by JEV"><span class="local-source">${hit.matchSource === 'content' ? 'TEXT' : 'NAME'}</span><span class="verification-label">Not JEV-checked</span></span>`}`;
      entry.signature = signature;
    }
    if (entry.node.dataset.index !== String(index)) entry.node.dataset.index = index;
    const selected = hit.path === state.selected;
    if (entry.selected !== selected) {
      entry.node.classList.toggle('selected', selected);
      entry.node.setAttribute('aria-selected', selected);
      entry.selected = selected;
    }
    if (entry.node !== position) list.insertBefore(entry.node, position);
    position = entry.node.nextElementSibling;
  }
}

function renderDetail() {
  const hit = state.hits.find(hit => hit.path === state.selected);
  if (!hit) { $('#detail').innerHTML = '<div class="detail-empty">Select a file to take a closer look.</div>'; state.detailSignature = ''; return; }
  const signature = JSON.stringify(hit);
  if (signature === state.detailSignature) return;
  state.detailSignature = signature;
  const date = hit.modified == null ? 'Not read yet' : new Date(hit.modified * 1000).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  $('#detail').innerHTML = `<div class="file-icon ${hit.kind}">${icon(hit.kind)}</div><h3>${escape(hit.name)}</h3><div class="detail-path">${escape(hit.relative)}</div><div class="detail-actions"><button data-action="open">Open ${icon('arrow')}</button><button data-action="reveal">Show in Finder</button></div><dl class="detail-meta"><dt>Type</dt><dd>${escape(typeName(hit.kind))}${hit.symlink ? ' · symbolic link' : ''}</dd><dt>Modified</dt><dd>${escape(date)}</dd>${hit.kind !== 'folder' ? `<dt>Size</dt><dd>${hit.size == null ? 'Not read yet' : size(hit.size)}</dd>` : ''}<dt>Match</dt><dd>${hit.probability != null ? `${Math.round(hit.probability * 100)}% JEV relevance${hit.localScore >= .45 ? (hit.matchSource === 'content' ? ' · text match' : ' · name match') : ''}` : hit.matchSource === 'content' ? 'Local text relevance · not JEV-checked' : 'Filename words · not JEV-checked'}</dd></dl><div class="evidence-heading">${icon('spark')} ${hit.excerpt ? (hit.probability == null ? 'MATCHING TEXT' : 'WHAT JEV READ') : 'SEARCH COVERAGE'}</div><p class="excerpt">${escape(hit.excerpt || (hit.probability == null && active() ? 'This is a local match. JEV has not evaluated this result.' : 'Only the name and path were available; no readable text excerpt was used.'))}</p><div class="coverage">${escape(hit.coverage)}${hit.placeholder ? ' · cloud file is not downloaded' : ''}</div><button class="copy-path" data-action="copy">Copy full path</button>`;
}

function selectResult(index, scroll = false) {
  const hit = visibleHits()[index];
  if (!hit) return;
  state.selected = hit.path;
  state.resultNavigation = true;
  for (const entry of resultRows.values()) {
    const selected = Number(entry.node.dataset.index) === index;
    if (entry.selected !== selected) { entry.node.classList.toggle('selected', selected); entry.node.setAttribute('aria-selected', selected); entry.selected = selected; }
    if (selected && scroll) entry.node.scrollIntoView({ block: 'nearest' });
  }
  renderDetail();
}
async function fileAction(action) {
  if (!state.selected) return;
  try { await window.jev.fileAction(action, state.selected); if (action === 'copy') toast('Full path copied.'); if (action === 'open' && !state.workspace) await window.jev.hideWindow(); }
  catch (error) { toast(error.message); }
}
function showSettings() {
  if (!state.settings) return;
  $('#api-key').value = '';
  $('#api-key').placeholder = state.settings.hasKey ? 'Key loaded · replace for this session' : 'sk-or-v1-…';
  $('#key-status').textContent = state.settings.hasKey ? '✓ Key loaded' : 'Not connected';
  $('#include-generated').checked = state.settings.includeGenerated;
  $('#read-contents').checked = state.settings.readContents;
  $('#concurrency').value = state.settings.concurrency;
  $('#settings-error').classList.add('hidden');
  if (!$('#settings-dialog').open) $('#settings-dialog').showModal();
  syncWindowLayout();
}

$('#layout-toggle').addEventListener('click', () => { state.workspace = !state.workspace; syncWindowLayout(); $('#query').focus(); });
$('#compact-settings').addEventListener('click', showSettings);
$('#close-window').addEventListener('click', () => window.jev.hideWindow());
$('#settings-dialog').addEventListener('close', syncWindowLayout);
$('#search-form').addEventListener('submit', event => { event.preventDefault(); startSearch(); });
$('#query').addEventListener('input', () => { state.resultNavigation = false; $('#clear-query').classList.toggle('hidden', !$('#query').value); if (!$('#query').value && state.phase !== 'idle') clearSearch(); });
async function clearSearch() {
  const running = active();
  state.searchId = 'cleared'; state.phase = 'idle'; state.hits = []; state.selected = null;
  state.resultNavigation = false; state.count = 0; state.stats = {};
  $('#query').value = ''; $('#clear-query').classList.add('hidden'); $('#welcome').classList.remove('hidden'); $('#results-area').classList.add('hidden');
  $('#search-button').innerHTML = 'Search <span>↵</span>'; $('#progress-bar').style.width = '0%'; $('#progress-bar').classList.remove('indeterminate'); $('#status-left').innerHTML = '<span class="status-dot"></span> Ready when you are'; $('#status-right').textContent = '⌘ K to search · ↑ ↓ to navigate'; notice(''); $('#query').focus();
  syncWindowLayout();
  if (running) await window.jev.cancel().catch(error => toast(error.message));
}
$('#clear-query').addEventListener('click', clearSearch);
$('#stop-button').addEventListener('click', () => window.jev.cancel().catch(error => toast(error.message)));
$('#widen-button').addEventListener('click', () => startSearch(state.query, 'deep'));
document.querySelectorAll('[data-query]').forEach(button => button.addEventListener('click', () => startSearch(button.dataset.query)));
document.querySelectorAll('[data-filter]').forEach(button => button.addEventListener('click', () => {
  state.filter = button.dataset.filter;
  document.querySelectorAll('[data-filter]').forEach(tab => { tab.classList.toggle('active', tab === button); tab.setAttribute('aria-selected', tab === button); });
  if (state.phase !== 'idle') render();
}));
$('#results-list').addEventListener('click', event => { const row = event.target.closest('[data-index]'); if (row) selectResult(Number(row.dataset.index)); });
$('#results-list').addEventListener('dblclick', event => { if (event.target.closest('[data-index]')) fileAction('open'); });
$('#detail').addEventListener('click', event => { const button = event.target.closest('[data-action]'); if (button) fileAction(button.dataset.action); });
$('#compact-folder').addEventListener('click', async () => {
  try { if (active()) await window.jev.cancel(); const prior = state.settings.root; updateSettings(await window.jev.chooseFolder()); if (state.settings.root !== prior) { await clearSearch(); toast('Folder changed. Your next search will scan it fresh.'); } }
  catch (error) { toast(error.message); }
});
$('#settings-close').addEventListener('click', () => $('#settings-dialog').close());
$('#settings-form').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    updateSettings(await window.jev.saveSettings({ apiKey: $('#api-key').value, includeGenerated: $('#include-generated').checked, readContents: $('#read-contents').checked, concurrency: Number($('#concurrency').value) }));
    $('#api-key').value = ''; $('#settings-dialog').close(); toast('Settings saved. They apply to your next search.');
  } catch (error) { $('#settings-error').textContent = error.message; $('#settings-error').classList.remove('hidden'); }
});
window.jev.onSearch(event => {
  if (event.id && state.searchId && event.id !== state.searchId) return;
  if (event.type === 'results') {
    const updateResults = Array.isArray(event.hits);
    state.searchId = event.id;
    if (updateResults) state.hits = event.hits;
    state.stats = event.stats; state.phase = event.phase; state.count = event.matchCount;
    if (event.message) notice(event.message);
    render({ updateResults });
  } else if (event.type === 'warning') notice(event.message);
  else if (event.type === 'error') { state.phase = 'error'; notice(event.message); render(); }
});
window.jev.onFocus(() => { state.resultNavigation = false; $('#query').focus(); $('#query').select(); });
window.jev.onSettings(showSettings);
document.addEventListener('keydown', event => {
  if ((event.metaKey || event.ctrlKey) && ['k', 'f'].includes(event.key.toLowerCase())) { event.preventDefault(); state.resultNavigation = false; $('#query').focus(); $('#query').select(); }
  if ($('#settings-dialog').open) return;
  if (event.key === 'Escape') {
    if (active()) { event.preventDefault(); window.jev.cancel().catch(error => toast(error.message)); }
    else if (!state.workspace) { event.preventDefault(); if (state.phase !== 'idle' || $('#query').value) clearSearch(); else window.jev.hideWindow(); }
  }
  if (['ArrowDown', 'ArrowUp'].includes(event.key) && state.hits.length) {
    event.preventDefault(); const hits = visibleHits(); const index = state.resultNavigation ? hits.findIndex(hit => hit.path === state.selected) : -1;
    selectResult(Math.max(0, Math.min(hits.length - 1, index + (event.key === 'ArrowDown' ? 1 : -1))), true);
  }
  if (event.key === 'Enter' && (document.activeElement !== $('#query') || state.resultNavigation) && !document.activeElement.closest('button') && state.selected) { event.preventDefault(); fileAction(event.metaKey ? 'reveal' : 'open'); }
});
setInterval(() => { if (active()) $('#elapsed').textContent = duration((performance.now() - state.started) / 1000); }, 100);
window.jev.settings().then(settings => { updateSettings(settings); $('#query').focus(); }).catch(error => notice(error.message));
syncWindowLayout();
