"""
Ontology generation service
Interface 1: Analyze text content to generate entity and relationship type definitions suitable for social simulation
"""

from typing import Dict, Any, List, Optional
from ..prompts import get_prompt
from ..utils.i18n import get_active_locale
from ..utils.llm_client import LLMClient, create_smart_llm_client


class OntologyGenerator:
    """
    Ontology Generator
    Analyzes text content to generate entity and relationship type definitions
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or create_smart_llm_client()

    def generate(
        self,
        document_texts: List[str],
        simulation_requirement: str,
        additional_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate ontology definition

        Args:
            document_texts: List of document texts
            simulation_requirement: Simulation requirement description
            additional_context: Additional context

        Returns:
            Ontology definition (entity_types, edge_types, etc.)
        """
        locale = get_active_locale()

        # Build user message
        user_message = self._build_user_message(
            document_texts,
            simulation_requirement,
            additional_context,
            locale=locale,
        )

        messages = [
            {"role": "system", "content": get_prompt("ontology.system", locale)},
            {"role": "user", "content": user_message}
        ]

        # Call LLM (8K tokens to avoid truncation with verbose/thinking models)
        result = self.llm_client.chat_json(
            messages=messages,
            temperature=0.3,
            max_tokens=8192
        )

        # Validate and post-process
        result = self._validate_and_process(result)

        return result

    # Maximum text length sent to LLM (20,000 characters)
    # Most signal is in the first portion; reducing from 50K cuts inference
    # tokens by ~60% with negligible quality loss for ontology design.
    MAX_TEXT_LENGTH_FOR_LLM = 20000

    def _build_user_message(
        self,
        document_texts: List[str],
        simulation_requirement: str,
        additional_context: Optional[str],
        locale: str = "en",
    ) -> str:
        """Build user message"""

        # Merge texts
        combined_text = "\n\n---\n\n".join(document_texts)
        original_length = len(combined_text)

        # If text exceeds the limit, truncate (only affects content sent to LLM, does not affect graph building)
        if len(combined_text) > self.MAX_TEXT_LENGTH_FOR_LLM:
            combined_text = combined_text[:self.MAX_TEXT_LENGTH_FOR_LLM]
            combined_text += get_prompt(
                "ontology.user_truncation_note",
                locale,
                original_length=original_length,
                max_length=self.MAX_TEXT_LENGTH_FOR_LLM,
            )

        message = get_prompt(
            "ontology.user_intro",
            locale,
            simulation_requirement=simulation_requirement,
            combined_text=combined_text,
        )

        if additional_context:
            message += get_prompt(
                "ontology.user_additional_context",
                locale,
                additional_context=additional_context,
            )

        message += get_prompt("ontology.user_outro", locale)

        return message

    @staticmethod
    def _is_clean_identifier(s: str) -> bool:
        """Check that a type name is ASCII PascalCase or UPPER_SNAKE_CASE."""
        import re
        return bool(s) and bool(re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', s))

    def _validate_and_process(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and post-process results"""

        # Ensure required fields exist
        if "entity_types" not in result:
            result["entity_types"] = []
        if "edge_types" not in result:
            result["edge_types"] = []
        if "analysis_summary" not in result:
            result["analysis_summary"] = ""

        # Validate entity types — reject entries with non-ASCII / garbage names
        result["entity_types"] = [
            e for e in result["entity_types"]
            if isinstance(e, dict) and self._is_clean_identifier(e.get("name", ""))
        ]

        for entity in result["entity_types"]:
            if "attributes" not in entity:
                entity["attributes"] = []
            if "examples" not in entity:
                entity["examples"] = []
            # Ensure description does not exceed 100 characters
            if len(entity.get("description", "")) > 100:
                entity["description"] = entity["description"][:97] + "..."

        # Collect valid entity type names for relation target validation
        valid_type_names = {e["name"] for e in result["entity_types"]}

        # Validate relationship types
        for edge in result.get("edge_types", []):
            if "source_targets" not in edge:
                edge["source_targets"] = []
            if "attributes" not in edge:
                edge["attributes"] = []
            if len(edge.get("description", "")) > 100:
                edge["description"] = edge["description"][:97] + "..."
            # Drop source_targets referencing non-existent or garbled type names
            edge["source_targets"] = [
                st for st in edge["source_targets"]
                if isinstance(st, dict)
                and st.get("source", "") in valid_type_names
                and st.get("target", "") in valid_type_names
            ]

        # Remove edge types with no valid source_targets left
        result["edge_types"] = [
            e for e in result["edge_types"]
            if isinstance(e, dict)
            and self._is_clean_identifier(e.get("name", ""))
            and e.get("source_targets")
        ]

        # Limit: max 10 custom entity types, max 10 custom edge types
        MAX_ENTITY_TYPES = 10
        MAX_EDGE_TYPES = 10

        # Fallback type definitions
        person_fallback = {
            "name": "Person",
            "description": "Any individual person not fitting other specific person types.",
            "attributes": [
                {"name": "full_name", "type": "text", "description": "Full name of the person"},
                {"name": "role", "type": "text", "description": "Role or occupation"}
            ],
            "examples": ["ordinary citizen", "anonymous netizen"]
        }

        organization_fallback = {
            "name": "Organization",
            "description": "Any organization not fitting other specific organization types.",
            "attributes": [
                {"name": "org_name", "type": "text", "description": "Name of the organization"},
                {"name": "org_type", "type": "text", "description": "Type of organization"}
            ],
            "examples": ["small business", "community group"]
        }

        # Check if fallback types already exist
        entity_names = {e["name"] for e in result["entity_types"]}
        has_person = "Person" in entity_names
        has_organization = "Organization" in entity_names

        # Fallback types to add
        fallbacks_to_add = []
        if not has_person:
            fallbacks_to_add.append(person_fallback)
        if not has_organization:
            fallbacks_to_add.append(organization_fallback)

        if fallbacks_to_add:
            current_count = len(result["entity_types"])
            needed_slots = len(fallbacks_to_add)

            # If adding would exceed 10, need to remove some existing types
            if current_count + needed_slots > MAX_ENTITY_TYPES:
                # Calculate how many to remove
                to_remove = current_count + needed_slots - MAX_ENTITY_TYPES
                # Remove from the end (preserve more important specific types at the front)
                result["entity_types"] = result["entity_types"][:-to_remove]

            # Add fallback types
            result["entity_types"].extend(fallbacks_to_add)

        # Final check to ensure limits are not exceeded (defensive programming)
        if len(result["entity_types"]) > MAX_ENTITY_TYPES:
            result["entity_types"] = result["entity_types"][:MAX_ENTITY_TYPES]

        if len(result["edge_types"]) > MAX_EDGE_TYPES:
            result["edge_types"] = result["edge_types"][:MAX_EDGE_TYPES]

        return result
