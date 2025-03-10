"""Service to download and analyze active contracts from USAspending.gov for waste detection"""

__version__ = "0.1.0"

import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logging.info("Starting waste finder service...")
