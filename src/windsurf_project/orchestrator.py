#!/usr/bin/env python3
import os
import argparse
import logging
import time
from datetime import datetime
import json
import glob

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
    end_date=None,
    output_base_dir="processed_data",
    skip_download=False,
):
    """Process all award types for a single department"""
    results = {}

    # Create department output directory
    dept_dir = os.path.join(output_base_dir, dept_acronym)
    os.makedirs(dept_dir, exist_ok=True)

    for award_type in award_types:
        logging.info(f"Processing {dept_name} ({dept_acronym}) - {award_type}")

        zip_files = []
        
        # Step 1: Download contract data (if not skipped)
        if not skip_download:
            zip_files = download_contracts(dept_name, award_type, start_date, end_date)
            if not zip_files:
                logging.warning(f"No zip files downloaded for {dept_name} ({award_type})")
                continue
        else:
            # Find existing zip files for this department and award type
            # Format: department_of_X_awardtype_date_to_date.zip
            dept_name_lower = dept_name.lower().replace(" ", "_")
            zip_pattern = os.path.join("contract_data", f"{dept_name_lower}_{award_type}_*.zip")
            zip_files = glob.glob(zip_pattern)
            
            if not zip_files:
                logging.warning(f"No existing zip files found for {dept_name} ({award_type})")
                continue
                
            logging.info(f"Found {len(zip_files)} existing zip files for {dept_name} ({award_type})")

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


def process_all_existing_data(output_dir="processed_data"):
    """Process all existing downloaded data without re-downloading"""
    results = {}
    
    # Find all existing zip files
    zip_files = glob.glob(os.path.join("contract_data", "*.zip"))
    
    if not zip_files:
        logging.warning("No existing zip files found in contract_data directory")
        return results
        
    logging.info(f"Found {len(zip_files)} existing zip files to process")
    
    # Extract unique department-award type combinations from filenames
    dept_award_combos = set()
    
    for zip_file in zip_files:
        filename = os.path.basename(zip_file)
        
        # Expected format: department_of_X_awardtype_date_to_date.zip
        # Example: department_of_agriculture_grant_2024-01-01_to_2024-03-31.zip
        parts = filename.split('_')
        
        if len(parts) >= 4:
            # Extract department name and award type
            dept_parts = []
            award_type = None
            
            for i, part in enumerate(parts):
                if part in AWARD_TYPES:
                    award_type = part
                    dept_parts = parts[:i]
                    break
            
            if not award_type or not dept_parts:
                logging.warning(f"Could not parse department and award type from filename: {filename}")
                continue
                
            # Reconstruct department name
            dept_name = " ".join(dept_parts).replace("department of ", "Department of ")
            
            # Find the department acronym
            dept_acronym = None
            for name, acronym in DEPARTMENTS.items():
                if name.lower() == dept_name.lower():
                    dept_acronym = acronym
                    dept_name = name  # Use the correct casing from the dictionary
                    break
            
            if not dept_acronym:
                logging.warning(f"Unknown department in filename: {dept_name}")
                continue
                
            if award_type in AWARD_TYPES:
                dept_award_combos.add((dept_name, dept_acronym, award_type))
    
    logging.info(f"Found {len(dept_award_combos)} unique department-award type combinations to process")
    
    # Process each unique combination
    for dept_name, dept_acronym, award_type in dept_award_combos:
        logging.info(f"Processing existing data for {dept_name} ({dept_acronym}) - {award_type}")
        
        # Create department output directory
        dept_dir = os.path.join(output_dir, dept_acronym)
        os.makedirs(dept_dir, exist_ok=True)
        
        # Transform and filter data
        master_file = transform_data(
            zip_dir="contract_data",
            output_dir=dept_dir,
            dept_name=dept_name,
            dept_acronym=dept_acronym,
            sub_award_type=award_type,
        )
        
        if master_file:
            if dept_acronym not in results:
                results[dept_acronym] = {}
            results[dept_acronym][award_type] = master_file
        
        # Add a small delay between processing
        time.sleep(1)
    
    return results


def main(
    departments=None, 
    award_types=None, 
    start_date=None, 
    end_date=None,
    output_dir="processed_data", 
    skip_download=False,
    process_existing=False
):
    """Main function to orchestrate the entire workflow"""
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Process all existing data if requested
    if process_existing:
        logging.info("Processing all existing downloaded data without re-downloading")
        results = process_all_existing_data(output_dir)
    else:
        # Use all departments if none specified
        if not departments:
            departments = list(DEPARTMENTS.keys())

        # Use all award types if none specified
        if not award_types:
            award_types = AWARD_TYPES

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
                dept_name, 
                dept_acronym, 
                award_types, 
                start_date, 
                end_date,
                output_dir,
                skip_download
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
        "--end-date",
        default=None,
        help="End date in YYYY-MM-DD format (default: today)",
    )
    parser.add_argument(
        "--output-dir",
        default="processed_data",
        help="Base directory for output files (default: processed_data)",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip downloading and use existing files (must specify departments and award types)",
    )
    parser.add_argument(
        "--process-existing",
        action="store_true",
        help="Process all existing downloaded data without re-downloading (ignores departments and award types arguments)",
    )

    args = parser.parse_args()
    
    # Validate arguments
    if args.skip_download and args.process_existing:
        parser.error("Cannot use both --skip-download and --process-existing together")

    main(
        args.departments, 
        args.award_types, 
        args.start_date, 
        args.end_date,
        args.output_dir, 
        args.skip_download,
        args.process_existing
    )
