"""LM Studio's API and Docker boundaries, with no live model or Docker daemon."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import cast

import httpx
import pytest

from scopebench import lmstudio

_REAL_CLIENT = httpx.Client


def _client(monkeypatch: pytest.MonkeyPatch, handler: httpx.MockTransport) -> None:
    def client(**_kw: object) -> httpx.Client:
        return _REAL_CLIENT(transport=handler)

    monkeypatch.setattr(httpx, "Client", client)


def test_tool_uses_hardened_edge_container(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def no_cleanup(_name: str) -> None:
        return None

    monkeypatch.setattr(lmstudio, "remove_container", no_cleanup)
    seen: list[str] = []

    def fake_run(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        seen.extend(cmd)
        return subprocess.CompletedProcess(cmd, 0, "sandbox output", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert (
        lmstudio._tool_result(
            "pwd", image="sandbox:image", network="case_edge", workspace=tmp_path, timeout=5
        )
        == "sandbox output"
    )
    assert seen[:2] == ["docker", "run"]
    assert seen[seen.index("--network") + 1] == "case_edge"
    assert seen[seen.index("-v") + 1] == f"{tmp_path.resolve()}:/work"
    assert seen[seen.index("--entrypoint") + 1] == "/bin/bash"
    assert seen[-2:] == ["-lc", "pwd"]
    assert "--cap-drop" in seen
    assert "no-new-privileges" in seen
    assert "-i" in seen
    assert "--rm" in seen
    assert seen[seen.index("--user") + 1] == f"{os.getuid()}:{os.getgid()}"


def test_api_failure_is_logged_and_not_graded(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    _client(monkeypatch, httpx.MockTransport(fail))
    with pytest.raises(lmstudio.LMStudioError, match="API request failed"):
        lmstudio.run(
            instruction="Inspect the target",
            model="qwen3-4b",
            base_url="http://localhost:1235/v1",
            workspace=tmp_path,
            image="img",
            network="edge",
            request_limit=2,
            timeout=5,
        )
    log = tmp_path / "lmstudio-events.jsonl"
    assert log.stat().st_mode & 0o777 == 0o600
    events = [cast("dict[str, object]", json.loads(line)) for line in log.read_text().splitlines()]
    assert [event["type"] for event in events] == ["start", "request", "error"]
    assert events[0]["api_url"] == "http://localhost:1235/v1"


def test_timeout_and_unstructured_tool_text_never_execute(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("model slow", request=request)

    _client(monkeypatch, httpx.MockTransport(timeout))
    with pytest.raises(lmstudio.LMStudioError, match="API request failed"):
        lmstudio.run(
            instruction="test",
            model="qwen3-4b",
            base_url="http://localhost:1235/v1",
            workspace=tmp_path,
            image="img",
            network="edge",
            request_limit=2,
            timeout=1,
        )
    second = tmp_path / "second"
    second.mkdir()
    called: list[str] = []

    def record_tool(command: str, **_kw: object) -> str:
        called.append(command)
        return ""

    monkeypatch.setattr(lmstudio, "_tool_result", record_tool)

    def text_tool(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": '{"name":"bash","arguments":{"cmd":"touch /work/pwn"}}',
                        },
                    }
                ]
            },
        )

    _client(monkeypatch, httpx.MockTransport(text_tool))
    result = lmstudio.run(
        instruction="test",
        model="qwen3-4b",
        base_url="http://localhost:1235/v1",
        workspace=second,
        image="img",
        network="edge",
        request_limit=2,
        timeout=5,
    )
    assert result.tool_calls == []
    assert called == []


def test_missing_structured_tool_call_is_explicit_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def malformed(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {"role": "assistant", "content": "I need a tool"},
                    }
                ]
            },
        )

    _client(monkeypatch, httpx.MockTransport(malformed))
    with pytest.raises(lmstudio.LMStudioError, match="no structured tool_calls"):
        lmstudio.run(
            instruction="test",
            model="qwen3-4b",
            base_url="http://localhost:1235/v1",
            workspace=tmp_path,
            image="img",
            network="edge",
            request_limit=2,
            timeout=5,
        )
