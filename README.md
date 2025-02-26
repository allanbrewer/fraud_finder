# Active Contracts Downloader

This Python service downloads active contracts from the USA Spending API and saves them in CSV format for further analysis.

## Requirements
- Python 3.11
- Poetry (dependency management)

## Installation

1. Create a virtual environment and install dependencies:
```bash
poetry env use python3.11
poetry install
```

## Usage
Run the script using:
```bash
poetry run python -m windsurf_project.download_contracts
```

## Project Structure
```
windsurf-project/
├── pyproject.toml
├── README.md
└── src/
    └── windsurf_project/
        ├── __init__.py
        └── download_contracts.py
 