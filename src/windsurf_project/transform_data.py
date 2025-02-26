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
        "subscription",
        # "support",
        "consulting",
        # "services",
        # "administrative",
        # "initiative",
        "public-facing",
        # "applications",
        "observe",
        "mail",
        "inform",
        "facilitate",
        # "institute",
        "non-binary",
    ]
    # Create a regex pattern to match whole words or phrases
    pattern = re.compile(
        r"\b" + "|".join([re.escape(kw) for kw in keywords]) + r"\b", re.IGNORECASE
    )
    return pattern


def process_csv_file(csv_path, flagged_dir, pattern, today_date, output_prefix):
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
        if not active_df.empty:
            relevant_columns = [
                "award_id_piid",  # Award ID
                "total_dollars_obligated",  # Total amount
                "prime_award_base_transaction_description",  # Description
                "awarding_agency_name",  # Agency
                "period_of_performance_current_end_date",  # End date
            ]
            active_df = active_df[relevant_columns]
            logging.info(f"  Total rows: {len(df)}, Active rows: {len(active_df)}")
        else:
            logging.info("  No active rows found")

        # Filter active contracts with matching keywords in description
        flagged_df = active_df[
            active_df["prime_award_base_transaction_description"]
            .fillna("")
            .str.contains(pattern, na=False)
        ]
        logging.info(f"  Flagged rows: {len(flagged_df)}")

        # Save flagged files
        file_base = os.path.splitext(csv_file)[0]
        flagged_path = os.path.join(
            flagged_dir, f"{output_prefix}flagged_{file_base}.csv"
        )
        flagged_df.to_csv(flagged_path, index=False)

        return flagged_path

    except Exception as e:
        logging.error(f"Error processing {csv_file}: {str(e)}")
        return None


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

        master_df = (
            master_df.groupby("award_id_piid")
            .agg(
                {
                    "total_dollars_obligated": "sum",
                    "prime_award_base_transaction_description": "first",
                    "awarding_agency_name": "first",
                    "period_of_performance_current_end_date": "max",
                }
            )
            .reset_index()
        )

        logging.info(
            f"Deduped rows: {len(master_df)} rows, Total $: {master_df['total_dollars_obligated'].sum():,.2f}"
        )

        master_df.to_csv(output_file, index=False)
        logging.info(f"{file_type.capitalize()} dataset: saved to {output_file}")
        return True
    except Exception as e:
        logging.error(f"Error combining {file_type} files: {str(e)}")
        return False


def main(
    csv_dir="contract_data",
    flagged_dir="flagged_contracts",
    output_prefix="",
):
    """Main function to process all CSV files and create master datasets"""
    # Create output directories
    os.makedirs(flagged_dir, exist_ok=True)

    # Setup
    pattern = setup_keywords()
    today_date = datetime.now().strftime("%Y-%m-%d")

    # Lists to hold filtered file paths
    flagged_files = []

    # Process each CSV file
    csv_files = [f for f in os.listdir(csv_dir) if f.endswith(".csv")]
    if not csv_files:
        logging.warning(f"No CSV files found in {csv_dir}")
        return

    logging.info(f"Found {len(csv_files)} CSV files to process")

    # Create master files
    if output_prefix:
        output_prefix += "_"

    for csv_file in csv_files:
        csv_path = os.path.join(csv_dir, csv_file)
        flagged_path = process_csv_file(
            csv_path, flagged_dir, pattern, today_date, output_prefix
        )

        if flagged_path:
            flagged_files.append(flagged_path)

    # Save the combined master file in the same directory as the input CSVs
    master_file_path = os.path.join(
        csv_dir, f"{output_prefix}flagged_contracts_master.csv"
    )
    success = combine_csv_files(flagged_files, master_file_path, "flagged")

    # Delete temporary files after successful combination
    if success and flagged_files:
        logging.info("Cleaning up temporary files...")
        for temp_file in flagged_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    logging.debug(f"Deleted temporary file: {temp_file}")
            except Exception as e:
                logging.warning(
                    f"Failed to delete temporary file {temp_file}: {str(e)}"
                )

        # Try to remove the flagged directory if it's empty
        try:
            if os.path.exists(flagged_dir) and not os.listdir(flagged_dir):
                os.rmdir(flagged_dir)
                logging.info(f"Removed empty directory: {flagged_dir}")
        except Exception as e:
            logging.warning(f"Failed to remove directory {flagged_dir}: {str(e)}")

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
        "--flagged-dir",
        default="flagged_contracts",
        help="Directory for flagged output files (default: flagged_contracts)",
    )
    parser.add_argument(
        "--prefix", default="", help="Prefix for output master files (default: none)"
    )

    args = parser.parse_args()

    main(args.csv_dir, args.flagged_dir, args.prefix)
