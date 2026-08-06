"""Minimal EN/FR toggle for the app's primary chrome (titles, tab labels, key captions) and for
steering the LLM's response language. This is a partial translation — deep widget labels inside
the calculator/reorg planner forms remain English-only; see README known limitations.
"""

STRINGS = {
    "app_title": {"en": "🍁 Canada HR Employment Standards Assistant", "fr": "🍁 Assistant des normes d'emploi RH Canada"},
    "app_caption": {
        "en": "Ask about employment standards, workplace injury/disability, or severance across any "
              "Canadian province or territory. Grounded in official government sources, refreshed nightly.",
        "fr": "Posez des questions sur les normes d'emploi, les accidents du travail/l'invalidité ou "
              "l'indemnité de départ pour toute province ou tout territoire canadien. Réponses fondées "
              "sur des sources gouvernementales officielles, actualisées chaque nuit.",
    },
    "tab_qa": {"en": "💬 Ask a Question", "fr": "💬 Poser une question"},
    "tab_calculator": {"en": "🧮 Severance Calculator", "fr": "🧮 Calculateur d'indemnité de départ"},
    "tab_reorg": {"en": "🏗️ Reorg Scenario Planner", "fr": "🏗️ Planificateur de scénarios de réorganisation"},
    "tab_forms": {"en": "📋 Forms & Guides", "fr": "📋 Formulaires et guides"},
    "chat_placeholder": {
        "en": "e.g. What is the minimum severance notice in Ontario vs. Quebec?",
        "fr": "ex. Quel est le préavis minimal en Ontario par rapport au Québec?",
    },
    "disclaimer": {
        "en": "This tool provides general information and simplified statutory formulas. It is not "
              "legal advice. Confirm high-stakes or ambiguous situations with employment counsel.",
        "fr": "Cet outil fournit des renseignements généraux et des formules légales simplifiées. Il "
              "ne s'agit pas d'un avis juridique. Confirmez toute situation à enjeux élevés ou ambiguë "
              "auprès d'un conseiller juridique en droit du travail.",
    },
}


def t(key: str, lang: str) -> str:
    entry = STRINGS.get(key, {})
    return entry.get(lang, entry.get("en", key))


LANGUAGE_INSTRUCTION = {
    "en": "Respond in English unless the user writes in French, in which case respond in French.",
    "fr": "Réponds en français par défaut, sauf si l'utilisateur écrit en anglais — dans ce cas, "
          "réponds en anglais.",
}
