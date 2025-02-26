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


def process_csv_file(csv_path, filtered_dir, flagged_dir, pattern, today_date):
    """Process a single CSV file and return paths to filtered and flagged files"""
    csv_file = os.path.basename(csv_path)
    logging.info(f"Processing {csv_file}...")

    try:
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
                "award_id_piid",  # Award ID
                "total_dollars_obligated",  # Total amount
                "prime_award_base_transaction_description",  # Description
                "awarding_agency_name",  # Agency
                "period_of_performance_current_end_date",  # End date
            ]
            flagged_df = flagged_df[relevant_columns]
            logging.info(f"  Flagged rows: {len(flagged_df)}")
        else:
            logging.info("  No flagged rows found")

        # Save filtered and flagged files
        file_base = os.path.splitext(csv_file)[0]
        filtered_path = os.path.join(filtered_dir, f"filtered_{file_base}.csv")
        active_df.to_csv(filtered_path, index=False)

        flagged_path = os.path.join(flagged_dir, f"flagged_{file_base}.csv")
        flagged_df.to_csv(flagged_path, index=False)

        return filtered_path, flagged_path

    except Exception as e:
        logging.error(f"Error processing {csv_file}: {str(e)}")
        return None, None


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
    csv_dir="contract_data",
    filtered_dir="filtered_contracts",
    flagged_dir="flagged_contracts",
    output_prefix="",
):
    """Main function to process all CSV files and create master datasets"""
    # Create output directories
    os.makedirs(filtered_dir, exist_ok=True)
    os.makedirs(flagged_dir, exist_ok=True)

    # Setup
    pattern = setup_keywords()
    today_date = datetime.now().strftime("%Y-%m-%d")

    # Lists to hold filtered file paths
    filtered_files = []
    flagged_files = []

    # Process each CSV file
    csv_files = [f for f in os.listdir(csv_dir) if f.endswith(".csv")]
    if not csv_files:
        logging.warning(f"No CSV files found in {csv_dir}")
        return

    logging.info(f"Found {len(csv_files)} CSV files to process")

    for csv_file in csv_files:
        csv_path = os.path.join(csv_dir, csv_file)
        filtered_path, flagged_path = process_csv_file(
            csv_path, filtered_dir, flagged_dir, pattern, today_date
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
        "--csv-dir",
        default="contract_data",
        help="Directory containing CSV files (default: contract_data)",
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

    main(args.csv_dir, args.filtered_dir, args.flagged_dir, args.prefix)
