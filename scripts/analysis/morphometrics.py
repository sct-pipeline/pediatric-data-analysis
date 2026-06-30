import sys, os
import argparse
import glob
import numpy as np
import nibabel as nib
from scipy.interpolate import interp1d
import pandas as pd
import spinalcordtoolbox.utils as sct
from spinalcordtoolbox.scripts import sct_process_segmentation

"""
This script computes spinal cord morphometrics (e.g., CSA) from T2-weighted data.

The script :
1. Computes morphometrics using `sct_process_segmentation` per slice.
2. Gets the z-slices corresponding to each disc label.
3. Using the PMJ distances from the `sct_process_segmentation` output, it adds the PMJ distances for each disc label. 
4. Interpolates PMJ distances for each Vertebral Level, and computes morphometrics at each interpolated PMJ distance 
   (at 0.1 mm intervals between each Vertebral Level) using `sct_process_segmentation`

Outputs :
- {subject}_per_slice.csv : CSV files containing morphometrics per slice
- {subject}_PMJ_dist.csv : CSV files with Slice indexes and PMJ distances for each disc label
- {subject}_PMJ_dist_interp.csv : CSV files with the interpolated PMJ distances
- {subject}_temp_pmj_{level}.csv: Temporary CSV files for each interpolated PMJ distance
- {subject}_interpolated_morphometrics.csv : A combined CSV containing CSA values for each interpolated distance. This final CSV also
   contains age and sex information, taken from the `participants.tsv` file.

Usage : 
    The script can be run with `sct_run_batch` using the wrapper script `wrapper_rootlets.sh` as follows:
        
        sct_run_batch -config config/config_morphometrics.yaml -script wrappers/wrapper_morphometrics.sh

Author: Samuelle St-Onge

"""

def run_sct_process_segmentation_per_slice(pmj, t2w_seg_file, output_per_slice_csv):

    """
    This function computes sct_process_segmentation to get the PMJ distances of each slice

    Args:
        pmj: Path to the PMJ label file
        t2w_seg_file: Path to the T2w SC segmentation file
        output_per_slice_csv: the output CSV file containing morphometrics per slice

    Output:
        {subject}_per_slice.csv : CSV files containing morphometrics per slice

    """

    sct_process_segmentation.main([
        '-i', t2w_seg_file,
        '-pmj', pmj,
        '-perslice', '1',
        '-o', output_per_slice_csv,
        '-append', '1'
    ])

def get_disc_label_PMJ_dist(subject, per_slice_csv, output_csv_dir, label_file, output_PMJ_dist_csv):
    """
    Get the PMJ distances of each disc label

    This function:
    1. Generates a CSV file containing the slice indexes corresponding to each disc label ({subject}_PMJ_dist.csv)
    2. Using a previously generated CSV file from sct_process_segmentation per slice, gets the PMJ distances of the slice indexes of each disc label
       and adds it to the {subject}_PMJ_dist.csv.
    
    Args:
        subject: participant ID 
        per_slice_csv: CSV file containing morphometrics per slice 
        output_csv_dir: path to output csv files
        label_file: file containing disc labels
        output_PMJ_dist_csv : the output CSV file containing the list of disc labels with their corresponding slice indexes and PMJ distances

    Output:
        {subject}_PMJ_dist.csv : CSV file containing list of disc labels with their corresponding slice indexes and PMJ distances

    This function was inspired by : https://github.com/sct-pipeline/pmj-based-csa/blob/main/get_disc_slice.py 
    """

    # Load label image
    labels = nib.load(label_file)
    data = labels.get_fdata()

    print("unique labels:", np.unique(data))

    # Find axis corresponding to the S-I axis
    axcodes = nib.aff2axcodes(labels.affine)
    si_axis = next(i for i, code in enumerate(axcodes) if code in ("S", "I"))

    # Extract the slice corresponding to each label 
    rows = []

    for level in np.unique(data):
        if level == 0:
            continue

        coords = np.where(data == level)
        si_coords = coords[si_axis]

        rows.append({
            "Subject": subject,
            "Level": int(level),
            "Slices": int(si_coords)
        })

    log = pd.DataFrame(rows)
    log = log.sort_values("Level").reset_index(drop=True)

    # Merge PMJ distances with slices 
    per_slice_df = pd.read_csv(per_slice_csv)

    slice_col = "Slice (I->S)"
    pmj_col = "DistancePMJ"

    log = log.merge(
        per_slice_df[[slice_col, pmj_col]],
        left_on="Slices",
        right_on=slice_col,
        how="left"
    )

    # Save csv 
    log.to_csv(output_PMJ_dist_csv, index=False)


def compute_interpolated_morphometrics(
    subject,
    output_csv_path,
    PMJ_distances_csv,
    pmj,
    t2w_seg_file,
    participants_info,
    interp_PMJ_dist_csv,
    final_csv_filename,
    max_level
):
    """
    This function computes interpolated morphometrics up to max_level, and appends the results to the existing final CSV.

    Args:
        subject: participant ID
        output_csv_path: folder containing CSV files
        PMJ_distances_csv: CSV with PMJ distances per level
        pmj: PMJ label file path
        t2w_seg_file: T2w SC segmentation file path
        participants_info: participants.tsv path
        interp_PMJ_dist_csv: intermediate interpolated PMJ CSV
        final_csv_filename: output CSV file for morphometrics
        max_level: maximum vertebral level to compute 
    """

    # Read existing final CSV if it exists
    if os.path.exists(final_csv_filename):
        final_results_df = pd.read_csv(final_csv_filename)
        computed_levels = final_results_df['VertLevel'].unique()
    else:
        final_results_df = pd.DataFrame()
        computed_levels = []

    # Read PMJ distances and generate levels
    pmj_df = pd.read_csv(PMJ_distances_csv)
    if 'DistancePMJ' not in pmj_df.columns:
        raise ValueError(f"Missing 'DistancePMJ' column in {PMJ_distances_csv}")

    levels = pmj_df['Level'].values
    pmj_distances = pmj_df['DistancePMJ'].values
    interp_func = interp1d(levels, pmj_distances, kind='linear', fill_value='extrapolate')

    # Generate all levels up to max_level
    all_levels = np.arange(int(levels.min()), max_level + 0.1, 0.1)
    all_levels = np.round(all_levels, 1)

    # Only keep levels not already computed
    levels_to_compute = [lvl for lvl in all_levels if lvl not in computed_levels]
    if not levels_to_compute:
        print(f"All levels up to {max_level} already computed for {subject}. Nothing to do.")
        return

    # Compute interpolated PMJ distances for missing levels
    interp_distances = interp_func(levels_to_compute)

    # Read participant info
    df_participants_info = pd.read_csv(participants_info, sep='\t').rename(columns={'participant_id': 'subject'})
    
    # List to store new results
    new_results = []

    for level, distance_pmj in zip(levels_to_compute, interp_distances):
        temp_csv_filename = os.path.join(output_csv_path, f"{subject}_temp_pmj_{level}.csv")

        # Skip if temp file already exists (safety)
        if os.path.exists(temp_csv_filename):
            print(f"Temporary file exists: {temp_csv_filename}, skipping level {level}")
            continue

        # Run sct_process_segmentation
        sct_process_segmentation.main([
            '-i', t2w_seg_file,
            '-pmj', pmj,
            '-pmj-distance', str(distance_pmj),
            '-pmj-extent', '3',
            '-perlevel', '1',
            '-o', temp_csv_filename,
        ])

        # Read temp results
        temp_df = pd.read_csv(temp_csv_filename)
        temp_df['VertLevel'] = level
        temp_df['DistancePMJ'] = distance_pmj
        temp_df['subject'] = subject

        # Rename columns
        temp_df = temp_df.rename(columns={
            'MEAN(area)': 'CSA',
            'MEAN(diameter_AP)': 'AP_diameter',
            'MEAN(diameter_RL)': 'RL_diameter',
            'MEAN(eccentricity)': 'eccentricity',
            'MEAN(solidity)': 'solidity'
        })

        # Keep only relevant columns
        temp_df = temp_df[['subject', 'VertLevel', 'DistancePMJ', 'CSA', 'AP_diameter', 'RL_diameter', 'eccentricity', 'solidity']]

        new_results.append(temp_df)

        print(f"Processed VertLevel {level} (PMJ distance: {distance_pmj})")

    # Concatenate new results to existing CSV
    if new_results:
        new_results_df = pd.concat(new_results, ignore_index=True)
        new_results_df = new_results_df.merge(df_participants_info[['subject', 'age', 'sex']], on='subject', how='left')

        if final_results_df.empty:
            final_results_df = new_results_df
        else:
            final_results_df = pd.concat([final_results_df, new_results_df], ignore_index=True)
            final_results_df = final_results_df.sort_values('VertLevel').reset_index(drop=True)

        # Save updated CSV
        final_results_df.to_csv(final_csv_filename, index=False)
        print(f"Updated morphometrics saved to: {final_csv_filename}")
    else:
        print("No new levels were computed.")


def main(subject, data_path, path_output, subject_dir, file_t2):

    # Define paths
    t2w_seg_file = os.path.join(subject_dir, f"{file_t2}_label-SC_mask.nii.gz")
    t2w_disc_labels = os.path.join(subject_dir, f"{file_t2}_labels-disc_step1_levels.nii.gz")
    t2w_pmj_label = os.path.join(subject_dir, f"{file_t2}_label-PMJ_dlabel.nii.gz")
    participants_info = os.path.join(data_path, 'participants.tsv')

    # Define output CSV files
    output_csv_dir = os.path.join("results/tables/morphometrics")
    os.makedirs(output_csv_dir, exist_ok=True) # Create a folder named "morphometrics" inside the output results folder
    output_per_slice_csv = os.path.join(output_csv_dir, f"{subject}_per_slice.csv")
    output_PMJ_dist_csv = os.path.join(output_csv_dir, f"{subject}_PMJ_dist.csv")
    interp_PMJ_dist_csv = os.path.join(output_csv_dir, f"{subject}_PMJ_dist_interp.csv")
    final_csv = os.path.join(output_csv_dir, f"{subject}_interpolated_morphometrics.csv")

    # Define max vert level
    max_level = 20.0

    # Step 1 : Run sct_process_segmentation per slice to get the PMJ distances of each slice
    run_sct_process_segmentation_per_slice(
        pmj=t2w_pmj_label,
        t2w_seg_file=t2w_seg_file,
        output_per_slice_csv=output_per_slice_csv
        )
    
    # Step 2 : Get the disc label slices and add the PMJ distances of each disc label
    get_disc_label_PMJ_dist(
        subject, 
        output_per_slice_csv,
        output_csv_dir, 
        t2w_disc_labels,
        output_PMJ_dist_csv=output_PMJ_dist_csv)
    
    # Step 3 : Interpolate the PMJ distances and run sct_process_segmentation for all interpolated PMJ distances
    print(f"Computing interpolated morphometrics up to level {max_level} for subject {subject}")
    compute_interpolated_morphometrics(
        subject=subject,
        output_csv_path=output_csv_dir,
        PMJ_distances_csv=output_PMJ_dist_csv,
        pmj=t2w_pmj_label,
        t2w_seg_file=t2w_seg_file,
        participants_info=participants_info,
        interp_PMJ_dist_csv=interp_PMJ_dist_csv,
        final_csv_filename=final_csv,
        max_level=max_level
    )

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run morphometric extraction for one subject")
    parser.add_argument("--subject", required=True, help="Subject ID (e.g., sub-001)")
    parser.add_argument("--data-path", required=True, help="Path to raw data")
    parser.add_argument("--path-output", required=True, help="Path to output results")
    parser.add_argument("--subject-dir", required=True, help="Path to subject folder (e.g., sub-001)")
    parser.add_argument("--file-t2", required=True, help="T2-weighted image prefix (e.g., sub-01_T2w)")

    args = parser.parse_args()

    main(args.subject, args.data_path, args.path_output, args.subject_dir, args.file_t2)
