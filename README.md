# Fraud Finder

This Python service downloads active contracts from the USA Spending API, analyzes them using various LLM models, and provides chat interfaces for interactive analysis.

## Requirements
- Python 3.11
- Poetry (dependency management)
- OpenAI API key, Anthropic API key, or XAI API key

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

## Environment Setup

Create a `.env` file in the root directory with your API keys:

```
OPENAI_API_KEY=your_openai_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key
XAI_API_KEY=your_xai_api_key
```

## Usage

### 1. Download Contracts Data

```bash
poetry run python -m src.waste-finder.download_contracts --max-contracts 1000 --fiscal-year 2023 --save-dir ./data
```

### 2. Transform Contract Data

```bash
poetry run python -m src.waste-finder.transform_data --input ./data/contracts.csv --output ./data/transformed.csv
```

### 3. Analyze Contract Data

```bash
poetry run python -m src.waste-finder.csv_analyzer ./data/transformed.csv --output-dir ./results --prompt-type dei --user-id my_session
```

### 4. Chat with LLM

```bash
poetry run python -m src.waste-finder.llm_chat --interactive --prompt-type dei --user-id my_session
```

### 5. Run Complete Pipeline

```bash
poetry run python -m src.waste-finder.orchestrator --max-contracts 100 --fiscal-year 2023 --prompt-type dei --user-id my_session
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

## Project Structure

```
src/waste-finder/
├── __init__.py              # Package initialization
├── download_contracts.py    # Download contract data from USAspending.gov
├── transform_data.py        # Transform contract data
├── base_llm.py              # Base LLM class with shared functionality
├── csv_analyzer.py          # CSV file analyzer using LLM
├── llm_chat.py              # Interactive chat with LLM
├── prompt.py                # Prompt templates
└── orchestrator.py          # End-to-end orchestration