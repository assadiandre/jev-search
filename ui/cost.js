// Format provider-reported USD totals without implying unreported usage is free.
function describeSearchCost(stats = {}, phase = 'starting') {
  const raw = Number(stats.cost ?? 0);
  const amount = Number.isFinite(raw) && raw >= 0 ? raw : 0;
  const running = ['starting', 'scanning', 'thinking'].includes(phase);
  const incomplete = Boolean(stats.costUnreported || stats.billingIncomplete) || ['stopped', 'partial', 'error'].includes(phase);
  const unavailable = Boolean(stats.costUnreported) && !stats.costReports;
  const formatted = amount > 0 && amount < 0.0001 ? '<$0.0001' : `$${amount.toFixed(4)}`;
  let detail = 'Sum of costs reported by OpenRouter for this search, in US dollars. Updates as API responses arrive.';
  if (incomplete) detail += ' This is a partial reported total; unreported or in-flight requests may still incur charges.';
  else if (phase === 'complete' && !stats.requests) detail = 'No paid API requests were made. Filename search is free.';
  return {
    label: unavailable ? 'Cost unavailable' : incomplete ? 'Reported cost' : running ? 'Cost so far' : 'Search cost',
    value: unavailable ? '—' : formatted,
    detail,
    incomplete,
  };
}
if (typeof module !== 'undefined') module.exports = { describeSearchCost };
