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
  - Flags mass/group termination thresholds per jurisdiction, unionized/CBA employees, fixed-term
    contracts, and possible industry exclusions — so those cases get routed to legal/labour
    relations instead of the statutory calculator giving a false-confidence number.
  - Every calculation includes plain-language notes explaining exactly how each number was derived.
  - Scenarios live for the browser session — build and iterate freely, no save step required.
    When finalized, download the full scenario as a self-contained PDF (methodology, totals,
    flags, and employee-level detail) or as Excel for further analysis.
- **Change detection** — the nightly refresh diffs each government page against the prior version;
  material changes surface in a "government source page(s) changed recently" panel in-app.
- **Cache freshness indicator** — a color-coded banner (green/amber/red) shows how old the cached
  government data is, so answers are never silently stale.
- **Forms & Guides tab** — a dedicated tab for new HRBPs: pick a situation (workplace injury,
  termination, leave of absence, human rights concern) and a jurisdiction, and get the steps in
  order with the correct official form linked exactly where it's needed (plus reporting deadlines
  where known, e.g. "WSIB requires the employer's report within 3 days"). Also includes a
  browsable directory of all official forms (WSIB/WorkSafeBC/CNESST injury reporting, ROE, human
  rights complaints, etc.), and relevant forms are surfaced inline in Q&A answers too.
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

## Durable storage (optional but recommended for production)

By default, the audit trail and query log live in a local SQLite file (`data/app.sqlite3`) — fine
for local dev, but Streamlit Community Cloud's filesystem is ephemeral and resets on every
redeploy (including the nightly refresh commit), so that history doesn't persist long-term.

To make it durable, create a free Postgres database (e.g. [Supabase](https://supabase.com) or
[Neon](https://neon.tech)) and add its connection string to **Settings → Secrets**:
```toml
DATABASE_URL = "postgresql://user:password@host:5432/dbname"
```
`backend/db.py` automatically switches to Postgres when this is set — no code changes needed.

Reorg scenarios themselves are intentionally session-only (not persisted) — build, customize, and
download as PDF/Excel within a session rather than saving to a database.

## Nightly data refresh

`.github/workflows/refresh.yml` runs daily (09:00 UTC) via GitHub Actions: it fetches the official
pages listed in `data/sources.json`, writes `data/knowledge_cache.json`, and commits the update.
Streamlit Cloud auto-redeploys on every push to `main`, so the app always reflects the latest
refresh. The app's banner shows the cache's last-refreshed timestamp. Run
`python scripts/refresh_knowledge.py` manually to test or force a refresh.

Some source URLs in `data/sources.json` may 404 or block bot traffic over time — the refresh script
skips failures gracefully and the app falls back to live web search for anything not cached. Check
the workflow logs / script output periodically and fix stale URLs there.

### Optional: Slack/Teams notification on page changes

The refresh script diffs each page against its previous version and, when a material change is
detected, can post a summary to a Slack or Microsoft Teams incoming webhook. This is separate from
the app's own `ANTHROPIC_API_KEY`/`DATABASE_URL` secrets — it's a **GitHub Actions secret**, since
the nightly job runs outside the Streamlit app:

1. Create an incoming webhook in Slack ([guide](https://api.slack.com/messaging/webhooks)) or Teams.
2. In this repo on GitHub: **Settings → Secrets and variables → Actions → New repository secret**,
   name it `CHANGE_NOTIFY_WEBHOOK_URL`, and paste the webhook URL.
3. No code changes needed — the workflow picks it up automatically on the next scheduled run.

Without this secret set, change detection still works and still shows in the app's banner; you
just won't get a push notification outside the app.

## Language

A language toggle (sidebar) switches the app's main chrome (titles, tab labels, chat placeholder)
between English and French, and instructs Claude to answer in the selected language (while still
honoring whichever language the user actually types in). This is a **partial** translation — form
field labels inside the calculator and reorg planner remain English-only, and the underlying
government source cache is fetched from English-language pages, so French answers are Claude's
translation of that content rather than sourced from native French government pages (relevant for
Quebec/CNESST content in particular).

## Known limitations

- The severance calculator and reorg planner's built-in statutory formulas cover all 10 provinces,
  3 territories, and federally regulated employers, but are simplified summaries — always verify
  against current legislation for an actual termination.
- The reorg planner's Low/Moderate/High scenarios are planning estimates using a simplified
  common-law rule of thumb, not a substitute for legal/actuarial review of an actual reorg.
- Without `DATABASE_URL` configured, the query log and audit trail live in a local SQLite file —
  on Streamlit Community Cloud the filesystem is ephemeral and resets on redeploy, so this data
  persists for the life of a running instance rather than forever. See "Durable storage" above.
- Reorg scenarios are session-only by design — closing the tab or refreshing loses in-progress
  work, so download the PDF/Excel before navigating away once a scenario is finalized.
- No authentication/access control — anyone with the app URL can run calculations. Add SSO/auth
  before using this beyond an internal pilot.
- UI translation is partial — see "Language" above.

## Disclaimer

This tool provides general information sourced from official government sites and simplified
statutory formulas. It is not legal advice. Confirm high-stakes or ambiguous situations with
employment counsel.
