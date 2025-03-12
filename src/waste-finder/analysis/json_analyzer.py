#!/usr/bin/env python3
import os
import json
import argparse
import logging
import time
import sys
from dotenv import load_dotenv
from datetime import datetime
import re

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
                    "x_doge": "Generate a Twitter post about government waste and fraud.",
                    "x_post": "Create a social media post about suspicious government spending.",
                }
                raise ImportError(
                    f"Could not import BaseLLM. Check your Python path and file structure: {e}"
                )

# Log available prompts
if "prompts" in locals():
    logger.info(f"Available prompts: {', '.join(prompts.keys())}")


class JSONAnalyzer(BaseLLM):
    """Class to analyze JSON contract data and generate X/Twitter posts"""

    def __init__(
        self,
        api_key=None,
        model=None,
        provider="xai",
        max_tokens=4096,
        temperature=0.7,  # Higher temperature for creative post generation
        user_id="default_user",
    ):
        """
        Initialize JSON Analyzer

        Args:
            api_key: API key for the LLM provider
            model: Model name to use
            provider: LLM provider (openai, anthropic, xai)
            max_tokens: Maximum tokens for response
            temperature: Temperature for response generation
            user_id: User ID for memory operations
        """
        super().__init__(api_key, model, provider, max_tokens, temperature, user_id)

    def research_entity(self, award_data):
        """
        Research an entity for more information

        Args:
            award_data: Dictionary containing award information

        Returns:
            String containing research information about the entity
        """
        # Create a system message that instructs the LLM to research the entity
        system_message = """You are a government waste investigator researching entities that receive government grants.
        
        Use sources like USASpending.gov, fpds.gov, and other federal government databases to research the entity.

        Also look into company/NGO registation records online to get all available information.

        Look for:
        - News articles, affiliations, or reports indicating fraudulent activity, shell company traits, or conflicts of interest.
        - Red flags such as:
          - Lack of transparency (e.g., no website, minimal public info).
          - Sudden receipt of large grants with no prior track record.
          - Connections to known fraudulent entities or individuals.
          - Recent formation with no clear mission or activity history.
          - Leadership with conflicts of interest (e.g., ties to awarding agency).
        
        Provide a concise summary of findings, highlighting any red flags or lack thereof.
        
        Provide concise information about this entity focusing on:
        1. What type of organization they are
        2. Their main activities
        3. Any controversies or questionable practices
        4. Political affiliations or connections
        5. Recent news or developments
        6. What other activity do they do for the federal government
        7. Have they recieved additional grants and what are they
        
        Format your response as a brief research report with key facts only.
        """

        # Create a prompt to research the entity
        prompt = f"Research the following entity that recieved an award with the following details:\n{json.dumps(award_data, indent=2)}"

        logger.info(f"Researching entity: {award_data['recipient_name']}")

        if self.provider == "openai":
            response_text = self.call_openai_api(prompt, system_message)
        elif self.provider == "anthropic":
            response_text = self.call_anthropic_api(prompt, system_message)
        elif self.provider == "xai":
            response_text = self.call_xai_api(prompt, system_message)
        else:
            logger.error(f"Unknown provider: {self.provider}")
            return None

        return response_text

    def extract_grants_info(
        self, json_file, award_type=None, research_entities=True, output_dir=None
    ):
        """
        Extract grants information from JSON file

        Args:
            json_file: Path to JSON file
            award_type: Type of award (procurement, grant, etc.)
            research_entities: Whether to research entities
            output_dir: Directory to save research results (default: llm_analysis)

        Returns:
            Dictionary containing grants information
        """
        try:
            # Load JSON data
            with open(json_file, "r") as f:
                data = json.load(f)

            # Extract grants information
            grants_info = {}

            # Check if data is a dictionary or list
            if isinstance(data, dict):
                # Extract information from dictionary
                grants_info = self._extract_from_dict(data)
            elif isinstance(data, list):
                # Extract information from list
                grants_info = self._extract_from_list(data)
            else:
                logger.error(f"Unsupported data type: {type(data)}")
                return None

            # Add award type if specified
            if award_type:
                grants_info["award_type"] = award_type
                logger.info(f"Added award type: {award_type}")

            # Research entities if required
            if research_entities and "recipient_name" in grants_info:
                entity_research = self.research_entity(grants_info)
                grants_info["entity_research"] = entity_research
                logger.info("Added entity research to grants information")

                # Save research results to file if output directory is specified
                if output_dir is not None:
                    self._save_research_results(grants_info, output_dir)

            return grants_info
        except Exception as e:
            logger.error(f"Error extracting grants information: {str(e)}")
            return None

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

    def _extract_from_list(self, data):
        """
        Extract grants information from list

        Args:
            data: List containing grants information

        Returns:
            Dictionary with extracted grants information
        """
        grants_info = {}

        # Extract information from list
        for item in data:
            if isinstance(item, dict):
                # Try to extract from the top level
                if "award_id_fain" in item:
                    grants_info["award_id"] = item.get("award_id_fain")
                elif "award_id_piid" in item:
                    grants_info["award_id"] = item.get("award_id_piid")
                elif "id" in item:
                    grants_info["award_id"] = item.get("id")

                # Extract description
                if "description" in item:
                    grants_info["description"] = item.get("description")
                elif "prime_award_base_transaction_description" in item:
                    grants_info["description"] = item.get(
                        "prime_award_base_transaction_description"
                    )

                # Extract amount
                if "amount" in item:
                    grants_info["amount"] = item.get("amount")
                elif "total_obligated_amount" in item:
                    grants_info["amount"] = item.get("total_obligated_amount")
                elif "current_total_value_of_award" in item:
                    grants_info["amount"] = item.get("current_total_value_of_award")

                # Extract recipient
                if "recipient" in item:
                    grants_info["recipient_name"] = item.get("recipient")
                elif "recipient_name" in item:
                    grants_info["recipient_name"] = item.get("recipient_name")

                # Extract recipient info if available
                if "recipient_info" in item:
                    grants_info["recipient_info"] = item.get("recipient_info")

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

    def create_system_message_for_post(self, grants_info):
        """
        Create system message for post generation

        Args:
            grants_info: Dictionary with grant information

        Returns:
            System message string
        """
        # Create a system message that instructs the LLM to generate a post
        system_message = """You are a government waste investigator creating social media posts about suspicious government grants.
        
        Your task is to create a compelling, factual post about potential government waste or fraud in the grant data provided.
        
        Focus on:
        1. The amount of money spent
        2. Who received the grant
        3. Any suspicious patterns or red flags
        4. Why taxpayers should be concerned
        
        Your post should be concise, attention-grabbing, and under 280 characters.
        Do not use hastags
        
        Format your response as a JSON object with 'text' and 'quote_tweet_id' fields.
        """

        # Add memory information if available
        if hasattr(self, "memory") and self.memory is not None:
            try:
                # Create a query based on the grant information
                memory_query = f"government grants to {grants_info.get('recipient_name', 'unknown recipient')}"

                # Retrieve relevant memories
                memories = self.memory.search(memory_query)

                if memories and len(memories) > 0:
                    memory_texts = [f"- {mem.text}" for mem in memories]
                    memory_context = "\n".join(memory_texts)

                    system_message += f"\n\nHere are some relevant facts from your previous investigations:\n{memory_context}"
                    logger.info(f"Added {len(memories)} memories to system message")
            except Exception as e:
                logger.warning(f"Error retrieving memories: {str(e)}")

        return system_message

    def analyze_json(
        self,
        json_file,
        output_file=None,
        prompt_type="x_doge",
        research_entities=True,
        output_dir="llm_analysis",
    ):
        """
        Analyze JSON file with contract data and generate an X/Twitter post

        Args:
            json_file: Path to JSON file with contract data
            output_file: Path to save output JSON
            prompt_type: Type of prompt to use (default: x_doge)
            research_entities: Whether to research the entities found in the JSON
            output_dir: Directory to save research results

        Returns:
            JSON object with tweet text
        """
        # Extract grants information
        grants_info = self.extract_grants_info(
            json_file, research_entities=research_entities, output_dir=output_dir
        )
        if not grants_info:
            return None

        # Create prompt
        complete_prompt = self.create_prompt_for_post(grants_info, prompt_type)

        # Call appropriate API based on provider
        logger.info(f"Calling {self.provider.upper()} API...")
        start_time = time.time()

        if self.provider == "openai":
            system_message = self.create_system_message_for_post(grants_info)
            response_text = self.call_openai_api(complete_prompt, system_message)
        elif self.provider == "anthropic":
            system_message = self.create_system_message_for_post(grants_info)
            response_text = self.call_anthropic_api(complete_prompt, system_message)
        elif self.provider == "xai":
            system_message = self.create_system_message_for_post(grants_info)
            response_text = self.call_xai_api(complete_prompt, system_message)
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

    def create_prompt_for_post(self, grants_info, prompt_type):
        """
        Create prompt for post generation

        Args:
            grants_info: Dictionary with grant information
            prompt_type: Type of prompt to use

        Returns:
            Prompt string
        """
        # Select the appropriate prompt
        if prompt_type in prompts:
            selected_prompt = prompts[prompt_type]
            logger.info(f"Using prompt type: {prompt_type}")
        else:
            selected_prompt = prompts["x_doge"]
            logger.info(f"Prompt type {prompt_type} not found, using x_doge prompt")

        # Create a complete prompt with the grants data
        complete_prompt = f"{selected_prompt}\n\nHere is the grant information to use:\n{json.dumps(grants_info, indent=2)}"

        return complete_prompt


def main():
    """Main function to run JSON analysis from command line"""
    parser = argparse.ArgumentParser(
        description="Analyze JSON grant data and generate X/Twitter posts"
    )

    # Add input JSON file argument
    parser.add_argument(
        "json_file", help="Path to JSON file with grant data to analyze"
    )

    # Add output file argument
    parser.add_argument(
        "--output-file", "-o", help="Path to save output JSON with post content"
    )

    # Add prompt type argument
    parser.add_argument(
        "--prompt-type",
        "-p",
        default="x_doge",
        choices=prompts.keys(),
        help=f"Type of prompt to use (default: x_doge, available: {', '.join(prompts.keys())})",
    )

    # Add no-research flag
    parser.add_argument(
        "--no-research",
        action="store_true",
        help="Skip researching entities in the grant data",
    )

    # Add output directory argument
    parser.add_argument(
        "--output-dir",
        default="llm_analysis",
        help="Directory to save research results (default: llm_analysis)",
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
        )
    except ValueError as e:
        logger.error(f"Error initializing analyzer: {str(e)}")
        return 1

    # Analyze JSON file
    result = analyzer.analyze_json(
        args.json_file,
        args.output_file,
        args.prompt_type,
        not args.no_research,
        args.output_dir,
    )

    # Print result
    if result:
        if "text" in result:
            print("\nGenerated X/Twitter post:")
            print("-" * 40)
            print(result["text"])
            print("-" * 40)
            if (
                "quote_tweet_id" in result
                and result["quote_tweet_id"]
                and result["quote_tweet_id"].lower() != "none"
            ):
                print(f"Quote tweet ID: {result['quote_tweet_id']}")
            print()
        else:
            logger.error("Generated result does not contain 'text' field")
            print(json.dumps(result, indent=2))
    else:
        logger.error("Analysis failed")
        return 1

    return 0


if __name__ == "__main__":
    # This code only runs when the module is executed directly
    # It will not run when the module is imported
    sys.exit(main())
