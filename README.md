# Fraud Finder

This Python service downloads active contracts from the USA Spending API, analyzes them using various LLM models, and provides chat interfaces for interactive analysis.

## Requirements
- Python 3.11
- Poetry (dependency management)
- OpenAI API key, Anthropic API key, XAI API or XAI cookies (for Grok-Beta)

## Installation

1. Create a virtual environment and install dependencies:
```bash
poetry env use python3.11
poetry install
```

2. Set up environment variables:
Create a `.env` file in the project root with the following variables:
```
OPENAI_API_KEY=your_openai_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key
XAI_API_KEY=your_xai_api_key
```

## Environment Setup

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Create a `.env` file with the following variables:
   - `OPENAI_API_KEY`: Your OpenAI API key
   - `ANTHROPIC_API_KEY`: Your Anthropic API key
   - `XAI_API_KEY`: Your XAI API key for grok-2 access
   - `XAI_COOKIES`: Your XAI cookies for grok-beta browser-based access (required for grok3_chat.py)

### Grok3 API Setup

The `grok3_chat.py` tool requires the Grok3 API client, which needs to be installed separately:

```bash
# Clone the repository
git clone https://github.com/mem0ai/grok3-api.git /tmp/grok3-api

# Install the package
cd /tmp/grok3-api && pip install -e .
```

The Grok3 API client uses browser cookies for authentication. You need to set the `XAI_COOKIES` environment variable with your Grok browser cookies in the following format:

```
x-anonuserid=value1; x-challenge=value2; x-signature=value3; sso=value4; sso-rw=value5
```

You can obtain these cookies by:
1. Logging into https://grok.com in your browser
2. Opening the developer tools (F12)
3. Going to the Application tab
4. Finding the cookies under the Storage section
5. Copying the values for the required cookies

## Usage

### Download Contracts
Download active contracts from the USA Spending API:
```bash
poetry run python -m waste-finder.download_contracts
```

### Transform Data
Transform downloaded contract data:
```bash
poetry run python -m waste-finder.transform_data \
  --input-file path/to/input.csv \
  --output-file path/to/output.csv
```

### LLM Analyzer
Analyze contracts using LLM models with various options:

#### Analyze CSV files
```bash
poetry run python -m waste-finder.llm_analyzer analyze \
  --csv-file path/to/contracts.csv \
  --max-rows 100 \
  --output-dir llm_analysis \
  --prompt-type dei \
  --system-message "You are an expert contract analyst." \
  --description "Analyze these government contracts" \
  --memory-query "government contracts" \
  --user-id "analyst1"
```

Options:
- `--csv-file`: Path to CSV file or directory containing CSV files (required)
- `--max-rows`: Maximum rows to include from CSV (default: all)
- `--output-dir`: Directory to save output files (default: llm_analysis)
- `--prompt-type`: Type of prompt to use (default: dei, options: dei, ngo_fraud)
- `--prompt-file`: Custom prompt file (default: use built-in prompt)
- `--system-message`: System message to include in API call (default: "You are an expert contract analyst for the Department of Government Efficiency (DOGE).")
- `--description`: Simple description to include in the system message
- `--memory-query`: Query to use for retrieving memories
- `--user-id`: User ID for memory operations (default: default_user)

#### Chat with LLM
```bash
poetry run python -m waste-finder.llm_analyzer chat \
  --interactive \
  --provider openai \
  --model gpt-4 \
  --temperature 0.7 \
  --system-message "You are a helpful assistant." \
  --user-id "user1"
```

Options:
- `--interactive`: Start interactive chat session
- `--message`: Message to send to the LLM (non-interactive mode)
- `--provider`: API provider (default: openai, options: openai, anthropic, xai)
- `--model`: Model to use (default: gpt-4 for OpenAI, claude-3-opus-20240229 for Anthropic, grok-1 for XAI)
- `--temperature`: Temperature for generation (default: 0.7)
- `--system-message`: System message to include in API call
- `--user-id`: User ID for memory operations (default: default_user)

### Grok-3 Chat
Chat with Grok-3 with memory support:

```bash
poetry run python -m waste-finder.grok3_chat \
  --interactive \
  --temperature 0.7 \
  --max-tokens 1000 \
  --system-message "You are a helpful assistant." \
  --user-id "user1" \
  --prompt-type dei
```

Options:
- `--interactive`: Interactive chat mode
- `--message`: Single message to send
- `--temperature`: Temperature for generation (default: 0.7)
- `--max-tokens`: Maximum tokens to generate (default: 1000)
- `--system-message`: System message to include
- `--user-id`: User ID for memory operations (default: default_user)
- `--cookies`: Cookies for authentication (overrides XAI_COOKIES env var)
- `--prompt-type`: Type of prompt to use (default: dei, options: dei, ngo_fraud)
- `--save`: Save conversation to file

### Orchestrator
Run the complete pipeline:
```bash
poetry run python -m waste-finder.orchestrator \
  --download \
  --transform \
  --analyze
```

Options:
- `--download`: Download contracts from USA Spending API
- `--transform`: Transform downloaded data
- `--analyze`: Analyze transformed data using LLM
- `--max-rows`: Maximum rows to analyze (default: all)

## Memory System

Both the LLM Analyzer and Grok-3 Chat include a memory system that allows for persistent storage and retrieval of information across sessions. The memory system is user-specific, meaning different users can have separate memory spaces.

### Using Memory Commands

In both chat interfaces, you can use the following memory commands:
- `memory: <content>` - Add a new memory

In Grok-3 Chat, you can also use:
- `prompt: <type>` - Change the prompt type (e.g., `prompt: dei` or `prompt: ngo_fraud`)

## Prompt System

The system includes multiple prompt types that can be selected:
- `dei`: Default prompt for analyzing DEI (Diversity, Equity, and Inclusion) contracts
- `ngo_fraud`: Prompt for analyzing potential fraud in NGO government awards

## Project Structure
```
waste-finder/
├── pyproject.toml
├── README.md
└── src/
    └── waste-finder/
        ├── __init__.py
        ├── download_contracts.py
        ├── transform_data.py
        ├── llm_analyzer.py
        ├── grok3_chat.py
        ├── prompt.py
        └── orchestrator.py
```