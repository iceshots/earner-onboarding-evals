"""Bot A: a tool-use loop over the two fixed tools, with a JSONL trace per question.

Public interface for the eval harness: ask(question, history=None) -> dict.
"""
import json
import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from .pricing import cost_usd
from .tools import dispatch

BOT_DIR = Path(__file__).resolve().parent
TRACE_PATH = BOT_DIR / "logs" / "traces.jsonl"
MAX_TOOL_ROUNDS = 6
MAX_TOKENS = 4096

load_dotenv(BOT_DIR.parent / ".env")


class MissingApiKeyError(RuntimeError):
    pass


@dataclass
class ModelResponse:
    content: list  # blocks as plain dicts: {"type": "text"|"tool_use"|..., ...}
    stop_reason: str
    input_tokens: int
    output_tokens: int


def load_config(version: str | None = None) -> dict:
    version = version or os.environ.get("BOT_CONFIG_VERSION", "v1")
    cfg_dir = BOT_DIR / "config" / version
    if not cfg_dir.is_dir():
        raise FileNotFoundError(f"No bot config at {cfg_dir}")
    system = (cfg_dir / "system_prompt.md").read_text(encoding="utf-8")
    dictionary = (cfg_dir / "data_dictionary.md").read_text(encoding="utf-8")
    tools = json.loads((cfg_dir / "tool_descriptions.json").read_text(encoding="utf-8"))
    modes = json.loads((cfg_dir / "modes.json").read_text(encoding="utf-8"))
    return {
        "version": version,
        "modes": {name: m["hint"] for name, m in modes.items()},
        "system": f"{system}\n\n# Data dictionary\n\n{dictionary}",
        "tools": [{"name": n, "description": t["description"], "input_schema": t["input_schema"]} for n, t in tools.items()],
    }


def call_model(model: str, system: str, tools: list, messages: list) -> ModelResponse:
    """The one place that talks to Anthropic. Swap this (or pass model_caller to ask) for tests or another provider.

    No temperature is sent: claude-sonnet-5-5 rejects non-default sampling parameters, and the API
    rejects temperature on every model from 2026-10-21. Effort is the main behaviour knob.
    """
    import anthropic

    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise MissingApiKeyError(
            "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key (never commit .env)."
        )
    client = anthropic.Anthropic(api_key=key)
    resp = client.messages.create(
        model=model,
        max_tokens=MAX_TOKENS,
        system=system,
        tools=tools,
        messages=messages,
        output_config={"effort": os.environ.get("BOT_EFFORT", "medium")},
    )
    return ModelResponse(
        content=[b.model_dump(exclude_none=True) for b in resp.content],
        stop_reason=resp.stop_reason,
        input_tokens=resp.usage.input_tokens,
        output_tokens=resp.usage.output_tokens,
    )


def _write_trace(record: dict) -> None:
    TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with TRACE_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def ask(question: str, history: list | None = None, mode: str | None = None, model_caller=None) -> dict:
    """Answer one question. history is a list of {"role": "user"|"assistant", "content": str} text turns.

    mode is an optional UI hint ("earner_lookup" or "cohort_report", see config/<version>/modes.json) that
    steers how a terse question is interpreted. It comes from a fixed list, never from free text.
    """
    caller = model_caller or call_model
    cfg = load_config()
    if mode is not None and mode not in cfg["modes"]:
        raise ValueError(f"Unknown mode {mode!r}. Valid modes: {', '.join(cfg['modes'])}.")
    cfg["mode"] = mode
    if mode:
        cfg["system"] += f"\n\n# Selected mode\n\n{cfg['modes'][mode]}"
    model = os.environ.get("BOT_MODEL", "claude-haiku-5-5")
    trace_id = uuid.uuid4().hex[:12]
    started = time.perf_counter()
    messages = [{"role": m["role"], "content": m["content"]} for m in (history or [])]
    messages.append({"role": "user", "content": question})

    tool_calls, in_tok, out_tok, answer, error, rounds = [], 0, 0, "", None, 0
    try:
        for _ in range(MAX_TOOL_ROUNDS + 1):
            resp = caller(model, cfg["system"], cfg["tools"], messages)
            in_tok += resp.input_tokens
            out_tok += resp.output_tokens
            texts = [b["text"] for b in resp.content if b["type"] == "text"]

            if resp.stop_reason != "tool_use":
                answer = "\n".join(texts).strip()
                if resp.stop_reason == "refusal":
                    error = "model refused (stop_reason=refusal)"
                break

            if rounds >= MAX_TOOL_ROUNDS:
                error = f"stopped after {MAX_TOOL_ROUNDS} tool rounds"
                answer = "I could not finish this request within the tool-call limit. Please try a narrower question."
                break
            rounds += 1

            messages.append({"role": "assistant", "content": resp.content})
            results = []
            for block in (b for b in resp.content if b["type"] == "tool_use"):
                out = dispatch(block["name"], block["input"])
                tool_calls.append({"name": block["name"], "arguments": block["input"], "result": out})
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block["id"],
                    "content": json.dumps(out),
                    **({"is_error": True} if "error" in out else {}),
                })
            messages.append({"role": "user", "content": results})
    except Exception as e:  # logged, then re-raised so the caller sees it
        error = f"{type(e).__name__}: {e}"
        _write_trace(_record(trace_id, cfg, model, question, history, tool_calls, answer, started, in_tok, out_tok, error))
        raise

    record = _record(trace_id, cfg, model, question, history, tool_calls, answer, started, in_tok, out_tok, error)
    _write_trace(record)
    return {
        "answer": answer,
        "tool_calls": tool_calls,
        "latency_ms": record["latency_ms"],
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "cost_usd": record["cost_usd"],
        "config_version": cfg["version"],
        "model": model,
        "mode": mode,
        "trace_id": trace_id,
        "error": error,
    }


def _record(trace_id, cfg, model, question, history, tool_calls, answer, started, in_tok, out_tok, error) -> dict:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "trace_id": trace_id,
        "config_version": cfg["version"],
        "model": model,
        "mode": cfg.get("mode"),
        "question": question,
        "history_length": len(history or []),
        "tool_calls": tool_calls,
        "answer": answer,
        "latency_ms": round((time.perf_counter() - started) * 1000),
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "cost_usd": cost_usd(model, in_tok, out_tok),
        "error": error,
    }
