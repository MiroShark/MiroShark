"""
Web Enrichment — uses the LLM to research real-world context for persona generation.

Triggers automatically when:
1. The entity looks like a notable/public figure (politician, celebrity, CEO, etc.)
2. The knowledge graph context is too thin to build a rich persona

Uses the existing LLM client (OpenRouter / OpenAI-compatible API) to research
the entity. Models with built-in web search (e.g. Perplexity sonar via
OpenRouter, or OpenAI with browsing) will return live data. Standard models
still have extensive training data on public figures.

If WEB_SEARCH_MODEL is set in .env, that model is used for research
(e.g. "perplexity/sonar-pro" for grounded web search). Otherwise falls
back to the default LLM.

Usage:
    enricher = WebEnricher()

    extra_context = enricher.enrich_if_needed(
        entity_name="Elon Musk",
        entity_type="PublicFigure",
        existing_context="CEO of Tesla and SpaceX.",  # thin
        simulation_requirement="Simulate reactions to AI regulation",
    )
    # Returns rich context string, or "" if enrichment wasn't needed/failed
"""

from __future__ import annotations

from typing import Optional

from ..config import Config
from ..prompts import get_prompt
from ..utils.i18n import get_active_locale
from ..utils.llm_client import create_llm_client, LLMClient
from ..utils.logger import get_logger

logger = get_logger("miroshark.web_enrichment")


# Entity types that are likely to be real-world figures worth searching
_NOTABLE_ENTITY_TYPES = {
    "publicfigure", "politician", "official", "celebrity", "ceo",
    "executive", "journalist", "activist", "expert", "scientist",
    "researcher", "author", "athlete", "artist", "musician",
    "entrepreneur", "investor", "regulator", "diplomat",
    "faculty", "professor",
}

# Entity types that are likely real-world organizations worth searching
_NOTABLE_ORG_TYPES = {
    "company", "mediaoutlet", "university", "governmentagency",
    "ngo", "organization", "institution", "politicalparty",
}

# Minimum context length (chars) below which we trigger enrichment
# even for non-notable entity types
_THIN_CONTEXT_THRESHOLD = 150


class WebEnricher:
    """Uses the LLM to research real-world context for entity personas.

    The LLM is treated as a knowledge base. If the configured model
    supports web search (Perplexity sonar, OpenAI with browsing, etc.),
    you get live data. Otherwise, you get training-data knowledge, which
    is still very useful for famous figures.
    """

    def __init__(self):
        self.enabled = Config.WEB_ENRICHMENT_ENABLED
        self._llm: Optional[LLMClient] = None
        self._cache: dict = {}  # entity_name_lower -> result string

    def _get_llm(self) -> LLMClient:
        """Create an LLM client per call for thread-safe parallel use."""
        # Use dedicated search model if configured, otherwise default LLM
        search_model = Config.WEB_SEARCH_MODEL
        if search_model:
            logger.info(f"Web enrichment using search model: {search_model}")
            return create_llm_client(model=search_model)
        return create_llm_client()

    def should_enrich(
        self,
        entity_name: str,
        entity_type: str,
        existing_context: str,
    ) -> bool:
        """Decide whether web enrichment is warranted.

        Returns True if:
        - Entity type is a known notable type (public figures, orgs)
        - OR the existing context from the knowledge graph is thin
        """
        if not self.enabled:
            return False

        et = entity_type.lower().replace(" ", "")

        # Notable figures/orgs always get enriched
        if et in _NOTABLE_ENTITY_TYPES or et in _NOTABLE_ORG_TYPES:
            return True

        # Thin context — not enough material to build a good persona
        if len(existing_context.strip()) < _THIN_CONTEXT_THRESHOLD:
            return True

        return False

    def enrich_if_needed(
        self,
        entity_name: str,
        entity_type: str,
        existing_context: str,
        simulation_requirement: str = "",
    ) -> str:
        """Check if enrichment is needed, and if so, research via LLM.

        Returns a formatted context string, or "" if not needed or failed.
        """
        if not self.should_enrich(entity_name, entity_type, existing_context):
            return ""

        # Check cache first (same entity = same research)
        cache_key = entity_name.lower().strip()
        if cache_key in self._cache:
            logger.info(f"Web enrichment cache hit for: {entity_name}")
            return self._cache[cache_key]

        logger.info(f"Web enrichment triggered for: {entity_name} ({entity_type})")

        result = self._research(
            entity_name, entity_type, simulation_requirement, existing_context,
        )
        if not result:
            logger.info(f"No enrichment result for: {entity_name}")
            self._cache[cache_key] = ""
            return ""

        logger.info(
            f"Web enrichment for {entity_name}: {len(result)} chars"
        )
        self._cache[cache_key] = result
        return result

    # Cap the simulation_requirement copy in entity-research prompts so a
    # multi-KB user briefing doesn't get pasted into every research call.
    # The model only needs a couple hundred tokens of "what's this sim
    # about" to ground per-entity research; anything more is wasted input.
    # Previous Langfuse traces showed 60-80k input tokens per entity from
    # this leak alone.
    _SIM_REQUIREMENT_CHAR_CAP = 1500

    def _research(
        self,
        entity_name: str,
        entity_type: str,
        simulation_requirement: str,
        existing_context: str,
    ) -> str:
        """Ask the LLM to research the entity.

        The prompt is crafted to get factual, structured information that's
        useful for persona generation. If the model has web search, it'll
        use it. If not, it draws from training data.
        """
        locale = get_active_locale()

        # Build the research prompt
        parts = [get_prompt("web_enrichment.user_intro", locale)]
        parts.append(get_prompt("web_enrichment.user_name_label", locale, name=entity_name))
        parts.append(get_prompt("web_enrichment.user_type_label", locale, type=entity_type))

        if simulation_requirement:
            sr = simulation_requirement.strip()
            if len(sr) > self._SIM_REQUIREMENT_CHAR_CAP:
                sr = sr[: self._SIM_REQUIREMENT_CHAR_CAP].rstrip() + " […]"
            parts.append(get_prompt("web_enrichment.user_sim_context_label", locale, context=sr))

        if existing_context and len(existing_context.strip()) > 20:
            # Give the LLM what we already know so it doesn't repeat it
            truncated = existing_context[:500] if len(existing_context) > 500 else existing_context
            parts.append(get_prompt("web_enrichment.user_existing_context", locale, existing=truncated))

        user_prompt = "\n".join(parts)

        try:
            llm = self._get_llm()
            response = llm.chat(
                messages=[
                    {"role": "system", "content": get_prompt("web_enrichment.system", locale)},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=1024,
            )

            if not response or len(response.strip()) < 30:
                return ""

            # Format as context section
            header = get_prompt("web_enrichment.header_research", locale, entity_name=entity_name)
            return f"{header}\n{response.strip()}"

        except Exception as e:
            logger.warning(f"Web enrichment LLM call failed for '{entity_name}': {e}")
            return ""
