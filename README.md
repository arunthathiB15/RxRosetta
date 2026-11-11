# RxRosetta
Post-discharge medication companion: paste discharge-paper medicine lines, get a verified plan in English, Tamil or Hindi, with safety checks, a teach-back quiz, a red-flag check-in and a live caregiver feed.

## Run
    pip install -r requirements.txt
    uvicorn app:app --port 8000
Windows: use `python -m pip install -r requirements.txt` and `python -m uvicorn app:app --port 8000`. Open http://localhost:8000 (two tabs: patient and Caregiver).

## How it works
- engine.py: parser (Indian 1-0-1 notation, brand names, fuzzy spelling), interaction and duplicate checks, rule-based triage, evaluation harness.
- kb.py: curated knowledge base and translations. Every warning shown comes from here, with a DailyMed link to verify.
- Triage is deterministic rules, never LLM guesswork. Unknown or uncertain medicines are flagged "Verify with your pharmacist".
- Evaluation: `GET /api/eval` (also the Evaluation tab). Synthetic data only; no real patient information.

## Limits
Decision support only, not medical advice. The knowledge base covers 18 common drugs. Tamil and Hindi text should be reviewed by a native speaker before real use.

## Deploy (optional, for a live demo link)
Any host that runs Python works. On Render: New Web Service from your GitHub repo, build command `pip install -r requirements.txt`, start command `uvicorn app:app --host 0.0.0.0 --port $PORT`. Photo scan is an experimental extra and needs `GEMINI_API_KEY` or `ANTHROPIC_API_KEY`; the app works fully without it.
