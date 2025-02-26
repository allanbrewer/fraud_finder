import requests
from datetime import datetime, UTC, timedelta
import os
import json
import time
import argparse
import logging
from dateutil.relativedelta import relativedelta

# Configure logging
logging.basicConfig(level=logging.INFO)

# API endpoint for USASpending.gov bulk downloads
BASE_URL = "https://api.usaspending.gov/api/v2/bulk_download/awards/"


def create_post_data(start_date: str, end_date: str, department: str):
    return {
        "filters": {
            "prime_award_types": [
                "A",
                "B",
                "C",
                "D",
                "IDV_A",
                "IDV_B",
                "IDV_B_A",
                "IDV_B_B",
                "IDV_B_C",
                "IDV_C",
                "IDV_D",
                "IDV_E",
            ],
            "date_type": "action_date",
            "date_range": {"start_date": start_date, "end_date": end_date},
            "def_codes": [],
            "agencies": [{"type": "awarding", "tier": "toptier", "name": department}],
        },
        "columns": [],
        "file_format": "csv",
    }


def request_download(start_date: str, end_date: str, department: str):
    try:
        payload = create_post_data(start_date, end_date, department)
        logging.info(
            f"Requesting {department} ({start_date} to {end_date}): {json.dumps(payload)}"
        )
        response = requests.post(
            url=BASE_URL,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json", "User-Agent": "curl/7.68.0"},
            timeout=60,  # Bumped up for bigger requests
        )
        response.raise_for_status()
        result = response.json()
        if "file_url" not in result:
            logging.warning(
                f"{department} ({start_date} to {end_date}): No file_url in response"
            )
            return None

        logging.info(f"Requested {department} ({start_date} to {end_date})")
        file_url = result["file_url"]
        logging.info(f"File URL: {file_url}")
        status_url = result.get("status_url", "N/A")  # Safe get in case it's missing
        logging.info(f"Status URL: {status_url}")
        return file_url
    except requests.exceptions.RequestException as e:
        logging.error(
            f"Error requesting download for {department} ({start_date} to {end_date}): {str(e)}"
        )
        return None


def check_file_status(file_url):
    """Check if the file is ready for download by making a HEAD request"""
    try:
        response = requests.head(file_url, timeout=30)
        return (
            response.status_code == 200
            and int(response.headers.get("Content-Length", 0)) > 0
        )
    except requests.exceptions.RequestException:
        return False


def download_file(file_url, department, start_date, end_date):
    output_dir = "contract_data"
    os.makedirs(output_dir, exist_ok=True)

    # Create a deterministic filename without timestamp to avoid duplicates
    file_id = (
        f"usaspending_{department.lower().replace(' ', '_')}_{start_date}_{end_date}"
    )
    output_file = os.path.join(output_dir, f"{file_id}.zip")

    # Check if file already exists
    if os.path.exists(output_file):
        logging.info(f"File already exists: {output_file}")
        return os.path.basename(output_file)

    try:
        logging.info(
            f"{department} ({start_date} to {end_date}): Downloading {file_url}"
        )
        response = requests.get(file_url, stream=True, timeout=600)
        response.raise_for_status()
        with open(output_file, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        logging.info(
            f"{department} ({start_date} to {end_date}): Saved to {output_file}"
        )
        return os.path.basename(output_file)
    except requests.exceptions.RequestException as e:
        logging.error(
            f"Error downloading {department} ({start_date} to {end_date}): {str(e)}"
        )
        return None


def fetch_download(
    file_url, department, start_date, end_date, max_wait_attempts=60, time_interval=30
):
    attempt = 1
    while attempt <= max_wait_attempts:
        # First check if the file is ready
        if check_file_status(file_url):
            filename = download_file(file_url, department, start_date, end_date)
            if filename:
                return filename

        logging.info(
            f"{department}: Attempt {attempt}/{max_wait_attempts} - File not ready yet, waiting..."
        )
        time.sleep(time_interval)
        attempt += 1

    logging.warning(
        f"{department} ({start_date} to {end_date}): Not ready after {max_wait_attempts} attempts."
    )
    return None


def check_and_download_missing(
    file_urls, successful_downloads, max_attempts=10, wait_interval=30
):
    missing_files = {}

    for (department, start, end), file_url in file_urls.items():
        # Skip if already downloaded or no URL available
        file_id = (
            f"usaspending_{department.lower().replace(' ', '_')}_{start}_{end}.zip"
        )
        if file_id in successful_downloads or file_url is None:
            continue

        logging.info(
            f"Attempting to recover missing file: {department} ({start} to {end})"
        )
        filename = fetch_download(
            file_url, department, start, end, max_attempts, wait_interval
        )
        if not filename:
            logging.warning(
                f"{department} ({start} to {end}): Still missing after cleanup."
            )
            missing_files[(department, start, end)] = file_url

    return missing_files


def create_date_ranges(start_date_str, end_date_str, interval_months=3):
    """Create date ranges with specified interval in months"""
    # Convert string dates to datetime objects
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")

    date_ranges = []
    current_start = start_date

    while current_start < end_date:
        # Simply add interval_months and subtract 1 day
        current_end = (
            current_start + relativedelta(months=interval_months) - timedelta(days=1)
        )

        # Ensure we don't go beyond the end_date
        if current_end > end_date:
            current_end = end_date

        # Add the date range as strings
        date_ranges.append(
            (current_start.strftime("%Y-%m-%d"), current_end.strftime("%Y-%m-%d"))
        )

        # Move to the next interval
        current_start = current_end + timedelta(days=1)

    return date_ranges


def main(department, start_date=None):
    # Set end date to today in UTC
    end_date = datetime.now(tz=UTC).strftime("%Y-%m-%d")

    # Set default start date if not provided
    if start_date is None:
        start_date = "2024-01-01"  # Default to Jan 1, 2024

    # Create date ranges in 3-month intervals
    date_ranges = create_date_ranges(start_date, end_date, interval_months=3)

    logging.info(f"Processing date ranges: {date_ranges}")

    # Step 1: Fire off all requests
    file_urls = {}
    logging.info("Initiating all download requests...")
    for start_date, end_date in date_ranges:
        file_url = request_download(start_date, end_date, department)
        file_urls[(department, start_date, end_date)] = file_url
        time.sleep(3)

    # Step 2: Fetch the files
    successful_downloads = []
    logging.info("\nFetching generated files...")
    for (department, start_date, end_date), file_url in file_urls.items():
        if file_url:
            filename = fetch_download(file_url, department, start_date, end_date)
            if filename:
                successful_downloads.append(filename)
        else:
            logging.warning(
                f"{department} ({start_date} to {end_date}): No file_url from initial request."
            )

    # Step 3: Cleanup - only try to download files that weren't successfully downloaded
    if len(successful_downloads) < len(date_ranges):
        logging.info("\nChecking for missing downloads...")
        still_missing = check_and_download_missing(file_urls, successful_downloads)
        if still_missing:
            logging.error(f"Couldn't recover these: {still_missing}")
        else:
            logging.info("All missing files recovered!")
    else:
        logging.info("\nAll files downloaded successfully!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Download contract data from USA Spending API"
    )
    parser.add_argument("--department", required=True, help="Department to download")
    parser.add_argument(
        "--start-date",
        default=None,
        help="Start date in YYYY-MM-DD format (default: 2022-01-01)",
    )

    args = parser.parse_args()

    main(args.department, args.start_date)
