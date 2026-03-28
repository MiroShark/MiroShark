"""
LLM client wrapper
Unified API calls using OpenAI format.
Supports OpenAI-compatible APIs and Claude Code CLI.
"""

import json
import logging
import os
import re

logger = logging.getLogger("miroshark.llm_client")
from typing import Optional, Dict, Any, List
from openai import OpenAI

from ..config import Config


def create_llm_client(
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    timeout: float = 300.0
):
    """
    Factory: returns ClaudeCodeClient when LLM_PROVIDER=claude-code,
    otherwise returns the standard LLMClient.
    """
    if Config.LLM_PROVIDER == 'claude-code':
        from .claude_code_client import ClaudeCodeClient
        return ClaudeCodeClient(model=model, timeout=timeout)
    return LLMClient(api_key=api_key, base_url=base_url, model=model, timeout=timeout)


def create_smart_llm_client(timeout: float = 300.0):
    """
    Factory for intelligence-sensitive workflows (reports, ontology, graph reasoning).
    Uses SMART_* config when set, otherwise falls back to the default LLM client.
    """
    if not Config.SMART_MODEL_NAME:
        return create_llm_client(timeout=timeout)

    provider = Config.SMART_PROVIDER or Config.LLM_PROVIDER

    if provider == 'claude-code':
        from .claude_code_client import ClaudeCodeClient
        return ClaudeCodeClient(model=Config.SMART_MODEL_NAME, timeout=timeout)

    return LLMClient(
        api_key=Config.SMART_API_KEY or Config.LLM_API_KEY,
        base_url=Config.SMART_BASE_URL or Config.LLM_BASE_URL,
        model=Config.SMART_MODEL_NAME,
        timeout=timeout,
    )


class LLMClient:
    """LLM client using OpenAI-compatible APIs"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 300.0
    ):
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = base_url or Config.LLM_BASE_URL
        self.model = model or Config.LLM_MODEL_NAME

        if not self.api_key:
            raise ValueError("LLM_API_KEY is not configured")

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=timeout,
        )

        # Ollama context window size — prevents prompt truncation.
        self._num_ctx = int(os.environ.get('OLLAMA_NUM_CTX', '8192'))

    def _is_ollama(self) -> bool:
        """Check if we're talking to an Ollama server."""
        return '11434' in (self.base_url or '')

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: Optional[Dict] = None
    ) -> str:
        """
        Send a chat request

        Args:
            messages: List of messages
            temperature: Temperature parameter
            max_tokens: Maximum number of tokens
            response_format: Response format (e.g., JSON mode)

        Returns:
            Model response text
        """
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if response_format:
            kwargs["response_format"] = response_format

        # For Ollama: pass num_ctx via extra_body to prevent prompt truncation
        if self._is_ollama() and self._num_ctx:
            kwargs["extra_body"] = {
                "options": {"num_ctx": self._num_ctx}
            }

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(**kwargs)
                content = response.choices[0].message.content
                # Some models include <think> reasoning that needs removal
                content = re.sub(r'<think>[\s\S]*?</think>', '', content).strip()
                return content
            except Exception as exc:
                if attempt == max_retries - 1:
                    raise
                wait = 2 ** attempt
                logger.warning(f"LLM call failed (attempt {attempt + 1}/{max_retries}), retrying in {wait}s: {exc}")
                import time
                time.sleep(wait)

    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096
    ) -> Dict[str, Any]:
        """
        Send a chat request and return JSON

        Args:
            messages: List of messages
            temperature: Temperature parameter
            max_tokens: Maximum number of tokens

        Returns:
            Parsed JSON object
        """
        response = self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"}
        )
        # Clean up markdown code block markers
        cleaned_response = response.strip()
        cleaned_response = re.sub(r'^```(?:json)?\s*\n?', '', cleaned_response, flags=re.IGNORECASE)
        cleaned_response = re.sub(r'\n?```\s*$', '', cleaned_response)
        cleaned_response = cleaned_response.strip()

        try:
            return json.loads(cleaned_response)
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON format returned by LLM: {cleaned_response}")
