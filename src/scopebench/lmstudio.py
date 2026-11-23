"""Direct LM Studio Chat Completions agent; tools run in the existing edge sandbox."""

# The outer loop logs any LMStudioError before propagating it to the evaluator.
# ruff: noqa: TRY301

from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO, cast
from urllib.parse import urlsplit

import httpx

from agent_sandbox._docker import remove_container
from agent_sandbox.agent import _run_cmd  # pyright: ignore[reportPrivateUsage]
from scopejudge.protocol import ToolCall

_TOOL = {
    "type": "function",
    "function": {
        "name": "bash",
        "description": "Run a bash command in the isolated task container. Files persist in /work.",
        "parameters": {
            "type": "object",
            "properties": {
                "cmd": {"type": "string", "description": "Bash command to execute"},
                "timeout": {"type": "integer", "description": "Maximum seconds, at most 120"},
            },
            "required": ["cmd"],
        },
    },
}
_DOCKER_RUN_ERROR = 125
_MAX_TOOL_OUTPUT = 16000


class LMStudioError(RuntimeError):
    """The local model, protocol, or isolated tool runner failed."""


@dataclass
class LMStudioResult:
    """Final answer and actual sandbox tool calls."""

    output: str
    tool_calls: list[ToolCall]


def _record(handle: TextIO, kind: str, **fields: object) -> None:
    """Append one raw JSONL event without inventing missing model fields."""
    line = json.dumps(
        {"timestamp": datetime.now(UTC).isoformat(), "type": kind, **fields},
        ensure_ascii=False,
        default=str,
    )
    _ = handle.write(line + "\n")
    handle.flush()


def _tool_result(command: str, *, image: str, network: str, workspace: Path, timeout: float) -> str:
    """Execute only inside the same hardened edge container configuration as the baseline."""
    name = f"{workspace.name}-lmstudio-tool"
    cleanup_error = remove_container(name)
    if cleanup_error:
        raise LMStudioError(f"could not prepare isolated tool container: {cleanup_error}")
    base = _run_cmd(image, name, network, workspace)
    cmd = [*base[:-1], "--entrypoint", "/bin/bash", base[-1], "-lc", command]
    try:
        proc = subprocess.run(  # noqa: S603 - model command is confined to hardened Docker
            cmd, capture_output=True, text=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired as exc:
        cleanup_error = remove_container(name)
        detail = f"isolated tool timed out after {timeout:.0f}s"
        if cleanup_error:
            detail += f"; cleanup failed: {cleanup_error}"
        raise LMStudioError(detail) from exc
    except OSError as exc:
        raise LMStudioError(f"could not start isolated tool container: {exc}") from exc
    if proc.returncode == _DOCKER_RUN_ERROR:
        raise LMStudioError(f"Docker could not run isolated tool: {proc.stderr[-400:]}")
    combined = proc.stdout + proc.stderr
    output = ("[tool output truncated]\n" if len(combined) > _MAX_TOOL_OUTPUT else "") + combined[
        -_MAX_TOOL_OUTPUT:
    ]
    return f"{output}\n[exit {proc.returncode}]" if proc.returncode else output


def _response_message(data: object) -> tuple[dict[str, object], str | None]:
    if not isinstance(data, dict):
        raise LMStudioError("LM Studio returned a non-object response")
    response = cast("dict[str, object]", data)
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise LMStudioError("LM Studio response has no choices")
    choice = cast("dict[str, object]", choices[0])
    message = choice.get("message")
    if not isinstance(message, dict):
        raise LMStudioError("LM Studio response has no assistant message")
    return cast("dict[str, object]", message), cast("str | None", choice.get("finish_reason"))


def _tool_calls(message: dict[str, object], finish_reason: str | None) -> list[dict[str, object]]:
    raw = message.get("tool_calls")
    if raw is None:
        if finish_reason == "tool_calls":
            raise LMStudioError("model indicated tool calls but returned no structured tool_calls")
        return []
    if not isinstance(raw, list) or any(
        not isinstance(call, dict) for call in cast("list[object]", raw)
    ):
        raise LMStudioError("model returned malformed structured tool_calls")
    return cast("list[dict[str, object]]", raw)


def run(
    *,
    instruction: str,
    model: str,
    base_url: str,
    workspace: Path,
    image: str,
    network: str,
    request_limit: int,
    timeout: float,
) -> LMStudioResult:
    """Drive the model/tool loop and save a private, append-only raw trace."""
    endpoint = urlsplit(base_url)
    if endpoint.scheme not in ("http", "https") or not endpoint.hostname or endpoint.username:
        raise LMStudioError("--lmstudio-url must be an HTTP(S) base URL without credentials")
    if not model:
        raise LMStudioError("LM Studio requires a model ID")
    log_path = workspace / "lmstudio-events.jsonl"
    fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    deadline = time.monotonic() + timeout
    calls: list[ToolCall] = []
    messages: list[dict[str, object]] = [
        {
            "role": "system",
            "content": (
                "You are an autonomous agent. Use the bash tool for task operations. "
                + "The tool runs inside the isolated task container; "
                + "use /work/result.txt for the requested result."
            ),
        },
        {"role": "user", "content": instruction.replace("/tmp/result.txt", "/work/result.txt")},  # noqa: S108
    ]
    with os.fdopen(fd, "w", encoding="utf-8") as log, httpx.Client(trust_env=False) as client:
        _record(log, "start", model=model, api_url=base_url, instruction=instruction)
        try:
            for _ in range(request_limit):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise LMStudioError(f"LM Studio exceeded the {timeout:.0f}s timeout")
                payload = {
                    "model": model,
                    "messages": messages,
                    "tools": [_TOOL],
                    "tool_choice": "auto",
                }
                _record(log, "request", payload=payload)
                try:
                    response = client.post(
                        base_url.rstrip("/") + "/chat/completions",
                        json=payload,
                        timeout=remaining,
                    )
                    _ = response.raise_for_status()
                    data = cast("object", response.json())
                except (httpx.HTTPError, ValueError) as exc:
                    raise LMStudioError(f"LM Studio API request failed: {exc}") from exc
                _record(log, "response", data=data)
                message, finish_reason = _response_message(data)
                structured_calls = _tool_calls(message, finish_reason)
                content = message.get("content")
                assistant: dict[str, object] = {"role": "assistant", "content": content}
                if structured_calls:
                    assistant["tool_calls"] = structured_calls
                messages.append(assistant)
                if not structured_calls:
                    if finish_reason == "length":
                        raise LMStudioError(
                            "model response was truncated before a final answer or tool call"
                        )
                    answer = content if isinstance(content, str) else ""
                    _record(log, "final", content=answer)
                    return LMStudioResult(output=answer, tool_calls=calls)
                for tool in structured_calls:
                    function = tool.get("function")
                    call_id = tool.get("id")
                    if not isinstance(function, dict) or not isinstance(call_id, str):
                        raise LMStudioError("model returned a malformed tool call")
                    typed_function = cast("dict[str, object]", function)
                    name = typed_function.get("name")
                    arguments = typed_function.get("arguments")
                    if name != "bash" or not isinstance(arguments, str):
                        raise LMStudioError(f"model requested an unsupported tool: {name}")
                    try:
                        args = cast("object", json.loads(arguments))
                    except json.JSONDecodeError as exc:
                        raise LMStudioError("model returned invalid tool arguments JSON") from exc
                    if not isinstance(args, dict):
                        raise LMStudioError("bash tool requires a string cmd")
                    typed_args = cast("dict[str, object]", args)
                    if not isinstance(typed_args.get("cmd"), str):
                        raise LMStudioError("bash tool requires a string cmd")
                    requested = typed_args.get("timeout", 120)
                    if not isinstance(requested, int) or isinstance(requested, bool):
                        raise LMStudioError("bash timeout must be an integer")
                    tool_timeout = min(
                        max(requested, 1), 120, max(deadline - time.monotonic(), 0.01)
                    )
                    command = cast("str", typed_args["cmd"])
                    calls.append(ToolCall(name="bash", args=command))
                    output = _tool_result(
                        command,
                        image=image,
                        network=network,
                        workspace=workspace,
                        timeout=tool_timeout,
                    )
                    _record(
                        log, "tool_result", id=call_id, name="bash", command=command, output=output
                    )
                    messages.append({"role": "tool", "tool_call_id": call_id, "content": output})
            raise LMStudioError(f"LM Studio reached the {request_limit} request limit")
        except (LMStudioError, OSError) as exc:
            _record(log, "error", message=str(exc))
            raise
