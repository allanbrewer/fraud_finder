import zipfile
import os
import pandas as pd
from datetime import datetime
import re

# Define keywords for filtering (case-insensitive)
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

# Today’s date for filtering active contracts
TODAY = datetime.now().strftime("%Y-%m-%d")

# Directory with zips
zip_dir = "contract_data"
filtered_dir = "filtered_contracts"
os.makedirs(filtered_dir, exist_ok=True)

# List to hold filtered file paths
filtered_files = []
flagged_files = []

for zip_file in os.listdir(zip_dir):
    if zip_file.endswith(".zip"):
        zip_path = os.path.join(zip_dir, zip_file)

        # Unzip
        extract_dir = os.path.join(zip_dir, f"extracted_{zip_file[:-4]}")
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(extract_dir)
            csv_file = [f for f in os.listdir(extract_dir) if f.endswith(".csv")][0]
            csv_path = os.path.join(extract_dir, csv_file)

        # Load and filter
        print(f"Processing {zip_file}...")
        df = pd.read_csv(csv_path, low_memory=False)

        # Convert date column to datetime
        df["period_of_performance_current_end_date"] = pd.to_datetime(
            df["period_of_performance_current_end_date"], errors="coerce"
        )

        # Filter active contracts
        active_df = df[df["period_of_performance_current_end_date"] > TODAY].copy()
        print(f"  Total rows: {len(df)}, Active rows: {len(active_df)}")

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

        # Save filtered and flagged files
        filtered_path = os.path.join(filtered_dir, f"filtered_{zip_file[:-4]}.csv")
        active_df.to_csv(filtered_path, index=False)
        filtered_files.append(filtered_path)

        flagged_path = os.path.join(filtered_dir, f"flagged_{zip_file[:-4]}.csv")
        flagged_df.to_csv(flagged_path, index=False)
        flagged_files.append(flagged_path)

        # Clean up extracted folder to save space
        for f in os.listdir(extract_dir):
            os.remove(os.path.join(extract_dir, f))
        os.rmdir(extract_dir)

# Join filtered files
print("\nJoining filtered files...")
master_df = pd.concat(
    [pd.read_csv(f, low_memory=False) for f in filtered_files], ignore_index=True
)
master_df.to_csv("active_contracts_master.csv", index=False)
print(f"Master dataset: {len(master_df)} rows, saved to active_contracts_master.csv")

# Join flagged files
print("\nJoining flagged files...")
flagged_df = pd.concat(
    [pd.read_csv(f, low_memory=False) for f in flagged_files], ignore_index=True
)
flagged_df.to_csv("flagged_contracts_master.csv", index=False)
print(f"Flagged dataset: {len(flagged_df)} rows, saved to flagged_contracts_master.csv")
