"""UI tests using Streamlit's headless AppTest. ask() is replaced, so no API key or network."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest
from streamlit.testing.v1.errors import AppTestError

from bot import agent


def fake_result(question, mode):
    return {"answer": f"answer to {question}", "tool_calls": [], "latency_ms": 5, "input_tokens": 1, "output_tokens": 1,
            "cost_usd": 0.0, "config_version": "v1", "model": "fake", "mode": mode, "trace_id": "abc123", "error": None}


def make_app(monkeypatch):
    seen = []

    def fake_ask(question, history=None, mode=None, **kw):
        seen.append({"question": question, "history": history, "mode": mode})
        return fake_result(question, mode)

    monkeypatch.setattr(agent, "ask", fake_ask)
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=30).run()
    return at, seen


def tile_buttons(at):
    return [b for b in at.button if str(b.key).startswith("tile-")]


def test_two_tiles_greeting_and_default_placeholder(monkeypatch):
    at, _ = make_app(monkeypatch)
    assert not at.exception
    assert len(tile_buttons(at)) == 2
    assert "Earner lookup" in tile_buttons(at)[0].label and "Cohort report" in tile_buttons(at)[1].label
    assert at.chat_input[0].placeholder.startswith("Ask me anything")


def test_selecting_a_tile_sets_mode_and_placeholder(monkeypatch):
    at, seen = make_app(monkeypatch)
    tile_buttons(at)[0].click().run()
    assert at.session_state.mode == "earner_lookup"
    assert "earner ID" in at.chat_input[0].placeholder
    at.chat_input[0].set_value("P-10482").run()
    assert seen[-1]["mode"] == "earner_lookup"


def test_clicking_selected_tile_again_clears_mode(monkeypatch):
    at, _ = make_app(monkeypatch)
    tile_buttons(at)[1].click().run()
    assert at.session_state.mode == "cohort_report"
    tile_buttons(at)[1].click().run()
    assert at.session_state.mode is None


def test_history_is_passed_on_follow_up(monkeypatch):
    at, seen = make_app(monkeypatch)
    at.chat_input[0].set_value("first").run()
    at.chat_input[0].set_value("second").run()
    assert [m["content"] for m in seen[1]["history"]] == ["first", "answer to first"]


def test_ten_question_limit(monkeypatch):
    at, seen = make_app(monkeypatch)
    for i in range(10):
        at.chat_input[0].set_value(f"q{i}").run()
    assert len(seen) == 10 and at.chat_input[0].disabled
    assert any("used all 10" in i.value for i in at.info)
    with pytest.raises(AppTestError):  # AppTest refuses input to a disabled widget, as a browser would
        at.chat_input[0].set_value("one too many")


def test_new_chat_clears_history_but_not_the_question_count(monkeypatch):
    at, seen = make_app(monkeypatch)
    at.chat_input[0].set_value("q1").run()
    next(b for b in at.button if b.label == "New chat").click().run()
    assert at.session_state.turns == [] and at.session_state.questions_asked == 1


def test_trace_line_shows_only_id_seconds_and_cost(monkeypatch):
    at, _ = make_app(monkeypatch)
    at.chat_input[0].set_value("hello").run()
    captions = [c.value for c in at.caption]
    assert "Trace abc123 · 0.0 s · $0.0000" in captions
    assert not at.expander and not at.json  # no tool calls, arguments or results in the UI
