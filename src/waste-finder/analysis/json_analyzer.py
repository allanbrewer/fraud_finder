#!/usr/bin/env python3
import os
import json
import argparse
import logging
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
                "x_doge": "Generate a Twitter post about government waste and fraud.",
            }


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

    def research_entity(self, entity_name):
        """
        Research an entity for more information

        Args:
            entity_name: The name of the entity to research

        Returns:
            String containing research information about the entity
        """
        # Create a system message that instructs the LLM to research the entity
        system_message = """You are a government waste investigator researching entities that receive government grants.
        
        Use sources like USASpending.gov, fpds.gov, and other federal government databases to research the entity.

        Also look into company/NGO registation records online to get all available information.
        
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
        prompt = f"Research the following entity that received government grants: {entity_name}"

        logger.info(f"Researching entity: {entity_name}")

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

    def analyze_json(
        self, json_file, output_file=None, prompt_type="x_doge", research_entities=True
    ):
        """
        Analyze JSON file with contract data and generate an X/Twitter post

        Args:
            json_file: Path to JSON file with contract data
            output_file: Path to save output JSON
            prompt_type: Type of prompt to use (default: x_doge)
            research_entities: Whether to research the entities found in the JSON

        Returns:
            JSON object with tweet text
        """
        # Load JSON data
        try:
            with open(json_file, "r") as f:
                data = json.load(f)
                logger.info(f"Loaded JSON data from {json_file}")
        except Exception as e:
            logger.error(f"Error loading JSON data: {str(e)}")
            return None

        # Extract relevant information from the JSON
        grants_info = self.extract_grants_info(data)
        if not grants_info:
            logger.error("No relevant grant information found in the JSON")
            return None

        # Research entities if required
        if research_entities and "recipient_name" in grants_info:
            entity_research = self.research_entity(grants_info["recipient_name"])
            grants_info["entity_research"] = entity_research
            logger.info("Added entity research to grants information")

        # Create system message
        system_message = self.create_system_message_for_post(grants_info)

        # Select the appropriate prompt
        if prompt_type in prompts:
            selected_prompt = prompts[prompt_type]
            logger.info(f"Using prompt type: {prompt_type}")
        else:
            selected_prompt = prompts["x_doge"]
            logger.info(f"Prompt type {prompt_type} not found, using x_doge prompt")

        # Generate the X/Twitter post
        logger.info(f"Generating X/Twitter post with {self.provider.upper()} API...")
        start_time = time.time()

        # Create a complete prompt with the grants data
        complete_prompt = f"{selected_prompt}\n\nHere is the grant information to use:\n{json.dumps(grants_info, indent=2)}"

        if self.provider == "openai":
            response_text = self.call_openai_api(complete_prompt, system_message)
        elif self.provider == "anthropic":
            response_text = self.call_anthropic_api(complete_prompt, system_message)
        elif self.provider == "xai":
            response_text = self.call_xai_api(complete_prompt, system_message)
        else:
            logger.error(f"Unknown provider: {self.provider}")
            return None

        elapsed_time = time.time() - start_time
        logger.info(f"Post generation completed in {elapsed_time:.2f} seconds")

        if not response_text:
            logger.error("Failed to generate post")
            return None

        # Parse JSON response
        try:
            result = json.loads(response_text)

            # Save to file if output file is specified
            if output_file:
                with open(output_file, "w") as f:
                    json.dump(result, f, indent=2)
                logger.info(f"Result saved to {output_file}")

            return result
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON response: {response_text}")

            # Save raw response to file if output file is specified
            if output_file:
                with open(output_file, "w") as f:
                    f.write(response_text)
                logger.info(f"Raw response saved to {output_file}")

            return {"error": "Failed to parse response", "raw_response": response_text}

    def extract_grants_info(self, data):
        """
        Extract relevant information from grant data JSON

        Args:
            data: JSON data from LLM analysis

        Returns:
            Dictionary with relevant grant information
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
            elif "total_dollars_obligated" in data:
                grants_info["amount"] = data.get("total_dollars_obligated")

            # Extract recipient name
            if "recipient" in data:
                grants_info["recipient_name"] = data.get("recipient")
            elif "recipient_name" in data:
                grants_info["recipient_name"] = data.get("recipient_name")

            # Extract recipient info
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

    def create_system_message_for_post(self, grants_info):
        """
        Create a system message for post generation

        Args:
            grants_info: Dictionary with grant information

        Returns:
            System message for the LLM
        """
        system_message = """You are a social media strategist for the Department of Government Efficiency (DOGE).
        Your task is to generate a compelling X/Twitter post that exposes government waste, fraud, or abuse.
        
        Follow these guidelines:
        1. Focus on the facts and highlight the most wasteful or suspicious aspects
        2. Keep the post under 280 characters
        3. Be provocative but professional
        4. Include specific details like dollar amounts, recipient names, or contract numbers when relevant
        5. Format the response as a valid JSON object with 'text' and 'quote_tweet_id' fields
        
        The post should be shareable and get people's attention about government waste.
        """

        # Add memory information if available
        if hasattr(self, "memory") and self.memory is not None:
            try:
                # Try to find relevant memories related to the recipient or contract type
                search_term = grants_info.get("recipient_name", "")
                if not search_term and "description" in grants_info:
                    # Extract keywords from description
                    search_term = grants_info["description"]

                if search_term:
                    relevant_memories = self.memory.search(
                        query=search_term, user_id=self.user_id, limit=3
                    )

                    if (
                        relevant_memories
                        and "results" in relevant_memories
                        and len(relevant_memories["results"]) > 0
                    ):
                        memory_text = "Consider these relevant past findings:\n\n"
                        for i, memory in enumerate(relevant_memories["results"]):
                            content = memory.get("memory", "")
                            if content:
                                memory_text += f"{i+1}. {content}\n\n"

                        system_message = f"{system_message}\n\n{memory_text}"
            except Exception as e:
                logger.error(f"Error retrieving memories: {str(e)}")

        return system_message


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
    sys.exit(main())
