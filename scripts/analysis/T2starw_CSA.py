import sys, os
import argparse
import glob
import numpy as np
from scipy.interpolate import interp1d
import pandas as pd
import spinalcordtoolbox.utils as sct
from spinalcordtoolbox.scripts import sct_process_segmentation, sct_label_vertebrae

"""
This script computes the cross-sectional area of the spinal cord, the gray matter and the white matter masks, from T2*-weighted images.
This script was used in the philadelphia-pediatric dataset, to compare WM and GM distributions across different ages in the spinal cord of 
typically-developing pediatric subjects. 

- One CSV is saved per subject inside their folder.
- All CSVs are then merged into a global CSV file 

Usage : 
    The script can be run with `sct_run_batch` using the wrapper script `wrapper_T2starw.sh` as follows:
        
        sct_run_batch -config config/config_T2starw.yaml -script wrappers/wrapper_T2starw.sh

Author: Samuelle St-Onge
"""

def compute_morphometrics(level_type, output_csv_filename, participants_info, t2starw_seg_file, label_file, levels, perlevel=0, perslice=0):
    """
    This function computes spinal cord morphometrics using `sct_process_segmentation`. 
    The output morphometrics are saved in a CSV file with the age and sex info for each subject, taken from the 1participants.tsv` file. 
    
    Args : 
        level_type: Either 'VertLevel' or 'SpinalLevel'
        output_csv_filename: Name of the output CSV file
        participants_info: Path to the `participants.tsv` file
        t2w_seg_file: Path to the spinal cord segmentation mask
        label_file: The labeled levels (either the labeled segmentation for vertebral levels, or the spinal level labels)
        vertlevels: The levels to compute the metrics across (i.e., 1:20)
        perlevel: Output either one metric per level (perlevel=1) or a single output metric for all levels (perlevel=0)
        perslice: Output either one metric per slice (perslice=1) or a single output metric for all slices (perslice=0)
        pmj: Path to the PMJ label
    """
    # Run sct_process_segmentation
    sct_process_segmentation.main([
        '-i', t2starw_seg_file,
        '-vert', levels,
        '-vertfile', label_file,
        '-perlevel', perlevel,
        '-perslice', perslice,
        '-o', output_csv_filename
    ])

    # Load results in output CSV file 
    df = pd.read_csv(output_csv_filename)

    # Get the subject ID from the filename
    df['subject'] = 'sub-' + df['Filename'].astype(str).str.extract(r'sub-([0-9]+)')[0]

    # Get the age and sex from the `participants.tsv`` file, and add to the morphometrics CSV file 
    df_age = pd.read_csv(participants_info, sep='\t').rename(columns={'participant_id': 'subject'})
    df.columns = df.columns.str.strip()
    df_age.columns = df_age.columns.str.strip()

    df = df.drop(columns=[col for col in ['age', 'sex'] if col in df.columns])
    df_merged = df.merge(df_age[['subject', 'age', 'sex']], on='subject', how='left')

    # Rename columns and save the changes to the CSV file
    df_merged = df_merged.rename(columns={
        'VertLevel': level_type,
        'MEAN(area)': 'CSA',
        'MEAN(diameter_AP)': 'AP_diameter',
        'MEAN(diameter_RL)': 'RL_diameter',
        'MEAN(eccentricity)': 'eccentricity',
        'MEAN(solidity)': 'solidity'
    })

    df_merged.to_csv(output_csv_filename, index=False)

def main(subject, data_path, path_output, subject_dir, file_t2star):

    # Define paths to SC, WM and GM segmentations
    t2w_SC_seg = os.path.join(subject_dir, f"{file_t2star}_label-SC_mask.nii.gz")
    t2w_WM_seg = os.path.join(subject_dir, f"{file_t2star}_label-WM_mask.nii.gz")
    t2w_GM_seg = os.path.join(subject_dir, f"{file_t2star}_label-GM_mask.nii.gz")
    
    # Define path to labeled segmentation
    t2w_labeled_seg = os.path.join(subject_dir, f"{file_t2star}_label-SC_mask_labeled.nii.gz")
    
    # Path to `participants.tsv` file
    participants_info = os.path.join(data_path, 'participants.tsv')

    # Define output folder for CSV files
    output_csv_dir = os.path.join("results/tables/T2starw")
    os.makedirs(output_csv_dir, exist_ok=True) # Create the T2starw folder if it doesn't exist
    output_csv_filename = os.path.join(output_csv_dir, f"{subject}_T2starw_CSA.csv")

    if os.path.exists(output_csv_filename):
        print(f"Final CSV already exists for subject {subject}: {output_csv_filename}. Skipping processing.")
        return
    else:
        print(f"Processing T2starw CSA for subject: {subject}")

    # Compute CSA for the spinal cord mask
    compute_morphometrics(
        level_type = 'VertLevel',
        output_csv_filename=os.path.join(output_csv_dir, f"{subject}_vert_level_morphometrics.csv"),
        participants_info=participants_info,
        t2w_seg_file=t2w_SC_seg,
        label_file=t2w_labeled_seg, # Use the labeled segmentation 
        levels='2:5',
        perlevel='1',
        perslice='0',
    )

    # Compute CSA for the gray matter mask
    compute_morphometrics(
        level_type = 'VertLevel',
        output_csv_filename=os.path.join(output_csv_dir, f"{subject}_vert_level_morphometrics.csv"),
        participants_info=participants_info,
        t2w_seg_file=t2w_GM_seg,
        label_file=t2w_labeled_seg, # Use the labeled segmentation 
        levels='2:5',
        perlevel='1',
        perslice='0',
    )

    # Compute CSA for the white matter mask
    compute_morphometrics(
        level_type = 'VertLevel',
        output_csv_filename=os.path.join(output_csv_dir, f"{subject}_vert_level_morphometrics.csv"),
        participants_info=participants_info,
        t2w_seg_file=t2w_WM_seg,
        label_file=t2w_labeled_seg, # Use the labeled segmentation 
        levels='2:5',
        perlevel='1',
        perslice='0',
    )