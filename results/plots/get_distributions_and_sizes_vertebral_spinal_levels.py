"""
This script generates a figure showing the distributions of the distances from PMJ for spinal and vertebral levels.
It also computes the mean and standard deviation for each spinal and vertebral level.

This script was modified from : https://github.com/ivadomed/model-spinal-rootlets/blob/main/utilities/hc-leipzig-7t-mp2rage/analysis_MP2RAGE_T2w/get_distributions_and_sizes.py
Author : Katerina Krejci

Usage: 
    python get_distributions_and_sizes_vertebral_spinal_levels.py -i <data_folder> -o <output_folder> -p <participants_file> -sex <M/F> -normalised <y/n>

Modified by : Samuelle St-Onge
"""
import os
import sys
import pandas as pd
from scipy.stats import shapiro
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from scipy.stats import norm
import glob
import argparse
import math

def get_parser():
    """
    Function to parse command line arguments.
    :return: command line arguments
    """
    parser = argparse.ArgumentParser(
        description='Generate a figures showing statistics distributions of the distances from PMJ for spinal and '
                    'vertebral levels', prog=os.path.basename(__file__).strip('.py'))
    
    parser.add_argument('-i', required=True, type=str, help='Path to the data_processed folder with CSV '
                        'files with distances from PMJ for spinal and vertebral levels (created by script '
                                                            'generate_figure_rootlets_and_vertebral_spinal_levels.py).')
    parser.add_argument('-o', required=True, type=str, help='Path to the output folder, where figures will '
                                                            'be saved.')    
    parser.add_argument('-participants', required=True, type=str, help='Path to the participants.tsv file.')

    parser.add_argument('-sex', required=False, type=str, help="Choose sex for the analysis. Options: 'M' or 'F'.")
    
    parser.add_argument('-normalised', required=True, type=str, choices=["y", "n"], help='Choice of '
                        'normalisation by height of subject (yes/no).')

    return parser


def process_data(df, level_type, normalised):
    """
    Function to process the data and create a pivot tables for the given level type (rootlets or vertebrae) - for
    analysis of midpoint positions and analysis of levels height.
    :param df: input dataframe with distances from PMJ for spinal and vertebral levels
    :param level_type: type of level to process ('rootlets' or 'vertebrae')
    :return: pivot tables with renamed columns according to anatomical nomenclature
    """
    # Filter dataframe by level type
    df_filtered = df[df["level_type"] == level_type].copy()

    # calculate distance from PMJ to the midpoint of the segment
    if normalised == "y":
        df_filtered["mean_distance_height_pmj"] = (((df_filtered[["distance_from_pmj_start", "distance_from_pmj_end"]].mean(axis=1))/(df_filtered["height_sub"])*df_filtered["height_sub"].median()))
    else:
        df_filtered["mean_distance_height_pmj"] = df_filtered[["distance_from_pmj_start", "distance_from_pmj_end"]].mean(axis=1)

    # make table with positions of midpoint from PMJ for each level
    df_pivot = df_filtered.pivot_table(index=["participant_id", "age", "height"], columns="spinal_level", values="mean_distance_height_pmj", aggfunc="mean")
    df_pivot.reset_index(inplace=True)

    # make table with mean and std of height for each segment
    print(df_filtered.columns.tolist())
    df_mean_std_height = df_filtered.pivot_table(index="participant_id", columns="spinal_level", values="height", aggfunc="mean")
    df_mean_std_height.reset_index(inplace=True)

    # rename columns to be consistent with anatomical nomenclature (spinal levels: C2, C3, C4, C5, C6, C7, C8, T1;
    # vertebral levels: C1, C2, C3, C4, C5, C6, C7, T1)
    for col in df_pivot.columns[2:]:  # skip participant_id and age
        try:
            col_int = int(col)  # try converting to int
        except ValueError:
            # If it fails, skip (it might already be renamed or not numeric)
            continue

        if level_type == "vertebrae":
            if col_int < 8:
                new_name = f"Vertebral level C{col_int}"
            else:
                new_name = f"Vertebral level T{col_int - 7}"
        else:
            if col_int < 9:
                new_name = f"Spinal level C{col_int}"
            else:
                new_name = f"Spinal level T{col_int - 8}"

        df_pivot.rename(columns={col: new_name}, inplace=True)
        df_mean_std_height.rename(columns={col: new_name}, inplace=True)

    return df_pivot, df_mean_std_height

def compute_mean_std_for_each_level(df_rootlets_pivot, df_vertebrae_pivot, output_path):
    """
    Function to compute the mean and standard deviation for each spinal and vertebral level and save the results to
    CSV files.
    :param df_rootlets_pivot: dataframe with distances from PMJ for spinal levels
    :param df_vertebrae_pivot: dataframe with distances from PMJ for vertebral levels
    :param output_path: path to the output folder where the results will be saved
    :return: mean and standard deviation for each spinal and vertebral level
    """
    # remove first column (subject) from the pivot tables
    df_rootlets_pivot = df_rootlets_pivot.iloc[:, 1:]
    df_vertebrae_pivot = df_vertebrae_pivot.iloc[:, 1:]

    # compute mean and std for each spinal and vertebral level
    mean_rootlets = df_rootlets_pivot.mean(axis=0).round(2)
    std_rootlets = df_rootlets_pivot.std(axis=0).round(2)
    mean_vertebrae = df_vertebrae_pivot.mean(axis=0).round(2)
    std_vertebrae = df_vertebrae_pivot.std(axis=0).round(2)

    # make tables for spinal levels and vertebral levels
    rootlets_table = pd.DataFrame(
        {"Spinal level": mean_rootlets.index, "Mean height": mean_rootlets.values, "Std height": std_rootlets.values})
    vertebrae_table = pd.DataFrame({"Vertebral level": mean_vertebrae.index, "Mean height": mean_vertebrae.values,
                                    "Std height": std_vertebrae.values})

    # save tables to csv
    rootlets_table.to_csv(os.path.join(output_path, "rootlets_size_mean_std.csv"))
    vertebrae_table.to_csv(os.path.join(output_path, "vertebrae_size_mean_std.csv"))

    return mean_rootlets, std_rootlets, mean_vertebrae, std_vertebrae


def compute_rmse(df_rootlets_pivot, df_vertebrae_pivot, output_dir):
    """
    Function to compute the RMSE between the rootlets and vertebrae midpoints for each spinal and vertebral level.
    :param df_rootlets_pivot: dataframe with distances from PMJ for spinal levels
    :param df_vertebrae_pivot: dataframe with distances from PMJ for vertebral levels
    return rmse
    """

    rmse_results = []

    vertebral_levels = [
        "Vertebral level C2",
        "Vertebral level C3",
        "Vertebral level C4",
        "Vertebral level C5",
        "Vertebral level C6",
        "Vertebral level C7",
        "Vertebral level T1"
    ]

    spinal_levels = [
        "Spinal level C3",
        "Spinal level C4",
        "Spinal level C5",
        "Spinal level C6",
        "Spinal level C7",
        "Spinal level C8",
        "Spinal level T1"
    ]

    # Loop through each age
    for age in sorted(df_rootlets_pivot["age"].dropna().unique()):

        # Filter by age
        rootlets = df_rootlets_pivot[df_rootlets_pivot["age"] == age].copy()
        vertebrae = df_vertebrae_pivot[df_vertebrae_pivot["age"] == age].copy()

        # Keep only the levels contained in the lists above
        rootlets = rootlets[spinal_levels].apply(pd.to_numeric, errors="coerce")
        vertebrae = vertebrae[vertebral_levels].apply(pd.to_numeric, errors="coerce")

        # Loop through each vertebral-spinal pair
        for vertebral_col, spinal_col in zip(vertebral_levels, spinal_levels):

            # Difference between corresponding midpoints
            differences = (vertebrae[vertebral_col] - rootlets[spinal_col])

            # RMSE for this pair at this age
            rmse = np.sqrt(np.nanmean(differences ** 2))

            # Save the RMSE in a dictionnary
            rmse_results.append({
                "age": age,
                "vertebral_level": vertebral_col,
                "spinal_level": spinal_col,
                "RMSE": rmse
            })

            print(
                f"Age {age}: "
                f"{vertebral_col} vs {spinal_col}: "
                f"RMSE = {rmse:.4f}"
            )

    # Convert all results to a dataframe
    rmse_df = pd.DataFrame(rmse_results)

    # Round at 2 decimals
    rmse_df["RMSE"] = rmse_df["RMSE"].round(2)

    # Save to csv
    csv_file = f"{output_dir}/rmse_by_age_and_level.csv"
    rmse_df.to_csv(csv_file, index=False)

    print("\nRMSE by age and vertebral-spinal pair:")
    print(rmse_df)

    return rmse_df

def compute_distances(df_rootlets_pivot, df_vertebrae_pivot, output_dir):
    """
    Compute the distance (difference) between corresponding spinal and vertebral level midpoints for each participant.
    """

    distance_results = []

    vertebral_levels = [
        "Vertebral level C2",
        "Vertebral level C3",
        "Vertebral level C4",
        "Vertebral level C5",
        "Vertebral level C6",
        "Vertebral level C7",
        "Vertebral level T1"
    ]

    spinal_levels = [
        "Spinal level C3",
        "Spinal level C4",
        "Spinal level C5",
        "Spinal level C6",
        "Spinal level C7",
        "Spinal level C8",
        "Spinal level T1"
    ]

    # Merge the two dataframes using participant_id
    merged = pd.merge(
        df_rootlets_pivot,
        df_vertebrae_pivot,
        on=["participant_id", "age", "height"],
        how="inner",
        suffixes=("_rootlets", "_vertebrae")
    )

    # Loop through each participant
    for _, row in merged.iterrows():

        # Loop through corresponding vertebral/spinal pairs
        for vertebral_col, spinal_col in zip(vertebral_levels, spinal_levels):

            vertebral_distance = pd.to_numeric(row[vertebral_col], errors="coerce")
            spinal_distance = pd.to_numeric(row[spinal_col], errors="coerce")

            # Difference between the two midpoints
            distance = vertebral_distance - spinal_distance

            distance_results.append({
                "participant_id": row["participant_id"],
                "age": row["age"],
                "height": row["height"],
                "vertebral_level": vertebral_col,
                "spinal_level": spinal_col,
                "midpoint_distance": distance
            })

    # Convert results to dataframe
    distance_df = pd.DataFrame(distance_results)
    distance_df["midpoint_distance"] = distance_df["midpoint_distance"].round(2)

    # Save to CSV
    csv_file = f"{output_dir}/distance_by_participant_and_level.csv"
    distance_df.to_csv(csv_file, index=False)

    print("\nDistance between vertebral and spinal levels:")
    print(distance_df)

    return distance_df


def compute_level_proportions(df, level_type, output_dir):

    results = []

    if level_type == 'rootlets':
        df = df[df["level_type"] == 'rootlets']
        df = df[df["spinal_level"] <= 8].copy() # Keep only cervical levels

    if level_type == 'vertebrae':
        df = df[df["level_type"] == 'vertebrae']
        df = df[df["spinal_level"] <= 7].copy() # Keep only cervical levels

    for participant in df["participant_id"].unique():

        df_sub = df[df["participant_id"] == participant].copy()

        # total cervical length
        total_length = df_sub["height"].sum()

        # proportion of each level
        df_sub["proportion"] = df_sub["height"] / total_length

        for _, row in df_sub.iterrows():
            results.append({
                "participant_id": participant,
                "age": row["age"],
                "level": row["spinal_level"],
                "height": row["height"],
                "total_cervical_length": total_length,
                "proportion": row["proportion"]
            })

    # Save to CSV
    results = pd.DataFrame(results)
    csv_file = f"{output_dir}/spinal_level_proportions_{level_type}.csv"
    results.to_csv(csv_file, index=False)

    # Get the average proportion per age, per level
    table = (
        results.pivot_table(
            index="level",
            columns="age",
            values="proportion",
            aggfunc="mean"
        )
    )

    print(f'Table for {level_type} : {table}')

    # Save to csv : 
    results = pd.DataFrame(table)
    csv_file = f"{output_dir}/mean_spinal_level_proportions_{level_type}.csv"
    results.to_csv(csv_file, index=False)

    return results


def main():
    parser = get_parser()
    args = parser.parse_args()

    # Get data from the command line arguments
    output_path = os.path.abspath(args.o)
    normalised = args.normalised

    # Load the data
    # Parse the command line arguments
    parser = get_parser()
    args = parser.parse_args()

    dir_path = os.path.abspath(args.i)

    if not os.path.isdir(dir_path):
        print(f'ERROR: {args.i} does not exist.')
        sys.exit(1)

    df_participants = pd.read_csv(args.participants, sep='\t')
    participants_age = df_participants[['participant_id', 'age']]
    participants_sex = df_participants[['participant_id', 'sex']]
    participants_height = df_participants[['participant_id', 'height']]

    # Get all the CSV files in the directory generated by the 02a_rootlets_to_spinal_levels.py script
    csv_files = glob.glob(os.path.join(dir_path, '**', '*pmj_distance_*[vertebral_disc|rootlets].csv'), recursive=True)

    # if csv_files is empty, exit
    if len(csv_files) == 0:
        print(f'ERROR: No CSV files found in {dir_path}')

    # Initialize an empty list to store the parsed data
    parsed_data = []

    # Loop across CSV files and aggregate the results into pandas dataframe
    for csv_file in csv_files:
        df_file = pd.read_csv(csv_file)
        parsed_data.append(df_file)

    # Combine list of dataframes into one dataframe
    df = pd.concat(parsed_data)
    print(df)

    # Function to get the age of the subjects from the participants.tsv file 
    def get_age(x):
        filename = os.path.basename(x)  # e.g. 'sub-107_acq-top_run-1_T2w...'
        participant_id = filename.split('_')[0]    # split at the first underscore (e.g. 'sub-107')
        participant_id = participant_id.strip() 
        matching = participants_age[participants_age['participant_id'] == participant_id]
        if matching.empty:
            print(f"No matching 'age' value for {participant_id} from filename {filename}")
            return None
        return matching['age'].values[0]
    
    # Function to get the sex of the subjects from the participants.tsv file 
    def get_sex(x):
        filename = os.path.basename(x)  
        participant_id = filename.split('_')[0] 
        participant_id = participant_id.strip()
        matching = participants_sex[participants_sex['participant_id'] == participant_id]
        if matching.empty:
            print(f"No matching 'sex' value for {participant_id} from filename {filename}")
            return None
        return matching['sex'].values[0]

    # Function to get the height of the subjects from the participants.tsv file 
    def get_height(x):
        filename = os.path.basename(x)  
        participant_id = filename.split('_')[0] 
        participant_id = participant_id.strip()
        matching = participants_height[participants_height['participant_id'] == participant_id]
        if matching.empty:
            print(f"No matching 'height' value for {participant_id} from filename {filename}")
            return None
        return matching['height'].values[0]

    # Get the age of the subjects
    df['age'] = df['fname'].apply(get_age)

    # Get the height of the subjects
    df['height'] = df['fname'].apply(get_height)

    # Extract rootlets or vertebrae level type from the fname and add it as a column
    df['level_type'] = df['fname'].apply(lambda x: 'rootlets' if 'label-rootlets' in x else 'vertebrae')

    # Extract subjectID from the fname and add it as a column
    df['participant_id'] = df['fname'].apply(lambda x: x.split('_')[0])

    # Extract spinal level (cervical 3-9) and vertebral level (2-8)
    df = df[((df['level_type'] == 'rootlets') & (df['spinal_level'].isin([3, 4, 5, 6, 7, 8, 9]))) |
        ((df['level_type'] == 'vertebrae') & (df['spinal_level'].isin([2, 3, 4, 5, 6, 7, 8])))]

    if args.sex not in ['M', 'F']:
        sex = "all"
    else:
        sex = f"{args.sex}"
        df['sex'] = df['fname'].apply(get_sex)

        # Filter by selected sex
        df = df[df['sex'] == args.sex]

    # Sort the DataFrame based on the age column
    df = df.sort_values('age').reset_index(drop=True)

    # Process the data and create pivot tables
    df_rootlets_pivot, df_mean_std_height_rootlets = process_data(df, "rootlets", normalised)
    df_vertebrae_pivot, df_mean_std_height_vertebrae = process_data(df, "vertebrae", normalised)

    # Compute mean and standard deviation for each spinal and vertebral level
    compute_mean_std_for_each_level(df_mean_std_height_rootlets, df_mean_std_height_vertebrae, output_path)

    # Compute distances between midpoints (for each participant, for each pair of spinal/vertebral levels)
    compute_distances(df_rootlets_pivot, df_vertebrae_pivot, output_dir='results/tables/rootlets')

    # Compute RMSE between rootlets and vertebrae midpoints for each spinal and vertebral level
    compute_rmse(df_rootlets_pivot, df_vertebrae_pivot, output_dir='results/tables/rootlets')

    # Compute proportions for spinal levels
    compute_level_proportions(df, level_type = 'rootlets', output_dir='results/tables/rootlets/')

    # Compute proportions for vertebral levels
    compute_level_proportions(df, level_type = 'vertebrae', output_dir='results/tables/rootlets/')

if __name__ == "__main__":
    main()