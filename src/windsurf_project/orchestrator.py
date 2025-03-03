#!/usr/bin/env python3
import os
import argparse
import logging
import time
from datetime import datetime
import json

# Import our modules
from download_contracts import main as download_contracts
from transform_data import main as transform_data

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Define department mapping (API name to acronym)
DEPARTMENTS = {
    "Department of Agriculture": "USDA",
    "Department of Commerce": "DOC",
    "Department of Defense": "DOD",
    "Department of Education": "ED",
    "Department of Energy": "DOE",
    "Department of Health and Human Services": "HHS",
    "Department of Homeland Security": "DHS",
    "Department of Housing and Urban Development": "HUD",
    "Department of Justice": "DOJ",
    "Department of Labor": "DOL",
    "Department of State": "DOS",
    "Department of the Interior": "DOI",
    "Department of the Treasury": "TREAS",
    "Department of Transportation": "DOT",
    "Department of Veterans Affairs": "VA",
    "Environmental Protection Agency": "EPA",
    "National Aeronautics and Space Administration": "NASA",
    "Small Business Administration": "SBA",
}

# Award types to process
AWARD_TYPES = ["procurement", "grant"]


def process_department(
    dept_name,
    dept_acronym,
    award_types,
    start_date=None,
    output_base_dir="processed_data",
):
    """Process all award types for a single department"""
    results = {}

    # Create department output directory
    dept_dir = os.path.join(output_base_dir, dept_acronym)
    os.makedirs(dept_dir, exist_ok=True)

    for award_type in award_types:
        logging.info(f"Processing {dept_name} ({dept_acronym}) - {award_type}")

        # Step 1: Download contract data
        zip_files = download_contracts(dept_name, award_type, start_date)
        if not zip_files:
            logging.warning(f"No zip files downloaded for {dept_name} ({award_type})")
            continue

        # Step 2: Transform and filter data
        master_file = transform_data(
            zip_dir="contract_data",
            output_dir=dept_dir,
            dept_name=dept_name,
            dept_acronym=dept_acronym,
            sub_award_type=award_type,
        )

        if master_file:
            results[award_type] = master_file

        # Add a small delay between processing different award types
        time.sleep(2)

    return results


def main(
    departments=None, award_types=None, start_date=None, output_dir="processed_data"
):
    """Main function to orchestrate the entire workflow"""
    # Use all departments if none specified
    if not departments:
        departments = list(DEPARTMENTS.keys())

    # Use all award types if none specified
    if not award_types:
        award_types = AWARD_TYPES

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    # Create a results dictionary
    results = {}

    # Process each department
    for dept_name in departments:
        if dept_name not in DEPARTMENTS:
            logging.warning(f"Unknown department: {dept_name}")
            continue

        dept_acronym = DEPARTMENTS[dept_name]
        logging.info(f"Processing department: {dept_name} ({dept_acronym})")

        dept_results = process_department(
            dept_name, dept_acronym, award_types, start_date, output_dir
        )

        if dept_results:
            results[dept_acronym] = dept_results

    # Save results summary
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_file = os.path.join(output_dir, f"processing_summary_{timestamp}.json")

    with open(summary_file, "w") as f:
        json.dump(results, f, indent=2)

    logging.info(f"Processing complete! Summary saved to {summary_file}")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Orchestrate the download and processing of contract data"
    )
    parser.add_argument(
        "--departments",
        nargs="+",
        help="List of departments to process (default: all departments)",
    )
    parser.add_argument(
        "--award-types",
        nargs="+",
        choices=AWARD_TYPES,
        help="Award types to process (default: all types)",
    )
    parser.add_argument(
        "--start-date",
        default=None,
        help="Start date in YYYY-MM-DD format (default: 2024-01-01)",
    )
    parser.add_argument(
        "--output-dir",
        default="processed_data",
        help="Base directory for output files (default: processed_data)",
    )

    args = parser.parse_args()

    main(args.departments, args.award_types, args.start_date, args.output_dir)
