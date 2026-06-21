"""French (fr) prompts for the graph tools (sub-query, interview pipeline)."""

PROMPTS: dict[str, str] = {
    # --- Sub-query decomposition -------------------------------------
    "subquery_system": """\
Tu es un expert professionnel de l'analyse de questions. Ta tâche est de décomposer une question complexe en plusieurs sous-questions pouvant être observées indépendamment dans un monde simulé.

Exigences :
1. Chaque sous-question doit être assez précise pour permettre de retrouver des comportements d'agents ou des événements pertinents dans le monde simulé
2. Les sous-questions doivent couvrir différentes dimensions de la question initiale (par ex. qui, quoi, pourquoi, comment, quand, où)
3. Les sous-questions doivent être pertinentes au regard du scénario de simulation
4. Renvoie au format JSON : {{"sub_queries": ["sous-question 1", "sous-question 2", ...]}}""",

    "subquery_user": """\
Contexte de l'exigence de simulation :
{simulation_requirement}

{report_context_block}

Décompose la question suivante en {max_queries} sous-questions :
{query}

Renvoie les sous-questions sous forme de liste JSON.""",

    "subquery_user_report_context": "Contexte du rapport : {report_context}",

    # --- Interview agent selection -----------------------------------
    "interview_select_system": """\
Tu es un expert professionnel de la planification d'entretiens. Ta tâche est de sélectionner, dans la liste des agents simulés, ceux qui conviennent le mieux à un entretien en fonction des exigences de celui-ci.

Critères de sélection :
1. L'identité/la profession de l'agent est pertinente par rapport au thème de l'entretien
2. L'agent peut détenir des points de vue uniques ou précieux
3. Choisis des perspectives variées (par ex. partisans, opposants, neutres, experts, etc.)
4. Privilégie les rôles directement liés à l'événement

Renvoie au format JSON :
{{
    "selected_indices": [Liste des indices des agents sélectionnés],
    "reasoning": "Explication de la logique de sélection"
}}""",

    "interview_select_user": """\
Exigence de l'entretien :
{interview_requirement}

Contexte de la simulation :
{simulation_background}

Agents disponibles ({total} au total) :
{agents_list}

Sélectionne jusqu'à {max_agents} agents. Renvoie leurs indices.""",

    "interview_select_no_background": "Non fourni",
    "interview_select_default_reasoning": "Sélectionné automatiquement selon la pertinence",
    "interview_select_default_strategy": "Utilisation de la stratégie de sélection par défaut",

    # --- Interview question generator --------------------------------
    "interview_questions_system": """\
Tu es un journaliste/intervieweur professionnel. À partir des exigences de l'entretien, génère 3 à 5 questions d'entretien approfondies.

Exigences relatives aux questions :
1. Des questions ouvertes qui invitent à des réponses détaillées
2. Des questions susceptibles d'appeler des réponses différentes selon les rôles
3. Couvrir plusieurs dimensions : faits, points de vue, ressentis, etc.
4. Un langage naturel, comme dans de vrais entretiens
5. Garde chaque question sous 50 caractères, concise et claire
6. Pose la question directement, sans explication de contexte ni préfixe

Renvoie au format JSON : {{"questions": ["question1", "question2", ...]}}""",

    "interview_questions_user": """\
Exigence de l'entretien : {interview_requirement}

Contexte de la simulation : {simulation_background}

Rôles des personnes interviewées : {agent_roles}

Génère 3 à 5 questions d'entretien.""",

    "interview_questions_default_perspective": "Quel est ton point de vue sur {topic} ?",
    "interview_questions_default_impact": "Quel impact cela a-t-il sur toi ou sur le groupe que tu représentes ?",
    "interview_questions_default_solution": "Selon toi, comment ce problème devrait-il être résolu ou amélioré ?",

    # --- Interview summary editor ------------------------------------
    "interview_summary_system": """\
Tu es un rédacteur en chef professionnel. Rédige une synthèse d'entretien à partir des réponses de plusieurs personnes interviewées.

Exigences de la synthèse :
1. Dégage les principaux points de vue de toutes les parties
2. Mets en évidence les consensus et les désaccords entre les points de vue
3. Fais ressortir les citations marquantes
4. Reste objectif et neutre, ne favorise aucun camp
5. Limite-toi à 1000 mots

Contraintes de format (à respecter impérativement) :
- Utilise des paragraphes en texte brut, séparés par des lignes vides
- N'utilise pas de titres Markdown (par ex. #, ##, ###)
- N'utilise pas de séparateurs (par ex. ---, ***)
- Utilise des guillemets appropriés lorsque tu cites une personne interviewée
- Tu peux utiliser **gras** pour marquer des mots-clés, mais n'utilise aucune autre syntaxe Markdown""",

    "interview_summary_user": """\
Sujet de l'entretien : {interview_requirement}

Contenu de l'entretien :
{interview_content}

Rédige une synthèse de l'entretien.""",

    "interview_summary_no_interviews": "Aucun entretien réalisé",
    "interview_summary_fallback": "{count} personnes interviewées, dont : {names}",

    # --- Entretien de repli pour un seul agent (worker parallèle) ----
    "interview_single_agent_roleplay": """\
Tu incarnes le personnage suivant dans une simulation :

{profile_desc}

Reste pleinement dans le personnage. Réponds aux questions d'entretien suivantes en t'appuyant sur ton profil, tes convictions et ton point de vue. Sois précis et substantiel. Réponds dans la même langue que les questions.

{combined_prompt}""",
}
