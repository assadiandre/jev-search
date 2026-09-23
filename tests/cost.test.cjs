const { test } = require('node:test');
const assert = require('node:assert/strict');
const { describeSearchCost: cost } = require('../ui/cost.js');

test('live amount becomes a persistent final total', () => {
  assert.equal(cost({ cost: .303542778, costReports: 684 }, 'thinking').label, 'Cost so far');
  assert.equal(cost({ cost: .303542778, costReports: 684 }, 'complete').label, 'Search cost');
  assert.equal(cost({ cost: .303542778, costReports: 684 }, 'complete').value, '$0.3035');
});
test('a positive sub-cent amount is never displayed as zero', () => {
  assert.equal(cost({ cost: .000001, costReports: 1 }, 'complete').value, '<$0.0001');
});
test('absent billing data is visibly unavailable', () => {
  const display = cost({ cost: 0, costUnreported: 1 }, 'complete');
  assert.equal(display.value, '—');
  assert.equal(display.label, 'Cost unavailable');
});
test('partial and cancelled costs retain the reported sum', () => {
  for (const phase of ['stopped', 'partial', 'error']) {
    const display = cost({ cost: .05, costReports: 2 }, phase);
    assert.equal(display.value, '$0.0500');
    assert.equal(display.label, 'Reported cost');
    assert.match(display.detail, /in-flight/);
  }
  assert.equal(cost({ cost: .05, costReports: 2, costUnreported: 1 }, 'complete').label, 'Reported cost');
});
test('a new search resets the total and free local searches are explained', () => {
  assert.equal(cost({}, 'starting').value, '$0.0000');
  assert.match(cost({ cost: 0, requests: 0 }, 'complete').detail, /free/);
});
