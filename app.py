"""
app.py
------
The user-facing piece, built as a chat interface: you ask a question, the
agent answers with its SQL, the data, a chart, and a takeaway — and every
past question/answer stays visible above, like a real conversation.

Streamlit re-runs this whole file top to bottom on every interaction, so
anything that needs to survive between interactions (the conversation
history) lives in st.session_state, which is just a persistent dictionary
Streamlit keeps alive for the browser tab's session.

Run it with:  streamlit run app.py
"""

import streamlit as st

from src.db import get_schema_description, run_query, UnsafeQueryError
from src.llm_client import generate_sql, generate_summary, DEFAULT_MODEL
from src.chart import pick_chart

st.set_page_config(
    page_title="Northwind Data Analyst Agent",
    layout="wide",
)

# A few small CSS touches on top of the theme in .streamlit/config.toml —
# rounded "cards" around chat turns and a tighter title block. Kept minimal
# on purpose: Streamlit's built-in theme does most of the work.
st.markdown(
    """
    <style>
    [data-testid="stChatMessage"] {
        background: #ffffff;
        border: 1px solid #e1e0d9;
        border-radius: 12px;
        padding: 0.75rem 1rem;
        margin-bottom: 0.5rem;
    }
    .agent-subtitle { color: #52514e; font-size: 0.95rem; margin-top: -0.6rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

EXAMPLE_QUESTIONS = [
    "What are the top 5 products by total revenue?",
    "Who are our top 10 customers by number of orders?",
    "How many orders came in each month?",
    "Which employees have sold the most?",
    "What's the average order value by shipping country?",
]


@st.cache_data
def load_schema():
    return get_schema_description()


schema = load_schema()

if "history" not in st.session_state:
    st.session_state.history = []
if "pending_question" not in st.session_state:
    st.session_state.pending_question = None

# ---------- Sidebar ----------
with st.sidebar:
    st.markdown("### Northwind Data Analyst Agent")
    st.caption(
        "A local LLM (via Ollama) turns your question into SQL, runs it "
        "against the real Northwind database, and explains the result."
    )

    st.markdown("**Model**")
    model_choice = st.selectbox(
        "Model",
        ["qwen2.5-coder:3b", "qwen2.5-coder:7b"],
        label_visibility="collapsed",
        help="3b is faster and works on most laptops. 7b is more accurate "
        "if you have 16GB+ RAM.",
    )

    st.markdown("**Try asking**")
    for q in EXAMPLE_QUESTIONS:
        if st.button(q, width="stretch", key=f"example::{q}"):
            st.session_state.pending_question = q

    st.divider()
    if st.button("Clear conversation", width="stretch"):
        st.session_state.history = []
        st.rerun()

# ---------- Header ----------
st.title("Ask Northwind")
st.markdown(
    '<p class="agent-subtitle">Customers, orders, products, employees, '
    "suppliers — ask in plain English.</p>",
    unsafe_allow_html=True,
)


def run_pipeline(question: str, model: str) -> dict:
    """Runs the full question -> SQL -> data -> chart -> summary pipeline,
    returning everything needed to render this turn (now, and again later
    when the conversation history is redrawn)."""
    turn = {"question": question}

    try:
        turn["sql"] = generate_sql(question, schema, model=model)
    except RuntimeError as e:
        turn["error"] = str(e)
        return turn

    try:
        df = run_query(turn["sql"])
    except UnsafeQueryError as e:
        turn["error"] = f"The model generated a query that wasn't allowed ({e}). Try rephrasing."
        return turn
    except Exception as e:
        turn["error"] = f"That SQL didn't run successfully ({e}). Try rephrasing your question."
        return turn

    if df.empty:
        turn["error"] = "The query ran but returned no rows."
        return turn

    turn["df"] = df
    turn["fig"] = pick_chart(df) if not (len(df) == 1 and len(df.columns) == 1) else None

    try:
        preview = df.head(10).to_string(index=False)
        turn["summary"] = generate_summary(question, preview, model=model)
    except RuntimeError:
        turn["summary"] = None  # not fatal — the data itself is still shown

    return turn


def render_answer(turn: dict):
    if turn.get("error"):
        st.error(turn["error"])
        return

    with st.expander("Generated SQL"):
        st.code(turn["sql"], language="sql")

    df = turn["df"]
    if len(df) == 1 and len(df.columns) == 1:
        st.metric(label=df.columns[0], value=df.iloc[0, 0])
    else:
        st.dataframe(df, width="stretch")
        if turn.get("fig") is not None:
            st.pyplot(turn["fig"], width="stretch")

    if turn.get("summary"):
        st.info(f"**Takeaway:** {turn['summary']}")


# Small custom-generated avatar images (see assets/) instead of Streamlit's
# default icon font — keeps the look consistent even offline or on a
# locked-down network that blocks external font requests.
USER_AVATAR = "assets/avatar_user.png"
AGENT_AVATAR = "assets/avatar_agent.png"

# ---------- Replay conversation history ----------
for turn in st.session_state.history:
    with st.chat_message("user", avatar=USER_AVATAR):
        st.write(turn["question"])
    with st.chat_message("assistant", avatar=AGENT_AVATAR):
        render_answer(turn)

# ---------- New input (typed, or from a sidebar example button) ----------
typed_question = st.chat_input("Ask a question about the Northwind data...")
question = typed_question or st.session_state.pending_question
st.session_state.pending_question = None

if question:
    with st.chat_message("user", avatar=USER_AVATAR):
        st.write(question)
    with st.chat_message("assistant", avatar=AGENT_AVATAR):
        with st.spinner("Writing SQL, running it, and summarizing..."):
            result_turn = run_pipeline(question, model=model_choice)
        render_answer(result_turn)
    st.session_state.history.append(result_turn)
