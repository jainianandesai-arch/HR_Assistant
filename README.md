# Canada HR Employment Standards Assistant

A Streamlit app for HRBP leaders covering Canadian employment standards, minimum wage, workplace
injury/disability, and severance/termination across all provinces, territories, and federally
regulated employers.

- **Q&A tab** — grounded in a nightly-refreshed cache of official government pages (Ministry of
  Labour, ESA, WSIB/WCB/CNESST, human rights tribunals). Falls back to live web search only when the
  cache doesn't cover the question, to keep per-query cost down.
- **Severance Calculator tab** — computes the statutory minimum notice/severance for a given
  jurisdiction and years of service, then optionally reconciles it against an uploaded/pasted
  company policy (the employee is always entitled to whichever is greater).
- Every query is logged locally (`data/query_log.sqlite3`) for cost and usage-pattern visibility
  (sidebar shows total queries, cache hit rate, most-asked jurisdictions).

## Run locally (VS Code)

1. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. Provide your Anthropic API key — copy `.streamlit/secrets.toml.example` to
   `.streamlit/secrets.toml` and fill it in, or set the `ANTHROPIC_API_KEY` environment variable.
3. (Optional) Seed/refresh the government source cache:
   ```bash
   python scripts/refresh_knowledge.py
   ```
4. Run the app:
   ```bash
   streamlit run app.py
   ```

## Deploy on Streamlit Community Cloud

1. Push this repo to GitHub.
2. On https://share.streamlit.io, create a new app pointing at this repo and `app.py`.
3. In the app's **Settings → Secrets**, add:
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-..."
   ```
4. The app has no separate API-key input field — it only reads from Secrets/env, by design.

## Nightly data refresh

`.github/workflows/refresh.yml` runs daily (09:00 UTC) via GitHub Actions: it fetches the official
pages listed in `data/sources.json`, writes `data/knowledge_cache.json`, and commits the update.
Streamlit Cloud auto-redeploys on every push to `main`, so the app always reflects the latest
refresh. The app's banner shows the cache's last-refreshed timestamp. Run
`python scripts/refresh_knowledge.py` manually to test or force a refresh.

Some source URLs in `data/sources.json` may 404 or block bot traffic over time — the refresh script
skips failures gracefully and the app falls back to live web search for anything not cached. Check
the workflow logs / script output periodically and fix stale URLs there.

## Known limitations

- The severance calculator's built-in statutory formulas cover Ontario, British Columbia, Alberta,
  Quebec, and federally regulated employers only; other provinces/territories should use the Q&A tab.
- The query log is a local SQLite file — on Streamlit Community Cloud the filesystem is ephemeral
  and resets on redeploy (including the nightly refresh commit), so usage analytics reset
  periodically rather than accumulating forever.

## Disclaimer

This tool provides general information sourced from official government sites and simplified
statutory formulas. It is not legal advice. Confirm high-stakes or ambiguous situations with
employment counsel.
