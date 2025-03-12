#!/usr/bin/env python3
import os
import json
import argparse
import logging
import sys
import time
from dotenv import load_dotenv
from requests_oauthlib import OAuth1Session

# Load environment variables
load_dotenv()

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


class TwitterPoster:
    """Class to post content to Twitter/X"""

    def __init__(
        self,
        consumer_key=None,
        consumer_secret=None,
        access_token=None,
        access_token_secret=None,
        user_id=None,
        username=None,
    ):
        """
        Initialize Twitter Poster

        Args:
            consumer_key: Twitter API consumer key
            consumer_secret: Twitter API consumer secret
            access_token: Twitter API access token
            access_token_secret: Twitter API access token secret
            user_id: Twitter user ID
            username: Twitter username
        """
        # Get API credentials from .env file if not provided
        self.consumer_key = consumer_key or os.getenv("TWITTER_CONSUMER_KEY")
        self.consumer_secret = consumer_secret or os.getenv("TWITTER_CONSUMER_SECRET")
        self.access_token = access_token or os.getenv("TWITTER_ACCESS_TOKEN")
        self.access_token_secret = access_token_secret or os.getenv(
            "TWITTER_ACCESS_TOKEN_SECRET"
        )
        self.user_id = user_id or os.getenv("TWITTER_USER_ID")
        self.username = username or os.getenv("TWITTER_USERNAME")

        # Validate API credentials
        if not all(
            [
                self.consumer_key,
                self.consumer_secret,
                self.access_token,
                self.access_token_secret,
            ]
        ):
            raise ValueError(
                "Missing Twitter API credentials. Set them in .env file or provide as arguments."
            )

        logger.info(f"Twitter poster initialized for user @{self.username}")

        # Set up OAuth 1.0a for Twitter API v2
        try:

            self.twitter = OAuth1Session(
                client_key=self.consumer_key,
                client_secret=self.consumer_secret,
                resource_owner_key=self.access_token,
                resource_owner_secret=self.access_token_secret,
            )
            logger.info("OAuth session created successfully")
        except ImportError:
            logger.error(
                "Failed to import OAuth libraries. Install with: pip install requests-oauthlib"
            )
            raise ImportError(
                "Missing required packages. Install with: pip install requests-oauthlib"
            )

    def post_tweet(self, text, quote_tweet_id=None):
        """
        Post a tweet to Twitter/X

        Args:
            text: Text content of the tweet (max 280 chars)
            quote_tweet_id: Optional ID of a tweet to quote

        Returns:
            Dictionary with tweet information or None if posting failed
        """
        # Validate tweet length
        if len(text) > 280:
            logger.warning(f"Tweet exceeds 280 characters ({len(text)}). Truncating...")
            text = text[:277] + "..."

        # Create payload
        payload = {"text": text}

        # Add quote tweet if provided and not "None"
        if quote_tweet_id and quote_tweet_id.lower() != "none":
            payload["quote_tweet_id"] = quote_tweet_id

        # Set up API endpoint for tweeting
        url = "https://api.twitter.com/2/tweets"

        try:
            logger.info(f"Posting tweet: {text[:50]}...")
            response = self.twitter.post(url, json=payload)

            # Check response
            if response.status_code == 201:
                logger.info("Tweet posted successfully")
                return response.json()
            else:
                logger.error(
                    f"Failed to post tweet. Status code: {response.status_code}"
                )
                logger.error(f"Response: {response.text}")
                return None

        except Exception as e:
            logger.error(f"Error posting tweet: {str(e)}")
            return None

    def post_from_json(self, json_file):
        """
        Post a tweet from a JSON file

        Args:
            json_file: Path to JSON file with tweet content

        Returns:
            Dictionary with tweet information or None if posting failed
        """
        try:
            with open(json_file, "r") as f:
                data = json.load(f)
                logger.info(f"Loaded tweet content from {json_file}")

            # Extract tweet content
            if "text" not in data:
                logger.error("JSON file does not contain 'text' field")
                return None

            text = data["text"]
            quote_tweet_id = data.get("quote_tweet_id")

            # Post tweet
            return self.post_tweet(text, quote_tweet_id)

        except Exception as e:
            logger.error(f"Error loading JSON data: {str(e)}")
            return None

    def get_user_info(self):
        """
        Get information about the authenticated user

        Returns:
            Dictionary with user information or None if request failed
        """
        url = f"https://api.twitter.com/2/users/me"

        try:
            response = self.twitter.get(url)

            if response.status_code == 200:
                logger.info("User information retrieved successfully")
                return response.json()
            else:
                logger.error(
                    f"Failed to get user information. Status code: {response.status_code}"
                )
                logger.error(f"Response: {response.text}")
                return None

        except Exception as e:
            logger.error(f"Error getting user information: {str(e)}")
            return None


class TwitterGenerator(BaseLLM):
    """Class to generate Twitter posts from JSON data"""

    def __init__(
        self,
        api_key=None,
        model=None,
        provider="xai",
        max_tokens=4096,
        temperature=0.7,
        user_id="default_user",
    ):
        """
        Initialize Twitter Generator

        Args:
            api_key: API key for the LLM provider
            model: Model name to use
            provider: LLM provider (openai, anthropic, xai)
            max_tokens: Maximum tokens for response
            temperature: Temperature for response generation
            user_id: User ID for memory operations
        """
        super().__init__(api_key, model, provider, max_tokens, temperature, user_id)

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

        # Add context about the source list if available
        if "source_list" in grants_info:
            source_list = grants_info.get("source_list")
            system_message += (
                f"\n\nThis grant was identified as part of a '{source_list}' list."
            )

        # Add context about other grants if available
        if "context" in grants_info:
            context = grants_info.get("context")
            system_message += f"\n\nAdditional context: {context}"

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

    def generate_post(
        self,
        grants_info,
        output_file=None,
        prompt_type="x_doge",
    ):
        """
        Generate a Twitter post from grant information

        Args:
            grants_info: Dictionary with grant information
            output_file: Path to save output JSON
            prompt_type: Type of prompt to use (default: x_doge)

        Returns:
            JSON object with tweet text
        """
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
                logger.info(f"Generated post saved to {output_file}")

            return result
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON response: {response_text}")

            # Save raw response to file if output file is specified
            if output_file:
                with open(output_file, "w") as f:
                    f.write(response_text)
                logger.info(f"Raw response saved to {output_file}")

            return {"error": "Failed to parse response", "raw_response": response_text}

    def generate_from_json_file(
        self,
        json_file,
        output_file=None,
        prompt_type="x_doge",
    ):
        """
        Generate a Twitter post from a JSON file

        Args:
            json_file: Path to JSON file with grant data
            output_file: Path to save output JSON
            prompt_type: Type of prompt to use (default: x_doge)

        Returns:
            JSON object with tweet text
        """
        try:
            # Load JSON data
            with open(json_file, "r") as f:
                data = json.load(f)
                logger.info(f"Loaded data from {json_file}")

            # Process the JSON data based on its structure
            if isinstance(data, dict):
                # Check if it contains a list of targets under a key
                target_lists = []
                for key, value in data.items():
                    if isinstance(value, list) and len(value) > 0:
                        target_lists.append((key, value))

                if target_lists:
                    # Use the first list found as our targets
                    list_name, targets = target_lists[0]
                    logger.info(
                        f"Using list '{list_name}' with {len(targets)} entries for post generation"
                    )

                    # If there are multiple targets, select one or combine information
                    if len(targets) > 1:
                        logger.info(
                            f"Multiple targets found, selecting most interesting one for post"
                        )
                        # Sort by amount (if available) to find the most expensive grant
                        sorted_targets = sorted(
                            targets,
                            key=lambda x: (
                                float(x.get("amount", 0))
                                if isinstance(x.get("amount"), (int, float, str))
                                else 0
                            ),
                            reverse=True,
                        )
                        selected_target = sorted_targets[0]
                        # Add context about other targets
                        selected_target["context"] = (
                            f"This is one of {len(targets)} questionable grants totaling ${sum(float(t.get('amount', 0)) for t in targets if isinstance(t.get('amount'), (int, float, str)))}."
                        )
                        grants_info = selected_target
                    else:
                        grants_info = targets[0]

                    # Add the list name for context
                    grants_info["source_list"] = list_name
                else:
                    # No lists found, use the dictionary as is
                    grants_info = data
            elif isinstance(data, list):
                # If it's a list, select the most interesting entry
                if len(data) > 1:
                    logger.info(
                        f"Multiple entries found, selecting most interesting one for post"
                    )
                    # Sort by amount (if available) to find the most expensive grant
                    sorted_data = sorted(
                        data,
                        key=lambda x: (
                            float(x.get("amount", 0))
                            if isinstance(x.get("amount"), (int, float, str))
                            else 0
                        ),
                        reverse=True,
                    )
                    selected_entry = sorted_data[0]
                    # Add context about other entries
                    selected_entry["context"] = (
                        f"This is one of {len(data)} questionable grants totaling ${sum(float(t.get('amount', 0)) for t in data if isinstance(t.get('amount'), (int, float, str)))}."
                    )
                    grants_info = selected_entry
                else:
                    grants_info = data[0] if data else {}
            else:
                logger.error(f"Unsupported data type: {type(data)}")
                return None

            # Generate post
            return self.generate_post(grants_info, output_file, prompt_type)

        except Exception as e:
            logger.error(f"Error generating post from JSON file: {str(e)}")
            return None


def main():
    """Main function to post tweets from command line"""
    parser = argparse.ArgumentParser(description="Post tweets to Twitter/X")

    # Add subparsers for different commands
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Post command
    post_parser = subparsers.add_parser("post", help="Post a tweet")
    post_parser.add_argument("text", help="Text content of the tweet")
    post_parser.add_argument("--quote-id", help="ID of a tweet to quote")

    # Post from JSON command
    json_parser = subparsers.add_parser("json", help="Post a tweet from a JSON file")
    json_parser.add_argument("json_file", help="Path to JSON file with tweet content")

    # Generate post command
    generate_parser = subparsers.add_parser(
        "generate", help="Generate a tweet from grant data"
    )
    generate_parser.add_argument("json_file", help="Path to JSON file with grant data")
    generate_parser.add_argument(
        "--output-file", "-o", help="Path to save output JSON with post content"
    )
    generate_parser.add_argument(
        "--prompt-type",
        "-p",
        default="x_doge",
        help=f"Type of prompt to use (default: x_doge)",
    )
    generate_parser.add_argument(
        "--provider",
        default="xai",
        choices=["openai", "anthropic", "xai"],
        help="LLM provider to use (default: xai)",
    )
    generate_parser.add_argument(
        "--model",
        help="Model to use (if not specified, will use provider's default model)",
    )
    generate_parser.add_argument(
        "--temperature",
        type=float,
        default=0.7,
        help="Temperature for response generation (default: 0.7)",
    )
    generate_parser.add_argument(
        "--post",
        action="store_true",
        help="Post the generated tweet to Twitter after generation",
    )

    # Generate and post command
    generate_post_parser = subparsers.add_parser(
        "generate-post", help="Generate and post a tweet from grant data"
    )
    generate_post_parser.add_argument(
        "json_file", help="Path to JSON file with grant data"
    )
    generate_post_parser.add_argument(
        "--output-file", "-o", help="Path to save output JSON with post content"
    )
    generate_post_parser.add_argument(
        "--prompt-type",
        "-p",
        default="x_doge",
        help=f"Type of prompt to use (default: x_doge)",
    )
    generate_post_parser.add_argument(
        "--provider",
        default="xai",
        choices=["openai", "anthropic", "xai"],
        help="LLM provider to use (default: xai)",
    )
    generate_post_parser.add_argument(
        "--model",
        help="Model to use (if not specified, will use provider's default model)",
    )
    generate_post_parser.add_argument(
        "--temperature",
        type=float,
        default=0.7,
        help="Temperature for response generation (default: 0.7)",
    )
    generate_post_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate the tweet but don't post it to Twitter",
    )

    # User info command
    info_parser = subparsers.add_parser(
        "info", help="Get information about the authenticated user"
    )

    # Parse arguments
    args = parser.parse_args()

    # Check if a command was provided
    if not args.command:
        parser.print_help()
        return 1

    # Execute command
    if args.command == "post":
        # Initialize Twitter poster
        try:
            poster = TwitterPoster()
        except ValueError as e:
            logger.error(f"Error initializing Twitter poster: {str(e)}")
            return 1
        except ImportError as e:
            logger.error(str(e))
            return 1

        # Post a tweet
        result = poster.post_tweet(args.text, args.quote_id)
        if result:
            print("Tweet posted successfully!")
            print(json.dumps(result, indent=2))
            return 0
        else:
            logger.error("Failed to post tweet")
            return 1

    elif args.command == "json":
        # Initialize Twitter poster
        try:
            poster = TwitterPoster()
        except ValueError as e:
            logger.error(f"Error initializing Twitter poster: {str(e)}")
            return 1
        except ImportError as e:
            logger.error(str(e))
            return 1

        # Post a tweet from a JSON file
        result = poster.post_from_json(args.json_file)
        if result:
            print("Tweet posted successfully!")
            print(json.dumps(result, indent=2))
            return 0
        else:
            logger.error("Failed to post tweet from JSON file")
            return 1

    elif args.command == "generate":
        # Initialize Twitter generator
        try:
            generator = TwitterGenerator(
                model=args.model,
                provider=args.provider,
                temperature=args.temperature,
            )
        except ValueError as e:
            logger.error(f"Error initializing Twitter generator: {str(e)}")
            return 1
        except ImportError as e:
            logger.error(str(e))
            return 1

        # Generate a tweet from grant data
        result = generator.generate_from_json_file(
            args.json_file, args.output_file, args.prompt_type
        )

        if result:
            print("\nGenerated Twitter post:")
            print("-" * 40)
            print(result.get("text", "No text generated"))
            print("-" * 40)

            if args.post:
                # Post the generated tweet
                try:
                    poster = TwitterPoster()
                    post_result = poster.post_tweet(
                        result.get("text"), result.get("quote_tweet_id")
                    )
                    if post_result:
                        print("Tweet posted successfully!")
                        print(json.dumps(post_result, indent=2))
                    else:
                        logger.error("Failed to post tweet")
                        return 1
                except ValueError as e:
                    logger.error(f"Error initializing Twitter poster: {str(e)}")
                    return 1
                except ImportError as e:
                    logger.error(str(e))
                    return 1

            return 0
        else:
            logger.error("Failed to generate tweet")
            return 1

    elif args.command == "generate-post":
        # Initialize Twitter generator
        try:
            generator = TwitterGenerator(
                model=args.model,
                provider=args.provider,
                temperature=args.temperature,
            )
        except ValueError as e:
            logger.error(f"Error initializing Twitter generator: {str(e)}")
            return 1
        except ImportError as e:
            logger.error(str(e))
            return 1

        # Generate a tweet from grant data
        result = generator.generate_from_json_file(
            args.json_file, args.output_file, args.prompt_type
        )

        if result:
            print("\nGenerated Twitter post:")
            print("-" * 40)
            print(result.get("text", "No text generated"))
            print("-" * 40)

            if not args.dry_run:
                # Post the generated tweet
                try:
                    poster = TwitterPoster()
                    post_result = poster.post_tweet(
                        result.get("text"), result.get("quote_tweet_id")
                    )
                    if post_result:
                        print("Tweet posted successfully!")
                        print(json.dumps(post_result, indent=2))
                    else:
                        logger.error("Failed to post tweet")
                        return 1
                except ValueError as e:
                    logger.error(f"Error initializing Twitter poster: {str(e)}")
                    return 1
                except ImportError as e:
                    logger.error(str(e))
                    return 1
            else:
                print("Dry run: Tweet not posted to Twitter")

            return 0
        else:
            logger.error("Failed to generate tweet")
            return 1

    elif args.command == "info":
        # Initialize Twitter poster
        try:
            poster = TwitterPoster()
        except ValueError as e:
            logger.error(f"Error initializing Twitter poster: {str(e)}")
            return 1
        except ImportError as e:
            logger.error(str(e))
            return 1

        # Get user information
        result = poster.get_user_info()
        if result:
            print("User information:")
            print(json.dumps(result, indent=2))
            return 0
        else:
            logger.error("Failed to get user information")
            return 1

    return 0


if __name__ == "__main__":
    # This code only runs when the module is executed directly
    # It will not run when the module is imported
    sys.exit(main())
