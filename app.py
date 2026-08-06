import os

import anthropic
import streamlit as st

st.set_page_config(page_title="Canada HR Employment Standards Assistant", page_icon="🍁", layout="centered")

MODEL = "claude-sonnet-4-5"

SYSTEM_PROMPT = """You are an assistant for HR Business Partner (HRBP) leaders researching Canadian \
employment standards, workplace injury/disability, and severance/termination questions across all \
provinces and territories (ON, QC, BC, AB, MB, SK, NS, NB, PE, NL, YT, NT, NU) as well as federally \
regulated employers.

Rules:
- Always ground your answer in current information from official government sources. Use the web \
search tool to look up the relevant provincial/territorial (or federal) Ministry of Labour, \
Employment Standards, Workers' Compensation Board (WCB/WSIB/CNESST/WorkSafeBC etc.), or Human Rights \
authority page before answering.
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
    "max_uses": 5,
}


def get_client() -> anthropic.Anthropic:
    api_key = (
        st.session_state.get("api_key")
        or st.secrets.get("ANTHROPIC_API_KEY", None)
        or os.environ.get("ANTHROPIC_API_KEY")
    )
    if not api_key:
        st.error("Enter your Anthropic API key in the sidebar to get started.")
        st.stop()
    return anthropic.Anthropic(api_key=api_key)


def render_sidebar() -> None:
    with st.sidebar:
        st.header("Settings")
        default_key = st.secrets.get("ANTHROPIC_API_KEY", None) or os.environ.get("ANTHROPIC_API_KEY", "")
        st.session_state["api_key"] = st.text_input(
            "Anthropic API key",
            value=st.session_state.get("api_key", default_key),
            type="password",
            help="Stored only for this session. Set ANTHROPIC_API_KEY as an env var / Streamlit secret to skip this.",
        )
        st.divider()
        st.caption(
            "Covers employment standards, workplace injury/disability, and severance/termination "
            "questions for all Canadian provinces, territories, and federally regulated employers."
        )
        if st.button("Clear conversation"):
            st.session_state["messages"] = []
            st.rerun()


def main() -> None:
    st.title("🍁 Canada HR Employment Standards Assistant")
    st.caption(
        "Ask about employment standards, workplace injury/disability, or severance across any "
        "Canadian province or territory. Answers are grounded in live searches of official government sources."
    )

    render_sidebar()

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

    with st.chat_message("assistant"):
        placeholder = st.empty()
        placeholder.markdown("Searching official government sources...")
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=2000,
                system=SYSTEM_PROMPT,
                tools=[WEB_SEARCH_TOOL],
                messages=[
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state["messages"]
                ],
            )
        except anthropic.APIError as e:
            placeholder.error(f"API error: {e}")
            st.session_state["messages"].pop()
            return

        answer_text = "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        )
        placeholder.markdown(answer_text)

    st.session_state["messages"].append({"role": "assistant", "content": answer_text})


if __name__ == "__main__":
    main()
