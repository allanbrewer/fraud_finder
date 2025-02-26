import zipfile
import os
import pandas as pd
from datetime import datetime
import re
import logging
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def setup_keywords():
    """Define keywords for filtering (case-insensitive)"""
    keywords = [
        "DEI",
        "diversity",
        "equity",
        "inclusion",
        "gender",
        "civil rights",
        "training",
        "workshops",
        "clerical",
        "mailing",
        "operations",
        "support",
        "consulting",
        "services",
        "administrative",
        "initiative",
        "public-facing",
        "applications",
        "observe",
        "mail",
        "facility",
        "institute",
        "non-binary",
    ]
    # Create a regex pattern to match whole words or phrases
    pattern = re.compile(
        r"\b(" + "|".join([re.escape(kw) for kw in keywords]) + r")\b", re.IGNORECASE
    )
    return pattern


def process_zip_file(zip_path, filtered_dir, flagged_dir, pattern, today_date):
    """Process a single zip file and return paths to filtered and flagged files"""
    zip_file = os.path.basename(zip_path)
    logging.info(f"Processing {zip_file}...")

    # Create extract directory
    extract_dir = os.path.join(os.path.dirname(zip_path), f"extracted_{zip_file[:-4]}")

    try:
        # Unzip
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(extract_dir)
            csv_files = [f for f in os.listdir(extract_dir) if f.endswith(".csv")]
            if not csv_files:
                logging.warning(f"No CSV files found in {zip_file}")
                return None, None

            csv_file = csv_files[0]
            csv_path = os.path.join(extract_dir, csv_file)

        # Load and filter
        df = pd.read_csv(csv_path, low_memory=False)

        # Convert date column to datetime
        df["period_of_performance_current_end_date"] = pd.to_datetime(
            df["period_of_performance_current_end_date"], errors="coerce"
        )

        # Filter active contracts
        active_df = df[df["period_of_performance_current_end_date"] > today_date].copy()
        logging.info(f"  Total rows: {len(df)}, Active rows: {len(active_df)}")

        # Filter active contracts with matching keywords in description
        flagged_df = active_df[
            active_df["description"].fillna("").str.contains(pattern, na=False)
        ]

        if not flagged_df.empty:
            relevant_columns = [
                "award_id",
                "total_obligation",
                "description",
                "awarding_agency_name",
                "period_of_performance_current_end_date",
            ]
            flagged_df = flagged_df[relevant_columns]
            logging.info(f"  Flagged rows: {len(flagged_df)}")
        else:
            logging.info("  No flagged rows found")

        # Save filtered and flagged files
        filtered_path = os.path.join(filtered_dir, f"filtered_{zip_file[:-4]}.csv")
        active_df.to_csv(filtered_path, index=False)

        flagged_path = os.path.join(flagged_dir, f"flagged_{zip_file[:-4]}.csv")
        flagged_df.to_csv(flagged_path, index=False)

        return filtered_path, flagged_path

    except Exception as e:
        logging.error(f"Error processing {zip_file}: {str(e)}")
        return None, None
    finally:
        # Clean up extracted folder to save space
        if os.path.exists(extract_dir):
            for f in os.listdir(extract_dir):
                os.remove(os.path.join(extract_dir, f))
            os.rmdir(extract_dir)


def combine_csv_files(file_paths, output_file, file_type):
    """Combine multiple CSV files into a single master file"""
    if not file_paths:
        logging.warning(f"No {file_type} files to combine")
        return

    valid_paths = [p for p in file_paths if p and os.path.exists(p)]
    if not valid_paths:
        logging.warning(f"No valid {file_type} files found")
        return

    logging.info(f"Joining {len(valid_paths)} {file_type} files...")
    try:
        master_df = pd.concat(
            [pd.read_csv(f, low_memory=False) for f in valid_paths], ignore_index=True
        )
        master_df.to_csv(output_file, index=False)
        logging.info(
            f"{file_type.capitalize()} dataset: {len(master_df)} rows, saved to {output_file}"
        )
    except Exception as e:
        logging.error(f"Error combining {file_type} files: {str(e)}")


def main(
    zip_dir="contract_data",
    filtered_dir="filtered_contracts",
    flagged_dir="flagged_contracts",
    output_prefix="",
):
    """Main function to process all zip files and create master datasets"""
    # Create output directories
    os.makedirs(filtered_dir, exist_ok=True)
    os.makedirs(flagged_dir, exist_ok=True)

    # Setup
    pattern = setup_keywords()
    today_date = datetime.now().strftime("%Y-%m-%d")

    # Lists to hold filtered file paths
    filtered_files = []
    flagged_files = []

    # Process each zip file
    zip_files = [f for f in os.listdir(zip_dir) if f.endswith(".zip")]
    if not zip_files:
        logging.warning(f"No zip files found in {zip_dir}")
        return

    logging.info(f"Found {len(zip_files)} zip files to process")

    for zip_file in zip_files:
        zip_path = os.path.join(zip_dir, zip_file)
        filtered_path, flagged_path = process_zip_file(
            zip_path, filtered_dir, flagged_dir, pattern, today_date
        )

        if filtered_path:
            filtered_files.append(filtered_path)
        if flagged_path:
            flagged_files.append(flagged_path)

    # Create master files
    if output_prefix:
        output_prefix += "_"

    combine_csv_files(
        filtered_files, f"{output_prefix}active_contracts_master.csv", "filtered"
    )
    combine_csv_files(
        flagged_files, f"{output_prefix}flagged_contracts_master.csv", "flagged"
    )

    logging.info("Processing complete!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Transform and filter contract data from USA Spending API"
    )
    parser.add_argument(
        "--zip-dir",
        default="contract_data",
        help="Directory containing zip files (default: contract_data)",
    )
    parser.add_argument(
        "--filtered-dir",
        default="filtered_contracts",
        help="Directory for filtered output files (default: filtered_contracts)",
    )
    parser.add_argument(
        "--flagged-dir",
        default="flagged_contracts",
        help="Directory for flagged output files (default: flagged_contracts)",
    )
    parser.add_argument(
        "--prefix", default="", help="Prefix for output master files (default: none)"
    )

    args = parser.parse_args()

    main(args.zip_dir, args.filtered_dir, args.flagged_dir, args.prefix)
