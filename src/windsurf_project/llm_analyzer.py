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

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Import the prompt from promt.py
try:
    from promt import prompt

    logging.info("Successfully imported prompt from promt.py")
except ImportError:
    try:
        # Try relative import if the first import fails
        from .promt import prompt

        logging.info("Successfully imported prompt from promt.py")
    except ImportError:
        logging.error("Could not import prompt from promt.py")
        prompt = None


class LLMAnalyzer:
    """Class to analyze contract data using LLM APIs"""

    def __init__(
        self,
        api_key=None,
        model=None,
        provider="openai",
        max_tokens=4096,
        temperature=0.1,
    ):
        """
        Initialize the LLM analyzer

        Args:
            api_key: API key for the LLM provider
            model: Model name to use
            provider: LLM provider (openai, anthropic, grok)
            max_tokens: Maximum tokens for response
            temperature: Temperature for response generation
        """
        self.provider = provider.lower()
        self.max_tokens = max_tokens
        self.temperature = temperature

        # Set default model based on provider
        if model is None:
            if self.provider == "openai":
                self.model = "gpt-4o-mini"
            elif self.provider == "anthropic":
                self.model = "claude-3-7-sonnet-latest"
            elif self.provider == "grok":
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
            elif self.provider == "grok":
                api_key = os.getenv("XAI_API_KEY")

        if not api_key:
            raise ValueError(
                f"API key not provided and not found in .env file for {provider}"
            )

        self.api_key = api_key

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

            # Limit rows if specified
            if max_rows and len(df) > max_rows:
                logging.warning(
                    f"CSV file has {len(df)} rows, limiting to {max_rows} rows"
                )
                df = df.head(max_rows)

            # Convert to string representation
            csv_string = df.to_csv(index=False)
            return csv_string

        except Exception as e:
            logging.error(f"Error preparing CSV data: {str(e)}")
            return None

    def create_prompt_with_data(self, csv_data, custom_prompt=None):
        """
        Create a prompt with CSV data

        Args:
            csv_data: CSV data as string
            custom_prompt: Custom prompt to use instead of default

        Returns:
            Complete prompt with CSV data
        """
        # Use custom prompt if provided, otherwise use default
        final_prompt = custom_prompt if custom_prompt else prompt

        # Add CSV data to prompt
        complete_prompt = (
            f"{final_prompt}\n\nHere is the CSV data to analyze:\n\n{csv_data}"
        )
        return complete_prompt

    def call_openai_api(self, complete_prompt):
        """
        Call OpenAI API with prompt

        Args:
            complete_prompt: Complete prompt with CSV data

        Returns:
            API response as JSON
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": complete_prompt}],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "response_format": {"type": "json_object"},
        }

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

    def call_anthropic_api(self, complete_prompt):
        """
        Call Anthropic API with prompt

        Args:
            complete_prompt: Complete prompt with CSV data

        Returns:
            API response as JSON
        """
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": complete_prompt}],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "system": "You are a contract analysis expert. Respond only with valid JSON.",
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

    def call_grok_api(self, complete_prompt):
        """
        Call Grok API with prompt

        Args:
            complete_prompt: Complete prompt with CSV data

        Returns:
            API response as JSON
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": complete_prompt}],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "response_format": {"type": "json_object"},
        }

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
            logging.error(f"Error calling Grok API: {str(e)}")
            if hasattr(e, "response") and e.response is not None:
                logging.error(f"Response status: {e.response.status_code}")
                logging.error(f"Response body: {e.response.text}")
            return None

    def analyze_csv(
        self, csv_file, custom_prompt=None, max_rows=None, output_file=None
    ):
        """
        Analyze CSV file using LLM

        Args:
            csv_file: Path to CSV file
            custom_prompt: Custom prompt to use instead of default
            max_rows: Maximum number of rows to include
            output_file: Path to save output JSON

        Returns:
            Analysis results as JSON object
        """
        # Prepare CSV data
        csv_data = self.prepare_csv_data(csv_file, max_rows)
        if not csv_data:
            return None

        # Create complete prompt
        complete_prompt = self.create_prompt_with_data(csv_data, custom_prompt)

        # Call appropriate API based on provider
        logging.info(f"Calling {self.provider.upper()} API with model {self.model}...")
        start_time = time.time()

        if self.provider == "openai":
            response_text = self.call_openai_api(complete_prompt)
        elif self.provider == "anthropic":
            response_text = self.call_anthropic_api(complete_prompt)
        elif self.provider == "grok":
            response_text = self.call_grok_api(complete_prompt)
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
        self, csv_files, custom_prompt=None, max_rows=None, output_dir=None
    ):
        """
        Analyze multiple CSV files

        Args:
            csv_files: List of CSV file paths
            custom_prompt: Custom prompt to use
            max_rows: Maximum rows per file
            output_dir: Directory to save output files

        Returns:
            Dictionary of results by file
        """
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        results = {}

        for csv_file in csv_files:
            filename = os.path.basename(csv_file)
            logging.info(f"Analyzing {filename}...")

            if output_dir:
                output_file = os.path.join(
                    output_dir, f"analysis_{os.path.splitext(filename)[0]}.json"
                )
            else:
                output_file = None

            result = self.analyze_csv(csv_file, custom_prompt, max_rows, output_file)

            if result:
                results[filename] = result

        return results


def main():
    """Main function to run LLM analysis from command line"""
    parser = argparse.ArgumentParser(description="Analyze contracts using LLM APIs")

    parser.add_argument(
        "--csv-file",
        required=True,
        help="Path to CSV file or directory containing CSV files",
    )
    parser.add_argument(
        "--provider",
        default="openai",
        choices=["openai", "anthropic", "grok"],
        help="LLM provider to use (default: openai)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model name to use (default depends on provider)",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="API key (default: read from .env file)",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Maximum rows to include from CSV (default: all)",
    )
    parser.add_argument(
        "--output-dir",
        default="llm_analysis",
        help="Directory to save output files (default: llm_analysis)",
    )
    parser.add_argument(
        "--prompt-file",
        default=None,
        help="Custom prompt file (default: use built-in prompt)",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=4096,
        help="Maximum tokens for response (default: 4096)",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.1,
        help="Temperature for response generation (default: 0.1)",
    )

    args = parser.parse_args()

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

    # Initialize analyzer
    try:
        analyzer = LLMAnalyzer(
            api_key=args.api_key,
            model=args.model,
            provider=args.provider,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
        )
    except ValueError as e:
        logging.error(str(e))
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
            csv_files, custom_prompt, args.max_rows, args.output_dir
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
            args.csv_file, custom_prompt, args.max_rows, output_file
        )

        if result:
            logging.info(f"Analysis complete. Results saved to {output_file}")
        else:
            logging.error("Analysis failed")
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
