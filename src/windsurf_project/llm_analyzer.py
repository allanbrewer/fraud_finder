#!/usr/bin/env python3
import os
import argparse
import logging
import json
import pandas as pd
import requests
from datetime import datetime
import time
import sys
from dotenv import load_dotenv
from mem0 import Memory

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Import the prompt from promt.py
try:
    from promt import dei_prompt, ngo_fraud_prompt
    
    # Create a dictionary of available prompts
    available_prompts = {
        "dei": dei_prompt,
        "ngo_fraud": ngo_fraud_prompt
    }
    
    logging.info(f"Successfully imported prompts from promt.py: {', '.join(available_prompts.keys())}")
except ImportError:
    try:
        # Try relative import if the first import fails
        from .promt import dei_prompt, ngo_fraud_prompt
        
        # Create a dictionary of available prompts
        available_prompts = {
            "dei": dei_prompt,
            "ngo_fraud": ngo_fraud_prompt
        }
        
        logging.info(f"Successfully imported prompts from promt.py: {', '.join(available_prompts.keys())}")
    except ImportError:
        logging.error("Could not import prompts from promt.py")
        available_prompts = {}

# Set default prompt
default_prompt = dei_prompt if 'dei' in available_prompts else None


class LLMAnalyzer:
    """Class to analyze contract data using LLM APIs"""

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
        Initialize the LLM analyzer

        Args:
            api_key: API key for the LLM provider
            model: Model name to use
            provider: LLM provider (openai, anthropic, xai)
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
                self.model = "gpt-4o-mini"
            elif self.provider == "anthropic":
                self.model = "claude-3-7-sonnet-latest"
            elif self.provider == "xai":
                self.model = "grok-2-latest"
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

        if not api_key:
            raise ValueError(
                f"API key not provided and not found in .env file for {provider}"
            )

        self.api_key = api_key

        # Config Memory - only for supported providers
        if self.provider in ["openai", "anthropic", "xai"]:
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
                        }
                    }
                }
                
                self.memory = Memory.from_config(config)
                logging.info(f"Memory initialized with provider {mem_provider} using default storage location at ~/.mem0 for user '{self.user_id}'")
            except Exception as e:
                logging.warning(f"Failed to initialize memory: {str(e)}")
                import traceback
                logging.warning(traceback.format_exc())
                self.memory = None
        else:
            logging.warning(f"Memory not supported for provider {self.provider}")
            self.memory = None

    def prepare_csv_data(self, csv_file, max_rows=None):
        """
        Prepare CSV data for LLM analysis

        Args:
            csv_file: Path to CSV file
            max_rows: Maximum number of rows to include (None for all)

        Returns:
            String representation of CSV data
        """
        try:
            df = pd.read_csv(csv_file)
            total_rows = len(df)
            logging.info(f"CSV file contains {total_rows} rows")

            # Limit rows if specified
            if max_rows and len(df) > max_rows:
                logging.warning(
                    f"CSV file has {total_rows} rows, limiting to {max_rows} rows"
                )
                df = df.head(max_rows)

            # Convert to string representation
            csv_string = df.to_csv(index=False)
            return csv_string, total_rows

        except Exception as e:
            logging.error(f"Error preparing CSV data: {str(e)}")
            return None, 0

    def create_prompt_with_data(self, csv_data, custom_prompt=None, prompt_type="dei"):
        """
        Create prompt with CSV data

        Args:
            csv_data: CSV data to include in prompt
            custom_prompt: Custom prompt to use
            prompt_type: Type of prompt to use (default: dei)

        Returns:
            Complete prompt with CSV data
        """
        # Use custom prompt if provided, otherwise use selected prompt type
        if custom_prompt:
            final_prompt = custom_prompt
        elif prompt_type in available_prompts:
            final_prompt = available_prompts[prompt_type]
        else:
            final_prompt = default_prompt
            logging.warning(f"Prompt type '{prompt_type}' not found, using default prompt")

        # Add CSV data to prompt
        complete_prompt = (
            f"{final_prompt}\n\nHere is the CSV data to analyze:\n\n{csv_data}"
        )
        return complete_prompt

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

        # Add current prompt if not in chat mode
        if not chat_history:
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
            logging.error(f"Error calling OpenAI API: {str(e)}")
            if hasattr(e, "response") and e.response is not None:
                logging.error(f"Response status: {e.response.status_code}")
                logging.error(f"Response body: {e.response.text}")
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

        messages = []

        # Add chat history if provided
        if chat_history:
            messages.extend(chat_history)
        else:
            # Add current prompt if not in chat mode
            messages.append({"role": "user", "content": complete_prompt})

        system = "You are a contract analysis expert. Respond only with valid JSON."
        if system_message:
            system = system_message

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "system": system,
        }

        try:
            response = requests.post(
                "https://api.anthropic.com/v1/messages", headers=headers, json=payload
            )
            response.raise_for_status()

            result = response.json()
            return result["content"][0]["text"]

        except requests.exceptions.RequestException as e:
            logging.error(f"Error calling Anthropic API: {str(e)}")
            if hasattr(e, "response") and e.response is not None:
                logging.error(f"Response status: {e.response.status_code}")
                logging.error(f"Response body: {e.response.text}")
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
            logging.error(f"Error calling Xai API: {str(e)}")
            if hasattr(e, "response") and e.response is not None:
                logging.error(f"Response status: {e.response.status_code}")
                logging.error(f"Response body: {e.response.text}")
            return None

    def analyze_csv(
        self,
        csv_file,
        custom_prompt=None,
        max_rows=None,
        output_file=None,
        system_message=None,
        description=None,
        memory_query=None,
        prompt_type="dei"
    ):
        """
        Analyze CSV file using LLM

        Args:
            csv_file: Path to CSV file
            custom_prompt: Custom prompt to use
            max_rows: Maximum number of rows to include
            output_file: Path to save output JSON
            system_message: Optional system message to include
            description: Optional description to include in the system message
            memory_query: Optional query to use for retrieving memories
            prompt_type: Type of prompt to use (default: dei)

        Returns:
            Analysis results as JSON object
        """
        # Prepare CSV data
        csv_data, total_rows = self.prepare_csv_data(csv_file, max_rows)
        if not csv_data:
            return None

        # Create complete prompt
        complete_prompt = self.create_prompt_with_data(csv_data, custom_prompt, prompt_type)

        # Create system message with description and memories if available
        final_system_message = self.create_system_message_with_memories(
            description, memory_query
        )
        if system_message:
            final_system_message = f"{final_system_message}\n\n{system_message}"

        # Call appropriate API based on provider
        logging.info(f"Calling {self.provider.upper()} API with model {self.model}...")
        start_time = time.time()

        if self.provider == "openai":
            response_text = self.call_openai_api(complete_prompt, final_system_message)
        elif self.provider == "anthropic":
            response_text = self.call_anthropic_api(complete_prompt, final_system_message)
        elif self.provider == "xai":
            response_text = self.call_xai_api(complete_prompt, final_system_message)
        else:
            logging.error(f"Unknown provider: {self.provider}")
            return None

        elapsed_time = time.time() - start_time
        logging.info(f"API call completed in {elapsed_time:.2f} seconds")

        if not response_text:
            return None

        # Parse JSON response
        try:
            result = json.loads(response_text)

            # Handle case where result is a list instead of a dictionary
            if isinstance(result, list):
                logging.warning(
                    "API returned a list instead of a dictionary. Converting to dictionary format."
                )
                result = {"dei_contracts": [], "doge_targets": result}

            # Ensure result has the expected structure
            if not isinstance(result, dict):
                logging.error(f"Unexpected result type: {type(result)}")
                logging.error(f"Raw response: {response_text}")
                return None

            # Ensure the required keys exist
            if "dei_contracts" not in result:
                result["dei_contracts"] = []
            if "doge_targets" not in result:
                result["doge_targets"] = []

            # Count contracts in output
            dei_count = len(result.get("dei_contracts", []))
            doge_count = len(result.get("doge_targets", []))
            total_contracts = dei_count + doge_count

            logging.info(
                f"LLM analysis found {total_contracts} contracts: {dei_count} DEI contracts and {doge_count} DOGE targets"
            )

            # Save to file if specified
            if output_file:
                with open(output_file, "w") as f:
                    json.dump(result, f, indent=2)
                logging.info(f"Results saved to {output_file}")

            return result

        except json.JSONDecodeError as e:
            logging.error(f"Error parsing JSON response: {str(e)}")
            logging.error(f"Raw response: {response_text}")
            return None

    def analyze_multiple_csv(
        self,
        csv_files,
        custom_prompt=None,
        max_rows=None,
        output_dir=None,
        system_message=None,
        description=None,
        memory_query=None,
        prompt_type="dei"
    ):
        """
        Analyze multiple CSV files

        Args:
            csv_files: List of CSV files to analyze
            custom_prompt: Custom prompt to use
            max_rows: Maximum rows to include
            output_dir: Directory to save output files
            system_message: Optional system message to include
            description: Optional description to include in the system message
            memory_query: Optional query to use for retrieving memories
            prompt_type: Type of prompt to use (default: dei)

        Returns:
            Dictionary of results by filename
        """
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        results = {}

        for csv_file in csv_files:
            filename = os.path.basename(csv_file)
            logging.info(f"Analyzing {filename}...")

            # Create output file path
            output_file = None
            if output_dir:
                output_file = os.path.join(
                    output_dir,
                    f"analysis_{os.path.splitext(filename)[0]}.json",
                )

            result = self.analyze_csv(
                csv_file,
                custom_prompt,
                max_rows,
                output_file,
                system_message,
                description,
                memory_query,
                prompt_type
            )

            if result:
                results[filename] = result

        return results

    def chat(
        self, user_input, system_message=None, chat_history=None
    ):
        """
        Chat with the LLM

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

        # Add user message to chat history
        chat_history.append({"role": "user", "content": user_input})

        # Create system message with memories if available
        final_system_message = system_message
        if hasattr(self, "memory") and self.memory is not None:
            try:
                # Search for relevant memories with the actual query
                # (Skip the empty query search that was causing the 400 error)
                logging.info(f"Searching for memories with query: '{user_input}' for user: '{self.user_id}'")
                relevant_memories = self.memory.search(
                    query=user_input, user_id=self.user_id, limit=5
                )
                
                # Log the raw memory results for debugging
                logging.info(f"Memory search results: {relevant_memories}")
                
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
                    
                    if final_system_message:
                        final_system_message = (
                            f"{system_message}\n\nRelevant information:\n{memory_text}"
                        )
                    else:
                        final_system_message = f"You are a helpful assistant. Consider this relevant information:\n{memory_text}"
                        
                    logging.info(
                        f"Added {len(relevant_memories['results'])} memories to system message"
                    )
            except Exception as e:
                logging.warning(f"Error retrieving memories: {str(e)}")
                import traceback
                logging.warning(traceback.format_exc())

        # Call appropriate API based on provider
        logging.info(
            f"Calling {self.provider.upper()} API for chat with model {self.model}..."
        )
        start_time = time.time()

        if self.provider == "openai":
            response_text = self.call_openai_api("", final_system_message, chat_history)
        elif self.provider == "anthropic":
            response_text = self.call_anthropic_api(
                "", final_system_message, chat_history
            )
        elif self.provider == "xai":
            response_text = self.call_xai_api("", final_system_message, chat_history)
        else:
            logging.error(f"Unknown provider: {self.provider}")
            return None, chat_history

        elapsed_time = time.time() - start_time
        logging.info(f"API call completed in {elapsed_time:.2f} seconds")

        if not response_text:
            return None, chat_history

        # Add assistant response to chat history
        chat_history.append({"role": "assistant", "content": response_text})

        return response_text, chat_history

    def add_memory(self, content, metadata=None):
        """
        Add a memory to the memory system

        Args:
            content: Memory content
            metadata: Optional metadata

        Returns:
            True if memory was added, False otherwise
        """
        if not hasattr(self, "memory") or self.memory is None:
            logging.warning(f"Memory not supported for provider {self.provider}")
            return False

        try:
            # Log memory addition attempt
            logging.info(f"Attempting to add memory for user '{self.user_id}': {content}")
            
            # Add memory directly as a string - this is the format that works best with mem0
            result = self.memory.add(content, user_id=self.user_id, metadata=metadata or {})
            logging.info(f"Added memory using string format: {result}")
            
            # Don't try to list all memories as it causes a 400 error with empty query
            logging.info(f"Successfully added memory for user {self.user_id}: {content}")
            return True
        except Exception as e:
            logging.error(f"Error adding memory: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
            return False

    def create_system_message_with_memories(
        self, description=None, query=None
    ):
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
                logging.info(f"Searching for memories with query: '{query}' for user: '{self.user_id}'")
                relevant_memories = self.memory.search(
                    query=query, user_id=self.user_id, limit=5
                )
                logging.info(f"Memory search results: {relevant_memories}")
                
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
                    base_message = (
                        f"{base_message}\n\nRelevant information:\n{memory_text}"
                    )
                    logging.info(
                        f"Added {len(relevant_memories['results'])} memories to system message"
                    )
            except Exception as e:
                logging.warning(f"Error retrieving memories: {str(e)}")
                import traceback
                logging.warning(traceback.format_exc())

        return base_message


def main():
    """Main function to run LLM analysis from command line"""
    parser = argparse.ArgumentParser(description="Analyze contracts using LLM APIs")

    # Create subparsers for different modes
    subparsers = parser.add_subparsers(dest="mode", help="Operation mode")

    # Analyze CSV mode
    analyze_parser = subparsers.add_parser(
        "analyze", help="Analyze contracts in CSV files"
    )
    analyze_parser.add_argument(
        "--csv-file",
        required=True,
        help="Path to CSV file or directory containing CSV files",
    )
    analyze_parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Maximum rows to include from CSV (default: all)",
    )
    analyze_parser.add_argument(
        "--output-dir",
        default="llm_analysis",
        help="Directory to save output files (default: llm_analysis)",
    )
    analyze_parser.add_argument(
        "--prompt-type",
        default="dei",
        choices=["dei", "ngo_fraud"],
        help="Type of prompt to use (default: dei)",
    )
    analyze_parser.add_argument(
        "--prompt-file",
        default=None,
        help="Custom prompt file (default: use built-in prompt)",
    )
    analyze_parser.add_argument(
        "--system-message",
        default="You are an expert contract analyst for the Department of Government Efficiency (DOGE).",
        help="System message to include in API call",
    )
    analyze_parser.add_argument(
        "--description",
        default=None,
        help="Simple description to include in the system message",
    )
    analyze_parser.add_argument(
        "--memory-query",
        default=None,
        help="Query to use for retrieving memories",
    )

    # Chat mode
    chat_parser = subparsers.add_parser("chat", help="Chat with the LLM")
    chat_parser.add_argument(
        "--message",
        default=None,
        help="Message to send to the LLM (non-interactive mode)",
    )
    chat_parser.add_argument(
        "--interactive",
        action="store_true",
        help="Start interactive chat session",
    )
    chat_parser.add_argument(
        "--save-history",
        default=None,
        help="File to save chat history to",
    )
    chat_parser.add_argument(
        "--system-message",
        default="You are an expert contract analyst for the Department of Government Efficiency (DOGE).",
        help="System message to include in API call",
    )
    chat_parser.add_argument(
        "--load-history",
        default=None,
        help="File to load chat history from",
    )

    # Common arguments for both modes
    for subparser in [analyze_parser, chat_parser]:
        subparser.add_argument(
            "--provider",
            default="xai",
            choices=["openai", "anthropic", "xai"],
            help="LLM provider to use (default: xai)",
        )
        subparser.add_argument(
            "--model",
            default=None,
            help="Model name to use (default: provider-specific default)",
        )
        subparser.add_argument(
            "--max-tokens",
            type=int,
            default=4096,
            help="Maximum tokens for response (default: 4096)",
        )
        subparser.add_argument(
            "--temperature",
            type=float,
            default=0.1,
            help="Temperature for response generation (default: 0.1)",
        )
        subparser.add_argument(
            "--user-id",
            default="default_user",
            help="User ID for memory operations (default: default_user)",
        )
        subparser.add_argument(
            "--api-key",
            default=None,
            help="API key (default: read from .env file)",
        )

    args = parser.parse_args()

    # Default to analyze mode if no mode specified
    if not args.mode:
        parser.print_help()
        return 1

    # Initialize analyzer
    try:
        analyzer = LLMAnalyzer(
            api_key=args.api_key,
            model=args.model,
            provider=args.provider,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
            user_id=args.user_id,
        )
    except ValueError as e:
        logging.error(str(e))
        return 1

    # Handle different modes
    if args.mode == "analyze":
        return handle_analyze_mode(args, analyzer)
    elif args.mode == "chat":
        return handle_chat_mode(args, analyzer)
    else:
        parser.print_help()
        return 1


def handle_analyze_mode(args, analyzer):
    """Handle analyze mode"""
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)

    # Load custom prompt if specified
    custom_prompt = None
    if args.prompt_file:
        try:
            with open(args.prompt_file, "r") as f:
                custom_prompt = f.read()
        except Exception as e:
            logging.error(f"Error reading prompt file: {str(e)}")
            return 1

    # Process CSV files
    if os.path.isdir(args.csv_file):
        # Process all CSV files in directory
        csv_files = [
            os.path.join(args.csv_file, f)
            for f in os.listdir(args.csv_file)
            if f.endswith(".csv")
        ]

        if not csv_files:
            logging.error(f"No CSV files found in {args.csv_file}")
            return 1

        logging.info(f"Found {len(csv_files)} CSV files to analyze")

        results = analyzer.analyze_multiple_csv(
            csv_files,
            custom_prompt,
            args.max_rows,
            args.output_dir,
            args.system_message,
            args.description,
            args.memory_query,
            args.prompt_type
        )

        # Save summary
        summary_file = os.path.join(args.output_dir, "analysis_summary.json")
        with open(summary_file, "w") as f:
            summary = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "provider": args.provider,
                "model": analyzer.model,
                "files_analyzed": len(results),
                "files": list(results.keys()),
            }
            json.dump(summary, f, indent=2)

        logging.info(f"Analysis complete. Results saved to {args.output_dir}")

    else:
        # Process single CSV file
        if not os.path.isfile(args.csv_file):
            logging.error(f"CSV file not found: {args.csv_file}")
            return 1

        output_file = os.path.join(
            args.output_dir,
            f"analysis_{os.path.splitext(os.path.basename(args.csv_file))[0]}.json",
        )

        result = analyzer.analyze_csv(
            args.csv_file,
            custom_prompt,
            args.max_rows,
            output_file,
            args.system_message,
            args.description,
            args.memory_query,
            args.prompt_type
        )

        if result:
            logging.info(f"Analysis complete. Results saved to {output_file}")
        else:
            logging.error("Analysis failed")
            return 1

    return 0


def handle_chat_mode(args, analyzer):
    """Handle chat mode"""
    # Load chat history if specified
    chat_history = None
    if args.load_history:
        try:
            with open(args.load_history, "r") as f:
                chat_history = json.load(f)
            logging.info(f"Loaded chat history from {args.load_history}")
        except Exception as e:
            logging.error(f"Error loading chat history: {str(e)}")
            chat_history = []

    # Interactive mode
    if args.interactive:
        print(f"Chat mode with {args.provider.upper()} ({analyzer.model})")
        print("Type 'exit' or 'quit' to end the conversation.")
        print("Type 'save' to save the conversation history.")
        print("Type 'memory: <content>' to add a memory.")
        print("-" * 50)

        # Initialize chat history if not loaded
        if chat_history is None:
            chat_history = []

        while True:
            try:
                user_input = input("\nYou: ")

                # Check for exit commands
                if user_input.lower() in ["exit", "quit"]:
                    break

                # Check for save command
                if user_input.lower() == "save":
                    save_path = args.save_history or "chat_history.json"
                    with open(save_path, "w") as f:
                        json.dump(chat_history, f, indent=2)
                    print(f"Chat history saved to {save_path}")
                    continue

                # Check for memory command
                if user_input.lower().startswith("memory:"):
                    memory_content = user_input[7:].strip()
                    if memory_content:
                        success = analyzer.add_memory(memory_content)
                        if success:
                            print(f"Memory added: {memory_content}")
                        else:
                            print(
                                "Failed to add memory. Memory might not be supported with the current provider."
                            )
                    else:
                        print("Memory content cannot be empty")
                    continue

                # Get response
                response, chat_history = analyzer.chat(
                    user_input, args.system_message, chat_history
                )

                if response:
                    print(f"\nAssistant: {response}")
                else:
                    print("\nAssistant: Sorry, I couldn't generate a response.")

            except KeyboardInterrupt:
                print("\nExiting chat...")
                break
            except Exception as e:
                logging.error(f"Error in chat: {str(e)}")
                print("\nAn error occurred. Please try again.")

        # Save chat history if specified
        if args.save_history and chat_history:
            try:
                with open(args.save_history, "w") as f:
                    json.dump(chat_history, f, indent=2)
                logging.info(f"Saved chat history to {args.save_history}")
            except Exception as e:
                logging.error(f"Error saving chat history: {str(e)}")

    # Single message mode
    elif args.message:
        response, _ = analyzer.chat(
            args.message, args.system_message, chat_history
        )
        if response:
            print(response)
        else:
            logging.error("Failed to get response")
            return 1

    # No message or interactive mode specified
    else:
        logging.error(
            "Either --message or --interactive must be specified for chat mode"
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
