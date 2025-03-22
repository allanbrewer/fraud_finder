#!/usr/bin/env python3
import os
import json
import argparse
import logging
import sys
from dotenv import load_dotenv
from datetime import datetime
import re
import time

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
                    "entity_research": "Analyze the grant data and entity infomration to research the entity and look for red flags and provide a concise report."
                }
                raise ImportError(
                    f"Could not import BaseLLM. Check your Python path and file structure: {e}"
                )

# Log available prompts
if "prompts" in locals():
    logger.info(f"Available prompts: {', '.join(prompts.keys())}")


class JSONAnalyzer(BaseLLM):
    """Class to analyze JSON contract data and research entities"""

    def __init__(
        self,
        api_key=None,
        model=None,
        provider="xai",
        max_tokens=4096,
        temperature=0.7,
        user_id="default_user",
        prompt_type="entity_research",
    ):
        """
        Initialize JSON Analyzer

        Args:
            api_key: API key for the LLM provider
            model: Model name to use
            provider: LLM provider (openai, anthropic, xai, gemini)
            max_tokens: Maximum tokens for response
            temperature: Temperature for response generation
            user_id: User ID for memory operations
            prompt_type: Type of prompt to use (default: entity_research)
        """
        super().__init__(api_key, model, provider, max_tokens, temperature, user_id)

    def research_entity(self, award_data, prompt_type="entity_research"):
        """
        Research an entity for more information

        Args:
            award_data: Dictionary containing award information
            prompt_type: Type of prompt to use (default: entity_research)

        Returns:
            String containing research information about the entity
        """
        # Create a system message that instructs the LLM to research the entity

        if prompt_type in prompts:
            system_message = prompts[prompt_type]
            logger.info(f"Using prompt type: {prompt_type}")
        else:
            system_message = prompts["entity_research"]  # Default to Research prompt
            logger.info("Using default prompt: entity_research")

        # Create a prompt to research the entity
        prompt = f"Research the following entity that recieved an award with the following details:\n{json.dumps(award_data, indent=2)}"

        logger.info(f"Researching award: \n{json.dumps(award_data, indent=2)}")

        # Call appropriate API based on provider
        logger.info(f"Calling {self.provider.upper()} API with model {self.model}...")
        start_time = time.time()

        if self.provider == "openai":
            response_text = self.call_openai_api(prompt, system_message)
        elif self.provider == "anthropic":
            response_text = self.call_anthropic_api(prompt, system_message)
        elif self.provider == "xai":
            response_text = self.call_xai_api(prompt, system_message)
        elif self.provider == "gemini":
            response_text = self.call_gemini_api(prompt, system_message)
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
            return result
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON response: {response_text}")
            return {"error": "Failed to parse response", "raw_response": response_text}

    def analyze_json(
        self,
        json_file,
        award_type=None,
        output_dir="llm_analysis",
        prompt_type="entity_research",
    ):
        """
        Analyze JSON file with contract data and research entities

        Args:
            json_file: Path to JSON file with contract data
            award_type: Type of award (procurement, grant, etc.)
            output_dir: Directory to save research results
            prompt_type: Type of prompt to use (default: entity_research)

        Returns:
            List or dictionary with research results
        """
        try:
            # Load JSON data
            with open(json_file, "r") as f:
                data = json.load(f)

            # Check if data is a dictionary with a list of targets
            if isinstance(data, dict):
                # Look for any list in the dictionary that might contain targets
                target_lists = []
                for key, value in data.items():
                    if isinstance(value, list) and len(value) > 0:
                        target_lists.append((key, value))

                # If we found lists of targets, process them
                if target_lists:
                    logger.info(
                        f"Found {len(target_lists)} lists of targets in the JSON data"
                    )
                    all_results = []

                    for list_name, targets in target_lists:
                        logger.info(
                            f"Processing list '{list_name}' with {len(targets)} entries"
                        )
                        results = self._process_multiple_entries(
                            targets, award_type, output_dir, prompt_type
                        )
                        if results:
                            # Add the list name to each result for reference
                            for result in results:
                                result["source_list"] = list_name
                            all_results.extend(results)

                    return all_results
                else:
                    # No lists found, process as a single entry
                    logger.info("Processing JSON as a single entry")
                    return self._process_single_entry(
                        data, award_type, output_dir, prompt_type
                    )
            elif isinstance(data, list):
                # Process as multiple entries directly
                logger.info(f"Processing JSON as a list with {len(data)} entries")
                return self._process_multiple_entries(
                    data, award_type, output_dir, prompt_type
                )
            else:
                logger.error(f"Unsupported data type: {type(data)}")
                return None
        except Exception as e:
            logger.error(f"Error analyzing JSON data: {str(e)}")
            return None

    def _process_single_entry(
        self, data, award_type=None, output_dir=None, prompt_type="entity_research"
    ):
        """
        Process a single grant entry from a dictionary

        Args:
            data: Dictionary containing grant data
            award_type: Type of award (procurement, grant, etc.)
            output_dir: Directory to save research results
            prompt_type: Type of prompt to use (default: entity_research)

        Returns:
            Dictionary with processed grant information
        """
        # Extract information from the entry
        grants_info = self._extract_from_dict(data)

        # Add award type if specified
        if award_type:
            grants_info["award_type"] = award_type

        # Research entity if required
        if "recipient_name" in grants_info:
            entity_research = self.research_entity(grants_info, prompt_type)
            grants_info["entity_research"] = entity_research

            # Save research results to file if output directory is specified
            if output_dir is not None:
                self._save_research_results(grants_info, output_dir)

        return grants_info

    def _process_multiple_entries(
        self, data, award_type=None, output_dir=None, prompt_type="entity_research"
    ):
        """
        Process multiple grant entries from a list

        Args:
            data: List containing grant data entries
            award_type: Type of award (procurement, grant, etc.)
            output_dir: Directory to save research results
            prompt_type: Type of prompt to use (default: entity_research)

        Returns:
            List of dictionaries with processed grant information
        """
        results = []

        for entry in data:
            if isinstance(entry, dict):
                # Process each entry
                grant_info = self._extract_from_dict(entry)

                # Add award type if specified
                if award_type:
                    grant_info["award_type"] = award_type

                # Research entity if required
                if "recipient_name" in grant_info:
                    entity_research = self.research_entity(grant_info, prompt_type)
                    grant_info["entity_research"] = entity_research

                    # Save research results to file if output directory is specified
                    if output_dir is not None:
                        self._save_research_results(grant_info, output_dir)

                results.append(grant_info)

        return results

    def _save_research_results(self, grants_info, output_dir="llm_analysis"):
        """
        Save research results to a file

        Args:
            grants_info: Dictionary containing grants information with entity research
            output_dir: Directory to save research results
        """
        try:
            # Create output directory if it doesn't exist
            os.makedirs(output_dir, exist_ok=True)

            # Extract entity name and award type for filename
            entity_name = grants_info.get("recipient_name", "unknown_entity")
            award_type = grants_info.get("award_type", "unknown_type")

            # Clean entity name for filename (remove special characters)
            clean_entity_name = (
                re.sub(r"[^\w\s-]", "", entity_name).strip().replace(" ", "_")
            )

            # Create filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"research_{clean_entity_name}_{award_type}_{timestamp}.json"
            filepath = os.path.join(output_dir, filename)

            # Save to file
            with open(filepath, "w") as f:
                json.dump(grants_info, f, indent=2)

            logger.info(f"Saved research results to {filepath}")

        except Exception as e:
            logger.error(f"Error saving research results: {str(e)}")

    def _extract_from_dict(self, data):
        """
        Extract grants information from dictionary

        Args:
            data: Dictionary containing grants information

        Returns:
            Dictionary with extracted grants information
        """
        grants_info = {}

        # Extract information from different possible JSON structures
        if isinstance(data, dict):
            # Try to extract from the top level
            if "award_id_fain" in data:
                grants_info["award_id"] = data.get("award_id_fain")
            elif "award_id_piid" in data:
                grants_info["award_id"] = data.get("award_id_piid")
            elif "id" in data:
                grants_info["award_id"] = data.get("id")

            # Extract description
            if "description" in data:
                grants_info["description"] = data.get("description")
            elif "prime_award_base_transaction_description" in data:
                grants_info["description"] = data.get(
                    "prime_award_base_transaction_description"
                )

            # Extract amount
            if "amount" in data:
                grants_info["amount"] = data.get("amount")
            elif "total_obligated_amount" in data:
                grants_info["amount"] = data.get("total_obligated_amount")
            elif "current_total_value_of_award" in data:
                grants_info["amount"] = data.get("current_total_value_of_award")

            # Extract recipient
            if "recipient" in data:
                grants_info["recipient_name"] = data.get("recipient")
            elif "recipient_name" in data:
                grants_info["recipient_name"] = data.get("recipient_name")

            # Extract recipient info if available
            if "recipient_info" in data:
                grants_info["recipient_info"] = data.get("recipient_info")

            # Copy any other relevant fields that might be useful
            for key in [
                "end_date",
                "period_of_performance_current_end_date",
                "award_type",
            ]:
                if key in data:
                    grants_info[key] = data.get(key)

            # Copy any other fields that aren't already captured
            for key, value in data.items():
                if key not in grants_info and key not in [
                    "award_id_fain",
                    "award_id_piid",
                    "id",
                    "description",
                    "prime_award_base_transaction_description",
                    "amount",
                    "total_obligated_amount",
                    "current_total_value_of_award",
                    "recipient",
                    "recipient_name",
                ]:
                    grants_info[key] = value

        # If we couldn't find enough information, log a warning
        required_fields = ["award_id", "recipient_name", "description"]
        missing_fields = [
            field for field in required_fields if field not in grants_info
        ]

        if missing_fields:
            logger.warning(
                f"Missing required fields in grant data: {', '.join(missing_fields)}"
            )

        return grants_info


def main():
    """Main function to run JSON analysis from command line"""
    parser = argparse.ArgumentParser(
        description="Analyze JSON grant data and research entities"
    )

    # Add input JSON file argument
    parser.add_argument(
        "json_file", help="Path to JSON file with grant data to analyze"
    )

    # Add output directory argument
    parser.add_argument(
        "--output-dir",
        "-o",
        default="llm_analysis",
        help="Directory to save research results (default: llm_analysis)",
    )

    # Add award type argument
    parser.add_argument(
        "--award-type",
        help="Type of award (procurement, grant, etc.)",
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
        help="Model to use (if not specified, will use provider's default model)",
    )

    parser.add_argument(
        "--temperature",
        type=float,
        default=0.7,
        help="Temperature for response generation (default: 0.7)",
    )

    parser.add_argument(
        "--max-tokens",
        type=int,
        default=4096,
        help="Maximum tokens for response (default: 4096)",
    )

    parser.add_argument(
        "--api-key",
        help="API key for LLM provider (if not specified, will use from .env file)",
    )

    parser.add_argument(
        "--user-id",
        default="default_user",
        help="User ID for memory operations (default: default_user)",
    )

    parser.add_argument(
        "--prompt-type",
        default="entity_research",
        choices=prompts.keys(),
        help=f"Type of prompt to use (default: entity_research, available: {', '.join(prompts.keys())})",
    )

    # Parse arguments
    args = parser.parse_args()

    # Initialize analyzer
    try:
        analyzer = JSONAnalyzer(
            api_key=args.api_key,
            model=args.model,
            provider=args.provider,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
            user_id=args.user_id,
            prompt_type=args.prompt_type,
        )
    except ValueError as e:
        logger.error(f"Error initializing analyzer: {str(e)}")
        return 1

    # Analyze JSON file
    result = analyzer.analyze_json(
        json_file=args.json_file,
        award_type=args.award_type,
        output_dir=args.output_dir,
        prompt_type=args.prompt_type,
    )

    # Print result
    if result:
        if isinstance(result, list):
            logger.info(f"Successfully analyzed {len(result)} grant entries")
            for i, entry in enumerate(result):
                print(f"\nEntry {i+1}:")
                print(json.dumps(entry, indent=2))
        else:
            logger.info("Successfully analyzed grant data")
            print(json.dumps(result, indent=2))
        return 0
    else:
        logger.error("Analysis failed")
        return 1


if __name__ == "__main__":
    # This code only runs when the module is executed directly
    # It will not run when the module is imported
    sys.exit(main())
