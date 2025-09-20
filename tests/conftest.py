# filename: tests/conftest.py
import asyncio
import json
import multiprocessing
import socket
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

try:
    import uvicorn
except ImportError:  # pragma: no cover - optional dependency
    uvicorn = None  # type: ignore[assignment]

from apps.mw.src.health import HEALTH_PAYLOAD

_HOST = "127.0.0.1"
_PORT = 8000


class _HealthHandler(BaseHTTPRequestHandler):
    """Fallback HTTP handler for smoke tests when uvicorn is unavailable."""

    def do_GET(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler API)
        if self.path == "/health":
            body = json.dumps(HEALTH_PAYLOAD).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        """Silence the default stdout logging."""
        return


def _run_with_uvicorn() -> None:
    assert uvicorn is not None  # for type checkers
    uvicorn.run("apps.mw.src.app:app", host=_HOST, port=_PORT, log_level="warning")


def _run_fallback_server() -> None:
    server = ThreadingHTTPServer((_HOST, _PORT), _HealthHandler)
    try:
        server.serve_forever()
    finally:
        server.server_close()


def _run_server() -> None:
    if uvicorn is not None:
        _run_with_uvicorn()
    else:
        _run_fallback_server()


def _wait_for_port(host: str, port: int, timeout: float = 10.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.connect((host, port))
            except OSError:
                time.sleep(0.1)
            else:
                return
    raise RuntimeError(f"Server on {host}:{port} did not start within {timeout} seconds")


@pytest.fixture(scope="session", autouse=True)
def _serve_app() -> Iterator[None]:
    """Run the application (or fallback server) once for all tests."""
    process = multiprocessing.Process(target=_run_server, daemon=True)
    process.start()
    try:
        _wait_for_port(_HOST, _PORT)
        yield
    finally:
        process.terminate()
        process.join(timeout=5)
        if process.is_alive():
            process.kill()
            process.join(timeout=5)


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "asyncio: mark test to run in an event loop")


def pytest_pyfunc_call(pyfuncitem: pytest.Function) -> bool | None:
    if asyncio.iscoroutinefunction(pyfuncitem.obj):
        loop = asyncio.new_event_loop()
        try:
            kwargs = {name: pyfuncitem.funcargs[name] for name in pyfuncitem._fixtureinfo.argnames}
            loop.run_until_complete(pyfuncitem.obj(**kwargs))
        finally:
            loop.close()
        return True
    return None
