import os
import argparse
from pathlib import Path
import pandas as pd
import yaml

"""
This script computes the average location of the spinal cord tip (conus medullaris), by processing the
`interpolated_morphometrics.csv` files inside the `results/tables/morphometrics` folder.

It computes both the average distance from PMJ to the conus medullaris, as well as the average position relative
to the vertebral levels. It outputs a csv file with the average by age. 
""" 

# Define the folder containing the `interpolated_morphometrics.csv` files
morphometrics_folder = Path("results/tables/morphometrics/")

# Process files ending with "interpolated_morphometrics"
file_suffix = "_interpolated_morphometrics.csv"     
age_column = "age"           
PMJ_distance_column = "DistancePMJ"
vertlevel_column = "VertLevel"

# Get list of t2w subjects to include (generated from `results/plots/morphometrics.ipynb`)
include_subjects_df = pd.read_csv("results/tables/morphometrics/include_t2w_subjects_with_sc_tip.csv")
include_subjects_list = include_subjects_df["participant_id"].values

include_subjects = set(
    include_subjects_df["participant_id"]
    .str.strip()
    .str.lower()
)

available_subjects = {
    csv_file.stem.replace(file_suffix.replace(".csv", ""), "").strip().lower()
    for csv_file in morphometrics_folder.glob(f"*{file_suffix}")
}

missing = include_subjects - available_subjects
print(missing)

# Go through each "interpolated_morphometrics" csv file in the folder, and append to a dictionnary
data = []

for csv_file in morphometrics_folder.glob(f"*{file_suffix}"):

    # Extract subject ID (e.g. "sub-101")
    subject = csv_file.stem.replace(file_suffix.replace(".csv", ""), "")

    if subject in include_subjects_list:

        df = pd.read_csv(csv_file)

        # Last row
        last_row = df.iloc[-1]

        data.append({
            "Age": last_row[age_column],
            "DistancePMJ": last_row[PMJ_distance_column],
            "VertLevel": last_row[vertlevel_column]
        })

# Compute averages per age

results = pd.DataFrame(data)

if results.empty:
    print("No files found")
else:

    average_by_age = (
        results
        .groupby("Age", as_index=False)
        .agg(
            mean_distance_from_PMJ=("DistancePMJ", "mean"),
            std_distance_from_PMJ=("DistancePMJ", "std"),
            mean_VertLevel=("VertLevel", "mean"),
            std_VertLevel=("VertLevel", "std"),
            N_participants=("Age", "count")
        )
        .sort_values("Age")
    )

    print(average_by_age)

    # Save the averages to a csv 
    output_dir = Path("results/tables/SC_tip")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = os.path.join(output_dir, "average_distance_PMJ_by_age.csv")
    average_by_age.to_csv(output_file, index=False)