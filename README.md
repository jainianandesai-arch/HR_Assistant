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
- **Reorg Scenario Planner tab** — upload an Excel list of employees in scope for a reorg and get
  Low/Moderate/High severance cost scenarios (Low = statutory minimum, High = greater of statutory
  or a common-law rule-of-thumb, Moderate = midpoint), plus an optional custom-policy column. The
  company policy is parsed by the LLM **once** per run (not once per employee) and applied
  deterministically, so bulk runs stay cheap regardless of headcount.
  - Flags mass/group termination thresholds per jurisdiction and unionized/CBA employees, so
    those cases get routed to legal/labour relations instead of the statutory calculator.
  - Every calculation includes plain-language notes explaining exactly how each number was derived.
  - Scenarios can be saved by name and reloaded later instead of re-uploading Excel each time.
  - Results download as Excel (summary + employee-level detail) or a polished one-page PDF summary.
- **Change detection** — the nightly refresh diffs each government page against the prior version;
  material changes surface in a "government source page(s) changed recently" panel in-app.
- **Cache freshness indicator** — a color-coded banner (green/amber/red) shows how old the cached
  government data is, so answers are never silently stale.
- **Forms & links directory** — a browsable and contextually-surfaced set of official forms (WSIB/
  WorkSafeBC/CNESST injury reporting, ROE, human rights complaints, etc.).
- **Audit trail** — every Q&A answer, calculation, and reorg run is logged with the full answer
  text, sources, model version, and cost, viewable from the sidebar — for compliance review if a
  number from this tool is ever relied on.
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

- The severance calculator and reorg planner's built-in statutory formulas cover all 10 provinces,
  3 territories, and federally regulated employers, but are simplified summaries — always verify
  against current legislation for an actual termination.
- The reorg planner's Low/Moderate/High scenarios are planning estimates using a simplified
  common-law rule of thumb, not a substitute for legal/actuarial review of an actual reorg.
- The query log, audit trail, and saved scenarios are local SQLite files — on Streamlit Community
  Cloud the filesystem is ephemeral and resets on redeploy (including the nightly refresh commit),
  so this data persists for the life of a running instance rather than forever.
- No authentication/access control — anyone with the app URL can run calculations. Add SSO/auth
  before using this beyond an internal pilot.
- The forms/links directory currently covers the most commonly needed jurisdictions (ON, QC, BC,
  AB, MB, SK, NS, NB, NL, Federal); PE/YT/NT/NU can be added to `data/forms.json`.

## Disclaimer

This tool provides general information sourced from official government sites and simplified
statutory formulas. It is not legal advice. Confirm high-stakes or ambiguous situations with
employment counsel.
