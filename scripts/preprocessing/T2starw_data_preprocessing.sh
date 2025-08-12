#!/bin/bash
#
# This version of the script performs the following preprocessing steps on the T2*w data of the philadelphia-pediatric dataset:
# - Segmentation of spinal cord (sct_deepseg_sc spinalcord)
# - Segmentation of the gray matter (sct_deepseg_sc graymatter)
# - Compute the white matter segmentation by substracting the gray matter mask from the full spinal cord segmentation
# - Compute CSA for gray and white matter
#
# The script can be run across multiple subjects using `sct_run_batch` by the following command:
#   sct_run_batch -path-data /path/to/data/ -path-output /path/to/output -script T2starw_data_preprocessing.sh
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

# Path to QC
QC_PATH=${PATH_DERIVATIVES}/QC/QC_T2starw/SCT_QC_Report_T2starw

# get starting time:
start=`date +%s`

# FUNCTIONS
# ==============================================================================

# Segment spinal cord if it does not exist
segment_sc(){
  # Input
  T2star_FILE="${PATH_DATA}/${SUBJECT}/anat/${file_t2star}.nii.gz"
  # Output
  SEG_FILE="${file_t2star}_label-SC_mask"
  SEG_PATH="${PATH_DERIVATIVES}/labels/${SUBJECT}/anat/${SEG_FILE}.nii.gz"
  echo "Looking for manual segmentation: $SEG_PATH"
  if [[ -e $SEG_PATH ]]; then
    echo "Found SC segmentation."
    rsync -avzh "${PATH_DERIVATIVES}/labels/${SUBJECT}/anat/"
  else
    echo "SC segmentation not found. Proceeding with automatic segmentation."
    # Segment spinal cord
    sct_deepseg spinalcord -i ${T2star_FILE} -c t2 -qc ${QC_PATH} -qc-subject ${SUBJECT} -o ${SEG_PATH} #spinal cord is the contrast agnostic model
  fi
}

# Segment gray matter if it does not exist
segment_gm(){
  # Input
  T2star_FILE="${PATH_DATA}/${SUBJECT}/anat/${file_t2star}.nii.gz"
  # Output
  SEG_FILE="${file_t2star}_label-GM_mask"
  SEG_PATH="${PATH_DERIVATIVES}/labels/${SUBJECT}/anat/${SEG_FILE}.nii.gz"
  echo "Looking for manual segmentation: $SEG_PATH"
  if [[ -e $SEG_PATH ]]; then
    echo "Found GM segmentation."
    rsync -avzh "${PATH_DERIVATIVES}/labels/${SUBJECT}/anat/"
  else
    echo "GM segmentation not found. Proceeding with automatic segmentation."
    # Segment gray matter
    sct_deepseg graymatter -i ${T2star_FILE} -qc ${QC_PATH} -qc-subject ${SUBJECT} -o ${SEG_PATH} #spinal cord is the contrast agnostic model
  fi
}


# SCRIPT STARTS HERE
# ==============================================================================
# Display useful info for the log, such as SCT version, RAM and CPU cores available
sct_check_dependencies -short

# Go to folder where data will be copied and processed
cd $PATH_DATA_DERIVATIVES

# Copy source images
# Note: we copy only T2w to save space
rsync -Ravzh ${PATH_DATA}/./${SUBJECT}/anat/${SUBJECT//[\/]/_}_*T2w.* .

# Go to anat folder where all structural data are located
cd ${SUBJECT}/anat

# Define the suffix for the T2*w files (with `run-1` or `run-2`)
if [[ -e "${PATH_DATA}/${SUBJECT}/anat/${SUBJECT}_run-1_T2starw.nii.gz" ]]; then
  file_t2star=${SUBJECT}_run-1_T2starw
elif [[ -e "${PATH_DATA}/${SUBJECT}/anat/${SUBJECT}_run-2_T2starw.nii.gz" ]]; then
  file_t2star=${SUBJECT}_run-2_T2starw
fi

# Generate the labeled segmentation (with the vertebral disc labels)
echo "------------------ Generating the spinal cord segmentation for ${SUBJECT} ------------------ "
segment_sc ${file_t2star}.nii.gz

# Generate the labeled segmentation (with the vertebral disc labels)
echo "------------------ Generating the gray matter segmentation for ${SUBJECT} ------------------ "
segment_gm ${file_t2star}.nii.gz


# Display useful info for the log
end=`date +%s`
runtime=$((end-start))
echo
echo "~~~"
echo "SCT version: `sct_version`"
echo "Ran on:      `uname -nsr`"
echo "Duration:    $(($runtime / 3600))hrs $((($runtime / 60) % 60))min $(($runtime % 60))sec"
echo "~~~"