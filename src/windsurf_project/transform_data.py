import os
import pandas as pd
from datetime import datetime
import re
import logging
import argparse
import zipfile
import shutil

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
        "observ",
        "inform",
        "mail",
        "facility",
        "institute",
        "non-binary",
        "environmental justice",
        "sustainability",
        "resilience",
        "energy",
        "conservation",
        "empowerment",
        "inclusive",
        "justice",
        "social justice",
        "racial justice",
        "gender justice",
        "female",
        "indigenous",
        "LGBT",
        "literacy",
        "education",
        "health",
        "poverty",
        "humanitarian",
        "foreign aid",
        "international development",
        "organizational culture",
        "leadership development",
        "retreat",
        "study tour",
        "mentorship",
        "Integrated Pest Management",
        "civil society",
        "media programs",
        "democracy",
        "accountability",
        "male circumcision",
        "membership",
    ]

    # Create a regex pattern to match whole words or phrases
    pattern = re.compile(
        r"\b" + "|".join([re.escape(kw) for kw in keywords]) + r"\b", re.IGNORECASE
    )
    return pattern


def extract_zip_file(zip_path, extract_dir):
    """Extract a zip file to the specified directory"""
    try:
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(extract_dir)
        return True
    except Exception as e:
        logging.error(f"Error extracting {zip_path}: {str(e)}")
        return False


def find_all_csv_files(directory):
    """Recursively find all CSV files in a directory and its subdirectories"""
    csv_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".csv"):
                csv_files.append(os.path.join(root, file))
    return csv_files


def process_csv_file(
    csv_path, output_dir, pattern, today_date, sub_award_type, dept_acronym
):
    """Process a single CSV file and return path to flagged file"""
    csv_file = os.path.basename(csv_path)
    logging.info(f"Processing {csv_file}...")

    try:
        # Load and filter
        df = pd.read_csv(csv_path, low_memory=False)

        # Define columns to keep based on award type
        if sub_award_type == "procurement":
            columns_to_keep = [
                "award_id_piid",
                "prime_award_base_transaction_description",
                "action_type_code",
                "total_dollars_obligated",
                "current_total_value_of_award",
                "period_of_performance_current_end_date",
                "recipient_name",
                "awarding_agency_name",
            ]
            id_column = "award_id_piid"
            desc_column = "prime_award_base_transaction_description"
        else:  # grant
            columns_to_keep = [
                "award_id_fain",
                "prime_award_base_transaction_description",
                "total_obligated_amount",
                "period_of_performance_current_end_date",
                "recipient_name",
                "awarding_agency_name",
            ]
            id_column = "prime_award_fain"
            desc_column = "prime_award_base_transaction_description"

        # Check if date column exists, use alternative if needed
        date_column = "period_of_performance_current_end_date"
        if date_column not in df.columns:
            date_column = "period_of_performance_end_date"
            if date_column not in df.columns:
                logging.warning(f"No performance end date column found in {csv_file}")
                return None

        # Convert date column to datetime
        df[date_column] = pd.to_datetime(df[date_column], errors="coerce")

        # Filter active contracts/grants (those that expire after today)
        active_df = df[df[date_column] > today_date].copy()

        if active_df.empty:
            logging.info("  No active rows found")
            return None

        # Filter to only include columns that exist in the dataframe
        existing_columns = [col for col in columns_to_keep if col in active_df.columns]
        if len(existing_columns) < len(columns_to_keep):
            missing = set(columns_to_keep) - set(existing_columns)
            logging.warning(f"Missing columns in CSV: {missing}")

        # Only keep the columns we're interested in if they exist
        if existing_columns:
            active_df = active_df[existing_columns]

        logging.info(f"  Total rows: {len(df)}, Active rows: {len(active_df)}")

        # Ensure description column exists
        if desc_column not in active_df.columns:
            # Try alternative column names
            alt_desc_columns = [
                "description",
                "award_description",
                "prime_award_project_description",
            ]
            for alt_col in alt_desc_columns:
                if alt_col in active_df.columns:
                    desc_column = alt_col
                    break
            else:
                logging.warning(f"No description column found in {csv_file}")
                return None

        # Filter active contracts/grants with matching keywords in description
        flagged_df = active_df[
            active_df[desc_column].fillna("").str.contains(pattern, na=False)
        ]

        if flagged_df.empty:
            logging.info("  No flagged rows found")
            return None

        # Save flagged file with department acronym and award type
        flagged_path = os.path.join(
            output_dir, f"{dept_acronym}_{sub_award_type}_{csv_file}_flagged.csv"
        )
        flagged_df.to_csv(flagged_path, index=False)
        logging.info(f"  Saved {len(flagged_df)} flagged rows to {flagged_path}")

        return flagged_path

    except Exception as e:
        logging.error(f"Error processing {csv_file}: {str(e)}")
        return None


def combine_csv_files(file_paths, output_file, file_type):
    """Combine multiple CSV files into a single master file"""
    if not file_paths:
        logging.warning(f"No {file_type} files to combine")
        return False

    valid_paths = [p for p in file_paths if p and os.path.exists(p)]
    if not valid_paths:
        logging.warning(f"No valid {file_type} files found")
        return False

    logging.info(f"Joining {len(valid_paths)} {file_type} files...")
    try:
        master_df = pd.concat(
            [pd.read_csv(f, low_memory=False) for f in valid_paths], ignore_index=True
        )

        if "procurement" in output_file.split("_"):
            logging.info("Combining procurement files...")
            master_df = (
                master_df.groupby("award_id_piid")
                .agg(
                    {
                        "current_total_value_of_award": "max",
                        "prime_award_base_transaction_description": "first",
                        "action_type_code": "last",
                        "recipient_name": "first",
                        "awarding_agency_name": "first",
                        "period_of_performance_current_end_date": "max",
                    }
                )
                .reset_index()
            )
        elif "grant" in output_file.split("_"):
            logging.info("Combining grant files...")
            master_df = (
                master_df.groupby("award_id_fain")
                .agg(
                    {
                        "total_obligated_amount": "max",
                        "prime_award_base_transaction_description": "first",
                        "recipient_name": "first",
                        "awarding_agency_name": "first",
                        "period_of_performance_current_end_date": "max",
                    }
                )
                .reset_index()
            )

        logging.info(f"Deduped rows: {len(master_df)} rows")

        master_df.to_csv(output_file, index=False)
        logging.info(f"{file_type.capitalize()} dataset: saved to {output_file}")
        return True
    except Exception as e:
        logging.error(f"Error combining {file_type} files: {str(e)}")
        return False


def process_zip_files(zip_files, dept_name, dept_acronym, sub_award_type, output_dir):
    """Process all zip files for a department and award type"""
    # Create temporary directory for extraction
    temp_dir = os.path.join(output_dir, "temp_extract")
    os.makedirs(temp_dir, exist_ok=True)

    # Setup
    pattern = setup_keywords()
    today_date = datetime.now().strftime("%Y-%m-%d")

    # List to hold flagged file paths
    flagged_files = []

    try:
        # Process each zip file
        for zip_path in zip_files:
            if not os.path.exists(zip_path):
                logging.warning(f"Zip file not found: {zip_path}")
                continue

            # Extract zip file
            logging.info(f"Extracting {zip_path}...")
            if not extract_zip_file(zip_path, temp_dir):
                continue

            # Find all CSV files in the extraction directory (including subdirectories)
            csv_files = find_all_csv_files(temp_dir)

            if not csv_files:
                logging.warning(f"No CSV files found in {zip_path}")
                continue

            logging.info(f"Found {len(csv_files)} CSV files in {zip_path}")

            for csv_path in csv_files:
                flagged_path = process_csv_file(
                    csv_path,
                    output_dir,
                    pattern,
                    today_date,
                    sub_award_type,
                    dept_acronym,
                )

                if flagged_path:
                    flagged_files.append(flagged_path)

            # Clean up extracted files after processing each zip
            shutil.rmtree(temp_dir)
            os.makedirs(temp_dir, exist_ok=True)

        # Combine all flagged files into a master file
        if flagged_files:
            master_file = os.path.join(
                output_dir, f"{dept_acronym}_{sub_award_type}_flagged_master.csv"
            )
            success = combine_csv_files(flagged_files, master_file, "flagged")

            # Delete individual flagged files after successful combination
            if success:
                logging.info("Cleaning up temporary flagged files...")
                for temp_file in flagged_files:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)

            return master_file
        else:
            logging.info(f"No flagged files found for {dept_name} ({sub_award_type})")
            return None

    finally:
        # Clean up temporary directory
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


def main(
    zip_dir="contract_data",
    output_dir=None,
    dept_name=None,
    dept_acronym=None,
    sub_award_type="procurement",
):
    """Process zip files for a specific department and award type"""
    if not dept_name or not dept_acronym:
        logging.error("Department name and acronym must be provided")
        return None

    # Set output directory
    if not output_dir:
        output_dir = os.path.join("processed_data", dept_acronym)

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    # Find zip files for this department and award type
    dept_name_pattern = dept_name.replace(" ", "_").lower()

    zip_files = []
    for file in os.listdir(zip_dir):
        if file.startswith(f"{dept_name_pattern}_{sub_award_type}_") and file.endswith(
            ".zip"
        ):
            zip_files.append(os.path.join(zip_dir, file))

    if not zip_files:
        logging.warning(f"No zip files found for {dept_name} ({sub_award_type})")
        return None

    logging.info(f"Found {len(zip_files)} zip files for {dept_name} ({sub_award_type})")

    # Process the zip files
    master_file = process_zip_files(
        zip_files, dept_name, dept_acronym, sub_award_type, output_dir
    )

    return master_file


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
        "--output-dir",
        default=None,
        help="Directory for output files (default: processed_data/<dept_acronym>)",
    )
    parser.add_argument(
        "--dept-name",
        required=True,
        help="Department name as used in the API",
    )
    parser.add_argument(
        "--dept-acronym",
        required=True,
        help="Department acronym for file naming",
    )
    parser.add_argument(
        "--sub-award-type",
        default="procurement",
        choices=["procurement", "grant"],
        help="Type of award to process (default: procurement)",
    )

    args = parser.parse_args()

    main(
        args.zip_dir,
        args.output_dir,
        args.dept_name,
        args.dept_acronym,
        args.sub_award_type,
    )
