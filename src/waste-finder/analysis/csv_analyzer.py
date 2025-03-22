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

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Handle imports for both direct execution and module import
try:
    # Try relative import (when used as a package)
    from ..core.base_llm import BaseLLM
    from ..core.prompt import prompts

    logger.debug(f"Using relative imports")
except ImportError:
    try:
        # Try absolute import with dots (common when using python -m)
        from src.waste_finder.core.base_llm import BaseLLM
        from src.waste_finder.core.prompt import prompts

        logger.debug(f"Using absolute imports with dots")
    except ImportError:
        try:
            # Try absolute import with underscores (fallback)
            from src.waste_finder.core.base_llm import BaseLLM
            from src.waste_finder.core.prompt import prompts

            logger.debug(f"Using absolute imports with underscores")
        except ImportError:
            # Last resort: modify sys.path and try again
            parent_dir = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "../..")
            )
            if parent_dir not in sys.path:
                sys.path.insert(0, parent_dir)
            try:
                from src.waste_finder.core.base_llm import BaseLLM
                from src.waste_finder.core.prompt import prompts

                logger.debug(f"Using sys.path modification and absolute imports")
            except ImportError as e:
                logger.error(f"Failed to import required modules: {e}")
                # Provide fallback prompts
                prompts = {
                    "waste": "Analyze this CSV data to identify wasteful contracts with vague descriptions.",
                    "ngo_fraud": "Analyze this CSV for potential fraud in NGO contracts.",
                }
                raise ImportError(
                    f"Could not import BaseLLM. Check your Python path and file structure: {e}"
                )

# Log available prompts
if "prompts" in locals():
    logger.info(f"Available prompts: {', '.join(prompts.keys())}")


class CSVAnalyzer(BaseLLM):
    """Class to analyze contract data from CSV files using LLM APIs"""

    def prepare_csv_data(self, csv_file, max_rows=None, start_row=0, batch_size=None):
        """
        Prepare CSV data for LLM analysis

        Args:
            csv_file: Path to CSV file
            max_rows: Maximum number of rows to include (None for all)
            start_row: Starting row index for batch processing
            batch_size: Number of rows to include in this batch

        Returns:
            String representation of CSV data and total number of rows
        """
        try:
            # Load CSV data
            df = pd.read_csv(csv_file)
            total_rows = len(df)
            logger.info(
                f"Loaded CSV with {total_rows} rows and {len(df.columns)} columns"
            )

            # Apply max_rows limit if specified
            if max_rows and max_rows < total_rows:
                df = df.iloc[:max_rows]
                total_rows = len(df)
                logger.info(f"Limited to {max_rows} rows")

            # Apply batch processing if specified
            if batch_size:
                end_row = min(start_row + batch_size, total_rows)
                df = df.iloc[start_row:end_row]
                logger.info(
                    f"Processing batch from row {start_row} to {end_row-1} ({len(df)} rows)"
                )

            # Convert to string representation
            csv_string = df.to_string()
            return csv_string, total_rows
        except Exception as e:
            logger.error(f"Error preparing CSV data: {str(e)}")
            return None, 0

    def create_prompt_with_data(
        self, csv_data, custom_prompt=None, prompt_type="waste"
    ):
        """
        Create prompt with CSV data

        Args:
            csv_data: CSV data to include in prompt
            custom_prompt: Custom prompt to use
            prompt_type: Type of prompt to use (default: waste)

        Returns:
            Complete prompt with CSV data
        """
        # Use custom prompt if provided, otherwise use default prompt
        if custom_prompt:
            instruction = custom_prompt
            logger.info("Using custom prompt")
        elif prompt_type in prompts:
            instruction = prompts[prompt_type]
            logger.info(f"Using prompt type: {prompt_type}")
        else:
            instruction = prompts["waste"]  # Default to Waste prompt
            logger.info("Using default prompt: waste")

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
        prompt_type="waste",
        batch_size=75,
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
            prompt_type: Type of prompt to use (default: waste)
            batch_size: Number of rows to process in each batch (default: 75)

        Returns:
            Analysis results as JSON object
        """
        # First check if the file exists
        if not os.path.exists(csv_file):
            logger.error(f"CSV file not found: {csv_file}")
            return None

        # Get total rows and prepare first batch
        csv_data, total_rows = self.prepare_csv_data(csv_file, max_rows)
        if not csv_data:
            return None

        # If total rows is less than batch size, process normally
        if max_rows and max_rows <= batch_size:
            return self._analyze_csv_single_batch(
                csv_data,
                custom_prompt,
                output_file,
                system_message,
                description,
                memory_query,
                prompt_type,
            )

        # For larger files, process in batches
        if total_rows > batch_size:
            logger.info(
                f"CSV has {total_rows} rows, processing in batches of {batch_size}"
            )

            # Initialize combined results
            combined_results = {"doge_targets": []}

            # Calculate effective total rows (considering max_rows limit)
            effective_total = min(total_rows, max_rows) if max_rows else total_rows

            # Process each batch
            for start_row in range(0, effective_total, batch_size):
                batch_end = min(start_row + batch_size, effective_total)
                logger.info(
                    f"Processing batch {start_row//batch_size + 1}: rows {start_row} to {batch_end-1}"
                )

                # Prepare batch data
                batch_data, _ = self.prepare_csv_data(
                    csv_file,
                    max_rows=effective_total,
                    start_row=start_row,
                    batch_size=batch_size,
                )

                # Process this batch
                batch_result = self._analyze_csv_single_batch(
                    batch_data,
                    custom_prompt,
                    None,  # Don't save intermediate batches
                    system_message,
                    description,
                    memory_query,
                    prompt_type,
                )

                # Combine results
                if batch_result and "doge_targets" in batch_result:
                    combined_results["doge_targets"].extend(
                        batch_result["doge_targets"]
                    )
                    logger.info(
                        f"Added {len(batch_result['doge_targets'])} targets from batch {start_row//batch_size + 1}"
                    )
                else:
                    logger.warning(
                        f"No valid results from batch {start_row//batch_size + 1}"
                    )

            # Save combined results
            if output_file and combined_results["doge_targets"]:
                with open(output_file, "w") as f:
                    json.dump(combined_results, f, indent=2)
                logger.info(f"Combined analysis saved to {output_file}")

            return combined_results

        # If we get here, process normally as a single batch
        return self._analyze_csv_single_batch(
            csv_data,
            custom_prompt,
            output_file,
            system_message,
            description,
            memory_query,
            prompt_type,
        )

    def _analyze_csv_single_batch(
        self,
        csv_data,
        custom_prompt=None,
        output_file=None,
        system_message=None,
        description=None,
        memory_query=None,
        prompt_type="waste",
    ):
        """
        Analyze a single batch of CSV data using LLM

        Args:
            csv_data: Prepared CSV data string
            custom_prompt: Custom prompt to use
            output_file: Path to save output JSON
            system_message: Optional system message to include
            description: Optional description to include in the system message
            memory_query: Optional query to use for retrieving memories
            prompt_type: Type of prompt to use (default: waste)

        Returns:
            Analysis results as JSON object
        """
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
        elif self.provider == "gemini":
            response_text = self.call_gemini_api(complete_prompt, final_system_message)
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
        prompt_type="waste",
        batch_size=75,
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
            prompt_type: Type of prompt to use (default: waste)
            batch_size: Number of rows to process in each batch (default: 75)

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
                    output_dir, f"analysis_{base_name}_{timestamp}.json"
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
                batch_size,
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
        default="waste",
        choices=prompts.keys(),
        help=f"Type of prompt to use (default: waste, available: {', '.join(prompts.keys())})",
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
    parser.add_argument(
        "--batch-size",
        type=int,
        default=75,
        help="Number of rows to process in each batch (default: 75)",
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
        args.batch_size,
    )

    # Print results
    for csv_file, result in results.items():
        if result:
            logger.info(f"Analysis for {csv_file} completed successfully")
        else:
            logger.error(f"Analysis for {csv_file} failed")

    return 0


if __name__ == "__main__":
    # This code only runs when the module is executed directly
    # It will not run when the module is imported
    sys.exit(main())
