"""Regressions for irrelevant local matches surviving semantic rejection."""
import json
from pathlib import Path

import httpx
import pytest

from backend.core import Matcher, Options, Record, Search
from backend.fast import Candidate, RetrievalMatcher, select_candidates


def record(relative):
    return Record('/fixture/' + relative, relative, Path(relative).name, 'document', None, None)


async def ignore(event):
    pass


@pytest.mark.parametrize('query,relative,text,visible', [
    ('cat', 'vacation.jpg', '', False),
    ('cat', 'certificate.pdf', '', False),
    ('cat', 'cat.jpg', '', True),
    ('cat', 'cat_care.txt', '', True),
    ('annual budget', 'annualBudgetDraft2024.txt', '', True),
    ('rental agreement', 'rental_agreement_copy.txt', '', True),
    ('rental agreement', 'agreement.txt', '', False),
    ('tax', 'tax/readme.txt', '', False),
    ('my resume', 'old/CV.pdf', '', False),
    ('resume', 'Résumé_2024.pdf', '', True),
    ('rental agreement', 'opaque.txt', 'A rental agreement for the apartment.', True),
    ('rental agreement', 'opaque.txt', 'A lease agreement for the apartment.', False),
    ('rental agreement', 'opaque.txt', 'Car rental prices. An unrelated business agreement.', False),
])
def test_local_results_require_direct_filename_words_or_literal_text(query, relative, text, visible):
    search = Search(ignore); search.matcher = RetrievalMatcher(query)
    file = record(relative)
    search.add_hit(file, text=text)
    assert (file.path in search.hits) == visible


def test_partial_names_parent_context_and_aliases_still_reach_candidates():
    for query, relative in [('rental agreement', 'agreement.txt'), ('tax', 'tax/readme.txt'), ('resume', 'CV.pdf')]:
        search = Search(ignore); search.matcher = RetrievalMatcher(query)
        file = record(relative)
        candidate = Candidate(file, search.matcher.score(file))
        assert candidate.name_score >= .45
        assert select_candidates([candidate], 1)[0][0] is candidate
        search.add_hit(file)
        assert not search.hits
        search.add_hit(file, .9)
        assert search.hits[file.path]['probability'] == .9


@pytest.mark.parametrize('query,relative,text', [
    ('cat', 'cat_care.txt', ''),
    ('cat', 'cat.txt', ''),
    ('rental agreement', 'opaque.txt', 'A rental agreement for the apartment.'),
])
def test_jev_rejection_removes_existing_local_hit_and_blocks_late_updates(query, relative, text):
    search = Search(ignore); search.matcher = RetrievalMatcher(query)
    file = record(relative)
    search.add_hit(file, text=text)
    assert file.path in search.hits
    search.add_hit(file, .03, text)
    assert file.path not in search.hits
    search.add_hit(file, text=text)
    assert file.path not in search.hits


@pytest.mark.asyncio
async def test_jev_rank_is_not_inflated_and_checked_matches_precede_unchecked():
    events = []
    async def emit(event): events.append(event)
    search = Search(emit); search.matcher = Matcher('budget')
    strong_name, high_jev, unchecked = record('budget_draft.txt'), record('opaque.txt'), record('budget.txt')
    search.add_hit(strong_name, .65, 'Original evidence')
    search.add_hit(high_jev, .9)
    search.add_hit(unchecked)
    search.add_hit(strong_name, text='Late local evidence')
    await search.update('complete', True)
    assert [h['path'] for h in events[-1]['hits']] == [high_jev.path, strong_name.path, unchecked.path]
    assert search.hits[strong_name.path]['rank'] == .65
    assert search.hits[strong_name.path]['excerpt'] == 'Original evidence'
    assert events[-1]['stats']['verifiedMatches'] == 2
    assert events[-1]['stats']['unverifiedMatches'] == 1
    search.add_hit(strong_name, .01)
    await search.update('complete', True)
    assert strong_name.path not in {h['path'] for h in events[-1]['hits']}
    assert events[-1]['stats']['verifiedMatches'] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['fast', 'deep'])
async def test_both_search_modes_remove_false_positive_local_results(tmp_path, mode):
    (tmp_path / 'rental_agreement_notes.txt').write_text('A rental agreement mentioned in unrelated fiction.')
    (tmp_path / 'opaque.txt').write_text('A residential lease contract with the landlord.')
    events = []
    async def emit(event): events.append(event)
    def handler(request):
        data = json.loads(request.content)
        return httpx.Response(200, json={
            'answers': {r['id']: {'noul': .95 if r['name'] == 'opaque.txt' else .03} for r in data['state']['records']},
            'usage': {'cost': .001},
        })
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await Search(emit).run(tmp_path, 'rental agreement', 'test-key', Options(mode=mode), client)
    assert events[-1]['phase'] == 'complete'
    assert [h['name'] for h in events[-1]['hits']] == ['opaque.txt']
    assert events[-1]['stats']['evaluated'] == 2
    assert events[-1]['stats']['verifiedMatches'] == 1
    assert events[-1]['stats']['unverifiedMatches'] == 0
    assert events[-1]['stats']['cost'] == .001
    assert any(any(h['name'] == 'rental_agreement_notes.txt' for h in e.get('hits', [])) for e in events[:-1])


@pytest.mark.asyncio
async def test_configured_threshold_and_new_query_do_not_reuse_old_decisions(tmp_path):
    (tmp_path / 'budget.txt').write_text('Budget')
    events = []
    async def emit(event): events.append(event)
    def handler(request):
        data = json.loads(request.content)
        return httpx.Response(200, json={'answers': {k: {'noul': .7} for k in data['questions']}, 'usage': {'cost': 0}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await Search(emit).run(tmp_path, 'budget', 'test-key', Options(threshold=.8), client)
        assert not events[-1]['hits']
        await Search(emit).run(tmp_path, 'budget', 'test-key', Options(), client)
        assert events[-1]['hits'][0]['probability'] == .7
