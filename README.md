# Northwind Data Analyst Agent

Ask a business question in plain English — a locally-run LLM writes the SQL,
runs it against a real relational database, and returns a chart and a
plain-English takeaway, all inside a chat-style interface. No API keys, no
cloud calls: the model runs entirely on your own machine via
[Ollama](https://ollama.com).

![App screenshot](screenshots/app_demo.png)

## Why this project

Most portfolio "LLM + data" projects either query a single flat CSV, or call
a paid API. This one does neither: it uses a proper multi-table relational
database (the classic [Northwind](https://github.com/jpwhite3/northwind-SQLite3)
trading-company schema — customers, orders, order line items, products,
employees, suppliers), which forces the model to generate real SQL joins,
and it runs entirely offline/free via a local open-source model.

## How it works

```
You type: "Which product category made the most revenue?"
        |
        v
[Your question + database schema] --> [Local LLM via Ollama] --> SQL text
        |
        v
[Safety check: read-only SELECT only] --> [Run against Northwind.db]
        |
        v
[Real result data] --> [Auto-picked chart type] --> [Plain-English summary]
        |
        v
[Streamlit page: your question, the SQL, the table, the chart, the takeaway]
```

- **`src/db.py`** — reads the database's own metadata to build a schema
  description for the model, and safely executes generated SQL (read-only,
  single-statement only).
- **`src/llm_client.py`** — builds the prompt (question + schema + a
  worked example) and talks to the local Ollama API; defensively parses the
  model's response in case it doesn't follow the "SQL only" instruction
  exactly.
- **`src/chart.py`** — picks a chart type from the *shape* of the result
  (single value -> stat, category + amount -> bar, date + amount ->
  chronological line chart, category + multiple metrics -> grouped bar) and
  renders it with a small fixed color palette.
- **`app.py`** — the Streamlit UI: a chat interface with conversation
  history, example-question shortcuts and a model picker in the sidebar,
  and a small custom theme (`.streamlit/config.toml`) instead of Streamlit's
  defaults.
- **`tests/test_project.py`** — covers schema reading, the SQL safety guard,
  response parsing, and chart selection, all without needing Ollama running.

## Setup

**1. Clone and install Python dependencies**

```bash
git clone <this-repo-url>
cd llm-data-agent
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**2. Install Ollama and pull a model (one-time, ~5 minutes)**

macOS/Linux:
```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5-coder:3b
```
Windows: download the installer from [ollama.com/download](https://ollama.com/download), then run `ollama pull qwen2.5-coder:3b` in a terminal.

This downloads a ~1.9GB open-source model that runs on CPU on basically any
modern laptop. (Have 16GB+ RAM and want better accuracy? Swap the model name
in `src/llm_client.py`'s `DEFAULT_MODEL` for `qwen2.5-coder:7b`.)

**3. Run the app**

```bash
streamlit run app.py
```

Ollama's desktop app runs its server automatically; if you installed via the
command line instead, run `ollama serve` in a separate terminal first.

## Example questions

- What are the top 5 products by total revenue?
- Who are our top 10 customers by number of orders?
- How many orders came in each month?
- Which employees have sold the most, and in which countries?
- What's the average order value by shipping country?

## Running the tests

```bash
pip install pytest
pytest tests/ -v
```

## Tech stack

Python, SQLite, pandas, matplotlib, Streamlit, Ollama (local LLM runtime,
`qwen2.5-coder:3b`).

## Known limitations

- The SQL safety check is a keyword/regex allowlist, not a full SQL parser —
  fine for a local single-user tool, not meant as a production-grade
  defense against a hostile database or hostile prompts.
- Chart-type selection is a simple, explainable heuristic (data shape ->
  chart type), not a general-purpose auto-viz engine — it covers the common
  cases a business-analyst-style question tends to produce.
- Small local models occasionally misread ambiguous questions; rephrasing
  usually fixes it, and the generated SQL is always shown so you can see why.
