import asyncio
import io
import json
from types import SimpleNamespace

import pytest

from backend import server


@pytest.mark.asyncio
async def test_service_reuses_connection_pool_and_refreshes_credentials(monkeypatch):
    clients, calls = [], []
    class Client:
        def __init__(self, **kwargs):
            self.closed = False
            self.authorization = kwargs['headers']['Authorization']
            clients.append(self)
        async def aclose(self): self.closed = True
    class Search:
        def __init__(self, emit): pass
        def cancel(self): pass
        async def run(self, root, query, key, options, client):
            calls.append(client)
    requests = [dict(action='search', id=str(i), root='/fixture', query='needle', key=key)
                for i, key in enumerate(['test-a', 'test-a', 'test-b'])]
    requests.append(dict(action='shutdown'))
    data = ''.join(json.dumps(request) + '\n' for request in requests).encode()
    monkeypatch.setattr(server.sys, 'stdin', SimpleNamespace(buffer=io.BytesIO(data)))
    monkeypatch.setattr(server, 'send', lambda event: None)
    monkeypatch.setattr(server, 'Search', Search)
    monkeypatch.setattr(server.httpx, 'AsyncClient', Client)
    await server.main()
    assert len(clients) == 2 and all(c.closed for c in clients)
    assert calls[0] is calls[1] and calls[2] is not calls[0]
    assert calls[2].authorization == 'Bearer test-b'
