import sys
import subprocess
import argparse
import numpy as np
import os
import shutil
import pandas as pd
from spinalcordtoolbox.scripts import sct_label_utils
from spinalcordtoolbox.image import Image

"""
This script is used to extract spinal levels from the segmented rootlets of the spinal cord in pediatric subjects. The script calls functions from
the https://github.com/ivadomed/model-spinal-rootlets repository to process the rootlets segmentation and extract spinal levels.  

The script : 
    - Runs `zeroing_false_positive_rootlets.py` from the model-spinal-rootlets/pediatric_rootlets directory to remove false positive rootlets below the Th1 level.
    - Runs `02a_rootlets_to_spinal_levels.py` from the model-spinal-rootlets/inter-rater_variability directory to extract spinal levels from the rootlets segmentation.
    - Extracts the center of mass of each spinal level and saves it in a nii.gz file.
    - Computes the distance between the center of mass of each spinal level and the PMJ, and saves it to a CSV file. 
    - Computes the distance between the vertebral levels and the PMJ, and saves it to a CSV file. 

Usage : 
    The script can be ran with sct_run_batch using the wrapper script `wrapper_rootlets.sh` as follows:
        
        sct_run_batch -config config/config_rootlets.yaml -script wrappers/wrapper_rootlets.sh
    
Author: Samuelle St-Onge

"""

def get_distance_from_pmj(centerline_points, z_index, px, py, pz):
    """
    Function taken from : model-rootlets-r20250318/inter-rater_variability/02a_rootlets_to_spinal_levels.py 
    Authors : Jan Valosek, Theo Mathieu
    URL: https://github.com/ivadomed/model-spinal-rootlets
    
    Compute distance from projected pontomedullary junction (PMJ) on centerline and cord centerline.
    Inspiration: https://github.com/sct-pipeline/pmj-based-csa/blob/419ece49c81782f23405d89c7b4b15d8e03ed4bd/get_distance_pmj_disc.py#L40-L60
    :param centerline_points: 3xn array: Centerline in continuous coordinate (float) for each slice in RPI orientation.
    :param z_index: z index PMJ on the centerline.
    :param px: x pixel size.
    :param py: y pixel size.
    :param pz: z pixel size.
    :return: nd-array: distance from PMJ and corresponding indexes.
    """
    length = 0
    arr_length = [0]
    for i in range(z_index, 0, -1):
        distance = np.sqrt(((centerline_points[0, i] - centerline_points[0, i - 1]) * px) ** 2 +
                           ((centerline_points[1, i] - centerline_points[1, i - 1]) * py) ** 2 +
                           ((centerline_points[2, i] - centerline_points[2, i - 1]) * pz) ** 2)
        length += distance
        arr_length.append(length)
    arr_length = arr_length[::-1]
    arr_length = np.stack((arr_length, centerline_points[2][:z_index + 1]), axis=0)

    return arr_length

def find_nearest_centerline_index(point, centerline_points):
    distances = np.linalg.norm(centerline_points.T - point, axis=1)
    return np.argmin(distances)

def center_of_mass_to_PMJ(label, label_fname, file_t2, subject_dir, pmj_label, centerline_csv, participants_tsv, csv_out_path):
    """
    Function to compute the distance from the center of mass of each spinal level or vert level to the PMJ.
    
    This function : 
    - Computes the center of mass from the labels using sct_label_utils
    - Projects the labels to the spinal cord centerline using sct_label_utils
    - Computes the distance from the center of mass to the PMJ using the centerline coordinates and the PMJ label.

    """
        # Extract the center of mass of each spinal level and save it in a nii.gz file
    sct_label_utils.main([
        '-i', label_fname,
        '-cubic-to-point',  # To compute center of mass
        '-o', f'{subject_dir}/{file_t2}_label-rootlets_center_of_mass_{label}.nii.gz',
    ]) 

    # Project the center of mass of the spinal levels onto the centerline to obtain the vertebral levels
    sct_label_utils.main([
        '-i', f'{subject_dir}/{file_t2}_centerline.nii.gz',
        '-project-centerline', f'{subject_dir}/{file_t2}_label-rootlets_center_of_mass_{label}.nii.gz',
        '-o', f'{subject_dir}/{file_t2}_label-rootlets_center_of_mass_{label}_projected.nii.gz'
    ])

    # Load center of mass image (labels) and get the coordinates of the center of mass points (x, y, z, label)
    center_of_mass_label_image = Image(f'{subject_dir}/{file_t2}_label-rootlets_center_of_mass_{label}_projected.nii.gz').change_orientation('RPI')
    center_of_mass_coords = center_of_mass_label_image.getNonZeroCoordinates(sorting='value')

    # Load centerline CSV 
    centerline_array = np.genfromtxt(centerline_csv, delimiter=',')

    # Get the PMJ index on the centerline (which corresponds to the max z value)
    pmj_index = centerline_array[2].argmax()

    # Get voxel sizes from the PMJ label image for physical distances (assumed consistent across images)
    pmj_img = Image(pmj_label).change_orientation('RPI')
    px, py, pz = pmj_img.dim[4], pmj_img.dim[5], pmj_img.dim[6]

    # Compute the cumulative distance from the PMJ along the centerline
    centerline_dist = get_distance_from_pmj(centerline_array, pmj_index, px, py, pz)

    # Get the distance from PMJ for the nearest centerline point coresponding to the center of mass point
    results = []
    for x, y, z, label_index in center_of_mass_coords:
        point = np.array([x, y, z])
        nearest_centerline_index = find_nearest_centerline_index(point, centerline_array)
        dist_to_pmj = centerline_dist[0, nearest_centerline_index] # Distance from PMJ to the center of mass point
        results.append({
            'level': int(label_index),
            'fname': f'{subject_dir}/{file_t2}_label-rootlets_center_of_mass_{label}_projected.nii.gz',
            'x': x,
            'y': y,
            'z': z,
            'distance_from_pmj_mm': dist_to_pmj
            })

    # Save results to CSV in the results folder alongside the PMJ distance CSV
    df_com_dist = pd.DataFrame(results)
    df_com_dist.to_csv(csv_out_path, index=False)
    print(f"Center of mass distances saved to {csv_out_path}")

    print(f"Using participants file at: {participants_tsv}")
    assert os.path.isfile(participants_tsv), f"File not found: {participants_tsv}"
    
    return


def main(subject, data_path, subject_dir, file_t2, rootlets_model_dir):

    # Define paths
    rootlets_seg = os.path.join(subject_dir, f"{file_t2}_label-rootlets_dseg.nii.gz")
    disc_labels = os.path.join(subject_dir, f"{file_t2}_labels-disc_step1_levels.nii.gz")
    rootlets_modif = os.path.join(subject_dir, f"{file_t2}_label-rootlets_dseg_modif.nii.gz")
    sc_mask = os.path.join(subject_dir, f"{file_t2}_label-SC_mask.nii.gz")
    pmj_label = os.path.join(subject_dir, f"{file_t2}_label-PMJ_dlabel.nii.gz")
    centerline_csv = os.path.join(subject_dir, f"{file_t2}_label-SC_mask_centerline_extrapolated.csv")
    participants_tsv = os.path.join(data_path, 'participants.tsv')
    dst_folder = 'results/tables/rootlets'  # Destination folder for results
    csv_out_path = os.path.join(dst_folder, f"{file_t2}_label-rootlets_center_of_mass_vert_levels_pmj_distance.csv") # Output CSV file for center of mass distances
    python_executable = sys.executable

    if not os.path.exists(csv_out_path):
        # Run `zeroing_false_positive_rootlets.py` (from the rootlets model) to remove all false positive rootlets, i.e., rootlets below the Th1 level 
        subprocess.run([
            python_executable,
            os.path.join(rootlets_model_dir, "pediatric_rootlets", "zeroing_false_positive_rootlets.py"),
            "-rootlets-seg", rootlets_seg,
            "-d", disc_labels,
            "-x", "11"
        ], check=True)

        # Run `02a_rootlets_to_spinal_levels.py` (from the rootlets model) to extract the spinal levels from the rootlets segmentation, 
        # and save the entry and exit point distances for each spinal level relative to the PMJ in a CSV file.
        subprocess.run([
            python_executable,
            os.path.join(rootlets_model_dir, "inter-rater_variability", "02a_rootlets_to_spinal_levels.py"),
            "-i", rootlets_modif,
            "-s", sc_mask,
            "-pmj", pmj_label
        ], check=True)

        # Call `discs_to_vertebral_levels.py`
        subprocess.run([
            python_executable,
            os.path.join(rootlets_model_dir, "pediatric_rootlets", "discs_to_vertebral_levels.py"),
            "-centerline", centerline_csv,
            "-disclabel", disc_labels,
        ], check=True)

        # Change the generated CSV files to the `results/tables` folder 
        PMJ_rootlets_dist_src = f'{subject_dir}/{file_t2}_label-rootlets_dseg_modif_pmj_distance.csv'
        PMJ_vertlevels_dist_src = f'{subject_dir}/{file_t2}_labels-disc_step1_levels_pmj_distance_vertebral_disc.csv'

        # Move the files
        shutil.move(PMJ_rootlets_dist_src, dst_folder)
        shutil.move(PMJ_vertlevels_dist_src, dst_folder)

        # Rename the rootlets PMJ distance CSV file to add "_rootlets" to the filename
        old_path = os.path.join(dst_folder, os.path.basename(PMJ_rootlets_dist_src))
        new_filename = os.path.basename(PMJ_rootlets_dist_src).replace('_pmj_distance.csv', '_pmj_distance_rootlets.csv')
        new_path = os.path.join(dst_folder, new_filename)
        os.rename(old_path, new_path)

        # Compute the distance from the center of mass of each spinal and vertebral level to the PMJ
        spinal_levels_label_file = f'{subject_dir}/{file_t2}_label-rootlets_dseg_modif_spinal_levels.nii.gz'
        center_of_mass_to_PMJ(
            label='spinal_levels',
            label_fname=spinal_levels_label_file,
            file_t2=file_t2,
            subject_dir=subject_dir,
            pmj_label=pmj_label,
            centerline_csv=centerline_csv,
            participants_tsv=participants_tsv,
            csv_out_path=os.path.join(dst_folder, f"{file_t2}_label-rootlets_center_of_mass_spinal_levels_pmj_distance.csv")
        )

        vert_levels_label_file = f'{subject_dir}/{file_t2}_label-SC_mask_labeled.nii.gz'
        center_of_mass_to_PMJ(
            label='vert_levels',
            label_fname=vert_levels_label_file,
            file_t2=file_t2,
            subject_dir=subject_dir,
            pmj_label=pmj_label,
            centerline_csv=centerline_csv,
            participants_tsv=participants_tsv,
            csv_out_path=os.path.join(dst_folder, f"{file_t2}_label-rootlets_center_of_mass_vert_levels_pmj_distance.csv")
        )

    else:
        print(f"Rootlets already processed for subject {subject}. Going straight to generating figure.")
    
    # Generate figure for all subjects (male + female)
    subprocess.run([
        python_executable,
        os.path.join(f'results/plots/', "generate_figure_rootlets_and_vertebral_spinal_levels.py"),
        "-i", 'results/tables/rootlets', # path to pmj distance csv files
        "-participants", participants_tsv
    ], check=True)

    # Generate figure for female subjects only
    subprocess.run([
        python_executable,
        os.path.join(f'results/plots/', "generate_figure_rootlets_and_vertebral_spinal_levels.py"),
        "-i", 'results/tables/rootlets', # path to pmj distance csv files
        "-participants", participants_tsv,
        '-sex', 'F'
    ], check=True)

    # Generate figure for male subjects only 
    subprocess.run([
        python_executable,
        os.path.join(f'results/plots/', "generate_figure_rootlets_and_vertebral_spinal_levels.py"),
        "-i", 'results/tables/rootlets', # path to pmj distance csv files
        "-participants", participants_tsv,
        '-sex', 'M'
    ], check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run rootlets processing for one subject")
    parser.add_argument("--subject", required=True, help="Subject ID (e.g., sub-001)")
    parser.add_argument("--data-path", required=True, help="Path to raw data")
    parser.add_argument("--subject-dir", required=True, help="Path to subject folder")
    parser.add_argument("--file-t2", required=True, help="T2-weighted filename prefix")
    parser.add_argument("--rootlets-model-dir", required=True, help="Path to your local `model-spinal-rootlets` repository")
    args = parser.parse_args()

    main(args.subject, args.data_path, args.subject_dir, args.file_t2, args.rootlets_model_dir)

