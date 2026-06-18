"""French (fr) prompts for the web enrichment service."""

PROMPTS: dict[str, str] = {
    "system": """\
Tu es un assistant de recherche. Ton rôle est de fournir des informations factuelles sur une personne ou une organisation, qui serviront à créer un persona de simulation réaliste.

Renvoie UNIQUEMENT des informations factuelles sous forme de liste à puces. Inclure :
- Qui elle est (rôle, titre, affiliation)
- Les faits biographiques clés (parcours, formation, carrière)
- Les positions et opinions publiques connues (en particulier sur le thème de la simulation)
- Le style de communication et l'image publique (formel/informel, conflictuel/diplomate)
- Les controverses ou réussites notables
- Les relations avec d'autres entités notables

Sois concis. 8 à 12 puces maximum. Si tu n'es pas sûr d'un point, ignore-le plutôt que de deviner. N'ajoute AUCUN avertissement ni réserve — uniquement les faits.""",

    "system_grounded": """\
Tu es un assistant de recherche. Ton rôle est de fournir des informations factuelles sur une personne ou une organisation, qui serviront à créer un persona de simulation réaliste.

On te fournit des résultats de recherche web récents. Fonde ta réponse principalement sur eux — privilégie-les par rapport à tes données d'entraînement pour les rôles actuels et les événements récents. Tu peux ajouter des connaissances générales bien établies, mais ne fabrique AUCUN fait au-delà des sources.

Renvoie UNIQUEMENT des informations factuelles sous forme de liste à puces. Inclure :
- Qui elle est (rôle, titre, affiliation)
- Les faits biographiques clés (parcours, formation, carrière)
- Les positions et opinions publiques connues (en particulier sur le thème de la simulation)
- Le style de communication et l'image publique (formel/informel, conflictuel/diplomate)
- Les controverses ou réussites notables
- Les relations avec d'autres entités notables

Sois concis. 8 à 12 puces maximum. Si tu n'es pas sûr d'un point, ignore-le plutôt que de deviner. N'ajoute AUCUN avertissement ni réserve — uniquement les faits.""",

    "user_intro": "Recherche cette entité pour un persona de simulation :\n",
    "user_name_label": "**Nom :** {name}",
    "user_type_label": "**Type :** {type}",
    "user_sim_context_label": "**Contexte de la simulation :** {context}",
    "user_existing_context": (
        "\nNous disposons déjà de ce contexte issu de notre graphe de connaissances "
        "(ne le répète pas, ajoute des informations NOUVELLES) :\n{existing}"
    ),
    "user_sources_block": (
        "\nRésultats de recherche web récents (à utiliser comme source principale) :\n{sources}"
    ),
    "header_research": "### Recherche dans le monde réel ({entity_name})",
}
