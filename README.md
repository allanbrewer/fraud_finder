# Fraud Finder

[![License: CC BY-NC 4.0](https://img.shields.io/badge/License-CC_BY--NC_4.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc/4.0/)

This Python service downloads active contracts from the USA Spending API, analyzes them using various LLM models, and provides chat interfaces for interactive analysis.

## Requirements
- Python 3.11
- Poetry (dependency management)
- OpenAI API key, Anthropic API key, XAI API key, Gemini API key
- Twitter Developer account and Twitter App with OAuth 1.0a authentication (for Twitter integration)

## Installation

### Using Poetry

1. Clone the repository:
```bash
git clone https://github.com/allanbrewer/fraud_finder.git
cd fraud_finder
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
   - `GEMINI_API_KEY`: Your Gemini API key
   - `TWITTER_USER_ID`: Your Twitter user ID
   - `TWITTER_USERNAME`: Your Twitter username
   - `TWITTER_CONSUMER_KEY`: Your Twitter App consumer key
   - `TWITTER_CONSUMER_SECRET`: Your Twitter App consumer secret
   - `TWITTER_ACCESS_TOKEN`: Your Twitter access token
   - `TWITTER_ACCESS_TOKEN_SECRET`: Your Twitter access token secret

## Usage

### 1. Download Contracts Data

```bash
poetry run python -m src.waste-finder.data.download_contracts --department "Department of Energy" --start-date "2024-01-01"
```

### 2. Transform Contract Data

```bash
poetry run python -m src.waste-finder.data.transform_data --dept-name "Department of Energy" --dept-acronym "DOE"
```

### 3. Data Orchestrator

```bash
poetry run python -m src.waste-finder.orchestration.orchestrator --departments "Department of Energy" --start-date "2024-01-01" --skip-download --process-existing
```

### 4. Filter Contracts

```bash
poetry run python -m src.waste-finder.data.filter_contracts --input-dir ./processed_data/ --output-dir ./filtered_data/ --min-amount 1000000 --keyword-type waste
```

### 5. Analyze Contract Data

```bash
poetry run python -m src.waste-finder.analysis.csv_analyzer ./filtered_data/ --prompt-type ngo_fraud --user-id default_user
```

### 6. Chat with LLM

```bash
poetry run python -m src.waste-finder.interaction.llm_chat --interactive --prompt-type ngo_fraud --user-id default_user
```

### 7. Analyze JSON Data

```bash
poetry run python -m src.waste-finder.analysis.json_analyzer ./llm_analysis/waste_procurement/file.json --award-type procurement --user-id default_user
```

### 8. Twitter Poster

```bash
poetry run python -m src.waste-finder.interaction.twitter_poster json ./posts/post.json
```

### 9. Run JSON and Twitter Orchestrator

```bash
poetry run python -m src.waste-finder.orchestration.fraud_poster --file ./llm_analysis/file.json --user-id default_user
```

The Fraud Poster orchestrator has been updated to coordinate between the new JSON analyzer and Twitter components, handling both single entries and lists of targets.

## Command-Line Arguments

### Download Contracts Arguments

```
--department          Department name to download contracts for (required)
--sub-award-type      Type of award to download (default: procurement)
--start-date          Start date for contracts in YYYY-MM-DD format (default: 30 days ago)
--end-date            End date for contracts in YYYY-MM-DD format (default: today)
--api-key             USAspending API key (if not specified, will use from .env file)
```

### Transform Data Arguments

```
--zip-dir             Directory containing downloaded zip files (default: contract_data)
--output-dir          Directory to save processed data (default: processed_data)
--dept-name           Full department name (required)
--dept-acronym        Department acronym (required)
--sub-award-type      Type of award to process (default: procurement)
```

### Filter Contracts Arguments

```
--input-dir           Directory containing processed CSV files (default: processed_data)
--output-dir          Directory to save filtered data (default: filtered_data)
--min-amount          Minimum contract amount to include (default: 500000)
--combine             Combine all filtered results into one file (default: True)
--award-type          Type of award to filter (default: None, processes all types)
--keyword-type        Type of keywords to use (default: waste)
```

### CSV Analyzer Arguments

```
csv_file              Path to CSV file or directory with grant data to analyze
--custom-prompt       Custom prompt to use for analysis
--max-rows            Maximum number of rows to include from CSV
--output-dir          Directory to save output files
--system-message      Custom system message for the LLM
--description         Description of the data for the LLM
--memory-query        Query to retrieve relevant memories
--prompt-type         Type of prompt to use (default: ngo_fraud)
--provider            LLM provider to use (default: xai)
--model               Model to use (default depends on provider)
--temperature         Temperature for response generation (default: 0.7)
--max-tokens          Maximum tokens for response (default: 4096)
--api-key             API key for LLM provider (if not specified, will use from .env file)
--user-id             User ID for memory operations (default: default_user)
```

### LLM Chat Arguments

```
--interactive         Start interactive chat mode
--prompt-type         Type of prompt to use (default: ngo_fraud)
--provider            LLM provider to use (default: xai)
--model               Model to use (default depends on provider)
--temperature         Temperature for response generation (default: 0.7)
--max-tokens          Maximum tokens for response (default: 4096)
--api-key             API key for LLM provider (if not specified, will use from .env file)
--user-id             User ID for memory operations (default: default_user)
```

### JSON Analyzer Arguments

```
json_file             Path to JSON file with grant data to analyze
--output-dir          Directory to save output files (default: llm_analysis)
--award-type          Type of award to analyze (optional)
--provider            LLM provider to use (default: xai)
--model               Model to use (default depends on provider)
--temperature         Temperature for response generation (default: 0.7)
--max-tokens          Maximum tokens for response (default: 4096)
--api-key             API key for LLM provider (if not specified, will use from .env file)
--user-id             User ID for memory operations (default: default_user)
```

The JSON analyzer now supports processing JSON files with different structures:
- Single grant entry as a dictionary
- Multiple grant entries as a list
- Dictionary with lists of targets under various keys (e.g., "doge_targets")

### Twitter Poster Arguments

```
command               Command to execute: 'post', 'json', or 'generate'
content               Text to post, path to JSON file with post content, or path to grant data JSON
--quote-id            ID of tweet to quote (optional, for 'post' command)
--output-file         Path to save generated post (for 'generate' command)
--prompt-type         Type of prompt to use (default: x_doge, for 'generate' command)
--provider            LLM provider to use (default: xai, for 'generate' command)
--model               Model to use (default depends on provider, for 'generate' command)
--user-id             User ID for memory operations (default: default_user, for 'generate' command)
--dry-run             Don't actually post to Twitter, just print what would be posted
```

The Twitter poster now supports three commands:
- `post`: Post text directly to Twitter
- `json`: Post content from a JSON file
- `generate`: Generate a post from grant data JSON without posting

### Fraud Poster Arguments

```
--file                Path to JSON file with grant data to analyze
--dir                 Directory containing JSON files to analyze
--output-dir          Directory to save output files
--prompt-type         Type of prompt to use (default: x_doge)
--no-research         Skip researching entities in the grant data
--no-post             Don't post to Twitter, just generate posts
--dry-run             Don't actually post to Twitter, just print what would be posted
--provider            LLM provider to use (default: xai)
--model               Model to use (default depends on provider)
--temperature         Temperature for response generation (default: 0.7)
--max-tokens          Maximum tokens for response (default: 4096)
--api-key             API key for LLM provider (if not specified, will use from .env file)
--user-id             User ID for memory operations (default: default_user)
```

### Orchestrator Arguments

```
--departments         Comma-separated list of departments to process
--start-date          Start date for contracts in YYYY-MM-DD format (default: 30 days ago)
--end-date            End date for contracts in YYYY-MM-DD format (default: today)
--skip-download       Skip downloading new contracts
--skip-transform      Skip transforming downloaded data
--skip-filter         Skip filtering transformed data
--process-existing    Process existing data in the processed directory
--min-amount          Minimum contract amount to include (default: 500000)
--output-dir          Directory to save output files
```

## Workflow Example

Here's a complete example workflow:

1. **Download contracts for the Department of Energy**:
```bash
poetry run python -m src.waste-finder.data.download_contracts --department "Department of Energy" --start-date "2024-01-01"
```

2. **Transform the downloaded data**:
```bash
poetry run python -m src.waste-finder.data.transform_data --dept-name "Department of Energy" --dept-acronym "DOE"
```

3. **Filter contracts by amount**:
```bash
poetry run python -m src.waste-finder.data.filter_contracts --min-amount 1000000 --keyword-type waste
```

4. **Analyze filtered contracts**:
```bash
poetry run python -m src.waste-finder.analysis.csv_analyzer ./filtered_data/ --prompt-type ngo_fraud --user-id default_user
```

5. **Generate social media posts from analysis**:
```bash
poetry run python -m src.waste-finder.analysis.json_analyzer ./llm_analysis/analysis_file.json --output-file ./posts/post.json
```

6. **Post findings to Twitter**:
```bash
poetry run python -m src.waste-finder.interaction.twitter_poster json ./posts/post.json
```

7. **Or use the combined fraud poster**:
```bash
poetry run python -m src.waste-finder.orchestration.fraud_poster --file ./llm_analysis/analysis_file.json --output-dir ./posts
```

8. **Or run the entire orchestration process**:
```bash
poetry run python -m src.waste-finder.orchestration.orchestrator --departments "Department of Energy" --start-date "2024-01-01"
```

## Environment Variables

The following environment variables are used by the project:

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

You can obtain Twitter credentials by creating a Twitter Developer account and setting up a Twitter App with OAuth 1.0a authentication.

## License

This project is licensed under the Creative Commons Attribution-NonCommercial 4.0 International License - see the [LICENSE](LICENSE) file for details.

## Project Structure

```
src/waste-finder/
│
├── __init__.py                  # Main package initialization
│
├── core/                        # Core functionality
│   ├── __init__.py
│   ├── keyword.py               # Keyword definitions for filtering
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