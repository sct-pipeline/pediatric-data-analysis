#!/bin/bash
#
# This script performs the following preprocessing steps on the DWI data of the philadelphia-pediatric dataset:
# - Generate the mean DWI image
# - Spinal cord segmentation
# - Motion correction 
# - DTI metrics 
# - Registration to PAM50 template
# - Segmentation of rootlets (model-spinal-rootlets_ventral_D106_r20250318)
#
# The script can be run across multiple subjects using `sct_run_batch` by the following command:
#   sct_run_batch -path-data /path/to/data/ -path-output /path/to/output -script DWI_data_preprocessing.sh
# 
# It is also possible to add an exclude.yml file to exclude certain subjects from the batch processing. 
# To do so, the argument '-exclude' can be added to the command above, followed by the path to the exclude.yml file.
# 
# Author: Samuelle St-Onge
#

# Uncomment for full verbose
set -x

# Immediately exit if error
set -e -o pipefail

# Exit if user presses CTRL+C 
trap "echo Caught Keyboard Interrupt within script. Exiting now.; exit" INT

# Retrieve input parameters
SUBJECT=$1

# Define path to derivatives according to the data path 
PATH_DERIVATIVES=${PATH_DATA}/derivatives

echo "data path : ${PATH_DATA}"

# Path to QC
QC_PATH=${PATH_QC}

# get starting time:
start=`date +%s`

# FUNCTIONS
# ==============================================================================

# Generate the mean DWI image if it does not exist
generate_mean_DWI(){
  # Inputs 
  DWI_DATA_FOLDER="${PATH_DATA}/${SUBJECT}/dwi/"
  DWI_FILE=${DWI_DATA_FOLDER}/${file_dwi}
  # Outputs 
  MEAN_DWI_FILE="${file_dwi}_mean.nii.gz"
  MEAN_DWI_FOLDER="${PATH_DERIVATIVES}/labels/${SUBJECT}/dwi"
  MEAN_DWI_FILE_PATH="${MEAN_DWI_FOLDER}/${MEAN_MEAN_DWI_FILE}"
  echo "Looking for manual segmentation: $SEG_PATH"
  if [[ -e $MEAN_DWI_FILE_PATH ]]; then
    echo "Found! Using $MEAN_DWI_FILE as the mean image."
  else
    echo "Not found. Proceeding with sct_dmri_separate_b0_and_dwi"
    # Generate the mean DWI image
    sct_dmri_separate_b0_and_dwi -i ${DWI_FILE}.nii.gz -bvec ${DWI_FILE}.bvec -bval ${DWI_FILE}.bval -ofolder ${MEAN_DWI_FOLDER}
  fi
}

# Segment spinal cord if it does not exist
segment_spinal_cord(){
  MEAN_DWI_FILE="${PATH_DERIVATIVES}/labels/${SUBJECT}/dwi/${file_dwi}_dwi_mean.nii.gz"
  SEG_FILE="${file_dwi}_label-SC_mask.nii.gz"
  SEG_PATH="${PATH_DERIVATIVES}/labels/${SUBJECT}/dwi/${SEG_FILE}"
  echo "Looking for segmentation: $SEG_PATH"
  if [[ -e $SEG_PATH ]]; then
    echo "Found! Using $SEG_FILE as the segmentation."
  else
    echo "Not found. Proceeding with sct_deepseg spinalcord."
    # Segment spinal cord using the contrast-agnostic model from sct_deepseg
    sct_deepseg spinalcord -i ${MEAN_DWI_FILE} -c dwi -qc ${QC_PATH} -qc-subject ${SUBJECT} -o ${SEG_PATH}
  fi
}

# Generate a mask around the spinal cord for the motion correction 
create_mask(){
  MASK_FILE="${PATH_DERIVATIVES}/labels/${SUBJECT}/dwi/${file_dwi}_mask_dmri_dwi_mean.nii.gz"
  MEAN_DWI_FILE="${PATH_DERIVATIVES}/labels/${SUBJECT}/dwi/${file_dwi}_dwi_mean.nii.gz"
  SEG_FILE="${file_dwi}_label-SC_mask.nii.gz"
  SEG_PATH="${PATH_DERIVATIVES}/labels/${SUBJECT}/dwi/${SEG_FILE}"
  echo "Looking for mask: $MASK_FILE"
  if [[ -e $MASK_FILE ]]; then
    echo "Found! Using $MASK_FILE as the mask."
  else
    echo "Not found. Proceeding with sct_create_mask."
    sct_create_mask -i ${MEAN_DWI_FILE} -p centerline,${SEG_PATH} -size 40mm -o ${MASK_FILE}
  fi
}

# Perform motion correction 
motion_correction(){
  # Input
  DWI_DATA_FOLDER="${PATH_DATA}/${SUBJECT}/dwi/"
  DWI_FILE=${DWI_DATA_FOLDER}/${file_dwi}
  MASK_FILE="${PATH_DERIVATIVES}/labels/${SUBJECT}/dwi/${file_dwi}_mask_dmri_dwi_mean.nii.gz"
  SEG_PATH="${PATH_DERIVATIVES}/labels/${SUBJECT}/dwi/${SEG_FILE}"
  # Output
  MOCO_DWI_FILE="${PATH_DERIVATIVES}/labels/${SUBJECT}/dwi/${SUBJECT}_dwi_moco.nii.gz"
  echo "Looking for motion corrected files"
  if [[ -e $MOCO_DWI_FILE ]]; then
    echo "Found! Using $SEG_FILE as the motion corrected files."
  else
    echo "Not found. Proceeding with sct_deepseg spinalcord."
    # Perform motion correction
    sct_dmri_moco -i ${DWI_FILE}.nii.gz -m ${MASK_FILE} -bvec ${DWI_FILE}.bvec -qc ${QC_PATH} -qc-seg ${SEG_PATH} -o ${PATH_DERIVATIVES}/labels/${SUBJECT}/dwi/
  fi
}

# SCRIPT STARTS HERE
# ==============================================================================
# Display useful info for the log, such as SCT version, RAM and CPU cores available
sct_check_dependencies -short

# Go to folder where data will be copied and processed
# cd $PATH_DERIVATIVES

# Go to anat folder where DWI data are located
# cd ${SUBJECT}/dwi

# Define the suffix for the DWI files (with `run-1` or `run-2``)
if [[ -e "${PATH_DATA}/${SUBJECT}/dwi/${SUBJECT}_run-1_dwi.nii.gz" ]]; then
  file_dwi=${SUBJECT}_run-1_dwi
elif [[ -e "${PATH_DATA}/${SUBJECT}/dwi/${SUBJECT}_run-2_dwi.nii.gz" ]]; then
  file_dwi=${SUBJECT}_run-2_dwi
fi

# Generate the mean DWI image 
echo "------------------ Generating mean DWI image for ${SUBJECT} ------------------ "
generate_mean_DWI ${file_dwi}

# Segment spinal cord
echo "------------------ Performing segmentation for ${SUBJECT} ------------------ "
segment_spinal_cord ${file_dwi}

# Create mask around the spinal cord for motion correction 
echo "------------------ Creating spinal cord mask for ${SUBJECT} ------------------ "
create_mask ${file_dwi}

# Perform motion correction
echo "------------------ Performing motion correction for ${SUBJECT} ------------------ "
motion_correction ${file_dwi}

# # Compute DTI metrics 
# echo "------------------ Computing DTI metrics for ${SUBJECT}------------------"
# compute_DTI ${file_dwi}

# # Perform registration to and from the PAM50 template
# echo "------------------ Registration of DWI data with PAM50 template ${SUBJECT} ------------------ "
# registration_with_PAM50 ${file_dwi}.nii.gz

# # Extract DTI metrics 
# echo "------------------ Extracting DTI metrics for ${SUBJECT} using the PAM50 atlas ------------------ "
# extract_DTI_metrics ${file_dwi}.nii.gz

# Display useful info for the log
end=`date +%s`
runtime=$((end-start))
echo
echo "~~~"
echo "SCT version: `sct_version`"
echo "Ran on:      `uname -nsr`"
echo "Duration:    $(($runtime / 3600))hrs $((($runtime / 60) % 60))min $(($runtime % 60))sec"
echo "~~~"