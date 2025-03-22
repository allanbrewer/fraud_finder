#!/usr/bin/env python3
import logging
import json
import sys
import argparse
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Try to import base_llm from different possible paths
try:
    from src.waste_finder.core.base_llm import BaseLLM
except ImportError:
    try:
        from waste_finder.core.base_llm import BaseLLM
    except ImportError:
        try:
            from ..core.base_llm import BaseLLM
        except ImportError:
            raise ImportError(
                "Could not import BaseLLM. Check your python path and file structure."
            )

# Import the prompts from prompt.py
try:
    from src.waste_finder.core.prompt import prompts

    logger.info(
        f"Successfully imported prompts from prompt.py: {', '.join(prompts.keys())}"
    )
except ImportError:
    try:
        from waste_finder.core.prompt import prompts

        logger.info(
            f"Successfully imported prompts from prompt.py: {', '.join(prompts.keys())}"
        )
    except ImportError:
        try:
            from ..core.prompt import prompts

            logger.info(
                f"Successfully imported prompts from prompt.py: {', '.join(prompts.keys())}"
            )
        except ImportError:
            logger.error("Failed to import prompts from prompt.py")
            prompts = {
                "dei": "Analyze this contract data for DEI spending...",
                "ngo_fraud": "Analyze this contract data for NGO fraud...",
            }


class LLMChat(BaseLLM):
    """Class for interactive chat with LLM APIs"""

    def __init__(
        self,
        api_key=None,
        model=None,
        provider="xai",
        max_tokens=4096,
        temperature=0.1,
        user_id="default_user",
    ):
        super().__init__(api_key, model, provider, max_tokens, temperature, user_id)

    def chat(
        self, user_input, system_message=None, chat_history=None, prompt_type=None
    ):
        """
        Chat with the LLM

        Args:
            user_input: User message
            system_message: Optional system message
            chat_history: Optional chat history
            prompt_type: Optional prompt type to use (overrides system_message)

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

        # Check if this is a prompt type change command
        if user_input.lower().startswith("prompt:"):
            prompt_type_requested = user_input[7:].strip().lower()
            if prompt_type_requested in prompts:
                prompt_type = prompt_type_requested
                logger.info(f"Changed prompt type to: {prompt_type}")
                return f"Prompt type changed to: {prompt_type}", chat_history
            else:
                available_prompts = ", ".join(prompts.keys())
                return (
                    f"Invalid prompt type. Available options: {available_prompts}",
                    chat_history,
                )

        # Add user message to chat history
        chat_history.append({"role": "user", "content": user_input})

        # Create system message with memories if available
        final_system_message = system_message
        if hasattr(self, "memory") and self.memory is not None:
            try:
                # Search for relevant memories with the actual query
                # (Skip the empty query search that was causing the 400 error)
                logger.info(
                    f"Searching for memories with query: '{user_input}' for user: '{self.user_id}'"
                )

                # Use try-except to handle the case where there are fewer memories than requested
                try:
                    relevant_memories = self.memory.search(
                        query=user_input, user_id=self.user_id, limit=5
                    )
                    logger.info(f"Found {len(relevant_memories)} relevant memories")
                except Exception as e:
                    # If there's an error with the limit, try with a smaller limit
                    logger.warning(
                        f"Memory search error: {str(e)}, trying with smaller limit"
                    )
                    try:
                        relevant_memories = self.memory.search(
                            query=user_input, user_id=self.user_id, limit=3
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
                    and "results" in relevant_memories
                    and len(relevant_memories["results"]) > 0
                ):
                    # Build memory text
                    memory_text = "Here are some relevant memories:\n\n"
                    for i, memory in enumerate(relevant_memories["results"]):
                        # Access the direct memory content (not in metadata)
                        content = memory.get("memory", "")
                        if content:
                            memory_text += f"{i+1}. {content}\n\n"

                    logger.info(f"Adding memories to system message:\n{memory_text}")

                    if final_system_message:
                        final_system_message = f"{final_system_message}\n\nRelevant information:\n{memory_text}"
                    else:
                        final_system_message = f"You are a helpful assistant. Consider this relevant information:\n{memory_text}"
                else:
                    logger.info("No relevant memories found")
            except Exception as e:
                logger.error(f"Error retrieving memories: {str(e)}")
                import traceback

                logger.error(traceback.format_exc())

        # If prompt_type is provided, override the system message
        if prompt_type and prompt_type in prompts:
            if final_system_message:
                final_system_message = (
                    f"{prompts[prompt_type]}\n\n{final_system_message}"
                )
            else:
                final_system_message = prompts[prompt_type]
            logger.info(f"Using prompt type: {prompt_type}")

        # Call appropriate API based on provider
        logger.info(f"Calling {self.provider.upper()} API with model {self.model}...")

        if self.provider == "openai":
            response_text = self.call_openai_api("", final_system_message, chat_history)
        elif self.provider == "anthropic":
            response_text = self.call_anthropic_api(
                "", final_system_message, chat_history
            )
        elif self.provider == "xai":
            response_text = self.call_xai_api("", final_system_message, chat_history)
        elif self.provider == "gemini":
            response_text = self.call_gemini_api("", final_system_message, chat_history)
        else:
            logger.error(f"Unknown provider: {self.provider}")
            return None, chat_history

        if not response_text:
            logger.error("Failed to get response from API")
            return (
                "Failed to get response from the model. Please try again.",
                chat_history,
            )

        # Add response to chat history
        chat_history.append({"role": "assistant", "content": response_text})

        return response_text, chat_history


def handle_interactive_chat(args, chat_module):
    """
    Handle interactive chat mode

    Args:
        args: Command line arguments
        chat_module: LLMChat instance
    """
    # Create system message
    system_message = args.system_message
    if args.description:
        base_system_message = chat_module.create_system_message_with_memories(
            args.description, args.memory_query
        )
        if system_message:
            system_message = f"{base_system_message}\n\n{system_message}"
        else:
            system_message = base_system_message

    # Initialize chat history
    chat_history = []

    # Print welcome message
    provider_model = f"{args.provider.upper()} ({chat_module.model})"
    print(f"Chat mode with {provider_model}")
    print("Type 'exit' or 'quit' to end the conversation.")
    print("Type 'save' to save the conversation history.")
    print("Type 'memory: <content>' to add a memory.")
    print("Type 'prompt: <type>' to change the prompt type.")
    print("--------------------------------------------------")
    print()

    # Interactive chat loop
    current_prompt_type = args.prompt_type
    while True:
        # Get user input
        user_input = input("You: ")
        if not user_input:
            continue

        # Handle special commands
        if user_input.lower() in ["exit", "quit"]:
            break
        elif user_input.lower() == "save":
            # Save chat history to file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"chat_history_{timestamp}.json"
            with open(filename, "w") as f:
                json.dump(chat_history, f, indent=2)
            print(f"Chat history saved to {filename}")
            continue
        elif user_input.lower().startswith("prompt:"):
            # Extract prompt type
            prompt_type_requested = user_input[7:].strip().lower()
            if prompt_type_requested in prompts:
                current_prompt_type = prompt_type_requested
                print(f"Prompt type changed to: {current_prompt_type}")
                continue
            else:
                available_prompts = ", ".join(prompts.keys())
                print(f"Invalid prompt type. Available options: {available_prompts}")
                continue

        # Get response from model
        response, chat_history = chat_module.chat(
            user_input, system_message, chat_history, current_prompt_type
        )

        # Print response
        print()
        print(f"A: {response}")
        print()


def main():
    """Main function to run LLM chat from command line"""
    parser = argparse.ArgumentParser(description="Chat with LLM")

    # Add arguments
    parser.add_argument(
        "--system-message",
        help="System message to include in API request",
    )
    parser.add_argument(
        "--description",
        help="Description to include in system message",
    )
    parser.add_argument(
        "--memory-query",
        help="Query to use for retrieving memories (optional)",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Run in interactive mode (default: false)",
    )
    parser.add_argument(
        "--prompt-type",
        default="dei",
        choices=prompts.keys(),
        help=f"Type of prompt to use (default: dei, available: {', '.join(prompts.keys())})",
    )

    # Common arguments for LLM configuration
    parser.add_argument(
        "--provider",
        default="xai",
        choices=["openai", "anthropic", "xai", "gemini"],
        help="LLM provider to use (default: xai)",
    )
    parser.add_argument(
        "--model",
        help="Model to use (default depends on provider)",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.1,
        help="Temperature for LLM (default: 0.1)",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=4096,
        help="Maximum tokens for LLM response (default: 4096)",
    )
    parser.add_argument(
        "--api-key",
        help="API key (optional, default: from environment variables)",
    )
    parser.add_argument(
        "--user-id",
        default="default_user",
        help="User ID for memory operations (default: default_user)",
    )

    # Parse arguments
    args = parser.parse_args()

    # Initialize chat module
    try:
        chat_module = LLMChat(
            api_key=args.api_key,
            model=args.model,
            provider=args.provider,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
            user_id=args.user_id,
        )
    except ValueError as e:
        logger.error(f"Error initializing chat module: {str(e)}")
        return 1

    # Run in interactive mode
    if args.interactive:
        handle_interactive_chat(args, chat_module)
    else:
        print("Error: Non-interactive mode not implemented. Use --interactive flag.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
