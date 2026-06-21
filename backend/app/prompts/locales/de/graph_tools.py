"""Deutsche Prompts für die Graph-Tools (Sub-Query-Zerlegung, Interview-Pipeline)."""

PROMPTS: dict[str, str] = {
    # --- Sub-Query-Zerlegung -----------------------------------------
    "subquery_system": """\
Du bist ein professioneller Fraganalyse-Experte. Deine Aufgabe ist es, eine komplexe Frage in mehrere Teilfragen zu zerlegen, die in einer simulierten Welt unabhängig voneinander beobachtet werden können.

Anforderungen:
1. Jede Teilfrage soll konkret genug sein, um verwandtes Agenten-Verhalten oder Ereignisse in der simulierten Welt zu finden
2. Die Teilfragen sollen verschiedene Dimensionen der ursprünglichen Frage abdecken (z. B. Wer, Was, Warum, Wie, Wann, Wo)
3. Die Teilfragen sollen für das Simulationsszenario relevant sein
4. Ausgabe im JSON-Format: {{"sub_queries": ["Teilfrage 1", "Teilfrage 2", ...]}}""",

    "subquery_user": """\
Hintergrundinformation zur Simulationsanforderung:
{simulation_requirement}

{report_context_block}

Bitte zerlege die folgende Frage in {max_queries} Teilfragen:
{query}

Gib die Teilfragen als JSON-Liste zurück.""",

    "subquery_user_report_context": "Berichtskontext: {report_context}",

    # --- Auswahl der Interview-Agenten -------------------------------
    "interview_select_system": """\
Du bist ein professioneller Interview-Planungsexperte. Deine Aufgabe ist es, aus der Liste der simulierten Agenten die am besten geeigneten für ein Interview auszuwählen, basierend auf den Interviewanforderungen.

Auswahlkriterien:
1. Die Identität/der Beruf des Agenten ist für das Interviewthema relevant
2. Der Agent kann einzigartige oder wertvolle Perspektiven einbringen
3. Wähle diverse Perspektiven (z. B. Befürworter, Gegner, Neutrale, Experten usw.)
4. Bevorzuge Rollen, die direkt mit dem Ereignis zusammenhängen

Ausgabe im JSON-Format:
{{
    "selected_indices": [Liste der Indizes der ausgewählten Agenten],
    "reasoning": "Begründung der Auswahlentscheidung"
}}""",

    "interview_select_user": """\
Interviewanforderung:
{interview_requirement}

Simulationshintergrund:
{simulation_background}

Verfügbare Agenten ({total} insgesamt):
{agents_list}

Wähle bis zu {max_agents} Agenten aus. Gib deren Indizes zurück.""",

    "interview_select_no_background": "Nicht angegeben",
    "interview_select_default_reasoning": "Automatisch anhand der Relevanz ausgewählt",
    "interview_select_default_strategy": "Standardauswahlstrategie wird verwendet",

    # --- Generator für Interviewfragen --------------------------------
    "interview_questions_system": """\
Du bist ein professioneller Journalist/Interviewer. Generiere basierend auf den Interviewanforderungen 3 bis 5 tiefgründige Interviewfragen.

Anforderungen an die Fragen:
1. Offene Fragen, die zu ausführlichen Antworten anregen
2. Fragen, die für verschiedene Rollen unterschiedliche Antworten liefern können
3. Abdeckung mehrerer Dimensionen: Fakten, Standpunkte, Gefühle usw.
4. Natürliche Sprache, wie in echten Interviews
5. Jede Frage soll unter 50 Zeichen lang sein, prägnant und klar
6. Direkt fragen, keine Hintergrunderklärungen oder Präfixe

Ausgabe im JSON-Format: {{"questions": ["Frage 1", "Frage 2", ...]}}""",

    "interview_questions_user": """\
Interviewanforderung: {interview_requirement}

Simulationshintergrund: {simulation_background}

Rollen der Interviewpartner: {agent_roles}

Bitte generiere 3 bis 5 Interviewfragen.""",

    "interview_questions_default_perspective": "Was ist Ihre Meinung zu {topic}?",
    "interview_questions_default_impact": "Welche Auswirkungen hat das auf Sie oder die Gruppe, die Sie vertreten?",
    "interview_questions_default_solution": "Wie sollte dieses Problem Ihrer Meinung nach gelöst oder verbessert werden?",

    # --- Zusammenfassungsredakteur für Interviews ---------------------
    "interview_summary_system": """\
Du bist ein professioneller Nachrichtenredakteur. Erstelle eine Interviewzusammenfassung auf Grundlage der Antworten mehrerer Interviewpartner.

Anforderungen an die Zusammenfassung:
1. Extrahiere die wesentlichen Standpunkte aller Parteien
2. Zeige Übereinstimmungen und Meinungsverschiedenheiten auf
3. Hebe wertvolle Zitate hervor
4. Bleib objektiv und neutral, begünstige keine Seite
5. Halte die Zusammenfassung unter 1000 Wörtern

Formatvorgaben (verbindlich):
- Verwende reine Textabsätze, getrennt durch Leerzeilen
- Keine Markdown-Überschriften (z. B. #, ##, ###)
- Keine Trennlinien (z. B. ---, ***)
- Verwende angemessene Anführungszeichen beim Zitieren von Interviewpartnern
- **Fettdruck** zur Hervorhebung von Schlüsselwörtern ist erlaubt, andere Markdown-Syntax jedoch nicht""",

    "interview_summary_user": """\
Interviewthema: {interview_requirement}

Interviewinhalt:
{interview_content}

Bitte erstelle eine Interviewzusammenfassung.""",

    "interview_summary_no_interviews": "Keine Interviews abgeschlossen",
    "interview_summary_fallback": "{count} Interviewpartner befragt, darunter: {names}",

    # --- Einzel-Agent-Fallback-Interview (paralleler Worker) ---------
    "interview_single_agent_roleplay": """\
Du spielst in einer Simulation die folgende Figur:

{profile_desc}

Bleibe vollständig in der Rolle. Beantworte die folgenden Interviewfragen auf Grundlage deines Profils, deiner Überzeugungen und deiner Perspektive. Sei konkret und gehaltvoll. Antworte in derselben Sprache wie die Fragen.

{combined_prompt}""",
}
