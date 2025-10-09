"""
Custom LLM implementation for llama.cpp server compatibility.
This module provides a custom LLM class that properly handles responses from llama.cpp servers.
"""

import logging
import requests
import json
from typing import Dict, List, Optional, Sequence, Any
from llama_index.core.llms import CustomLLM, CompletionResponse, ChatMessage, MessageRole, LLMMetadata
from llama_index.core.llms.callbacks import llm_chat_callback, llm_completion_callback
from llama_index.core.bridge.pydantic import Field
import os

logger = logging.getLogger(__name__)

class LlamaCppLLM(CustomLLM):
    """
    Custom LLM implementation for llama.cpp server compatibility.

    This class directly communicates with llama.cpp servers using HTTP requests
    and handles the specific response format that llama.cpp servers return.
    """

    model_name: str = Field(description="The model name to use")
    base_url: str = Field(description="The base URL of the llama.cpp server")
    temperature: float = Field(default=0.3, description="Temperature for generation")
    max_tokens: Optional[int] = Field(default=None, description="Maximum tokens to generate")
    timeout: float = Field(default=120.0, description="Request timeout in seconds")

    def __init__(self,
                 model_name: str = "Qwen3-Coder-30B-A3B-Instruct-UD-Q4_K_XL.gguf",
                 base_url: str = "http://localhost:8080",
                 temperature: float = 0.3,
                 max_tokens: Optional[int] = None,
                 timeout: float = 120.0,
                 **kwargs):
        super().__init__(
            model_name=model_name,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            **kwargs
        )
        logger.debug(f"[DEBUG] Initialized LlamaCppLLM with model: {model_name}, base_url: {base_url}")

    @property
    def metadata(self) -> LLMMetadata:
        """Return LLM metadata as LLMMetadata object."""
        return LLMMetadata(
            context_window=self.context_window,
            num_output=self.max_tokens or 1024,
            is_chat_model=True,
            model_name=self.model_name,
        )

    @property
    def context_window(self) -> int:
        """Return the context window size."""
        # Default context window for the model
        return 4096

    def _format_messages_for_llamacpp(self, messages: Sequence[ChatMessage]) -> List[Dict[str, str]]:
        """Format messages for llama.cpp server."""
        formatted_messages = []
        for message in messages:
            formatted_messages.append({
                "role": message.role.value,
                "content": message.content
            })
        return formatted_messages

    def _make_llamacpp_request(self, messages: List[Dict[str, str]]) -> Dict:
        """Make HTTP request to llama.cpp server."""
        api_url = f"{self.base_url}/v1/chat/completions"

        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": self.temperature,
        }

        if self.max_tokens:
            payload["max_tokens"] = self.max_tokens

        logger.debug(f"[DEBUG] LlamaCppLLM request to: {api_url}")
        logger.debug(f"[DEBUG] Request payload: {payload}")

        try:
            response = requests.post(api_url, json=payload, timeout=self.timeout)
            response.raise_for_status()

            data = response.json()
            logger.debug(f"[DEBUG] LlamaCppLLM response status: {response.status_code}")
            logger.debug(f"[DEBUG] LlamaCppLLM response keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")

            return data

        except Exception as e:
            logger.error(f"[DEBUG] LlamaCppLLM request failed: {str(e)}")
            logger.error(f"[DEBUG] Exception type: {type(e).__name__}")
            raise

    def _extract_content_from_response(self, response_data: Dict) -> str:
        """Extract content from llama.cpp server response."""
        logger.debug(f"[DEBUG] Extracting content from response")

        # Handle OpenAI-like format from llama.cpp
        if 'choices' in response_data and response_data['choices']:
            choice = response_data['choices'][0]
            logger.debug(f"[DEBUG] Found choices field, first choice keys: {list(choice.keys()) if isinstance(choice, dict) else 'Not a dict'}")

            if 'message' in choice and isinstance(choice['message'], dict):
                if 'content' in choice['message']:
                    content = choice['message']['content']
                    logger.debug(f"[DEBUG] Extracted content from choice.message.content: {len(content)} chars")
                    return content
                else:
                    logger.warning(f"[DEBUG] choice.message found but no content field. Keys: {list(choice['message'].keys())}")
            else:
                logger.warning(f"[DEBUG] choice.message not found or not a dict")

        # Handle alternative formats
        if 'content' in response_data:
            content = response_data['content']
            logger.debug(f"[DEBUG] Extracted content from root content field: {len(content)} chars")
            return content

        if 'response' in response_data:
            content = response_data['response']
            logger.debug(f"[DEBUG] Extracted content from response field: {len(content)} chars")
            return content

        logger.error(f"[DEBUG] Could not extract content from response. Available fields: {list(response_data.keys()) if isinstance(response_data, dict) else 'Not a dict'}")
        logger.error(f"[DEBUG] Full response: {response_data}")
        raise ValueError(f"Unable to extract content from llama.cpp response: {response_data}")

    @llm_chat_callback()
    def chat(self, messages: Sequence[ChatMessage], **kwargs) -> CompletionResponse:
        """Chat with the llama.cpp server."""
        logger.debug(f"[DEBUG] LlamaCppLLM.chat called with {len(messages)} messages")

        # Format messages for llama.cpp
        formatted_messages = self._format_messages_for_llamacpp(messages)
        logger.debug(f"[DEBUG] Formatted messages: {formatted_messages}")

        try:
            # Make request to llama.cpp server
            response_data = self._make_llamacpp_request(formatted_messages)

            # Extract content
            content = self._extract_content_from_response(response_data)

            # Create completion response
            completion_response = CompletionResponse(text=content)
            logger.debug(f"[DEBUG] LlamaCppLLM chat completed successfully, response length: {len(content)}")

            return completion_response

        except Exception as e:
            logger.error(f"[DEBUG] LlamaCppLLM chat failed: {str(e)}")
            raise

    @llm_completion_callback()
    def complete(self, prompt: str, **kwargs) -> CompletionResponse:
        """Complete text using the llama.cpp server."""
        logger.debug(f"[DEBUG] LlamaCppLLM.complete called with prompt length: {len(prompt)}")

        # Convert prompt to chat format
        messages = [ChatMessage(role=MessageRole.USER, content=prompt)]

        # Use chat method for completion
        return self.chat(messages, **kwargs)

    def _validate_response_format(self, response_data: Dict) -> bool:
        """Validate that the response format is expected."""
        if not isinstance(response_data, dict):
            logger.warning(f"[DEBUG] Response is not a dict: {type(response_data)}")
            return False

        # Check for expected fields
        if 'choices' in response_data:
            logger.debug(f"[DEBUG] Response has 'choices' field")
            return True
        elif 'content' in response_data:
            logger.debug(f"[DEBUG] Response has 'content' field")
            return True
        elif 'response' in response_data:
            logger.debug(f"[DEBUG] Response has 'response' field")
            return True
        else:
            logger.warning(f"[DEBUG] Response missing expected fields. Available: {list(response_data.keys())}")
            return False

    @llm_completion_callback()
    def stream_complete(self, prompt: str, **kwargs):
        """Stream completion (not implemented for this custom LLM)."""
        # For now, we'll just return the complete response
        # In a full implementation, this would handle streaming
        logger.debug(f"[DEBUG] Stream complete called for prompt length: {len(prompt)}")
        completion_response = self.complete(prompt, **kwargs)

        # Yield the completion as a single chunk
        yield completion_response