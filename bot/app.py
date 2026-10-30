"""Thin Streamlit chat UI over bot.agent.ask. No logic lives here.

Run from the repo root:  streamlit run bot/app.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

from bot.agent import MissingApiKeyError, ask

MAX_QUESTIONS = int(os.environ.get("BOT_MAX_QUESTIONS_PER_SESSION", "10"))

# Tiles: mode id (matches bot/config/<version>/modes.json) -> what the user sees.
TILES = {
    "earner_lookup": {
        "key": "lookup",
        "title": ":material/person_search: Earner lookup",
        "description": "Look up one earner by ID: overall result, each check and its recorded failure reason.",
        "placeholder": "Enter an earner ID, e.g. P-10482",
    },
    "cohort_report": {
        "key": "report",
        "title": ":material/bar_chart: Cohort report",
        "description": "Counts and percentages for a group of earners, with top reasons and re-cuts by region, type or month.",
        "placeholder": "e.g. What % of APAC restaurants that started in September are stuck on payment profile?",
    },
}
DEFAULT_PLACEHOLDER = "Ask me anything about earner onboarding..."

st.set_page_config(page_title="Heimdall: Earner Onboarding Assistant", page_icon=":material/chat:", layout="centered")

st.html(
    """
<style>
.hero { text-align: center; margin: 1rem 0 1.5rem; }
.hero .logo { width: 3.2rem; height: 3.2rem; border-radius: 50%; background: #0F172A; color: #fff;
  display: inline-flex; align-items: center; justify-content: center; font-size: 1.2rem;
  box-shadow: 0 0 0 0.5rem #E3EBF7; margin-bottom: 1rem; }
.hero .title { color: #0F172A; font-size: 1.7rem; font-weight: 600; line-height: 1.25; }
.hero .hello { color: #94A3B8; font-size: 1.15rem; font-weight: 500; margin-top: 0.4rem; }
.hero .about { color: #475569; font-size: 0.9rem; line-height: 1.5; max-width: 34rem; margin: 0.9rem auto 0; }
[class*="st-key-tile-"] button { height: auto; min-height: 7.5rem; align-items: flex-start; justify-content: flex-start;
  text-align: left; padding: 1rem; background: #fff; border: 1px solid #E2E8F0;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06); }
[class*="st-key-tile-"] button:hover { border-color: #7DD3FC; }
[class*="st-key-tile-"] button > div, [class*="st-key-tile-"] button [data-testid="stMarkdownContainer"] { width: 100%; text-align: left; }
[class*="st-key-tile-"] button p { font-size: 0.9rem; font-weight: 400; color: #475569; line-height: 1.45;
  white-space: normal; overflow: visible; text-overflow: clip; }
[class*="st-key-tile-"] button strong { font-weight: 700; color: #0F172A; }
[class*="st-key-tile-"][class*="-on"] button { border: 2px solid #0284C7; background: #F0F9FF; }
</style>
"""
)

if "turns" not in st.session_state:
    st.session_state.turns = []  # each: {"question", "mode", "result"}
if "mode" not in st.session_state:
    st.session_state.mode = None  # None, or a key of TILES
if "questions_asked" not in st.session_state:
    st.session_state.questions_asked = 0  # survives "New chat" so the cap cannot be reset from the UI


def history_for_model() -> list:
    h = []
    for t in st.session_state.turns:
        h += [{"role": "user", "content": t["question"]}, {"role": "assistant", "content": t["result"]["answer"]}]
    return h


def render_trace(r: dict) -> None:
    """Only the trace id, seconds and cost are shown. Full details are in bot/logs/traces.jsonl."""
    cost = f"${r['cost_usd']:.4f}" if r.get("cost_usd") is not None else "$ n/a"
    st.caption(f"Trace {r['trace_id']} · {r['latency_ms'] / 1000:.1f} s · {cost}")


def toggle_mode(mode: str) -> None:
    st.session_state.mode = None if st.session_state.mode == mode else mode


def new_chat() -> None:
    st.session_state.turns = []
    st.session_state.mode = None


_, new_chat_col = st.columns([4, 1])
new_chat_col.button("New chat", icon=":material/add:", type="primary", on_click=new_chat, width="stretch")

if not st.session_state.turns:
    st.html(
        '<div class="hero"><div class="logo">&#9670;</div>'
        '<div class="title">Heimdall : The Earner Onboarding Assistant</div>'
        '<div class="hello">How can I help? &#128075;</div>'
        '<div class="about">Heimdall shows where earners are stuck in onboarding, and why, '
        "so you can unblock them faster.</div></div>"
    )

for col, (mode, tile) in zip(st.columns(len(TILES)), TILES.items()):
    selected = st.session_state.mode == mode
    col.button(
        f"**{tile['title']}**  \n{tile['description']}",
        key=f"tile-{tile['key']}-{'on' if selected else 'off'}",
        on_click=toggle_mode,
        args=(mode,),
        width="stretch",
    )

for t in st.session_state.turns:
    with st.chat_message("user"):
        st.write(t["question"])
    with st.chat_message("assistant"):
        st.write(t["result"]["answer"])
        render_trace(t["result"])

limit_reached = st.session_state.questions_asked >= MAX_QUESTIONS
placeholder = TILES[st.session_state.mode]["placeholder"] if st.session_state.mode else DEFAULT_PLACEHOLDER
question = st.chat_input(placeholder, disabled=limit_reached)

if limit_reached:
    st.info(f"You have used all {MAX_QUESTIONS} questions for this session. Reload the page to start a new session.")

if question:
    st.session_state.questions_asked += 1
    with st.chat_message("user"):
        st.write(question)
    with st.chat_message("assistant"):
        try:
            with st.spinner("Thinking..."):
                result = ask(question, history_for_model(), mode=st.session_state.mode)
        except MissingApiKeyError as e:
            st.session_state.questions_asked -= 1  # no model call was made
            st.error(str(e))
        except Exception as e:
            st.error(f"Something went wrong: {e}")
        else:
            st.write(result["answer"])
            render_trace(result)
            st.session_state.turns.append({"question": question, "mode": st.session_state.mode, "result": result})
            if st.session_state.questions_asked >= MAX_QUESTIONS:
                st.rerun()  # redraw so the input is disabled straight after the last allowed question
