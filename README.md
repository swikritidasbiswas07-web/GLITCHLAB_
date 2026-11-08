# GLITCHLAB — Round 2 Working MVP
**Axiom · CodeTitans India 2026**

Functional local demo of a source-aware brand-policy testing and human approval workflow.

## Prerequisites
- Python 3.10+
- Node.js 20+
- Windows PowerShell or command prompt

## Run backend
Open terminal in `backend`:

```powershell
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

## Run frontend
Open a **second** terminal in `frontend`:

```powershell
npm.cmd install
npm.cmd run dev
```

Open http://localhost:5173

If your PowerShell execution policy prevents `npm`, use `npm.cmd`, not `npm`.

## Demo journey
1. Open **Policy Vault** and inspect 5 synthetic approved rules and source labels.
2. Open **Content Lab** (preloaded NovaCell X advertisement) and run tests.
3. Review source-linked findings, then apply suggested patches.
4. Run tests again to persist a new draft version. Handle any remaining issue manually.
5. Open **Review Station**, choose the draft, enter reviewer name, approve it.
6. Check the version history and approval record.

## Run automated tests
```powershell
cd backend
.venv\Scripts\python.exe -m pytest -q
```

## Feature scope and integrity
### Working in this initial codebase
- Seeded policy source library; creation of regex-based rules
- Content draft creation, stored version history
- Deterministic case-insensitive content inspection
- Findings connected to approved rule metadata and exact source labels
- Targeted manual-accept correction suggestions and rerun
- Recorded human approval / change requests; approval blocked for untested or failing latest version
- SQLite persistence for fast local demonstration
- Browser interface for content, rules and reviews

### Not yet implemented
- Production authentication or organisation isolation
- PDF/image ingestion, LLM, automatic contradiction detection, full policy compilation
- PostgreSQL deployment, public hosted link, rule unit-testing authoring UI
- Comprehensive legal, tone or accessibility evaluation

**Important:** This is a public-demo prototype, not secure document hosting. Do not enter confidential materials. Role names are not authenticated identities.

## Key technical decisions
Deterministic rules are inspectable and easy to reproduce. Every finding records the matched span, explanation and source. Approval requires testing the exact current version with zero configured-rule findings. Suggestions are never silently applied.

## Development and AI disclosure
Initial implementation was generated with AI assistance under the sole participant's direction. Review, adapt, test and disclose AI assistance in the event submission. Confirm that this code was generated after the organiser-authorised build start.
