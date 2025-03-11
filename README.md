# Fraud Finder

[![License: CC BY-NC 4.0](https://img.shields.io/badge/License-CC_BY--NC_4.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc/4.0/)

This Python service downloads active contracts from the USA Spending API, analyzes them using various LLM models, and provides chat interfaces for interactive analysis.

## Requirements
- Python 3.11
- Poetry (dependency management)
- OpenAI API key, Anthropic API key, or XAI API key
- Twitter Developer account and Twitter App with OAuth 1.0a authentication (for Twitter integration)

## Installation

### Using Poetry

1. Clone the repository:
```bash
git clone https://github.com/yourusername/waste-finder.git
cd waste-finder
```

2. Install dependencies using Poetry:
```bash
poetry env use python3.11
poetry install
```

3. Create a `.env` file with the following variables:
   - `OPENAI_API_KEY`: Your OpenAI API key
   - `ANTHROPIC_API_KEY`: Your Anthropic API key
   - `XAI_API_KEY`: Your XAI API key for Grok-2 access
   - `TWITTER_USER_ID`: Your Twitter user ID
   - `TWITTER_USERNAME`: Your Twitter username
   - `TWITTER_CONSUMER_KEY`: Your Twitter App consumer key
   - `TWITTER_CONSUMER_SECRET`: Your Twitter App consumer secret
   - `TWITTER_ACCESS_TOKEN`: Your Twitter access token
   - `TWITTER_ACCESS_TOKEN_SECRET`: Your Twitter access token secret

## Environment Setup

Create a `.env` file in the root directory with your API keys:

```
OPENAI_API_KEY=your_openai_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key
XAI_API_KEY=your_xai_api_key
TWITTER_USER_ID='your_twitter_user_id'
TWITTER_USERNAME='your_twitter_username'
TWITTER_CONSUMER_KEY='your_app_consumer_key'
TWITTER_CONSUMER_SECRET='your_app_consumer_secret'
TWITTER_ACCESS_TOKEN='your_access_token'
TWITTER_ACCESS_TOKEN_SECRET='your_access_token_secret'
```

## Usage

### 1. Download Contracts Data

```bash
poetry run python -m src.waste-finder.download_contracts --department "Department of Energy" --start-date "2024-01-01"
```

### 2. Transform Contract Data

```bash
poetry run python -m src.waste-finder.transform_data --dept-name "Department of Energy" --dept-acronym "DOE"
```

### 3. Data Orchestrator

```bash
poetry run python -m src.waste-finder.orchestrator --departments "Department of Energy" --start-date "2024-01-01" --skip-download --process-existing
```

### 4. Filter Contracts

```bash
poetry run python -m src.waste-finder.data.filter_contracts --input-dir ./processed_data/ --output-dir ./filtered_data/ --min-amount 1000000
```

### 5. Analyze Contract Data

```bash
poetry run python -m src.waste-finder.csv_analyzer ./filtered_data/ --prompt-type ngo_fraud --user-id default_user
```

### 6. Chat with LLM

```bash
poetry run python -m src.waste-finder.llm_chat --interactive --prompt-type ngo_fraud --user-id default_user
```

### 7. Analyze JSON Data

```bash
poetry run python -m src.waste-finder.json_analyzer ./llm_analysis/ --user-id default_user
```

### 8. Twitter Poster

```bash
poetry run python -m src.waste-finder.twitter_poster json ./posts/post.json
```

### 9. Run JSON and Twitter Orchestrator

```bash
poetry run python -m src.waste-finder.fraud_poster --file ./llm_analysis/file.json --user-id default_user
```

## Command-Line Arguments

### CSV Analyzer Arguments

```
--custom-prompt       Custom prompt to use for analysis
--max-rows            Maximum number of rows to include from CSV
--output-dir          Directory to save output files
--system-message      System message to include in API request
--description         Description to include in system message
--memory-query        Query to use for retrieving memories
--prompt-type         Type of prompt to use (default: dei)
--provider            LLM provider to use (default: xai)
--model               Model to use (default depends on provider)
--temperature         Temperature for LLM (default: 0.1)
--max-tokens          Maximum tokens for LLM response (default: 4096)
--api-key             API key (optional, default: from environment variables)
--user-id             User ID for memory operations (default: default_user)
```

### LLM Chat Arguments

```
--interactive         Run in interactive mode
--system-message      System message to include in API request
--description         Description to include in system message
--memory-query        Query to use for retrieving memories
--prompt-type         Type of prompt to use (default: dei)
--provider            LLM provider to use (default: xai)
--model               Model to use (default depends on provider)
--temperature         Temperature for LLM (default: 0.1)
--max-tokens          Maximum tokens for LLM response (default: 4096)
--api-key             API key (optional, default: from environment variables)
--user-id             User ID for memory operations (default: default_user)
```

### JSON Analyzer Arguments

```
json_file              Path to JSON file with grant data to analyze
--output-file, -o      Path to save output JSON with post content
--prompt-type, -p      Type of prompt to use (default: x_doge)
--no-research          Skip researching entities in the grant data
--provider             LLM provider to use (default: xai)
--model                Model to use (default depends on provider)
--temperature          Temperature for response generation (default: 0.7)
--max-tokens           Maximum tokens for response (default: 4096)
--api-key              API key for LLM provider (if not specified, will use from .env file)
--user-id              User ID for memory operations (default: default_user)
```

### Twitter Poster Arguments

```
post                   Post a tweet
  text                 Text content of the tweet
  --quote-id           ID of a tweet to quote

json                   Post a tweet from a JSON file
  json_file            Path to JSON file with tweet content

info                   Get information about the authenticated user
```

### Fraud Poster Arguments

```
--file, -f             Path to a single JSON file to process
--directory, -d        Directory containing JSON files to process
--output-dir, -o       Directory to save output files
--prompt-type, -p      Type of prompt to use for generating posts (default: x_doge)
--no-research          Skip researching entities in the grant data
--dry-run              Don't actually post to Twitter, just generate the posts
--limit, -l            Maximum number of files to process from directory
--file-pattern         Pattern to match JSON files (default: *.json)
--provider             LLM provider to use (default: xai)
--model                Model to use (default depends on provider)
--temperature          Temperature for response generation (default: 0.7)
--max-tokens           Maximum tokens for response (default: 4096)
--api-key              API key for LLM provider
--user-id              User ID for memory operations (default: default_user)
```

### Chat Commands
In interactive chat mode, you can use the following special commands:

- `exit` or `quit`: End the conversation
- `save`: Save the conversation history to a JSON file
- `memory: <content>`: Add a memory to the system
- `prompt: <type>`: Change the prompt type during the session

## Memory System

The LLM analyzer includes an integrated memory system that allows the AI to remember important information across sessions. This is useful for maintaining context in long-running analyses.

The memory system is automatically initialized when you specify a `--user-id` parameter. Memories are stored in a local database at `~/.mem0/`.

To leverage the memory system:

1. Always use the same `--user-id` for related sessions
2. Use the `--memory-query` parameter to search for relevant memories
3. The system will automatically retrieve and incorporate relevant memories into the analysis

## LLM Providers

The system supports multiple LLM providers:

- **XAI (Default)**: Uses the Grok-2-latest model
- **OpenAI**: Uses GPT-4o-mini by default
- **Anthropic**: Uses Claude-3-7-sonnet-latest by default

You can specify the provider using the `--provider` flag when running the LLM analyzer.

## Prompt System

The system includes multiple prompt types that can be selected:
- `dei`: Prompt for analyzing DEI (Diversity, Equity, and Inclusion) contracts
- `ngo_fraud`: Prompt for analyzing potential fraud in NGO government awards
- `x_doge`: Prompt for generating Twitter posts

## Project Structure

```
src/waste-finder/
│
├── __init__.py                  # Main package initialization
│
├── core/                        # Core functionality
│   ├── __init__.py
│   ├── base_llm.py              # Base LLM functionality
│   └── prompt.py                # Prompt templates
│
├── data/                        # Data acquisition and processing
│   ├── __init__.py
│   ├── download_contracts.py    # Download contract data
│   ├── transform_data.py        # Transform contract data
│   └── filter_contracts.py      # Filter contract data
│
├── analysis/                    # Analysis modules
│   ├── __init__.py
│   ├── csv_analyzer.py          # CSV file analysis
│   └── json_analyzer.py         # JSON file analysis
│
├── interaction/                 # User/external system interaction
│   ├── __init__.py
│   ├── llm_chat.py              # Interactive chat functionality
│   └── twitter_poster.py        # Twitter posting functionality
│
└── orchestration/               # Process orchestration
    ├── __init__.py
    ├── orchestrator.py          # Main orchestration for analysis pipeline
    └── fraud_poster.py          # Orchestration for posting findings

```

## Twitter Integration Setup

To use the Twitter/X posting functionality, add the following variables to your `.env` file:

```
TWITTER_USER_ID='your_twitter_user_id'
TWITTER_USERNAME='your_twitter_username'
TWITTER_CONSUMER_KEY='your_app_consumer_key'
TWITTER_CONSUMER_SECRET='your_app_consumer_secret'
TWITTER_ACCESS_TOKEN='your_access_token'
TWITTER_ACCESS_TOKEN_SECRET='your_access_token_secret'
```

You can obtain these credentials by creating a Twitter Developer account and setting up a Twitter App with OAuth 1.0a authentication.