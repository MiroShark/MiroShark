"""French (fr) prompts for the ontology generator."""

PROMPTS: dict[str, str] = {
    "system": """\
Tu es concepteur d'ontologie de graphe de connaissances pour un système de simulation de réseaux sociaux. Renvoie uniquement du JSON valide.

Les entités représentent des sujets du monde réel capables de s'exprimer sur les réseaux sociaux : individus, entreprises, organisations, agences gouvernementales, médias, groupes de défense d'intérêts. PAS des concepts abstraits, des sujets ou des points de vue.

## Output Format

```json
{{
    "entity_types": [
        {{
            "name": "PascalCase name",
            "description": "Brief description (max 100 chars)",
            "attributes": [{{"name": "snake_case", "type": "text", "description": "..."}}],
            "examples": ["Example 1", "Example 2"]
        }}
    ],
    "edge_types": [
        {{
            "name": "UPPER_SNAKE_CASE",
            "description": "Brief description (max 100 chars)",
            "source_targets": [{{"source": "SourceType", "target": "TargetType"}}],
            "attributes": []
        }}
    ],
    "analysis_summary": "Brief analysis of the text content"
}}
```

## Règles sur les types d'entités (STRICT)

- Exactement 10 types d'entités
- Les 8 premiers : des types spécifiques dérivés du texte (par ex. Student, Professor, University pour des événements universitaires ; Company, CEO, Employee pour le monde de l'entreprise)
- Les 2 derniers DOIVENT être des types de repli : `Person` (tout individu) et `Organization` (toute organisation)
- Chaque type doit avoir 1 à 3 attributs. Noms d'attributs réservés (à NE PAS utiliser) : name, uuid, group_id, created_at, summary. Utilise full_name, title, role, position, etc.
- Les types spécifiques doivent avoir des frontières claires et sans recoupement

## Règles sur les types de relations

- 6 à 10 types de relations reflétant les interactions sur les réseaux sociaux
- source_targets doit référencer les types d'entités que tu as définis
- Types de référence : WORKS_FOR, STUDIES_AT, AFFILIATED_WITH, REPRESENTS, REGULATES, REPORTS_ON, COMMENTS_ON, RESPONDS_TO, SUPPORTS, OPPOSES, COLLABORATES_WITH, COMPETES_WITH

REMARQUE : émets toujours des identifiants ASCII pour les champs `name`. Les noms de types doivent être des identifiants Python valides (entités en PascalCase, relations en UPPER_SNAKE_CASE). Les descriptions et les exemples peuvent utiliser la langue de l'utilisateur.""",

    "user_intro": """\
## Simulation Requirement

{simulation_requirement}

## Document Content

{combined_text}
""",

    "user_truncation_note": """

...(Le texte original comporte {original_length} caractères ; les {max_length} premiers caractères ont été extraits pour l'analyse de l'ontologie)...""",

    "user_additional_context": """
## Notes complémentaires

{additional_context}
""",

    "user_outro": """
À partir du contenu ci-dessus, conçois des types d'entités et des types de relations adaptés à la simulation de l'opinion publique sur les réseaux sociaux.

**Règles à respecter impérativement** :
1. Produire exactement 10 types d'entités
2. Les 2 derniers doivent être des types de repli : Person (repli pour les individus) et Organization (repli pour les organisations)
3. Les 8 premiers sont des types spécifiques conçus à partir du contenu du texte
4. Tous les types d'entités doivent être des sujets du monde réel capables de s'exprimer, et non des concepts abstraits
5. Les noms d'attributs ne peuvent pas utiliser de mots réservés tels que name, uuid, group_id, etc. ; utilise plutôt full_name, org_name, etc.
""",
}
