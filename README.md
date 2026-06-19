# RentSnap

**Free rental comp reports — powered by AI.**

Enter a property address and RentSnap searches live comparable listings, analyzes the local rental market, and generates a full comp report in under a minute. No account. No payment.

**Live demo:** [your-app.railway.app](https://your-app.railway.app)

---

## How it works

```
User fills form (address, beds, baths)
        ↓
FastAPI receives POST /generate
        ↓
LangGraph agent runs two tools:
  • listing_search  — Tavily searches live rental listings
  • comp_analyzer   — Claude analyzes comps & market position
  • db_logger       — logs snapshot to SQLite
        ↓
Claude returns plain-text analysis
        ↓
Result rendered as HTML in the browser
```

## Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + Uvicorn |
| AI agent | LangGraph `create_react_agent` |
| LLM | Claude Haiku (via `langchain-anthropic`) |
| Search | Tavily Search API |
| Templates | Jinja2 |
| Database | SQLite (report counter) |
| Hosting | Railway |

## Local setup

### 1. Clone and create a virtual environment

```bash
git clone https://github.com/yourusername/rentsnap
cd rentsnap
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
```

### 2. Copy the agent files from dnh_intel

RentSnap reuses the agent and tools built for the DNH Rental Intelligence project.

```bash
cp ../dnh_intel/agent.py  ./agent.py
cp -r ../dnh_intel/tools  ./tools
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Add environment variables

Create a `.env` file in the project root:

```
ANTHROPIC_API_KEY=sk-ant-...
TAVILY_API_KEY=tvly-...
```

These are the same keys used by dnh_intel.

### 5. Run

```bash
uvicorn main:app --reload
```

Open [http://localhost:8000](http://localhost:8000).

---

## Deploy to Railway

1. Push the project to a GitHub repo
2. Create a new project at [railway.app](https://railway.app)
3. Connect the GitHub repo
4. Add your environment variables under **Variables**:
   - `ANTHROPIC_API_KEY`
   - `TAVILY_API_KEY`
5. Railway auto-detects the `Procfile` and deploys

---

## Project structure

```
rentsnap/
├── main.py              # FastAPI app — routes and request handling
├── agent_wrapper.py     # Bridges web form → analyze_unit()
├── agent.py             # LangGraph agent (copied from dnh_intel)
├── database.py          # SQLite report counter
├── tools/               # LangChain tools (copied from dnh_intel)
│   ├── listing_search.py
│   ├── comp_analyzer.py
│   └── db_logger.py
├── templates/
│   └── index.html       # Landing page + results (single template, two states)
├── requirements.txt
└── Procfile
```

---

## Background

Built as a public-facing wrapper around the [DNH Rental Intelligence](https://github.com/yourusername/dnh_intel) agent — an agentic AI tool for autonomously researching rental comps in the Richmond, KY market.

The goal was to take a working local agent and surface it as a useful, deployable web tool — going from script to product.
