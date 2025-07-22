#!/bin/bash
#
# This script was modified from https://github.com/ivadomed/model-spinal-rootlets/blob/main/pediatric_rootlets/pediatric_rootlets.sh
# Original authors : Katerina Krejci, Jan Valosek
#
# This version of the script performs the following preprocessing steps on the data:
# - Segmentation of spinal cord from T2w data (sct_deepseg_sc)
# - Detection of PMJ from T2w data (sct_detect_pmj)
# - Labeling of vertebral levels from T2w data (sct_label_vertebrae)
# - Segmentation of rootlets from T2w data (model-spinal-rootlets_ventral_D106_r20250318)
#
# The script can be run across multiple subjects using `sct_run_batch`` by the following command:
# sct_run_batch -path-data /path/to/data/ -path-output /path/to/output -script pediatric_rootlets.sh
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

# get starting time:
start=`date +%s`

# FUNCTIONS
# ==============================================================================

# Segment spinal cord if it does not exist
segment_sc_if_does_not_exist(){
  SEG_FILE="${file_t2}_label-SC_mask"
  SEG_PATH="${PATH_DERIVATIVES}/labels/${SUBJECT}/anat/${SEG_FILE}.nii.gz"
  QC_PATH="${PATH_DERIVATIVES}/labels/qc"
  echo "Looking for manual segmentation: $SEG_PATH"
  if [[ -e $SEG_PATH ]]; then
    echo "Found! Using manual segmentation."
    rsync -avzh "${PATH_DERIVATIVES}/labels/${SUBJECT}/anat/"
  else
    echo "Not found. Proceeding with automatic segmentation."
    # Segment spinal cord
    sct_deepseg spinalcord -i ${file_t2}.nii.gz -c t2 -qc ${QC_PATH} -qc-subject ${SUBJECT} -o ${SEG_PATH} #spinal cord is the contrast agnostic model
  fi
}

# Detect PMJ if it does not exist
detect_pmj_if_does_not_exist(){
  PMJ_FILE="${file_t2}_label-PMJ_dlabel"
  PMJ_PATH="${PATH_DERIVATIVES}/labels/${SUBJECT}/anat/${PMJ_FILE}.nii.gz"
  QC_PATH="${PATH_DERIVATIVES}/labels/qc"
  echo "Looking for manual PMJ detection: $PMJ_PATH"
  if [[ -e $PMJ_PATH ]]; then
    echo "Found! Using manual PMJ detection."
    rsync -avzh "${PATH_DERIVATIVES}/labels/${SUBJECT}/anat/"
    sct_detect_pmj -i ${file_t2}.nii.gz -s ${SEG_PATH}.nii.gz -c t2 -o ${PMJ_PATH} -qc ${QC_PATH} -qc-subject ${SUBJECT}
  else
    echo "Not found. Proceeding with automatic PMJ detection."
    sct_detect_pmj -i ${file_t2}.nii.gz -s ${SEG_PATH}.nii.gz -c t2 -o ${PMJ_PATH} -qc ${QC_PATH} -qc-subject ${SUBJECT}
  fi
}

# Label vertebral levels if it does not exist
label_if_does_not_exist(){
  # Update global variable with segmentation file name
  VERTLABEL_FILE="${file_t2}_labels-disc"
  VERTLABEL_PATH="${PATH_DERIVATIVES}/labels/${SUBJECT}/anat/${VERTLABEL_FILE}.nii.gz"
  QC_PATH="${PATH_DERIVATIVES}/labels/qc"
  echo "Looking for manual label: $VERTLABEL_PATH"
  if [[ -e "${PATH_DERIVATIVES}/labels/${SUBJECT}/anat/${SUBJECT}_rec-composed_T2w_labels-disc_step2_output.nii.gz" ]]; then
    echo "Found vertebral labels!"
  elif [[ -e "${PATH_DERIVATIVES}/labels/${SUBJECT}/anat/${SUBJECT}_rec-composed_run-1_T2w_labels-disc_step2_output.nii.gz" ]]; then
    echo "Found vertebral labels for top acquisition! "
  elif [[ -e "${PATH_DERIVATIVES}/labels/${SUBJECT}/anat/${SUBJECT}_acq-top_T2w_labels-disc_step2_output.nii.gz" ]]; then
    echo "Found vertebral labels for top acquisition! "
  elif [[ -e "${PATH_DERIVATIVES}/labels/${SUBJECT}/anat/${SUBJECT}_acq-top_run-1_T2w_labels-disc_step2_output.nii.gz" ]]; then
    echo "Found vertebral labels for top acquisition! "
  else
    echo "Manual intervertebral discs not found. Proceeding with automatic labeling."
    # Generate vertebral labeling using the totalspineseg model
    sct_deepseg totalspineseg -i ${file_t2}.nii.gz -o ${VERTLABEL_PATH} -qc ${QC_PATH} -qc-subject ${SUBJECT}
  fi
}

# Extract centerline if does not exist
extract_centerline_if_does_not_exist(){
  CENTERLINE_FILE="${file_t2}_centerline"
  CENTERLINE_PATH="${PATH_DERIVATIVES}/labels/${SUBJECT}/anat/${CENTERLINE_FILE}.nii.gz"
  QC_PATH="${PATH_DERIVATIVES}/labels/qc"
  echo "Looking for centerline: $PMJ_PATH"
  if [[ -e $PMJ_PATH ]]; then
    echo "Found! Using centerline."
    rsync -avzh "${PATH_DERIVATIVES}/labels/${SUBJECT}/anat/"
  else
    echo "Not found. Proceeding with automatic centerline detection."
    sct_get_centerline -i ${file_t2}.nii.gz -c t2 -o ${CENTERLINE_PATH} -qc ${QC_PATH} -qc-subject ${SUBJECT}
  fi
}

# Segment rootlets if it does not exist
segment_rootlets_if_does_not_exist(){
  ROOTLETSEG_FILE="${file_t2}_label-dorsal_rootlets_dseg"
  ROOTLETSEG_PATH="${PATH_DERIVATIVES}/labels/${SUBJECT}/anat/${ROOTLETSEG_FILE}.nii.gz"
  QC_PATH="${PATH_DERIVATIVES}/labels/qc"
  echo "Looking for rootlets segmentation: $SEG_PATH"
  if [[ -e $SEG_PATH ]]; then
    echo "Found! Using rootlets segmentation."
    rsync -avzh "${PATH_DERIVATIVES}/labels/${SUBJECT}/anat/"
  else
    echo "Not found. Proceeding with automatic rootlets segmentation."
    # Segment spinal cord ventral
    sct_deepseg rootlets_t2 -i ${file_t2}.nii.gz -qc ${QC_PATH} -qc-subject ${SUBJECT} -o ${ROOTLETSEG_PATH}
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

# Define the names of the T2w files
file_t2_composed=${SUBJECT}_rec-composed_T2w
file_t2_top=${SUBJECT}_acq-top_run-1_T2w

# Check if file_t2_composed exists
if [ -f ${file_t2_composed}.nii.gz ]; then
    file_t2=${file_t2_composed}
else
    # Check if file_t2_top exists
    if [ -f ${file_t2_top}.nii.gz ]; then
        file_t2=${file_t2_top}
        echo "Composed T2w file not found. Proceeding with top T2w file."
    else
        echo "Neither composed nor top T2w file found for subject ${SUBJECT}. Skipping."
        continue  # Skip to the next subject
    fi
fi
  
# Segment spinal cord (only if it does not exist)
echo "------------------ Performing segmentation for ${SUBJECT} ------------------ "
segment_sc_if_does_not_exist ${file_t2}.nii.gz

# Run totalspineseg for vertebral labeling
echo "------------------ Performing vertebral labeling for ${SUBJECT} ------------------ "
label_if_does_not_exist ${file_t2}.nii.gz

# Project the intervertebral disc labels to the spinal cord centerline
echo "------------------ Projecting intervertebral disc labels to spinal cord centerline for ${SUBJECT}------------------"
sct_label_utils -i ${FILESEG}.nii.gz -o ${FILELABEL}_centerline.nii.gz -project-centerline ${FILELABEL}.nii.gz -qc ${PATH_QC} -qc-subject ${SUBJECT}

# Detect PMJ (only if it does not exist)
echo "------------------ Detecting PMJ for ${SUBJECT} ------------------ "
detect_pmj_if_does_not_exist ${file_t2}.nii.gz

# Extract centerline (only if it does not exist)
echo "------------------ Extracting spinal cord centerline for ${SUBJECT} ------------------ "
extract_centerline_if_does_not_exist ${file_t2}.nii.gz

# Segment rootlets (only if it does not exist)
echo "Segmenting rootlets for ${SUBJECT}..."
segment_rootlets_if_does_not_exist ${file_t2}.nii.gz

# Display useful info for the log
end=`date +%s`
runtime=$((end-start))
echo
echo "~~~"
echo "SCT version: `sct_version`"
echo "Ran on:      `uname -nsr`"
echo "Duration:    $(($runtime / 3600))hrs $((($runtime / 60) % 60))min $(($runtime % 60))sec"
echo "~~~"