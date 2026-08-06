import os
from datetime import date, datetime, timezone

import anthropic
import streamlit as st

from backend import document_extract, knowledge, query_log, severance_rules

st.set_page_config(
    page_title="Canada HR Employment Standards Assistant",
    page_icon="🍁",
    layout="centered",
    initial_sidebar_state="collapsed",
)

MODEL = "claude-sonnet-4-5"

BASE_SYSTEM_PROMPT = """You are an assistant for HR Business Partner (HRBP) leaders researching Canadian \
employment law and workplace standards across all provinces and territories (ON, QC, BC, AB, MB, SK, \
NS, NB, PE, NL, YT, NT, NU) as well as federally regulated employers. You should be able to answer any \
HRBP question in this space, including but not limited to:
- Minimum wage (general, student, liquor server, and other special rates) and scheduled increases
- Hours of work, overtime rules and exemptions, breaks, and scheduling
- Vacation pay, vacation time, general holidays/statutory holidays
- Leaves of absence: sick leave, parental/maternity leave, family/caregiver leave, bereavement, \
domestic violence leave, reservist leave, etc.
- Workplace injury, occupational disease, and workers' compensation (claims process, wage-loss \
benefits, return-to-work obligations, employer reporting duties)
- Disability accommodation (short/long-term disability, duty to accommodate, undue hardship) under \
human rights law
- Termination and severance: statutory notice/pay in lieu, common-law reasonable notice, mass \
termination rules, group terminations, just-cause standards, ROE obligations
- Human rights and workplace harassment/violence prevention obligations
- Occupational health and safety (OHS) obligations, joint health and safety committees
- Pay equity and equal pay rules where applicable
- Independent contractor vs. employee classification

Rules:
- You will usually be given OFFICIAL SOURCE CONTEXT below, pulled from a nightly refresh of official \
government pages. Prefer answering from that context and cite it.
- Only use the web_search tool if the provided context is missing, insufficient, or clearly does not \
cover the jurisdiction/topic asked about. Do not search when the context already answers the question.
- Always state which jurisdiction(s) your answer applies to. If the user doesn't specify a province, \
ask which province/territory (or say you're covering the most common ones) before giving a definitive \
answer, or clearly summarize how the rule differs by province.
- Cite your sources with links so the HRBP can verify and share with legal/compliance.
- Clearly distinguish employment standards minimums (statutory) from common-law entitlements (e.g. \
severance/reasonable notice), and note when a topic depends on case law rather than a statute.
- This is not legal advice. Include a brief reminder to confirm with employment counsel for \
high-stakes or ambiguous situations.
- Be concise and structured (bullet points, tables for cross-province comparisons) since HRBPs need \
quick, actionable answers.
"""

WEB_SEARCH_TOOL = {
    "type": "web_search_20250305",
    "name": "web_search",
    "max_uses": 3,
}

# Pricing (USD) — check https://www.anthropic.com/pricing before relying on this for budgeting.
PRICE_PER_MTOK_INPUT = 3.00
PRICE_PER_MTOK_OUTPUT = 15.00
PRICE_PER_1K_SEARCHES = 10.00

CONTEXT_WARNING_TOKENS = 60_000
HISTORY_TURNS_KEPT = 6  # user+assistant pairs resent per call, to cap per-turn cost

CUSTOM_CSS = """
<style>
:root {
    --navy: #0b1f3a;
    --gold: #b98b2a;
    --paper: #fbfaf7;
}
html, body, [class*="css"] { font-family: "Georgia", "Iowan Old Style", serif; }
h1, h2, h3 { font-family: "Helvetica Neue", Arial, sans-serif; color: var(--navy); letter-spacing: -0.01em; }
.stApp { background-color: var(--paper); }
.hra-banner {
    background: var(--navy);
    color: #f4efe4;
    padding: 0.6rem 1rem;
    border-radius: 6px;
    font-family: "Helvetica Neue", Arial, sans-serif;
    font-size: 0.85rem;
    margin-bottom: 1rem;
    display: flex;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 0.5rem;
}
.hra-banner b { color: var(--gold); }
[data-testid="stChatMessage"] {
    border: 1px solid #e4dfd2;
    border-radius: 10px;
    background: #ffffff;
}
.stCaption, [data-testid="stCaptionContainer"] { font-family: "Helvetica Neue", Arial, sans-serif; }
section[data-testid="stSidebar"] {
    background: var(--navy);
}
section[data-testid="stSidebar"] * { color: #f4efe4 !important; }
section[data-testid="stSidebar"] .stTextInput input { color: #0b1f3a !important; }
</style>
"""


def get_secret(key: str) -> str | None:
    try:
        return st.secrets.get(key, None)
    except Exception:
        return None


def get_client() -> anthropic.Anthropic:
    api_key = get_secret("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        st.error(
            "No Anthropic API key configured. On Streamlit Cloud, add it under "
            "**Settings → Secrets** as `ANTHROPIC_API_KEY = \"sk-ant-...\"`. Locally, set it in "
            "`.streamlit/secrets.toml` or the `ANTHROPIC_API_KEY` environment variable."
        )
        st.stop()
    return anthropic.Anthropic(api_key=api_key)


def extract_web_citations(response) -> list[tuple[str, str]]:
    seen: dict[str, str] = {}
    for block in response.content:
        for citation in getattr(block, "citations", None) or []:
            url = getattr(citation, "url", None)
            if url and url not in seen:
                seen[url] = getattr(citation, "title", None) or ""
    return [(title, url) for url, title in seen.items()]


def freshness_banner() -> None:
    refreshed = knowledge.refreshed_at()
    if refreshed:
        dt = datetime.fromisoformat(refreshed)
        age_hours = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
        age_label = "today" if age_hours < 24 else f"{int(age_hours // 24)}d ago"
        label = f"Government source data refreshed <b>{dt.strftime('%Y-%m-%d %H:%M UTC')}</b> ({age_label})"
    else:
        label = "<b>No cached source data yet</b> — run scripts/refresh_knowledge.py, answers will use live search"
    stats = query_log.summary()
    st.markdown(
        f'<div class="hra-banner"><span>{label}</span>'
        f'<span>{stats["total_queries"]} queries logged · '
        f'{stats["cache_hit_rate"]*100:.0f}% answered from cache</span></div>',
        unsafe_allow_html=True,
    )


def render_sidebar() -> None:
    with st.sidebar:
        st.header("About")
        st.caption(
            "Covers employment standards, workplace injury/disability, and severance/termination "
            "questions for all Canadian provinces, territories, and federally regulated employers."
        )
        if st.button("Clear conversation"):
            st.session_state["messages"] = []
            st.rerun()

        st.divider()
        st.subheader("Usage insights")
        stats = query_log.summary()
        c1, c2 = st.columns(2)
        c1.metric("Queries", stats["total_queries"])
        c2.metric("Est. cost", f"${stats['total_cost']:.2f}")
        if stats["top_jurisdictions"]:
            st.caption("Most-asked jurisdictions")
            for jur, count in stats["top_jurisdictions"]:
                st.write(f"{jur}: {count}")


def render_qa_tab() -> None:
    if "messages" not in st.session_state:
        st.session_state["messages"] = []

    for msg in st.session_state["messages"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    question = st.chat_input("e.g. What is the minimum severance notice in Ontario vs. Quebec?")
    if not question:
        return

    st.session_state["messages"].append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    client = get_client()

    jurisdictions = knowledge.detect_jurisdictions(question)
    pages = knowledge.retrieve(question)
    context_text = knowledge.format_context(pages)
    system_prompt = BASE_SYSTEM_PROMPT
    if context_text:
        system_prompt += f"\n\nOFFICIAL SOURCE CONTEXT (refreshed {knowledge.refreshed_at()}):\n\n{context_text}"

    history = st.session_state["messages"][-(HISTORY_TURNS_KEPT * 2):]

    with st.chat_message("assistant"):
        placeholder = st.empty()
        placeholder.markdown("Checking cached government sources...")
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=2000,
                system=system_prompt,
                tools=[WEB_SEARCH_TOOL],
                messages=[{"role": m["role"], "content": m["content"]} for m in history],
            )
        except anthropic.APIError as e:
            placeholder.error(f"API error: {e}")
            st.session_state["messages"].pop()
            return

        answer_text = "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        )

        usage = response.usage
        num_searches = getattr(getattr(usage, "server_tool_use", None), "web_search_requests", 0) or 0
        used_web_search = num_searches > 0

        if used_web_search:
            sources = extract_web_citations(response)
        else:
            sources = [(p["topic"] + f" ({p['jurisdiction']})", p["url"]) for p in pages[:4]]

        if sources:
            answer_text += "\n\n**Sources:**\n" + "\n".join(
                f"- [{title or url}]({url})" for title, url in sources
            )
        placeholder.markdown(answer_text)

        cost = (
            usage.input_tokens * PRICE_PER_MTOK_INPUT / 1_000_000
            + usage.output_tokens * PRICE_PER_MTOK_OUTPUT / 1_000_000
            + num_searches * PRICE_PER_1K_SEARCHES / 1_000
        )
        total_tokens = usage.input_tokens + usage.output_tokens
        st.caption(
            f"~${cost:.4f} this turn · {usage.input_tokens:,} input / {usage.output_tokens:,} output tokens "
            f"· {'live web search' if used_web_search else 'answered from cache'}"
        )
        if total_tokens > CONTEXT_WARNING_TOKENS:
            st.warning(
                "This conversation is getting long. Consider **Clear conversation** in the sidebar "
                "before starting a new topic to keep costs and latency down."
            )

        query_log.log_query(
            question=question,
            jurisdictions=jurisdictions,
            used_web_search=used_web_search,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            num_searches=num_searches,
            cost_usd=cost,
        )

    st.session_state["messages"].append({"role": "assistant", "content": answer_text})


SEVERANCE_SYSTEM_PROMPT = """You are helping an HRBP reconcile a company severance/termination policy \
against the statutory minimum for a Canadian jurisdiction.

You will be given:
1. The statutory (legislative) minimum notice/severance already calculated by a rules engine — this is \
a hard floor. Never suggest a figure below it.
2. Employee details (years of service, jurisdiction, pay).
3. The company's policy text (typed or extracted from an uploaded document).

Your job:
- Read the policy text and extract any formula/entitlement it defines for termination notice, pay in \
lieu, or severance (e.g. "2 weeks per year of service", tiered by role/level, etc.).
- Calculate what the policy would provide for this employee.
- Compare it to the statutory minimum provided. The employee is entitled to whichever is GREATER — \
state this explicitly.
- If the policy is silent, ambiguous, or you can't confidently extract a formula, say so plainly and \
recommend defaulting to the statutory minimum plus common-law considerations, verified with legal/comp.
- Do not fabricate a policy provision that isn't in the text provided.
- Keep the answer short and structured: Policy-based entitlement, Statutory minimum (restate), Greater \
of the two (recommended payout), and any caveats.
- End with a reminder this is not legal advice and should be confirmed with employment counsel/legal.
"""


def render_calculator_tab() -> None:
    st.subheader("Legislative minimum")
    st.caption(
        "Built-in calculator currently covers Ontario, British Columbia, Alberta, Quebec, and "
        "federally regulated employers. For other provinces/territories, ask the Q&A tab."
    )

    col1, col2 = st.columns(2)
    with col1:
        jurisdiction = st.selectbox("Jurisdiction", severance_rules.SUPPORTED_JURISDICTIONS)
        hire_date = st.date_input("Hire date", value=date(date.today().year - 3, 1, 1))
    with col2:
        termination_date = st.date_input("Termination date", value=date.today())
        weekly_pay = st.number_input("Regular weekly pay ($)", min_value=0.0, value=1200.0, step=50.0)

    payroll_million = None
    if jurisdiction == "Ontario":
        payroll_million = st.number_input(
            "Employer's total Ontario payroll ($ millions)",
            min_value=0.0,
            value=1.0,
            step=0.5,
            help="Statutory severance pay (on top of notice) only applies if Ontario payroll ≥ $2.5M.",
        )

    years_of_service = max((termination_date - hire_date).days / 365.25, 0.0)
    st.metric("Years of service", f"{years_of_service:.2f}")

    result = severance_rules.calculate(jurisdiction, years_of_service, payroll_million)

    st.markdown("#### Statutory minimum result")
    if not result.supported:
        st.warning(result.notes[0])
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Notice", f"{result.notice_weeks:.1f} wks")
        c2.metric("Severance pay", f"{result.severance_weeks:.1f} wks")
        c3.metric("Total pay", f"${result.total_weeks * weekly_pay:,.0f}")
        for note in result.notes:
            st.caption(f"• {note}")
    st.caption(
        "This is a simplified statutory-minimum estimate, not legal advice. Common-law reasonable "
        "notice (for non-unionized employees without an enforceable termination clause) is often "
        "significantly higher than the statutory minimum — confirm with employment counsel."
    )

    st.divider()
    st.subheader("Customize with company policy (optional)")
    st.caption(
        "Paste or upload your company's severance/termination policy. The assistant will calculate "
        "your policy's entitlement and compare it to the statutory minimum above — the employee is "
        "always entitled to whichever is greater."
    )

    policy_text = st.text_area("Paste policy text", height=140, key="policy_text")
    uploaded = st.file_uploader("...or upload a policy document", type=["txt", "pdf", "docx"])

    combined_policy = policy_text.strip()
    if uploaded is not None:
        try:
            extracted = document_extract.extract_text(uploaded)
            combined_policy = f"{combined_policy}\n\n{extracted}".strip()
            st.success(f"Extracted {len(extracted):,} characters from {uploaded.name}.")
        except Exception as e:
            st.error(f"Couldn't read that file: {e}")

    if st.button("Calculate with company policy", disabled=not combined_policy or not result.supported):
        client = get_client()
        user_prompt = (
            f"Jurisdiction: {jurisdiction}\n"
            f"Years of service: {years_of_service:.2f}\n"
            f"Weekly pay: ${weekly_pay:,.2f}\n"
            f"Statutory minimum (already calculated): {result.notice_weeks:.1f} weeks notice + "
            f"{result.severance_weeks:.1f} weeks severance = {result.total_weeks:.1f} weeks total "
            f"(${result.total_weeks * weekly_pay:,.0f}).\n\n"
            f"Company policy text:\n{combined_policy}"
        )
        with st.spinner("Reconciling company policy against the statutory minimum..."):
            try:
                response = client.messages.create(
                    model=MODEL,
                    max_tokens=1200,
                    system=SEVERANCE_SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": user_prompt}],
                )
            except anthropic.APIError as e:
                st.error(f"API error: {e}")
                return

        answer_text = "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        )
        st.markdown(answer_text)

        usage = response.usage
        cost = (
            usage.input_tokens * PRICE_PER_MTOK_INPUT / 1_000_000
            + usage.output_tokens * PRICE_PER_MTOK_OUTPUT / 1_000_000
        )
        st.caption(f"~${cost:.4f} this calculation · {usage.input_tokens:,} input / {usage.output_tokens:,} output tokens")

        query_log.log_query(
            question=f"[Severance Calculator] {jurisdiction}, {years_of_service:.1f} yrs, with policy doc",
            jurisdictions=[jurisdiction],
            used_web_search=False,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            num_searches=0,
            cost_usd=cost,
        )


def main() -> None:
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    st.title("🍁 Canada HR Employment Standards Assistant")
    st.caption(
        "Ask about employment standards, workplace injury/disability, or severance across any "
        "Canadian province or territory. Grounded in official government sources, refreshed nightly."
    )

    render_sidebar()
    freshness_banner()

    qa_tab, calc_tab = st.tabs(["💬 Ask a Question", "🧮 Severance Calculator"])
    with qa_tab:
        render_qa_tab()
    with calc_tab:
        render_calculator_tab()


if __name__ == "__main__":
    main()
