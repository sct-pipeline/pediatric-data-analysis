import sys, os
import argparse
import glob
import numpy as np
from scipy.interpolate import interp1d
import pandas as pd
import spinalcordtoolbox.utils as sct
from spinalcordtoolbox.scripts import sct_process_segmentation
from spinalcordtoolbox.image import Image

"""
This script computes the gray matter (GM) and white matter (WM) distribution along the spinal cord in the native T2*-weighted space, using WM and GM segmentations on the T2*w data.

It requires as inputs (in the native T2*w space):
    - T2*-weighted image (in the native space)
    - The spinal cord segmentation 
    - The gray matter segmentation
    - The white matter segmentation 
    - Single-voxel point labels for the start and end of each spinal level (registered from the spinal levels in the T2w space)

These inputs can be obtained by running `scripts/preprocessing/T2starw_data_preprocessing.sh` 

This script will output the CSA of GM and WM, at each spinal level along the spinal cord. To do this, it will:
    - Get the slices corresponding to the start and end (inferior and superior limits) of each spinal level from the single-voxel point labels
    - Compute the slices between these start and end slices for each spinal level to get the slice range corresponding to each spinal level in the T2*w space
    - For each spinal level (for each slice range), run `sct_process_segmentation` to compute the CSA of GM, WM and SC (using the `-z` flag to define the slice range)

For each subject, an output CSV file will be saved in `results/tables/WMGM_distribution/` within folders `WM`, `GM` and `SC`. 

Usage : 
    The script can be run with `sct_run_batch` using the wrapper script `wrapper_GM_WM_distribution.sh` as follows:
        
        sct_run_batch -config config/config_preprocessing_T2starw.yaml -script wrappers/wrapper_GM_WM_distribution.sh

Author: Samuelle St-Onge
"""

def compute_GM_WM_distribution(subject, output_dir, spinal_levels_list, spinal_levels_sup_path, spinal_levels_inf_path, sc_seg_path, gm_seg_path, wm_seg_path):
    """
    Compute the GM and WM distribution along the spinal cord for a given subject.

    Parameters
    ----------
    subject : str
        Subject identifier.
    data_path : str
        Path to the data directory.
    file_t2star : str
        Filename of the T2*-weighted image.
    spinal_levels_start_path : str
        Path to the single-voxel point labels for the start of each spinal level.
    spinal_levels_end_path : str
        Path to the single-voxel point labels for the end of each spinal level.
    sc_seg_path : str
        Path to the spinal cord segmentation.
    gm_seg_path : str
        Path to the gray matter segmentation.
    wm_seg_path : str
        Path to the white matter segmentation.
    spinal_levels_list : list
        List of spinal levels to consider.
    """

    # Dictionary to store segmentation paths
    seg_paths = {
        'SC': sc_seg_path,
        'GM': gm_seg_path,
        'WM': wm_seg_path,
    }

    # Load spinal levels start and end labels
    spinal_levels_sup_img = Image(spinal_levels_sup_path)
    spinal_levels_inf_img = Image(spinal_levels_inf_path)


    # Loop through each spinal level
    for level in spinal_levels_list:

        print(f"----- Slices for spinal level {level} -----")

        ### Superior limit

        # Get the superior z slice where the label equals this level
        z_sup = np.where(spinal_levels_sup_img.data == level)[2]

        # Check if z_sup is empty
        if z_sup.size == 0:
            z_sup = spinal_levels_sup_img.dim[2] - 1
            print(f"Missing superior limit for spinal level {level}. Set z_sup to last slice: {z_sup}")
        else:
            z_sup = int(z_sup[0])
            print(f"z_sup : {z_sup}")

        ### Inferior limit

        # Get the inferior z slice where the label equals this level
        z_inf = np.where(spinal_levels_inf_img.data == level)[2]
        
        # Check if z_inf is empty
        if z_inf.size == 0:
            z_inf = 0
            print(f"Missing inferior limit for spinal level {level}. Set z_inf to first slice: {z_inf}")
        else:
            z_inf = int(z_inf[0])
            print(f"z_inf : {z_inf}")

        ### Define slice range string for sct_process_segmentation

        slice_range = f"{z_inf}:{z_sup}"
        
        print(f'slice range : {slice_range}')

        ### Compute CSA for SC, GM, and WM using sct_process_segmentation

        for label in ['SC', 'GM', 'WM']:
            print(f"---- Computing {label} CSA for {subject} ----")

            # Get the T2*w segmentation file path according to the label (SC, GM, WM)
            seg_file = seg_paths[label]

            # Define output CSV file path
            temp_csv = os.path.join(output_dir, label, f'{subject}_{label}_{level}_CSA.csv')

            # Call sct_process_segmentation
            sct_process_segmentation.main([
                '-i', seg_file,
                '-z', slice_range,
                '-o', temp_csv,
            ])

            # Add a column with the spinal level to the output CSV
            df = pd.read_csv(temp_csv)
            df['Spinal_Level'] = level
            df.to_csv(temp_csv, index=False)

    # Commpute sct_process_segmentation for all spinal levels combined

    print(f"----- Slices for all spinal levels combined -----")
    z_sup = spinal_levels_sup_img.dim[2] - 1 # last slice
    z_inf = 0 # first slice
    slice_range = f"{z_inf}:{z_sup}"
    print(f'image slice range : {slice_range}')
    
    for label in ['SC', 'GM', 'WM']:
        
        print(f"---- Computing {label} CSA for {subject} ----")

        # Get the T2*w segmentation file path according to the label (SC, GM, WM)
        seg_file = seg_paths[label]

        # Define output CSV file path
        temp_csv = os.path.join(output_dir, label, f'{subject}_{label}_all_levels_CSA.csv')

        # Call sct_process_segmentation
        sct_process_segmentation.main([
            '-i', seg_file,
            '-z', slice_range,
            '-o', temp_csv,
        ])

        # Add a column with the spinal level to the output CSV
        df = pd.read_csv(temp_csv)
        df['Spinal_Level'] = 'all_levels'
        df.to_csv(temp_csv, index=False)

    # At the end, concatenate all CSV files for each label into a single CSV file for each subject
    for label in ['SC', 'GM', 'WM']:
        print(f"---- Concatenating {label} CSA CSV files for {subject} ----")

        # Get all temporary CSV files for the subject and label
        temp_csv_files = glob.glob(os.path.join(output_dir, label, f'{subject}_{label}_*_CSA.csv'))

        # Concatenate all CSV files into a single DataFrame
        df_list = [pd.read_csv(f) for f in temp_csv_files]
        df_concat = pd.concat(df_list, ignore_index=True)

        # Define final output CSV file path
        final_csv = os.path.join(output_dir, label, f'{subject}_{label}_CSA.csv')

        # Save the concatenated DataFrame to the final CSV file
        df_concat.to_csv(final_csv, index=False)

        print(f"Saved concatenated CSV for {label} at {final_csv}")

        # Remove the temporary CSV files
        for f in temp_csv_files:
            os.remove(f)
    
def main(subject, data_path, path_output, subject_dir, file_t2star):

    # Load spinal levels start and end labels
    spinal_levels_inf_path = os.path.join(data_path, 'derivatives', 'labels', subject, 'anat', f"{file_t2star}_label-rootlets_spinal_levels_inf_dlabel.nii.gz")
    spinal_levels_sup_path = os.path.join(data_path, 'derivatives', 'labels', subject, 'anat', f"{file_t2star}_label-rootlets_spinal_levels_sup_dlabel.nii.gz")

    # Define the list of spinal levels from the coordinates (by getting the list of values from the single-voxel labels in the superior labels)
    spinal_levels_list = [3,4,5,6,7]

    # Define segmentation paths
    sc_seg_path = os.path.join(data_path, 'derivatives/labels', subject, 'anat', f"{file_t2star}_label-SC_mask.nii.gz")
    gm_seg_path = os.path.join(data_path, 'derivatives/labels', subject, 'anat', f"{file_t2star}_label-GM_mask.nii.gz")
    wm_seg_path = os.path.join(data_path, 'derivatives/labels', subject, 'anat', f"{file_t2star}_label-WM_mask.nii.gz")
    
    # Define SC, GM, WM masks from the PAM50 atlas registered in the T2*w space
    sc_atlas_path = os.path.join(data_path, 'derivatives/PAM50_registration', subject, 'anat/t2star/template', f"PAM50_cord.nii.gz")   
    gm_atlas_path = os.path.join(data_path, 'derivatives/PAM50_registration', subject, 'anat/t2star/template', f"PAM50_gm.nii.gz")
    wm_atlas_path = os.path.join(data_path, 'derivatives/PAM50_registration', subject, 'anat/t2star/template', f"PAM50_wm.nii.gz")  

    # # Create output directories to store the CSV files for WM, GM and SC CSA from the segmentations on the T2*w data
    # output_dir_t2star_seg = os.path.join("results/tables/GM_WM_distribution")
    # labels = ['WM', 'GM', 'SC']
    # os.makedirs(output_dir_t2star_seg, exist_ok=True)
    # for label in labels:
    #     os.makedirs(os.path.join(output_dir_t2star_seg, label), exist_ok=True)    

    # Create output directories to store the CSV files for WM, GM and SC CSA from the PAM50 atlas registered in the T2*w space
    output_dir_PAM50_atlas = os.path.join("results/tables/GM_WM_distribution_PAM50_atlas")
    labels = ['WM', 'GM', 'SC']
    os.makedirs(output_dir_PAM50_atlas, exist_ok=True)
    for label in labels:
        os.makedirs(os.path.join(output_dir_PAM50_atlas, label), exist_ok=True)    

    # Compute GM, WM and SC CSA using the segmentations in the T2*w space
    # compute_GM_WM_distribution(subject, output_dir_t2star_seg, spinal_levels_list, spinal_levels_sup_path, spinal_levels_inf_path, sc_seg_path, gm_seg_path, wm_seg_path)

    # Compute GM, WM and SC CSA using the PAM50 atlas registered in the T2*w space
    compute_GM_WM_distribution(subject, output_dir_PAM50_atlas, spinal_levels_list, spinal_levels_sup_path, spinal_levels_inf_path, sc_atlas_path, gm_atlas_path, wm_atlas_path)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run morphometric extraction for one subject")
    parser.add_argument("--subject", required=True, help="Subject ID (e.g., sub-001)")
    parser.add_argument("--data-path", required=True, help="Path to raw data")
    parser.add_argument("--path-output", required=True, help="Path to output results")
    parser.add_argument("--subject-dir", required=True, help="Path to subject folder (e.g., sub-001)")
    parser.add_argument("--file-t2star", required=True, help="T2star-weighted image prefix (e.g., sub-01_T2starw)")

    args = parser.parse_args()

    main(args.subject, args.data_path, args.path_output, args.subject_dir, args.file_t2star)