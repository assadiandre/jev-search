"""Private JSON-lines IPC over Electron's child-process pipes. No HTTP server."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import httpx

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.core import Options, Search


def send(message: dict) -> None:
    sys.stdout.write(json.dumps(message, ensure_ascii=True, allow_nan=False) + "\n")
    sys.stdout.flush()


async def main() -> None:
    active: asyncio.Task | None = None
    search: Search | None = None
    client: httpx.AsyncClient | None = None
    client_key = ""
    send({"type": "ready", "python": sys.version.split()[0]})
    while True:
        line = await asyncio.to_thread(sys.stdin.buffer.readline)
        if not line:
            break
        try:
            request = json.loads(line)
            action = request.get("action")
            if action in {"search", "cancel", "shutdown"} and active is not None:
                search.cancel(); active.cancel()
                try:
                    await active
                except asyncio.CancelledError:
                    pass
                active = None
            if action == "shutdown":
                break
            if action == "search":
                identifier = str(request["id"])
                query = str(request.get("query", "")).strip()[:2000]
                if not query:
                    continue
                root = Path(request["root"]).expanduser().absolute()
                key = str(request.get("key", ""))
                if key != client_key or client is None:
                    if client is not None:
                        await client.aclose()
                    client_key = key
                    client = httpx.AsyncClient(headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "X-Title": "JEV SEARCH"},
                                              timeout=httpx.Timeout(25, connect=8), limits=httpx.Limits(max_connections=24, max_keepalive_connections=24, keepalive_expiry=60))

                async def emit(message: dict, search_id: str = identifier) -> None:
                    send({**message, "id": search_id})

                search = Search(emit)
                active = asyncio.create_task(search.run(root, query, key, Options.from_dict(request.get("options", {})), client))
        except Exception as error:
            send({"type": "error", "message": str(error)})
    if active is not None:
        search.cancel(); active.cancel()
        try:
            await active
        except asyncio.CancelledError:
            pass
    if client is not None:
        await client.aclose()


if __name__ == "__main__":
    if '--stream-worker' in sys.argv:
        from backend.stream_worker import main as stream_main
        asyncio.run(stream_main())
    else:
        asyncio.run(main())
