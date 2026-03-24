"""
This script generates a figure showing the distributions of the distances from PMJ for spinal and vertebral levels.
It also computes the mean and standard deviation for each spinal and vertebral level.

This script was modified from : https://github.com/ivadomed/model-spinal-rootlets/blob/main/utilities/hc-leipzig-7t-mp2rage/analysis_MP2RAGE_T2w/get_distributions_and_sizes.py
Author : Katerina Krejci

Usage: 
    python get_distributions_and_sizes_vertebral_spinal_levels.py -i <input_file> -o <output_folder> -p <participants_file> -sex <M/F> -normalised <y/n>

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
    df_pivot = df_filtered.pivot_table(index=["participant_id", "age"], columns="spinal_level", values="mean_distance_height_pmj", aggfunc="mean")
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


def check_normality(df_pivot):
    """
    Function to check normality of the distributions for each spinal and vertebral level using Shapiro-Wilk test.
    :param df_pivot: dataframe with distances from PMJ for spinal and vertebral levels
    :return: dictionary with results of normality test for each level
    """
    for col in df_pivot.columns[1:]:
        data = df_pivot[col].dropna()
        stat, p_value = shapiro(data)
        if p_value > 0.05:
            print(f"Normal distribution of {col}")
        else:
            print(f"Not normal distribution of {col}")


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

def compute_rmse(df_rootlets_pivot, df_vertebrae_pivot, shifted):
    """
    Function to compute the RMSE between the rootlets and vertebrae midpoints for each spinal and vertebral level.
    :param df_rootlets_pivot: dataframe with distances from PMJ for spinal levels
    :param df_vertebrae_pivot: dataframe with distances from PMJ for vertebral levels
    return rmse
    """
    shifted_label = "shifted" if shifted else "not-shifted"
    rmse_shifted = []
    rmse_not_shifted = []

    # Remove first column (subject) from the pivot tables
    rootlets = df_rootlets_pivot.iloc[:, 1:]
    vertebrae = df_vertebrae_pivot.iloc[:, 1:]

    # Select the columns for (non)shifted variant of comparison
    if shifted:
        rootlets = rootlets.iloc[:, 1:]  # starts from C3 spinal level
    else:
        rootlets = rootlets.iloc[:, :-1]  # starts from C2 spinal level

    # Compute RMSE for each spinal and vertebral level
    for i, col in enumerate(vertebrae.columns):
        rmse = np.sqrt(np.mean((vertebrae[col] - rootlets.iloc[:, i]) ** 2))
        print(f"RMSE between {col} and {rootlets.columns[i]}: {rmse:.4f}")
        if shifted:
            rmse_shifted.append((vertebrae[col] - rootlets.iloc[:, i])**2)
        else:
            rmse_not_shifted.append((vertebrae[col] - rootlets.iloc[:, i])**2)

    # Compute overall RMSE
    if shifted:
        rmse_shifted = np.concatenate(rmse_shifted)
        rmse_overall_shifted = np.sqrt(np.sum(rmse_shifted)/len(rmse_shifted))
    else:
        rmse_not_shifted = np.concatenate(rmse_not_shifted)
        rmse_overall_not_shifted = np.sqrt(np.sum(rmse_not_shifted)/len(rmse_not_shifted))

    print(f"Overall RMSE for {shifted_label}: {rmse_overall_shifted:.4f}" if shifted else f"Overall RMSE for {shifted_label}: {rmse_overall_not_shifted:.4f}")


def plot_distributions_per_age(df_rootlets, df_vertebrae, output_path, normalised, levels_to_plot=None):
    """
    Plot distributions of distances from PMJ per age in subplots.
    Each subplot corresponds to one age and shows spinal and vertebral levels.

    :param df_rootlets: pivot table of spinal levels with 'age' column
    :param df_vertebrae: pivot table of vertebral levels with 'age' column
    :param output_path: path to save the figure
    :param normalised: 'y' or 'n', whether distances are normalised
    :param levels_to_plot: list of integers corresponding to levels (e.g., [2,3,4,5,6,7,8])
    """
    import math
    import matplotlib.pyplot as plt
    import numpy as np
    from scipy.stats import norm

    ages = sorted(df_rootlets['age'].dropna().unique())
    n_cols = 4
    n_rows = math.ceil(len(ages) / n_cols)

    fig, axes = plt.subplots(n_rows, n_cols, figsize=(16, 3 * n_rows))
    axes = axes.flatten()
    x_limit = 200
    y_limit = 0.3
    x_vals = np.linspace(0, x_limit, 2000)
    cmap = plt.get_cmap("tab10")

    # Build column names to plot
    if levels_to_plot is not None:
        rootlets_cols = [f"Spinal level C{lvl}" for lvl in levels_to_plot]
        vertebrae_cols = [f"Vertebral level C{lvl}" if lvl != 8 else "Vertebral level T1" for lvl in levels_to_plot]
    else:
        rootlets_cols = df_rootlets.columns[1:]
        vertebrae_cols = df_vertebrae.columns[1:]

    for i, age in enumerate(ages):
        ax = axes[i]
        df_rootlets_age = df_rootlets[df_rootlets['age'] == age]
        df_vertebrae_age = df_vertebrae[df_vertebrae['age'] == age]

        if df_rootlets_age.empty and df_vertebrae_age.empty:
            ax.set_visible(False)
            continue

        # Plot spinal levels
        for j, col in enumerate(rootlets_cols):
            if col not in df_rootlets_age.columns:
                continue
            data = df_rootlets_age[col].dropna()
            if len(data) == 0:
                continue
            mu, sigma = norm.fit(data)
            y = norm.pdf(x_vals, mu, sigma)
            ax.plot(x_vals, y, linestyle="-", color=cmap(j % 10), linewidth=1, label=col)

        # Plot vertebral levels
        for j, col in enumerate(vertebrae_cols):
            if col not in df_vertebrae_age.columns:
                continue
            data = df_vertebrae_age[col].dropna()
            if len(data) == 0:
                continue
            mu, sigma = norm.fit(data)
            y = norm.pdf(x_vals, mu, sigma)
            ax.plot(x_vals, y, linestyle=":", color=cmap(j % 10), linewidth=1, label=col)

        ax.set_title(f"Age {age}", fontsize=12, fontweight="bold")
        ax.set_xlim(0, x_limit)
        ax.set_ylim(0, y_limit)
        ax.set_xlabel("Distance from PMJ (mm)", fontsize=10)
        ax.set_ylabel("Probability", fontsize=10)
        ax.set_xticks(np.arange(0, 201, 25))
        ax.grid(alpha=0.2)

    # Hide unused subplots
    for k in range(len(ages), len(axes)):
        axes[k].set_visible(False)

    # Create one legend for the whole figure
    handles = []
    for idx, lvl in enumerate(levels_to_plot):
        color = cmap(idx % 10)
        # spinal
        handles.append(plt.Line2D([0], [0], color=color, linestyle='-', label=f'Spinal level C{lvl}'))
        # vertebral
        vert_label = f"Vertebral level C{lvl}" if lvl != 8 else "Vertebral level T1"
        handles.append(plt.Line2D([0], [0], color=color, linestyle='--', label=vert_label))

    fig.legend(handles=handles, ncol=len(levels_to_plot), fontsize=9,
               loc="upper center", bbox_to_anchor=(0.5, 1.0))

    plt.tight_layout(rect=[0, 0, 1, 0.95])  # leave space for the legend
    if output_path is not None:
        plt.savefig(os.path.join(output_path, "distributions_per_age_selected_levels.png"), dpi=300)
    plt.show()

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

    # Get the age of the subjects
    df['age'] = df['fname'].apply(get_age)

    # Extract rootlets or vertebrae level type from the fname and add it as a column
    df['level_type'] = df['fname'].apply(
        lambda x: 'rootlets' if 'label-rootlets' in x else 'vertebrae'
    )

    # Extract subjectID from the fname and add it as a column
    df['participant_id'] = df['fname'].apply(lambda x: x.split('_')[0])

    # Extract spinal level (cervical 1-8) and vertebral level (1-8)
    df = df[((df['level_type'] == 'rootlets') & (df['spinal_level'].isin([1, 2, 3, 4, 5, 6, 7, 8]))) |
        ((df['level_type'] == 'vertebrae') & (df['spinal_level'].isin([1, 2, 3, 4, 5, 6, 7, 8])))]

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

    # Check normality of the distributions
    check_normality(df_rootlets_pivot)
    check_normality(df_vertebrae_pivot)

    # Plot the distributions of the distances from PMJ for spinal and vertebral levels
    levels_to_plot = [2, 3, 4, 5, 6, 7, 8]
    plot_distributions_per_age(df_rootlets_pivot, df_vertebrae_pivot, output_path, normalised, levels_to_plot)

    # Compute mean and standard deviation for each spinal and vertebral level
    compute_mean_std_for_each_level(df_mean_std_height_rootlets, df_mean_std_height_vertebrae, output_path)

    # Compute RMSE between rootlets and vertebrae midpoints for each spinal and vertebral level
    compute_rmse(df_rootlets_pivot, df_vertebrae_pivot, shifted=False)
    compute_rmse(df_rootlets_pivot, df_vertebrae_pivot, shifted=True)


if __name__ == "__main__":
    main()