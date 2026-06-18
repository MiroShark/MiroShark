"""Deutsche Prompts für den Ontologie-Generator."""

PROMPTS: dict[str, str] = {
    "system": """\
Du bist ein Ontologie-Designer für Wissensgraphen in einem Social-Media-Simulationssystem. Gib ausschließlich gültiges JSON aus.

Entitäten repräsentieren reale Subjekte, die sich in sozialen Medien äußern können: Einzelpersonen, Unternehmen, Organisationen, Behörden, Medienunternehmen, Interessengruppen. KEINE abstrakten Konzepte, Themen oder Standpunkte.

## Ausgabeformat

```json
{{
    "entity_types": [
        {{
            "name": "PascalCase-Name",
            "description": "Kurze Beschreibung (max. 100 Zeichen)",
            "attributes": [{{"name": "snake_case", "type": "text", "description": "..."}}],
            "examples": ["Beispiel 1", "Beispiel 2"]
        }}
    ],
    "edge_types": [
        {{
            "name": "UPPER_SNAKE_CASE",
            "description": "Kurze Beschreibung (max. 100 Zeichen)",
            "source_targets": [{{"source": "Quelltyp", "target": "Zieltyp"}}],
            "attributes": []
        }}
    ],
    "analysis_summary": "Kurze Analyse des Textinhalts"
}}
```

## Regeln für Entitätstypen (STRIKT)

- Genau 10 Entitätstypen
- Die ersten 8: spezifische, aus dem Text abgeleitete Typen (z. B. Schüler, Professor, Universität für akademische Ereignisse; Unternehmen, CEO, Mitarbeiter für Wirtschaftsthemen)
- Die letzten 2 MÜSSEN Fallback-Typen sein: `Person` (beliebige Einzelperson) und `Organization` (beliebige Organisation)
- Jeder Typ benötigt 1–3 Attribute. Reservierte Attributnamen (NICHT verwenden): name, uuid, group_id, created_at, summary. Verwende stattdessen full_name, title, role, position usw.
- Spezifische Typen müssen klare, nicht überlappende Grenzen haben

## Regeln für Beziehungstypen

- 6–10 Beziehungstypen, die soziale Medieninteraktionen widerspiegeln
- source_targets müssen auf deine definierten Entitätstypen verweisen
- Referenztypen: WORKS_FOR, STUDIES_AT, AFFILIATED_WITH, REPRESENTS, REGULATES, REPORTS_ON, COMMENTS_ON, RESPONDS_TO, SUPPORTS, OPPOSES, COLLABORATES_WITH, COMPETES_WITH

HINWEIS: Verwende stets ASCII-Bezeichner für `name`-Felder. Typnamen müssen gültige Python-Bezeichner sein (PascalCase für Entitäten, UPPER_SNAKE_CASE für Beziehungen). Beschreibungen und Beispiele dürfen die Sprache des Nutzers verwenden.""",

    "user_intro": """\
## Simulationsanforderung

{simulation_requirement}

## Dokumentinhalt

{combined_text}
""",

    "user_truncation_note": """

...(Originaltext hat {original_length} Zeichen; die ersten {max_length} Zeichen wurden für die Ontologieanalyse extrahiert)...""",

    "user_additional_context": """
## Zusätzliche Hinweise

{additional_context}
""",

    "user_outro": """
Entwerfe auf Grundlage der obigen Inhalte Entitätstypen und Beziehungstypen, die für die Simulation öffentlicher Meinungen in sozialen Medien geeignet sind.

**Verbindlich einzuhaltende Regeln**:
1. Es müssen genau 10 Entitätstypen ausgegeben werden
2. Die letzten 2 müssen Fallback-Typen sein: Person (Fallback für Einzelpersonen) und Organization (Fallback für Organisationen)
3. Die ersten 8 sind spezifische Typen, die auf Basis des Textinhalts entworfen werden
4. Alle Entitätstypen müssen reale Subjekte sein, die sich äußern können – keine abstrakten Konzepte
5. Attributnamen dürfen keine reservierten Wörter wie name, uuid, group_id usw. verwenden; stattdessen full_name, org_name usw. nutzen
""",
}
