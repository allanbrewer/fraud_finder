#!/usr/bin/env python3
import os
import logging
import requests
from mem0 import Memory
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class BaseLLM:
    """Base class for LLM operations with shared functionality"""

    def __init__(
        self,
        api_key=None,
        model=None,
        provider="xai",
        max_tokens=4096,
        temperature=0.1,
        user_id="default_user",
    ):
        """
        Initialize Base LLM

        Args:
            api_key: API key for the LLM provider
            model: Model name to use
            provider: LLM provider (openai, anthropic, xai, gemini)
            max_tokens: Maximum tokens for response
            temperature: Temperature for response generation
            user_id: User ID for memory operations (default: default_user)
        """
        self.provider = provider.lower()
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.user_id = user_id

        # Set default model based on provider
        if model is None:
            if self.provider == "openai":
                self.model = "gpt-4o"
            elif self.provider == "anthropic":
                self.model = "claude-3-7-sonnet-latest"
            elif self.provider == "xai":
                self.model = "grok-2-latest"
            elif self.provider == "gemini":
                self.model = "gemini-2.0-flash"
            else:
                raise ValueError(f"Unknown provider: {provider}")
        else:
            self.model = model

        # Get API key from .env file if not provided
        if api_key is None:
            if self.provider == "openai":
                api_key = os.getenv("OPENAI_API_KEY")
            elif self.provider == "anthropic":
                api_key = os.getenv("ANTHROPIC_API_KEY")
            elif self.provider == "xai":
                api_key = os.getenv("XAI_API_KEY")
            elif self.provider == "gemini":
                api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            raise ValueError(
                f"API key not provided and not found in .env file for {provider}"
            )

        self.api_key = api_key

        # Config Memory - only for supported providers
        if self.provider in ["openai", "anthropic", "xai", "gemini"]:
            try:
                mem_provider = self.provider
                config = {
                    "llm": {
                        "provider": mem_provider,
                        "config": {
                            "model": self.model,
                            "temperature": self.temperature,
                            "max_tokens": self.max_tokens,
                        },
                    },
                    # Use the default mem0 storage configuration with a custom collection name
                    "vector_store": {
                        "provider": "chroma",
                        "config": {
                            "collection_name": f"fraud_finder_{self.user_id}",
                        },
                    },
                }

                self.memory = Memory.from_config(config)
                logger.info(
                    f"Memory initialized with provider {mem_provider} using default storage location at ~/.mem0 for user '{self.user_id}'"
                )
            except Exception as e:
                logger.warning(f"Failed to initialize memory: {str(e)}")
                import traceback

                logger.warning(traceback.format_exc())
                self.memory = None
        else:
            logger.warning(f"Memory not supported for provider {self.provider}")
            self.memory = None

    def call_openai_api(self, complete_prompt, system_message=None, chat_history=None):
        """
        Call OpenAI API with prompt

        Args:
            complete_prompt: Complete prompt with CSV data
            system_message: Optional system message to include
            chat_history: Optional list of previous messages in the chat

        Returns:
            API response as JSON
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        messages = []

        # Add system message if provided
        if system_message:
            messages.append({"role": "system", "content": system_message})

        # Add chat history if provided
        if chat_history:
            messages.extend(chat_history)
        else:
            # Add current prompt if not in chat mode
            # Ensure the prompt includes the word "json" when using JSON response format
            if "json" not in complete_prompt.lower():
                complete_prompt = (
                    f"{complete_prompt}\n\nProvide your response in JSON format."
                )
            messages.append({"role": "user", "content": complete_prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        # Add response format for non-chat mode
        if not chat_history:
            payload["response_format"] = {"type": "json_object"}

        try:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()

            result = response.json()
            return result["choices"][0]["message"]["content"]

        except requests.exceptions.RequestException as e:
            logger.error(f"Error calling OpenAI API: {str(e)}")
            if hasattr(e, "response") and e.response is not None:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response body: {e.response.text}")
            return None

    def call_anthropic_api(
        self, complete_prompt, system_message=None, chat_history=None
    ):
        """
        Call Anthropic API with prompt

        Args:
            complete_prompt: Complete prompt with CSV data
            system_message: Optional system message to include
            chat_history: Optional list of previous messages in the chat

        Returns:
            API response as JSON
        """
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }

        # Prepare messages
        messages = []

        if chat_history:
            # Add chat history
            messages.extend(chat_history)
        else:
            # Add user message if not in chat mode
            messages.append({"role": "user", "content": complete_prompt})

        # Prepare payload
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        # Add system message if provided
        if system_message:
            payload["system"] = system_message

        try:
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()

            result = response.json()
            return result["content"][0]["text"]

        except requests.exceptions.RequestException as e:
            logger.error(f"Error calling Anthropic API: {str(e)}")
            if hasattr(e, "response") and e.response is not None:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response body: {e.response.text}")
            return None

    def call_xai_api(self, complete_prompt, system_message=None, chat_history=None):
        """
        Call XAI API with prompt

        Args:
            complete_prompt: Complete prompt with CSV data
            system_message: Optional system message to include
            chat_history: Optional list of previous messages in the chat

        Returns:
            API response as JSON
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        messages = []

        # Add system message if provided
        if system_message:
            messages.append({"role": "system", "content": system_message})

        # Add chat history if provided
        if chat_history:
            messages.extend(chat_history)
        else:
            # Add current prompt if not in chat mode
            messages.append({"role": "user", "content": complete_prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        # Add response format for non-chat mode
        if not chat_history:
            payload["response_format"] = {"type": "json_object"}

        try:
            response = requests.post(
                "https://api.x.ai/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()

            result = response.json()
            return result["choices"][0]["message"]["content"]

        except requests.exceptions.RequestException as e:
            logger.error(f"Error calling Xai API: {str(e)}")
            if hasattr(e, "response") and e.response is not None:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response body: {e.response.text}")
            return None

    def call_gemini_api(self, complete_prompt, system_message=None, chat_history=None):
        """
        Call Gemini API with prompt

        Args:
            complete_prompt: Complete prompt with CSV data
            system_message: Optional system message to include
            chat_history: Optional list of previous messages in the chat

        Returns:
            API response as JSON
        """
        headers = {
            "Content-Type": "application/json",
        }

        # Structure the content as required by the Gemini API
        contents = []
        if system_message:
            contents.append({"role": "model", "parts": [{"text": system_message}]})
        if chat_history:
            for message in chat_history:
                role = message.get("role")
                content = message.get("content")
                if role and content:
                    contents.append({"role": role, "parts": [{"text": content}]})
        # Add the user's prompt
        contents.append({"role": "user", "parts": [{"text": complete_prompt}]})

        payload = {"contents": contents}

        try:
            response = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()

            result = response.json()
            # Extract the text response
            return result["candidates"][0]["content"]["parts"][0]["text"]

        except requests.exceptions.RequestException as e:
            logger.error(f"Error calling Gemini API: {str(e)}")
            if hasattr(e, "response") and e.response is not None:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response body: {e.response.text}")
            return None

    def add_memory(self, content, metadata=None):
        """
        Add memory to memory system

        Args:
            content: Memory content
            metadata: Optional metadata

        Returns:
            True if memory added successfully, False otherwise
        """
        if not hasattr(self, "memory") or self.memory is None:
            logger.warning("Memory system not initialized")
            return False

        try:
            # Using string format instead of message format to avoid parsing issues
            # The error was occurring because mem0 was trying to parse the content as a message
            # with role/content fields, but we're providing a simple string
            mem_id = self.memory.add(content, user_id=self.user_id)
            logger.info(f"Memory added with ID: {mem_id}")
            return True
        except Exception as e:
            logger.error(f"Error adding memory: {str(e)}")
            import traceback

            logger.error(traceback.format_exc())
            return False

    def create_system_message_with_memories(self, description=None, query=None):
        """
        Create a system message with relevant memories

        Args:
            description: Optional description to include in system message
            query: Optional query to use for retrieving memories

        Returns:
            System message with memories
        """
        base_message = "You are a contract analysis expert specialized in identifying DEI contracts and DOGE targets."

        if description:
            base_message = f"{base_message}\n\n{description}"

        # Add memories if available
        if hasattr(self, "memory") and self.memory is not None and query:
            try:
                # Search for relevant memories with the actual query
                # (Skip the empty query search that was causing the 400 error)
                logger.info(
                    f"Searching for memories with query: '{query}' for user: '{self.user_id}'"
                )

                # Use try-except to handle the case where there are fewer memories than requested
                try:
                    relevant_memories = self.memory.search(
                        query=query, user_id=self.user_id, limit=5
                    )
                    logger.info(f"Found {len(relevant_memories)} relevant memories")
                except Exception as e:
                    # If there's an error with the limit, try with a smaller limit
                    logger.warning(
                        f"Memory search error: {str(e)}, trying with smaller limit"
                    )
                    try:
                        relevant_memories = self.memory.search(
                            query=query, user_id=self.user_id, limit=3
                        )
                        logger.info(
                            f"Found {len(relevant_memories)} relevant memories with reduced limit"
                        )
                    except Exception as e2:
                        logger.error(
                            f"Memory search failed with reduced limit: {str(e2)}"
                        )
                        relevant_memories = []

                # Log the raw memory results for debugging
                logger.info(f"Memory search results: {relevant_memories}")

                if (
                    relevant_memories
                    and len(relevant_memories) > 0
                    and "matches" in relevant_memories
                    and len(relevant_memories["matches"]) > 0
                ):
                    # Build memory text
                    memory_text = "Here are some relevant memories:\n\n"
                    for i, memory in enumerate(relevant_memories["matches"]):
                        content = memory["metadata"].get("content", "")
                        if content:
                            memory_text += f"{i+1}. {content}\n\n"

                    logger.info(f"Adding memories to system message:\n{memory_text}")

                    if base_message:
                        base_message = (
                            f"{base_message}\n\nRelevant information:\n{memory_text}"
                        )
                    else:
                        base_message = f"You are a helpful assistant. Consider this relevant information:\n{memory_text}"
                else:
                    logger.info("No relevant memories found")
            except Exception as e:
                logger.error(f"Error retrieving memories: {str(e)}")
                import traceback

                logger.error(traceback.format_exc())

        return base_message
