"""Generic OpenAI-compatible model client with retry + JSON helpers."""
from __future__ import annotations

import json
import logging
import os
import re
import time
import requests
from typing import Any, List, Optional

from openai import OpenAI

from src.config.settings import settings

logger = logging.getLogger(__name__)

_JSON_BLOCK_PATTERN = re.compile(r"(\{.*\}|\[.*\])", re.DOTALL)


def _coalesce(*values: Optional[str]) -> Optional[str]:
    """Return the first truthy string from the provided values."""
    for value in values:
        if value:
            return value
    return None


class ModelClient:
    """Provider-agnostic chat completion helper."""

    def __init__(
        self,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        request_timeout: int = 120,
        max_retries: int = 3,
    ) -> None:
        self.provider = provider or settings.LLM_PROVIDER or "unknown"

        # Check if using Ollama
        self.use_ollama = self.provider.lower() == "ollama" or settings.OLLAMA_MODEL

        if self.use_ollama:
            # Use Ollama configuration
            self.ollama_url = settings.OLLAMA_URL
            self.ollama_model = _coalesce(
                model,
                settings.OLLAMA_MODEL,
                os.getenv("OLLAMA_MODEL"),
            )
            self.api_key = None
            self.base_url = None
            self.model = self.ollama_model
            self._client = None  # Ollama uses direct HTTP requests
            self.max_retries = max_retries  # Add missing max_retries for Ollama mode
            self.request_timeout = request_timeout  # Add missing request_timeout for Ollama mode
        else:
            # Use OpenAI-compatible API
            self.api_key = _coalesce(
                api_key,
                settings.resolved_llm_api_key,
                os.getenv("LLM_API_KEY"),
                os.getenv("DEEPSEEK_API_KEY"),
            )
            self.base_url = _coalesce(
                base_url,
                settings.resolved_llm_base_url,
                os.getenv("LLM_BASE_URL"),
                os.getenv("DEEPSEEK_BASE_URL"),
            )
            self.model = _coalesce(
                model,
                settings.resolved_llm_model,
                os.getenv("LLM_MODEL"),
                os.getenv("DEEPSEEK_MODEL"),
            )

            self.request_timeout = request_timeout
            self.max_retries = max_retries

            if not self.api_key:
                raise ValueError("LLM API key is not configured (LLM_API_KEY).")
            if not self.base_url:
                raise ValueError("LLM base URL is not configured (LLM_BASE_URL).")
            if not self.model:
                raise ValueError("LLM model name is not configured (LLM_MODEL).")

            self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            self.ollama_url = None
            self.ollama_model = None

    def run_prompt(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_output_tokens: int = 1024,
    ) -> str:
        """Execute a prompt against the configured provider and return raw text."""

        if self.use_ollama:
            return self._run_ollama_prompt(system_prompt, user_prompt, temperature, max_output_tokens)
        else:
            return self._run_openai_prompt(system_prompt, user_prompt, temperature, max_output_tokens)

    def _run_openai_prompt(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_output_tokens: int = 1024,
    ) -> str:
        """Execute OpenAI-compatible prompt."""
        last_error: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self._client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=temperature,
                    max_tokens=max_output_tokens,
                    timeout=self.request_timeout,
                )
                return self._extract_text(response)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                logger.warning(
                    "%s request failed on attempt %s/%s: %s",
                    self.provider,
                    attempt,
                    self.max_retries,
                    exc,
                )
                time.sleep(min(2 ** attempt, 10))

        raise RuntimeError(
            f"{self.provider} request failed after {self.max_retries} attempts: {last_error}"
        )

    def _run_ollama_prompt(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_output_tokens: int = 1024,
    ) -> str:
        """Execute Ollama prompt."""
        # Combine system and user prompts for Ollama
        full_prompt = f"System: {system_prompt}\n\nUser: {user_prompt}"

        last_error: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = requests.post(
                    self.ollama_url,
                    json={
                        "model": self.ollama_model,
                        "prompt": full_prompt,
                        "stream": False,
                        "options": {
                            "temperature": temperature,
                            "num_predict": max_output_tokens,
                        }
                    },
                    timeout=self.request_timeout
                )
                response.raise_for_status()
                result = response.json()
                return result.get("response", "").strip()
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                logger.warning(
                    "Ollama request failed on attempt %s/%s: %s",
                    attempt,
                    self.max_retries,
                    exc,
                )
                time.sleep(min(2 ** attempt, 10))

        raise RuntimeError(
            f"Ollama request failed after {self.max_retries} attempts: {last_error}"
        )

    def run_json_prompt(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_output_tokens: int = 1024,
    ) -> Any:
        """Execute a prompt and parse the first JSON block in the response."""

        raw_text = self.run_prompt(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
        json_text = self._extract_json_block(raw_text)
        try:
            return json.loads(json_text)
        except json.JSONDecodeError as exc:  # noqa: B904
            logger.error("Failed to parse JSON from %s response: %s", self.provider, exc)
            logger.error("Extracted JSON text (first 200 chars): %s", json_text[:200])
            logger.error("Full extracted JSON text: %s", json_text)
            logger.debug("Full raw response text: %s", raw_text)

            # Try to salvage by looking for alternative JSON patterns
            try:
                import re

                # First, try to find the last complete JSON object (Ollama sometimes puts explanation after JSON)
                # Prioritize objects over arrays
                json_objects = re.findall(r'\{(?:[^{}]|\{[^{}]*\})*\}', json_text)
                json_arrays = re.findall(r'\[(?:[^\[\]]|\[[^\[\]]*\])*\]', json_text)

                # Try objects first (what we expect)
                for potential_json in reversed(json_objects):
                    try:
                        parsed = json.loads(potential_json)
                        if isinstance(parsed, dict):  # Only accept objects, not arrays
                            return parsed
                    except json.JSONDecodeError:
                        continue

                # If no valid objects found, try arrays (fallback for malformed responses)
                for potential_json in reversed(json_arrays):
                    try:
                        return json.loads(potential_json)
                    except json.JSONDecodeError:
                        continue

                # Try to clean up common JSON formatting issues
                cleaned_json = re.sub(r',\s*}', '}', json_text)  # Remove trailing commas
                cleaned_json = re.sub(r',\s*]', ']', cleaned_json)  # Remove trailing commas in arrays
                cleaned_json = re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', cleaned_json)  # Quote unquoted keys
                try:
                    return json.loads(cleaned_json)
                except json.JSONDecodeError:
                    pass

                # Last resort: try to extract the first valid JSON-like structure
                brace_start = json_text.find('{')
                if brace_start != -1:
                    # Simple brace counting to find complete JSON
                    brace_count = 0
                    for i, char in enumerate(json_text[brace_start:]):
                        if char == '{':
                            brace_count += 1
                        elif char == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                potential_json = json_text[brace_start:brace_start+i+1]
                                try:
                                    return json.loads(potential_json)
                                except json.JSONDecodeError:
                                    break

            except Exception:
                # If all attempts fail, raise the original error
                raise exc

    @staticmethod
    def _extract_text(response: Any) -> str:
        """Flatten chat completion choices into plain text."""

        chunks: List[str] = []
        choices = getattr(response, "choices", []) or []
        for choice in choices:
            message = getattr(choice, "message", None)
            if not message:
                continue

            content = getattr(message, "content", "")
            if isinstance(content, list):
                for segment in content:
                    if isinstance(segment, dict) and segment.get("type") == "text":
                        chunks.append(str(segment.get("text", "")))
            else:
                chunks.append(str(content))

        return "".join(chunks).strip()

    @staticmethod
    def _extract_json_block(text: str) -> str:
        """Extract the first JSON object/array from text."""

        stripped = text.strip()

        # First, try to find complete JSON at the start
        if stripped.startswith("{") and stripped.endswith("}"):
            return stripped
        if stripped.startswith("[") and stripped.endswith("]"):
            return stripped

        # Look for JSON code blocks (```json ... ```)
        import re
        json_code_block = re.search(r'```json\s*(\{.*?\})\s*```', stripped, re.DOTALL)
        if json_code_block:
            return json_code_block.group(1).strip()

        # Also try without the 'json' language specifier
        json_code_block2 = re.search(r'```\s*(\{.*?\})\s*```', stripped, re.DOTALL)
        if json_code_block2:
            return json_code_block2.group(1).strip()

        # Look for any JSON block using regex
        match = _JSON_BLOCK_PATTERN.search(stripped)
        if match:
            return match.group(1)

        # Last resort: try to find the first complete JSON object
        # This handles cases where there might be extra text before or after
        json_start = stripped.find('{')
        if json_start != -1:
            brace_count = 0
            in_string = False
            escape_next = False

            for i, char in enumerate(stripped[json_start:], json_start):
                if escape_next:
                    escape_next = False
                    continue

                if char == '\\':
                    escape_next = True
                    continue

                if char == '"' and not escape_next:
                    in_string = not in_string
                    continue

                if not in_string:
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            # Found complete JSON object
                            return stripped[json_start:i+1]

        raise ValueError("No JSON block found in model response.")

