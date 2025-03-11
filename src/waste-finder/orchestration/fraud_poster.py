#!/usr/bin/env python3
import os
import json
import argparse
import logging
import time
import sys
from dotenv import load_dotenv
import glob
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Try to import modules from different possible paths
try:
    from src.waste_finder.analysis.json_analyzer import JSONAnalyzer
    from src.waste_finder.interaction.twitter_poster import TwitterPoster
except ImportError:
    try:
        from waste_finder.analysis.json_analyzer import JSONAnalyzer
        from waste_finder.interaction.twitter_poster import TwitterPoster
    except ImportError:
        try:
            from ..analysis.json_analyzer import JSONAnalyzer
            from ..interaction.twitter_poster import TwitterPoster
        except ImportError:
            raise ImportError(
                "Could not import required modules. Check your python path and file structure."
            )


class FraudPoster:
    """Orchestrator class to analyze JSON data and post findings to Twitter/X"""

    def __init__(
        self,
        api_key=None,
        model=None,
        provider="xai",
        max_tokens=4096,
        temperature=0.7,
        user_id="default_user",
        dry_run=False,
    ):
        """
        Initialize Fraud Poster

        Args:
            api_key: API key for the LLM provider
            model: Model name to use
            provider: LLM provider (openai, anthropic, xai)
            max_tokens: Maximum tokens for response
            temperature: Temperature for response generation
            user_id: User ID for memory operations
            dry_run: If True, will not actually post to Twitter
        """
        # Initialize JSON analyzer
        self.json_analyzer = JSONAnalyzer(
            api_key=api_key,
            model=model,
            provider=provider,
            max_tokens=max_tokens,
            temperature=temperature,
            user_id=user_id,
        )
        logger.info(f"JSON analyzer initialized with provider: {provider}")

        # Initialize Twitter poster (unless dry run)
        self.dry_run = dry_run
        if not dry_run:
            try:
                self.twitter_poster = TwitterPoster()
                logger.info("Twitter poster initialized")
            except (ValueError, ImportError) as e:
                logger.error(f"Error initializing Twitter poster: {str(e)}")
                logger.warning(
                    "Falling back to dry run mode (no tweets will be posted)"
                )
                self.dry_run = True
                self.twitter_poster = None
        else:
            logger.info("Running in dry run mode (no tweets will be posted)")
            self.twitter_poster = None

        # Save configuration
        self.user_id = user_id

    def process_json_file(
        self,
        json_file,
        prompt_type="x_doge",
        research_entities=True,
        post_to_twitter=True,
        output_dir=None,
    ):
        """
        Process a single JSON file: analyze and optionally post to Twitter

        Args:
            json_file: Path to JSON file with grant data
            prompt_type: Type of prompt to use
            research_entities: Whether to research entities in the grant data
            post_to_twitter: Whether to post results to Twitter
            output_dir: Directory to save output files

        Returns:
            Dictionary with processing results
        """
        logger.info(f"Processing JSON file: {json_file}")

        # Create output file path if output_dir is specified
        output_file = None
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(
                output_dir, f"{os.path.basename(json_file).split('.')[0]}_post.json"
            )

        # Analyze JSON file
        post_data = self.json_analyzer.analyze_json(
            json_file=json_file,
            output_file=output_file,
            prompt_type=prompt_type,
            research_entities=research_entities,
        )

        if not post_data:
            logger.error(f"Failed to analyze JSON file: {json_file}")
            return {
                "json_file": json_file,
                "success": False,
                "error": "Failed to analyze JSON file",
            }

        # Display generated post
        if "text" in post_data:
            logger.info("Generated X/Twitter post:")
            logger.info("-" * 40)
            logger.info(post_data["text"])
            logger.info("-" * 40)

            # Save post data if output directory is specified but no specific output file was created
            if output_dir and not output_file:
                output_file = os.path.join(
                    output_dir, f"{os.path.basename(json_file).split('.')[0]}_post.json"
                )
                with open(output_file, "w") as f:
                    json.dump(post_data, f, indent=2)
                logger.info(f"Post data saved to {output_file}")
        else:
            logger.error("Generated result does not contain 'text' field")
            logger.info(json.dumps(post_data, indent=2))
            return {
                "json_file": json_file,
                "success": False,
                "error": "Generated result does not contain 'text' field",
                "data": post_data,
            }

        # Post to Twitter if requested and not in dry run mode
        tweet_result = None
        if post_to_twitter and not self.dry_run and self.twitter_poster:
            logger.info("Posting to Twitter...")
            tweet_result = self.twitter_poster.post_tweet(
                text=post_data["text"], quote_tweet_id=post_data.get("quote_tweet_id")
            )

            if tweet_result:
                logger.info("Tweet posted successfully!")
                # Save the tweet result if output directory is specified
                if output_dir:
                    tweet_output_file = os.path.join(
                        output_dir,
                        f"{os.path.basename(json_file).split('.')[0]}_tweet.json",
                    )
                    with open(tweet_output_file, "w") as f:
                        json.dump(tweet_result, f, indent=2)
                    logger.info(f"Tweet result saved to {tweet_output_file}")
            else:
                logger.error("Failed to post tweet")
        elif post_to_twitter and self.dry_run:
            logger.info("Dry run mode: Tweet would have been posted")

        return {
            "json_file": json_file,
            "success": True,
            "post_data": post_data,
            "tweet_result": tweet_result,
            "output_file": output_file,
        }

    def process_directory(
        self,
        input_dir,
        prompt_type="x_doge",
        research_entities=True,
        post_to_twitter=True,
        output_dir=None,
        limit=None,
        file_pattern="*.json",
    ):
        """
        Process all JSON files in a directory

        Args:
            input_dir: Directory containing JSON files to process
            prompt_type: Type of prompt to use
            research_entities: Whether to research entities in the grant data
            post_to_twitter: Whether to post results to Twitter
            output_dir: Directory to save output files
            limit: Maximum number of files to process
            file_pattern: Pattern to match JSON files

        Returns:
            List of dictionaries with processing results
        """
        # Find all JSON files in the directory
        json_files = list(glob.glob(os.path.join(input_dir, file_pattern)))

        if not json_files:
            logger.error(
                f"No JSON files found in {input_dir} matching pattern {file_pattern}"
            )
            return []

        logger.info(f"Found {len(json_files)} JSON files in {input_dir}")

        # Limit the number of files to process if specified
        if limit and limit > 0 and limit < len(json_files):
            logger.info(f"Limiting to {limit} files")
            json_files = json_files[:limit]

        # Process each JSON file
        results = []
        for json_file in json_files:
            result = self.process_json_file(
                json_file=json_file,
                prompt_type=prompt_type,
                research_entities=research_entities,
                post_to_twitter=post_to_twitter,
                output_dir=output_dir,
            )
            results.append(result)

            # Add a delay between API calls to avoid rate limits
            if post_to_twitter and not self.dry_run and self.twitter_poster:
                logger.info("Waiting 5 seconds before processing next file...")
                time.sleep(5)

        # Summarize results
        successful = sum(1 for r in results if r["success"])
        logger.info(
            f"Processed {len(results)} files: {successful} successful, {len(results) - successful} failed"
        )

        return results


def main():
    """Main function to run fraud poster from command line"""
    parser = argparse.ArgumentParser(
        description="Analyze JSON grant data and post findings to Twitter/X"
    )

    # Input source arguments (file or directory)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--file", "-f", help="Path to a single JSON file to process"
    )
    input_group.add_argument(
        "--directory", "-d", help="Directory containing JSON files to process"
    )

    # Output directory
    parser.add_argument("--output-dir", "-o", help="Directory to save output files")

    # Processing options
    parser.add_argument(
        "--prompt-type",
        "-p",
        default="x_doge",
        help="Type of prompt to use for generating posts (default: x_doge)",
    )

    parser.add_argument(
        "--no-research",
        action="store_true",
        help="Skip researching entities in the grant data",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't actually post to Twitter, just generate the posts",
    )

    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        help="Maximum number of files to process from directory",
    )

    parser.add_argument(
        "--file-pattern",
        default="*.json",
        help="Pattern to match JSON files when processing a directory (default: *.json)",
    )

    # LLM configuration
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

    # Initialize fraud poster
    try:
        poster = FraudPoster(
            api_key=args.api_key,
            model=args.model,
            provider=args.provider,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
            user_id=args.user_id,
            dry_run=args.dry_run,
        )
    except ValueError as e:
        logger.error(f"Error initializing fraud poster: {str(e)}")
        return 1

    # Process input
    if args.file:
        # Process a single file
        result = poster.process_json_file(
            json_file=args.file,
            prompt_type=args.prompt_type,
            research_entities=not args.no_research,
            post_to_twitter=True,
            output_dir=args.output_dir,
        )

        if result["success"]:
            logger.info(f"Successfully processed {args.file}")
            return 0
        else:
            logger.error(f"Failed to process {args.file}")
            return 1

    elif args.directory:
        # Process all files in a directory
        results = poster.process_directory(
            input_dir=args.directory,
            prompt_type=args.prompt_type,
            research_entities=not args.no_research,
            post_to_twitter=True,
            output_dir=args.output_dir,
            limit=args.limit,
            file_pattern=args.file_pattern,
        )

        if results and any(r["success"] for r in results):
            logger.info(
                f"Successfully processed at least some files in {args.directory}"
            )
            return 0
        else:
            logger.error(f"Failed to process any files in {args.directory}")
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
