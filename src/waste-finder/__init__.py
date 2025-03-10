"""Service to download and analyze active contracts from USAspending.gov for waste detection"""

__version__ = "0.1.0"

import logging

# Configure the root logger
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Get the root logger
logger = logging.getLogger()

# Set the level for all loggers
logger.setLevel(logging.INFO)

# Log startup message
logging.info("Starting waste finder service...")
