#!/usr/bin/env python3
import os
import json
import argparse
import logging
import pandas as pd
from datetime import datetime
import time
import sys
from dotenv import load_dotenv

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

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

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
                "dei": "Analyze this CSV data to identify diversity, equity, and inclusion (DEI) contracts. Focus on finding contracts that mention diversity, inclusion, equity, race, gender, or related concepts.",
                "ngo_fraud": "Analyze this CSV for potential fraud in NGO contracts. Look for unusual patterns, inflated costs, vague descriptions, or any red flags that might indicate waste or fraud.",
            }


class CSVAnalyzer(BaseLLM):
    """Class to analyze contract data from CSV files using LLM APIs"""

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
            # Load CSV data
            df = pd.read_csv(csv_file)
            logger.info(f"Loaded CSV with {len(df)} rows and {len(df.columns)} columns")

            # Limit rows if specified
            if max_rows and max_rows < len(df):
                df = df.head(max_rows)
                logger.info(f"Limited to {max_rows} rows")

            # Convert to string representation
            csv_string = df.to_string()
            return csv_string
        except Exception as e:
            logger.error(f"Error preparing CSV data: {str(e)}")
            return None

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
        # Use custom prompt if provided, otherwise use default prompt
        if custom_prompt:
            instruction = custom_prompt
        elif prompt_type in prompts:
            instruction = prompts[prompt_type]
        else:
            instruction = prompts["dei"]  # Default to DEI prompt

        # Create complete prompt with CSV data
        complete_prompt = f"{instruction}\n\nHere is the CSV data:\n\n{csv_data}"
        return complete_prompt

    def create_system_message_with_memories(self, description=None, memory_query=None):
        """
        Create system message with relevant memories

        Args:
            description: Optional description to include in system message
            memory_query: Optional query to use for retrieving memories

        Returns:
            System message with memories
        """
        # Start with base message
        base_message = (
            description
            or "You are an expert contract analyst for the Department of Government Efficiency (DOGE)."
        )

        # Add memories if available
        if hasattr(self, "memory") and self.memory is not None and memory_query:
            try:
                logger.info(
                    f"Searching for memories with query: '{memory_query}' for user: '{self.user_id}'"
                )

                try:
                    # Search for relevant memories
                    relevant_memories = self.memory.search(
                        query=memory_query, user_id=self.user_id, limit=5
                    )
                    logger.info(f"Found {len(relevant_memories)} relevant memories")
                except Exception as e:
                    # Try with smaller limit if needed
                    logger.warning(
                        f"Memory search error: {str(e)}, trying with smaller limit"
                    )
                    try:
                        relevant_memories = self.memory.search(
                            query=memory_query, user_id=self.user_id, limit=3
                        )
                        logger.info(
                            f"Found {len(relevant_memories)} relevant memories with reduced limit"
                        )
                    except Exception as e2:
                        logger.error(
                            f"Memory search failed with reduced limit: {str(e2)}"
                        )
                        relevant_memories = []

                # Log memory search results
                logger.info(f"Memory search results: {relevant_memories}")

                # Add memories to system message if found
                if (
                    relevant_memories
                    and "results" in relevant_memories
                    and len(relevant_memories["results"]) > 0
                ):
                    # Build memory text
                    memory_text = "Here are some relevant memories:\n\n"
                    for i, memory in enumerate(relevant_memories["results"]):
                        # Access the direct memory content
                        content = memory.get("memory", "")
                        if content:
                            memory_text += f"{i+1}. {content}\n\n"

                    logger.info(f"Adding memories to system message:\n{memory_text}")
                    base_message = (
                        f"{base_message}\n\nRelevant information:\n{memory_text}"
                    )
                else:
                    logger.info("No relevant memories found")
            except Exception as e:
                logger.error(f"Error retrieving memories: {str(e)}")
                import traceback

                logger.error(traceback.format_exc())

        return base_message

    def analyze_csv(
        self,
        csv_file,
        custom_prompt=None,
        max_rows=None,
        output_file=None,
        system_message=None,
        description=None,
        memory_query=None,
        prompt_type="dei",
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
        csv_data = self.prepare_csv_data(csv_file, max_rows)
        if not csv_data:
            return None

        # Create prompt
        complete_prompt = self.create_prompt_with_data(
            csv_data, custom_prompt, prompt_type
        )

        # Create system message with memories if available
        final_system_message = self.create_system_message_with_memories(
            description, memory_query
        )
        if system_message:
            final_system_message = f"{final_system_message}\n\n{system_message}"

        # Call appropriate API based on provider
        logger.info(f"Calling {self.provider.upper()} API with model {self.model}...")
        start_time = time.time()

        if self.provider == "openai":
            response_text = self.call_openai_api(complete_prompt, final_system_message)
        elif self.provider == "anthropic":
            response_text = self.call_anthropic_api(
                complete_prompt, final_system_message
            )
        elif self.provider == "xai":
            response_text = self.call_xai_api(complete_prompt, final_system_message)
        else:
            logger.error(f"Unknown provider: {self.provider}")
            return None

        end_time = time.time()
        logger.info(f"API call completed in {end_time - start_time:.2f} seconds")

        if not response_text:
            logger.error("Failed to get response from API")
            return None

        # Parse JSON response
        try:
            result = json.loads(response_text)

            # Save to file if output file is specified
            if output_file:
                with open(output_file, "w") as f:
                    json.dump(result, f, indent=2)
                logger.info(f"Analysis saved to {output_file}")

            return result
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON response: {response_text}")

            # Save raw response to file if output file is specified
            if output_file:
                with open(output_file, "w") as f:
                    f.write(response_text)
                logger.info(f"Raw response saved to {output_file}")

            return {"error": "Failed to parse response", "raw_response": response_text}

    def analyze_multiple_csv(
        self,
        csv_files,
        custom_prompt=None,
        max_rows=None,
        output_dir=None,
        system_message=None,
        description=None,
        memory_query=None,
        prompt_type="dei",
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
        results = {}

        # Create output directory if it doesn't exist
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            logger.info(f"Created output directory: {output_dir}")

        # Analyze each CSV file
        for csv_file in csv_files:
            logger.info(f"Analyzing {csv_file}...")

            # Set output file path if output directory is specified
            output_file = None
            if output_dir:
                filename = os.path.basename(csv_file)
                base_name = os.path.splitext(filename)[0]
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_file = os.path.join(
                    output_dir, f"{base_name}_analysis_{timestamp}.json"
                )

            # Analyze CSV file
            result = self.analyze_csv(
                csv_file,
                custom_prompt,
                max_rows,
                output_file,
                system_message,
                description,
                memory_query,
                prompt_type,
            )

            # Add result to dictionary
            results[csv_file] = result

        return results


def main():
    """Main function to run CSV analysis from command line"""
    parser = argparse.ArgumentParser(description="Analyze CSV files using LLM")

    # Add subparser for analyze command
    parser.add_argument(
        "csv_files",
        nargs="+",
        help="CSV files to analyze",
    )
    parser.add_argument(
        "--custom-prompt",
        help="Custom prompt to use for analysis",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        help="Maximum number of rows to include from CSV",
    )
    parser.add_argument(
        "--output-dir",
        help="Directory to save output files",
    )
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
        "--prompt-type",
        default="dei",
        choices=prompts.keys(),
        help=f"Type of prompt to use (default: dei, available: {', '.join(prompts.keys())})",
    )

    # Common arguments for LLM configuration
    parser.add_argument(
        "--provider",
        default="xai",
        choices=["openai", "anthropic", "xai"],
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

    # Initialize analyzer
    try:
        analyzer = CSVAnalyzer(
            api_key=args.api_key,
            model=args.model,
            provider=args.provider,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
            user_id=args.user_id,
        )
    except ValueError as e:
        logger.error(f"Error initializing analyzer: {str(e)}")
        return 1

    # Analyze CSV files
    results = analyzer.analyze_multiple_csv(
        args.csv_files,
        args.custom_prompt,
        args.max_rows,
        args.output_dir,
        args.system_message,
        args.description,
        args.memory_query,
        args.prompt_type,
    )

    # Print results
    for csv_file, result in results.items():
        if result:
            logger.info(f"Analysis for {csv_file} completed successfully")
        else:
            logger.error(f"Analysis for {csv_file} failed")

    return 0


if __name__ == "__main__":
    sys.exit(main())
