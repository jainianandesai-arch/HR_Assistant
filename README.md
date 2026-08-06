# Canada HR Employment Standards Assistant

A Streamlit chat app for HRBP leaders to ask questions about Canadian employment standards,
workplace injury/disability, and severance/termination rules across all provinces, territories,
and federally regulated employers. Answers are grounded via Claude's live web search of official
government sources (Ministry of Labour, ESA, WSIB/WCB/CNESST, human rights tribunals, etc.).

## Run locally (VS Code)

1. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. Provide your Anthropic API key, either:
   - Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and fill in the key, or
   - Set the `ANTHROPIC_API_KEY` environment variable, or
   - Paste it into the sidebar field when the app is running.
3. Run the app:
   ```bash
   streamlit run app.py
   ```

## Deploy on Streamlit Community Cloud

1. Push this repo to GitHub.
2. On https://share.streamlit.io, create a new app pointing at this repo and `app.py`.
3. In the app's **Settings > Secrets**, add:
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-..."
   ```

## Disclaimer

This tool provides general information sourced from official government sites and is not legal
advice. Confirm high-stakes or ambiguous situations with employment counsel.
