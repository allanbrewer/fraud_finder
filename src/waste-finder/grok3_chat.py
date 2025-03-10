#!/usr/bin/env python3
"""
Grok3 Chat - A simple chat interface for Grok-3 with memory support
"""

import os
import sys
import json
import time
import logging
import argparse
import requests
from typing import List, Dict, Any, Tuple, Optional
from dotenv import load_dotenv

# Import the GrokClient from the newly installed package
from grok_client import GrokClient

# Import mem0 for memory support
from mem0 import Memory

# Configure logging
logger = logging.getLogger(__name__)

# Import prompts from prompt.py
try:
    from prompt import dei_prompt, ngo_fraud_prompt

    # Create a dictionary of available prompts
    available_prompts = {"dei": dei_prompt, "ngo_fraud": ngo_fraud_prompt}

    logger.info(
        f"Successfully imported prompts from prompt.py: {', '.join(available_prompts.keys())}"
    )
except ImportError:
    try:
        # Try relative import if the first import fails
        from .prompt import dei_prompt, ngo_fraud_prompt

        # Create a dictionary of available prompts
        available_prompts = {"dei": dei_prompt, "ngo_fraud": ngo_fraud_prompt}

        logger.info(
            f"Successfully imported prompts from prompt.py: {', '.join(available_prompts.keys())}"
        )
    except ImportError:
        logger.error("Could not import prompts from prompt.py")
        available_prompts = {}


class Grok3Chat:
    """
    Chat interface for Grok-3 with memory support
    """

    def __init__(
        self,
        cookies: str = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        user_id: str = "default_user",
        prompt_type: str = "ngo_fraud",
    ):
        """
        Initialize the Grok3 chat interface

        Args:
            cookies: Cookies for authentication (from XAI_COOKIES env var)
            temperature: Temperature for generation
            max_tokens: Maximum tokens to generate
            user_id: User ID for memory operations (default: default_user)
            prompt_type: Type of prompt to use (default: ngo_fraud)
        """
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.user_id = user_id
        self.prompt_type = prompt_type

        # Load cookies from environment if not provided
        if cookies is None:
            load_dotenv()
            cookies = os.environ.get("XAI_COOKIES")
            if not cookies:
                raise ValueError("XAI_COOKIES environment variable not set")

        # Parse cookies string into a dict for GrokClient
        try:
            # Parse the cookie string into a dictionary
            cookie_dict = {}
            for cookie in cookies.split(";"):
                if "=" in cookie:
                    name, value = cookie.strip().split("=", 1)
                    cookie_dict[name] = value

            # Initialize the GrokClient
            self.grok_client = GrokClient(cookie_dict)
            logger.info("GrokClient initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize GrokClient: {str(e)}")
            raise

        # Initialize Memory
        try:
            config = {
                "llm": {
                    "provider": "xai",  # mem0 requires a provider, using xai as default
                    "config": {
                        "model": "grok-beta",
                        "temperature": self.temperature,
                        "max_tokens": self.max_tokens,
                    },
                },
                # Use ChromaDB with a user-specific collection name
                "vector_store": {
                    "provider": "chroma",
                    "config": {
                        "collection_name": f"grok3_chat_{self.user_id}",
                    },
                },
            }

            self.memory = Memory.from_config(config)
            logger.info(
                f"Memory initialized for user '{self.user_id}' using default storage location at ~/.mem0"
            )
        except Exception as e:
            logger.warning(f"Failed to initialize memory: {str(e)}")
            import traceback

            logger.warning(traceback.format_exc())
            self.memory = None

    def chat(
        self,
        user_input: str,
        system_message: Optional[str] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> Tuple[Optional[str], List[Dict[str, str]]]:
        """
        Chat with Grok-3

        Args:
            user_input: User message
            system_message: Optional system message
            chat_history: Optional chat history

        Returns:
            Tuple of (response_text, updated_chat_history)
        """
        # Initialize chat history if not provided
        if chat_history is None:
            chat_history = []

        # Check if this is a memory command
        if user_input.lower().startswith("memory:"):
            memory_content = user_input[7:].strip()
            success = self.add_memory(memory_content)
            if success:
                return f"Memory added: {memory_content}", chat_history
            else:
                return "Failed to add memory.", chat_history

        # Check if this is a prompt selection command
        if user_input.lower().startswith("prompt:"):
            prompt_type = user_input[7:].strip().lower()
            if prompt_type in available_prompts:
                self.prompt_type = prompt_type
                return f"Prompt type set to: {prompt_type}", chat_history
            else:
                available = ", ".join(available_prompts.keys())
                return (
                    f"Invalid prompt type. Available types: {available}",
                    chat_history,
                )

        # Add user message to chat history
        chat_history.append({"role": "user", "content": user_input})

        # Create system message with memories if available
        final_system_message = system_message or "You are a helpful assistant."
        if self.memory is not None:
            try:
                # Search for relevant memories
                logger.info(
                    f"Searching for memories with query: '{user_input}' for user: '{self.user_id}'"
                )
                relevant_memories = self.memory.search(
                    query=user_input, user_id=self.user_id, limit=5
                )

                # Log the memory results for debugging
                logger.info(f"Memory search results: {relevant_memories}")

                if (
                    relevant_memories
                    and "results" in relevant_memories
                    and relevant_memories["results"]
                ):
                    memory_text = "\n".join(
                        [
                            f"- {entry['memory']}"
                            for entry in relevant_memories["results"]
                        ]
                    )

                    final_system_message = f"{final_system_message}\n\nRelevant information:\n{memory_text}"
                    logger.info(
                        f"Added {len(relevant_memories['results'])} memories to system message"
                    )
            except Exception as e:
                logger.warning(f"Error retrieving memories: {str(e)}")
                import traceback

                logger.warning(traceback.format_exc())

        # Call Grok3 API
        logger.info("Sending request to Grok3 API")
        start_time = time.time()

        try:
            # Format messages for Grok3
            messages = []

            # Add system message if available
            if final_system_message:
                messages.append({"role": "system", "content": final_system_message})

            # Add chat history
            for msg in chat_history:
                messages.append(msg)

            # Combine all messages into a single prompt
            combined_prompt = ""
            for msg in messages:
                role = msg["role"]
                content = msg["content"]
                if role == "system":
                    combined_prompt += f"System: {content}\n\n"
                elif role == "user":
                    combined_prompt += f"User: {content}\n\n"
                elif role == "assistant":
                    combined_prompt += f"Assistant: {content}\n\n"

            # Add the final user message if not already included
            if combined_prompt and not combined_prompt.endswith(
                f"User: {user_input}\n\n"
            ):
                combined_prompt += f"User: {user_input}\n\n"

            # If no messages, just use the user input
            if not combined_prompt:
                combined_prompt = user_input

            # Call the GrokClient send_message method
            logger.info(f"Sending message to Grok3: {combined_prompt[:100]}...")
            response_text = self.grok_client.send_message(combined_prompt)

            elapsed_time = time.time() - start_time
            logger.info(f"API call completed in {elapsed_time:.2f} seconds")

            if not response_text:
                logger.error("Empty response from Grok3 API")
                return None, chat_history
        except Exception as e:
            logger.error(f"Error calling Grok3 API: {str(e)}")
            import traceback

            logger.error(traceback.format_exc())
            return None, chat_history

        # Add assistant response to chat history
        chat_history.append({"role": "assistant", "content": response_text})

        return response_text, chat_history

    def add_memory(
        self, content: str, metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Add a memory to the memory system

        Args:
            content: Memory content
            metadata: Optional metadata

        Returns:
            True if memory was added, False otherwise
        """
        if self.memory is None:
            logger.warning("Memory not initialized")
            return False

        try:
            # Log memory addition attempt
            logger.info(
                f"Attempting to add memory for user '{self.user_id}': {content}"
            )

            # Add memory directly as a string
            result = self.memory.add(
                content, user_id=self.user_id, metadata=metadata or {}
            )
            logger.info(f"Added memory using string format: {result}")

            logger.info(f"Successfully added memory for user {self.user_id}: {content}")
            return True
        except Exception as e:
            logger.error(f"Error adding memory: {str(e)}")
            import traceback

            logger.error(traceback.format_exc())
            return False


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Grok3 Chat with Memory")

    # Chat mode options
    parser.add_argument(
        "--interactive", action="store_true", help="Interactive chat mode"
    )
    parser.add_argument("--message", type=str, help="Single message to send")

    # Configuration options
    parser.add_argument(
        "--temperature", type=float, default=0.7, help="Temperature for generation"
    )
    parser.add_argument(
        "--max-tokens", type=int, default=1000, help="Maximum tokens to generate"
    )
    parser.add_argument("--system-message", type=str, help="System message to include")
    parser.add_argument(
        "--user-id",
        type=str,
        default="default_user",
        help="User ID for memory operations",
    )
    parser.add_argument(
        "--cookies",
        type=str,
        help="Cookies for authentication (overrides XAI_COOKIES env var)",
    )
    parser.add_argument(
        "--prompt-type",
        default="ngo_fraud",
        choices=(
            list(available_prompts.keys())
            if available_prompts
            else ["dei", "ngo_fraud"]
        ),
        help="Type of prompt to use (default: ngo_fraud)",
    )

    # Output options
    parser.add_argument("--save", type=str, help="Save conversation to file")

    return parser.parse_args()


def handle_interactive_mode(chat, args):
    """Handle interactive chat mode"""
    print("Grok3 Chat")
    print("Type 'exit' or 'quit' to end the conversation.")
    print("Type 'save' to save the conversation history.")
    print("Type 'memory: <content>' to add a memory.")
    print("Type 'prompt: <type>' to change the prompt type.")
    print(f"Available prompt types: {', '.join(available_prompts.keys())}")
    print("--------------------------------------------------")
    print()

    chat_history = []

    while True:
        try:
            # Get user input
            user_input = input("You: ").strip()

            # Check for exit command
            if user_input.lower() in ["exit", "quit"]:
                break

            # Check for save command
            if user_input.lower() == "save":
                filename = f"grok3_chat_{time.strftime('%Y%m%d_%H%M%S')}.json"
                with open(filename, "w") as f:
                    json.dump(chat_history, f, indent=2)
                print(f"Conversation saved to {filename}")
                continue

            # Get response
            response, chat_history = chat.chat(
                user_input, args.system_message, chat_history
            )

            if response:
                print(f"\nA: {response}\n")
            else:
                print("\nFailed to get response.\n")

        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            logger.error(f"Error: {str(e)}")
            print(f"\nAn error occurred: {str(e)}\n")

    # Save conversation if requested
    if args.save:
        with open(args.save, "w") as f:
            json.dump(chat_history, f, indent=2)
        print(f"Conversation saved to {args.save}")


def main():
    """Main function"""
    args = parse_arguments()

    try:
        # Initialize chat
        chat = Grok3Chat(
            cookies=args.cookies,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            user_id=args.user_id,
            prompt_type=args.prompt_type,
        )

        # Interactive mode
        if args.interactive:
            handle_interactive_mode(chat, args)

        # Single message mode
        elif args.message:
            response, _ = chat.chat(args.message, args.system_message)
            if response:
                print(response)
            else:
                print("Failed to get response.")

        # No mode specified
        else:
            print("Please specify a mode: --interactive or --message")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        print(f"An error occurred: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
