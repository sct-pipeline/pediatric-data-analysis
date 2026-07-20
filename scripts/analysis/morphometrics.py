import sys, os
import argparse
import glob
import numpy as np
import nibabel as nib
from scipy.interpolate import interp1d
import pandas as pd
import spinalcordtoolbox.utils as sct
from spinalcordtoolbox.scripts import sct_process_segmentation
from spinalcordtoolbox.image import Image
from spinalcordtoolbox.centerline.core import get_centerline
from spinalcordtoolbox.types import Centerline
from spinalcordtoolbox.centerline.core import ParamCenterline

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

def get_max_pmj_distance(segmentation, pmj):
    """
    This function returns the maximum distance from the PMJ along the centerline (mm).

    Inspired by : https://github.com/spinalcordtoolbox/spinalcordtoolbox/blob/master/spinalcordtoolbox/csa_pmj.py
    """

    # Get the segmentation and PMJ label images
    im_seg = Image(segmentation).change_orientation("RPI")
    im_pmj = Image(pmj).change_orientation("RPI")

    # Add PMJ label to the segmentation
    im_seg_with_pmj = im_seg.copy()
    im_seg_with_pmj.data += im_pmj.data

    # Centerline parameters
    param_centerline = ParamCenterline()
    param_centerline.algo_fitting = "linear"
    param_centerline.smooth = 50
    param_centerline.minmax = True

    # Compute centerline
    _, arr_ctl_phys, arr_ctl_der_phys, _ = get_centerline(im_seg_with_pmj,param_centerline,verbose=0,space="phys",)
    ctl = Centerline(*arr_ctl_phys, *arr_ctl_der_phys)

    return float(ctl.incremental_length_inverse[::-1][0])

def run_sct_process_segmentation_per_slice(pmj, t2w_seg_file, output_per_slice_csv, centerline):

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
        '-angle-corr-centerline', centerline,
        '-o', output_per_slice_csv,
        '-append', '1'
    ])

def get_disc_label_PMJ_dist(subject, per_slice_csv, t2w_seg_file, t2w_pmj_label, vert_label_file, output_PMJ_dist_csv):
    """
    Get the PMJ distances of each disc label

    This function:
    1. Generates a CSV file containing the slice indexes corresponding to each disc label ({subject}_PMJ_dist.csv)
    2. Using a previously generated CSV file from sct_process_segmentation per slice, gets the PMJ distances of the slice indexes of each disc label
       and adds it to the {subject}_PMJ_dist.csv.
    
    Args:
        subject: participant ID 
        per_slice_csv: CSV file containing morphometrics per slice 
        label_file: file containing disc labels
        output_PMJ_dist_csv : the output CSV file containing the list of disc labels with their corresponding slice indexes and PMJ distances

    Output:
        {subject}_PMJ_dist.csv : CSV file containing list of disc labels with their corresponding slice indexes and PMJ distances

    This function was inspired by : https://github.com/sct-pipeline/pmj-based-csa/blob/main/get_disc_slice.py 
    """

    # Load vertebral labels image
    labels = nib.load(vert_label_file)
    data = labels.get_fdata()

    print("unique labels:", np.unique(data))

    # Find axis corresponding to the S-I axis in the labels file
    axcodes = nib.aff2axcodes(labels.affine)
    si_axis = next(i for i, code in enumerate(axcodes) if code in ("S", "I"))
    si_orientation = axcodes[si_axis] # Orientation of the SI axis
    print(f"SI axis: {si_axis}, orientation: {si_orientation}")

    indices = np.unique(data[data > 0])

    if si_orientation == "I":
        print(f'Orientation is I-S instead of S-I. Reversing the indices and PMJ distance.')
        # Reverse the indices if the SI orientation is inferior to superior 
        indices = indices[::-1]

        # Reverse PMJ distances
        max_distance = log["DistancePMJ"].max()
        log["DistancePMJ"] = max_distance - log["DistancePMJ"]

    # Read per_slice_dr
    per_slice_df = pd.read_csv(per_slice_csv)

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
            "Slice": int(si_coords)
        })

    log = pd.DataFrame(rows)
    log = log.sort_values("Level").reset_index(drop=True)

    # Merge PMJ distances with slices 
    slice_col = "Slice (I->S)"
    pmj_col = "DistancePMJ"

    log = log.merge(
        per_slice_df[[slice_col, pmj_col]],
        left_on="Slice",
        right_on=slice_col,
        how="left"
    )

    # Remove rows with missing PMJ distances
    log = log.dropna(subset=["DistancePMJ"]) 

    # Retrieve the last remaining row, corresponding to the last vertebral level included in the segmentation mask
    last_level = log.iloc[-1]["Level"]
    last_level_slice = log.iloc[-1]["Slice"]

    # Get the slice number corresponding to the next vertebral level
    next_level = last_level + 1
    coords_next_level = np.where(data == next_level)

    # Check if the next level exists in the image
    if coords_next_level[si_axis].size == 0:
        print(f"Level {next_level} not in the image. Stopping at level {last_level}.")
        
        # Save the CSV without adding the SC-tip as the last row
        log.to_csv(output_PMJ_dist_csv, index=False)
        return
    
    else:
        next_level_slice = int(coords_next_level[si_axis][0])
        print(f"Next level slice: {next_level_slice}")

        # Find the slice and PMJ distance corresponding to the tip of the SC mask (the last slice on the segmentation mask)
        SC_tip_slice = (per_slice_df.loc[per_slice_df["MEAN(area)"].notna(), "Slice (I->S)"].min())
        PMJ_SC_tip_dist = get_max_pmj_distance(t2w_seg_file, t2w_pmj_label) # maximum distance from the PMJ along the centerline 
        print(f"Slice corresponding to SC tip: {SC_tip_slice}")

        # Find the location of the SC tip (in percentage) between the last vertebral level and the next one
        ratio = (SC_tip_slice - last_level_slice) / (next_level_slice - last_level_slice)
        SC_tip_vert_level = last_level + ratio
        print("SC_tip_vert_level:", SC_tip_vert_level)

        # Append the row containing the next vert level
        log.loc[len(log)] = {
            "Subject": subject,
            "Level": SC_tip_vert_level,
            "Slice": SC_tip_slice,
            "Slice (I->S)": SC_tip_slice,
            "DistancePMJ": PMJ_SC_tip_dist,
        }

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
    final_csv_filename
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
    """

    # Read existing final CSV if it exists
    if os.path.exists(final_csv_filename):
        final_results_df = pd.read_csv(final_csv_filename)
        computed_levels = final_results_df['VertLevel'].unique()
    else:
        final_results_df = pd.DataFrame()
        computed_levels = []

    # Read PMJ distances in the '_PMJ_dist.csv' files and generate levels
    pmj_df = pd.read_csv(PMJ_distances_csv)
    if 'DistancePMJ' not in pmj_df.columns:
        raise ValueError(f"Missing 'DistancePMJ' column in {PMJ_distances_csv}")
    
    levels = pmj_df['Level'].values
    pmj_distances = pmj_df['DistancePMJ'].values
    interp_func = interp1d(levels, pmj_distances, kind='linear', fill_value='extrapolate')
    
    # Get min and max levels 
    min_level = levels.min()
    max_level = levels.max()

    # Generate levels every 0.1
    all_levels = np.arange(min_level, max_level, 0.1)
    all_levels = np.round(all_levels, 2) 

    # Make sure the last level is included
    if all_levels[-1] != max_level:
        all_levels = np.append(all_levels, max_level)

    # Define vertebral levels to compute
    levels_to_compute = [lvl for lvl in all_levels if lvl not in computed_levels]
    print(f"Vertebral levels to compute for {subject} : {levels_to_compute}")
    
    # Only keep levels not already computed
    if not levels_to_compute:
        print(f"All levels up to {max_level} already computed for {subject}.")
        return

    # Compute interpolated PMJ distances for missing levels
    interp_distances = interp_func(levels_to_compute)

    # Read participant info
    df_participants_info = pd.read_csv(participants_info, sep='\t').rename(columns={'participant_id': 'subject'})
    
    # List to store new results
    new_results = []
    temp_files = []

    # Run sct_process_segmentation for each interpolated vertebral level (1.0, 1.1, 1.2, etc.)
    for level, distance_pmj in zip(levels_to_compute, interp_distances):
        temp_csv_filename = os.path.join(output_csv_path, f"{subject}_temp_pmj_{level}.csv")
        temp_files.append(temp_csv_filename)

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
        new_results_df = new_results_df.merge(df_participants_info[['subject', 'age', 'sex', 'height', 'weight']], on='subject', how='left')

        if final_results_df.empty:
            final_results_df = new_results_df
        else:
            final_results_df = pd.concat([final_results_df, new_results_df], ignore_index=True)
            final_results_df = final_results_df.sort_values('VertLevel').reset_index(drop=True)

        # Save updated CSV
        final_results_df.to_csv(final_csv_filename, index=False)
        print(f"Updated morphometrics saved to: {final_csv_filename}")
        
        # Delete temporary files
        for temp_file in temp_files:
            if os.path.exists(temp_file):
                os.remove(temp_file)

        print(f"Deleted {len(temp_files)} temporary files.")
    
    else:
        print("No new levels were computed.")
        
        
def PMJ_SCtip_normalization(per_slice_csv):

    perslice_df = pd.read_csv(per_slice_csv)

    # Keep slices where CSA > 0 
    SC_slices = perslice_df[perslice_df["MEAN(area)"] > 0]

    # Get the first slice with CSA values (which corresponds to the tip of the SC)
    slice_SC_tip = SC_slices["Slice (I->S)"].min()

    print(f'Slice corresponding to SC tip : {slice_SC_tip}')

    # Get the PMJ distance of the SC tip
    dist_PMJ_SC_tip = perslice_df.loc[perslice_df["Slice (I->S)"] == slice_SC_tip, "DistancePMJ"].values[0]

    # Normalize distances between PMJ and the SC tip
    perslice_df["Normalized_PMJ_SCtip"] = perslice_df["DistancePMJ"] / dist_PMJ_SC_tip

    # Add the "NormalizedDistance" column to the per_slice_csv
    perslice_df.to_csv(per_slice_csv, index=False)
    print(f"Normalized morphometrics results saved to:\n{per_slice_csv}")


def main(subject, data_path, path_output, subject_dir, file_t2):

    # Define paths
    t2w_seg_file = os.path.join(subject_dir, f"{file_t2}_label-SC_mask.nii.gz")
    t2w_disc_labels = os.path.join(subject_dir, f"{file_t2}_labels-disc_step1_levels.nii.gz")
    t2w_pmj_label = os.path.join(subject_dir, f"{file_t2}_label-PMJ_dlabel.nii.gz")
    centerline = os.path.join(subject_dir, f"{file_t2}_centerline.nii.gz")
    participants_info = os.path.join(data_path, 'participants.tsv')

    # Define output CSV files
    output_csv_dir = os.path.join("results/tables/morphometrics")
    os.makedirs(output_csv_dir, exist_ok=True) # Create a folder named "morphometrics" inside the output results folder
    output_per_slice_csv = os.path.join(output_csv_dir, f"{subject}_per_slice.csv")
    output_PMJ_dist_csv = os.path.join(output_csv_dir, f"{subject}_PMJ_dist.csv")
    interp_PMJ_dist_csv = os.path.join(output_csv_dir, f"{subject}_PMJ_dist_interp.csv")
    final_csv = os.path.join(output_csv_dir, f"{subject}_interpolated_morphometrics.csv")

    # Define max vert level based on the maximum value in the t2w_disc_labels file
    labels_img = nib.load(t2w_disc_labels)
    labels_data = labels_img.get_fdata()
    max_level = int(np.max(labels_data))

    # # Step 1 : Run sct_process_segmentation per slice to get the PMJ distances of each slice
    # run_sct_process_segmentation_per_slice(
    #     pmj=t2w_pmj_label,
    #     t2w_seg_file=t2w_seg_file,
    #     output_per_slice_csv=output_per_slice_csv,
    #     centerline=centerline
    #     )
    
    # # Step 2 : Get the disc label slices and add the PMJ distances of each disc label
    # get_disc_label_PMJ_dist(
    #     subject, 
    #     output_per_slice_csv,
    #     t2w_seg_file, 
    #     t2w_pmj_label,
    #     t2w_disc_labels,
    #     output_PMJ_dist_csv=output_PMJ_dist_csv)

    # # Step 3 : Interpolate the PMJ distances and run sct_process_segmentation for all interpolated PMJ distances
    # print(f"Computing interpolated morphometrics up to level {max_level} for subject {subject}")
    # compute_interpolated_morphometrics(
    #     subject=subject,
    #     output_csv_path=output_csv_dir,
    #     PMJ_distances_csv=output_PMJ_dist_csv,
    #     pmj=t2w_pmj_label,
    #     t2w_seg_file=t2w_seg_file,
    #     participants_info=participants_info,
    #     interp_PMJ_dist_csv=interp_PMJ_dist_csv,
    #     final_csv_filename=final_csv
    # )

    # Step 4 : Normalize the distances using spinal cord landmarks (PMJ, cervical and lumbar enlargments, tip of SC)
    print(f"Normalizing SC with PMJ and SC tip for: {subject}")
    PMJ_SCtip_normalization(output_per_slice_csv) # Normalize with PMJ and SC tip only

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run morphometric extraction for one subject")
    parser.add_argument("--subject", required=True, help="Subject ID (e.g., sub-001)")
    parser.add_argument("--data-path", required=True, help="Path to raw data")
    parser.add_argument("--path-output", required=True, help="Path to output results")
    parser.add_argument("--subject-dir", required=True, help="Path to subject folder (e.g., sub-001)")
    parser.add_argument("--file-t2", required=True, help="T2-weighted image prefix (e.g., sub-01_T2w)")

    args = parser.parse_args()

    main(args.subject, args.data_path, args.path_output, args.subject_dir, args.file_t2)
