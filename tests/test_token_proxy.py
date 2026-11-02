"""src/token_proxy.py: подстановка id модели по алиасу и пересылка запроса без сети."""
from __future__ import annotations

import importlib.util
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

import pytest

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture
def proxy(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location("ai4science_token_proxy", REPO / "src" / "token_proxy.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "BUDGET_FILE", tmp_path / "budget.json")
    return mod


def _body(**kw) -> bytes:
    return json.dumps(kw, ensure_ascii=False).encode("utf-8")


@pytest.mark.parametrize("model, expected", [
    ("ai-pro", "ai-pro"),
    ("local-agent", "samcs-gpu/local-agent"),
    ("some-custom-model", "some-custom-model"),
])
def test_rewrite_model_aliases(proxy, model, expected):
    out = json.loads(proxy.rewrite_model(_body(model=model, messages=[{"role": "user", "content": "привет"}])))
    assert out["model"] == expected
    assert out["messages"][0]["content"] == "привет"


def test_rewrite_keeps_unknown_model_byte_for_byte(proxy):
    body = _body(model="samcs-gpu/local-agent", messages=[])
    assert proxy.rewrite_model(body) == body


@pytest.mark.parametrize("body", [b"", b"not json", b"[1, 2]", _body(input="x"), _body(model="")])
def test_rewrite_ignores_other_bodies(proxy, body):
    assert proxy.rewrite_model(body) == body


def test_proxy_forwards_rewritten_request(proxy, monkeypatch):
    seen: dict = {}

    class Upstream(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            seen["body"] = json.loads(self.rfile.read(n))
            seen["path"] = self.path
            seen["auth"] = self.headers.get("Authorization")
            resp = _body(choices=[{"message": {"content": "ok"}}], usage={"total_tokens": 7})
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp)))
            self.end_headers()
            self.wfile.write(resp)

    upstream = HTTPServer(("127.0.0.1", 0), Upstream)
    threading.Thread(target=upstream.serve_forever, daemon=True).start()
    monkeypatch.setattr(proxy, "UPSTREAM", f"http://127.0.0.1:{upstream.server_address[1]}")
    server = HTTPServer(("127.0.0.1", 0), proxy.ProxyHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        req = Request(
            f"http://127.0.0.1:{server.server_address[1]}/v1/chat/completions",
            data=_body(model="local-agent", messages=[{"role": "user", "content": "длинный текст " * 20}]),
            headers={"Content-Type": "application/json", "Authorization": "Bearer test"},
            method="POST",
        )
        out = json.load(urlopen(req, timeout=10))
    finally:
        server.shutdown()
        upstream.shutdown()
    assert out["choices"][0]["message"]["content"] == "ok"
    assert seen["body"]["model"] == "samcs-gpu/local-agent"
    assert seen["path"] == "/v1/chat/completions"
    assert seen["auth"] == "Bearer test"
    assert proxy._get_used() == 7
