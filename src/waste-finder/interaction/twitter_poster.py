#!/usr/bin/env python3
import os
import json
import argparse
import logging
import sys
from dotenv import load_dotenv
from requests_oauthlib import OAuth1Session

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


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

    # Initialize Twitter poster
    try:
        poster = TwitterPoster()
    except ValueError as e:
        logger.error(f"Error initializing Twitter poster: {str(e)}")
        return 1
    except ImportError as e:
        logger.error(str(e))
        return 1

    # Execute command
    if args.command == "post":
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
        # Post a tweet from a JSON file
        result = poster.post_from_json(args.json_file)
        if result:
            print("Tweet posted successfully!")
            print(json.dumps(result, indent=2))
            return 0
        else:
            logger.error("Failed to post tweet from JSON file")
            return 1

    elif args.command == "info":
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
    sys.exit(main())
