#!/usr/bin/env python3
import os
import pandas as pd
import re
import argparse
import logging
from datetime import datetime
import glob

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def setup_advanced_keywords():
    """Define more specific keywords for advanced filtering (case-insensitive)"""
    keywords = [
        "DEI",  # Explicit DEI catch-all
        "diversity",  # Core DEI term
        "equity",  # Core DEI term
        "inclusion",  # Core DEI term
        "gender",  # DEI-adjacent (e.g., "gender equity")
        "non-binary",  # DEI niche (rare, but DOGE hates it)
        # "training",  # DEI/waste flag (e.g., "DEI training" or vague $)
        # "consulting",  # Waste flag (overpaid fluff)
        # "support",  # Waste flag (vague "support services")
        # "initiative",  # Waste flag (e.g., "diversity initiative")
        # "administrative",  # Waste flag (clerical bloat)
        # "public-facing",
    ]

    # Create a regex pattern to match whole words or phrases
    pattern = re.compile(
        r"\b" + "|".join([re.escape(kw) for kw in keywords]) + r"\b", re.IGNORECASE
    )
    return pattern


def filter_by_amount_and_keywords(file_path, min_amount, pattern, output_dir):
    """
    Filter a CSV file by minimum amount and keywords

    Args:
        file_path: Path to the CSV file
        min_amount: Minimum dollar amount to include
        pattern: Regex pattern for keyword matching
        output_dir: Directory to save filtered file

    Returns:
        Path to filtered file or None if no matches
    """
    try:
        # Extract filename and department info
        filename = os.path.basename(file_path)
        logging.info(f"Processing {filename}...")

        # Load the CSV file
        df = pd.read_csv(file_path)
        original_count = len(df)

        if original_count == 0:
            logging.warning(f"  Empty file: {filename}")
            return None

        # Identify the amount column based on file type
        amount_columns = [
            "current_total_value_of_award",
            "total_dollars_obligated",
            "total_obligated_amount",
        ]

        amount_col = None
        for col in amount_columns:
            if col in df.columns:
                amount_col = col
                break

        if not amount_col:
            logging.warning(f"  No amount column found in {filename}")
            return None

        # Convert amount column to numeric, handling non-numeric values
        df[amount_col] = pd.to_numeric(df[amount_col], errors="coerce")

        # Filter by minimum amount
        amount_filtered = df[df[amount_col] >= min_amount].copy()
        amount_filtered_count = len(amount_filtered)

        if amount_filtered.empty:
            logging.info(f"  No contracts above ${min_amount:,} found")
            return None

        logging.info(
            f"  Filtered by amount: {original_count} -> {amount_filtered_count}"
        )

        # Identify the description column based on file type
        desc_columns = [
            "prime_award_base_transaction_description",
            "description",
            "award_description",
            "prime_award_project_description",
        ]

        desc_col = None
        for col in desc_columns:
            if col in amount_filtered.columns:
                desc_col = col
                break

        if not desc_col:
            logging.warning(f"  No description column found in {filename}")
            return None

        # Filter by keywords
        keyword_filtered = amount_filtered[
            amount_filtered[desc_col].fillna("").str.contains(pattern, na=False)
        ]

        if keyword_filtered.empty:
            logging.info(f"  No matching keywords found after amount filtering")
            return None

        keyword_filtered_count = len(keyword_filtered)
        logging.info(
            f"  Filtered by keywords: {amount_filtered_count} -> {keyword_filtered_count}"
        )

        # Check for and handle duplicate IDs within this file
        id_columns = ["award_id_piid", "award_id_fain"]
        id_col = None

        # Find the ID column
        for col in id_columns:
            if col in keyword_filtered.columns:
                id_col = col
                break

        if id_col:
            # Count duplicates before deduplication
            duplicate_count = (
                keyword_filtered_count - keyword_filtered[id_col].nunique()
            )

            if duplicate_count > 0:
                logging.info(f"  Found {duplicate_count} duplicate IDs in {filename}")

                # Sort by amount (descending) and keep first occurrence of each ID
                keyword_filtered = keyword_filtered.sort_values(
                    by=amount_col, ascending=False
                )
                keyword_filtered = keyword_filtered.drop_duplicates(
                    subset=[id_col], keep="first"
                )

                logging.info(
                    f"  Removed {duplicate_count} duplicate IDs, keeping highest value contracts"
                )
                keyword_filtered_count = len(keyword_filtered)
            else:
                logging.info(f"  No duplicate IDs found in {filename}")

        # Sort the final results by amount in descending order
        keyword_filtered = keyword_filtered.sort_values(by=amount_col, ascending=False)
        logging.info(f"  Sorted results by {amount_col} in descending order")

        # Save filtered file
        output_filename = f"filtered_{filename}"
        output_path = os.path.join(output_dir, output_filename)
        keyword_filtered.to_csv(output_path, index=False)

        logging.info(f"  Saved {keyword_filtered_count} rows to {output_path}")
        return output_path

    except Exception as e:
        logging.error(f"Error processing {file_path}: {str(e)}")
        return None


def combine_filtered_files(filtered_files, output_dir):
    """
    Combine all filtered files into a single master file

    Args:
        filtered_files: List of filtered file paths
        output_dir: Directory to save combined file

    Returns:
        Path to combined file or None if no files
    """
    if not filtered_files:
        return None

    # Read all filtered files
    dfs = []
    for file_path in filtered_files:
        try:
            df = pd.read_csv(file_path)
            dfs.append(df)
        except Exception as e:
            logging.error(f"Error reading {file_path}: {str(e)}")

    if not dfs:
        return None

    # Combine all dataframes
    combined_df = pd.concat(dfs, ignore_index=True)

    if combined_df.empty:
        return None

    # Check for and handle duplicate IDs
    id_columns = ["award_id_piid", "award_id_fain"]
    id_col = None

    # Find the ID column
    for col in id_columns:
        if col in combined_df.columns:
            id_col = col
            break

    if id_col:
        # Count duplicates before deduplication
        total_rows = len(combined_df)
        duplicate_count = total_rows - combined_df[id_col].nunique()

        if duplicate_count > 0:
            logging.info(f"Found {duplicate_count} duplicate IDs in combined data")

            # For each duplicate ID, keep the row with the highest amount
            amount_columns = [
                "current_total_value_of_award",
                "total_dollars_obligated",
                "total_obligated_amount",
            ]

            amount_col = None
            for col in amount_columns:
                if col in combined_df.columns:
                    amount_col = col
                    break

            if amount_col:
                # Sort by amount (descending) and keep first occurrence of each ID
                combined_df = combined_df.sort_values(by=amount_col, ascending=False)
                combined_df = combined_df.drop_duplicates(subset=[id_col], keep="first")

                logging.info(
                    f"Removed {duplicate_count} duplicate IDs, keeping highest value contracts"
                )
            else:
                # If no amount column, just keep first occurrence
                combined_df = combined_df.drop_duplicates(subset=[id_col], keep="first")
                logging.info(
                    f"Removed {duplicate_count} duplicate IDs (no amount column found)"
                )
        else:
            logging.info("No duplicate IDs found in combined data")
    else:
        logging.warning(
            "No ID column found in combined data, unable to check for duplicates"
        )

    # Ensure the final combined file is sorted by amount in descending order
    amount_columns = [
        "current_total_value_of_award",
        "total_dollars_obligated",
        "total_obligated_amount",
    ]

    amount_col = None
    for col in amount_columns:
        if col in combined_df.columns:
            amount_col = col
            break

    if amount_col:
        combined_df = combined_df.sort_values(by=amount_col, ascending=False)
        logging.info(f"Sorted combined results by {amount_col} in descending order")

    # Save combined file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    combined_path = os.path.join(output_dir, f"all_filtered_contracts_{timestamp}.csv")
    combined_df.to_csv(combined_path, index=False)

    logging.info(
        f"Combined {len(combined_df)} rows from {len(dfs)} files to {combined_path}"
    )
    return combined_path


def process_all_files(input_dir, output_dir, min_amount):
    """
    Process all CSV files in the input directory and its subdirectories

    Args:
        input_dir: Directory containing processed CSV files
        output_dir: Directory to save filtered files
        min_amount: Minimum dollar amount to include

    Returns:
        List of filtered file paths
    """
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    # Setup advanced keywords pattern
    pattern = setup_advanced_keywords()

    # Find all CSV files in input directory and subdirectories
    csv_files = []
    for root, _, files in os.walk(input_dir):
        for file in files:
            if file.endswith("_flagged_master.csv"):
                csv_files.append(os.path.join(root, file))

    if not csv_files:
        logging.warning(f"No CSV files found in {input_dir}")
        return []

    logging.info(f"Found {len(csv_files)} CSV files to process")

    # Process each file
    filtered_files = []
    for file_path in csv_files:
        filtered_path = filter_by_amount_and_keywords(
            file_path, min_amount, pattern, output_dir
        )
        if filtered_path:
            filtered_files.append(filtered_path)

    # Create a summary file
    if filtered_files:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        summary_path = os.path.join(output_dir, f"filtering_summary_{timestamp}.txt")

        with open(summary_path, "w") as f:
            f.write(f"Filtering Summary ({timestamp})\n")
            f.write(f"Minimum Amount: ${min_amount:,}\n")
            f.write(f"Files Processed: {len(csv_files)}\n")
            f.write(f"Files with Matches: {len(filtered_files)}\n\n")

            for file_path in filtered_files:
                file_name = os.path.basename(file_path)
                f.write(f"- {file_name}\n")

        logging.info(f"Summary saved to {summary_path}")

    return filtered_files


def main(
    input_dir="processed_data",
    output_dir="filtered_data",
    min_amount=500000,
    combine=True,
):
    """
    Main function to filter contracts by amount and keywords

    Args:
        input_dir: Directory containing processed CSV files
        output_dir: Directory to save filtered files
        min_amount: Minimum dollar amount to include
        combine: Whether to combine all filtered files into a single file

    Returns:
        List of filtered file paths
    """
    logging.info(f"Starting advanced filtering with minimum amount: ${min_amount:,}")

    # Process all files
    filtered_files = process_all_files(input_dir, output_dir, min_amount)

    if not filtered_files:
        logging.warning("No files passed the filtering criteria")
        return []

    logging.info(f"Created {len(filtered_files)} filtered files")

    # Combine filtered files if requested
    if combine and len(filtered_files) > 1:
        combined_path = combine_filtered_files(filtered_files, output_dir)
        if combined_path:
            logging.info(f"All filtered contracts combined into {combined_path}")

    return filtered_files


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Filter contracts by amount and keywords"
    )
    parser.add_argument(
        "--input-dir",
        default="processed_data",
        help="Directory containing processed CSV files (default: processed_data)",
    )
    parser.add_argument(
        "--output-dir",
        default="filtered_data",
        help="Directory to save filtered files (default: filtered_data)",
    )
    parser.add_argument(
        "--min-amount",
        type=int,
        default=500000,
        help="Minimum dollar amount to include (default: 500,000)",
    )
    parser.add_argument(
        "--no-combine",
        action="store_true",
        help="Do not combine filtered files into a single file",
    )

    args = parser.parse_args()

    main(args.input_dir, args.output_dir, args.min_amount, not args.no_combine)
