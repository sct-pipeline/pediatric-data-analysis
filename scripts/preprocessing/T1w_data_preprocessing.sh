#!/bin/bash
#
# This version of the script performs the following preprocessing steps on the T1w data of the philadelphia-pediatric dataset:
# - Segmentation of spinal cord (sct_deepseg_sc)
# - Labeling of vertebral levels (totalspineseg via sct_deepseg)
# - Labeling of the SC segmentation mask (sct_label_vertebrae)
#
# The script can be run across multiple subjects using `sct_run_batch` by the following command:
#   sct_run_batch -config config/preprocessing_T1w.yaml -script scripts/preprocessing/T1w_data_preprocessing.sh
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
QC_PATH=${PATH_DERIVATIVES}/QC/QC_DWI/SCT_QC_Report_T1w

# get starting time:
start=`date +%s`

# FUNCTIONS
# ==============================================================================

# Segment spinal cord if it does not exist
segment_sc_if_does_not_exist(){
  SEG_FILE="${file_t1}_label-SC_mask"
  SEG_PATH="${PATH_DERIVATIVES}/labels/${SUBJECT}/anat/${SEG_FILE}.nii.gz"
  echo "Looking for manual segmentation: $SEG_PATH"
  if [[ -e $SEG_PATH ]]; then
    echo "Found! Using manual segmentation."
    rsync -avzh "${PATH_DERIVATIVES}/labels/${SUBJECT}/anat/"
  else
    echo "Not found. Proceeding with automatic segmentation."
    # Segment spinal cord
    sct_deepseg spinalcord -i ${file_t1}.nii.gz -c t1 -qc ${QC_PATH} -qc-subject ${SUBJECT} -o ${SEG_PATH} #spinal cord is the contrast agnostic model
  fi
}

# Label vertebral levels if it does not exist
label_if_does_not_exist(){
  # Update global variable with segmentation file name
  VERTLABEL_FILE="${file_t1}_labels-disc"
  VERTLABEL_PATH="${PATH_DERIVATIVES}/labels/${SUBJECT}/anat/${VERTLABEL_FILE}.nii.gz"
  echo "Looking for manual label: $VERTLABEL_PATH"
  if [[ -e "${PATH_DERIVATIVES}/labels/${SUBJECT}/anat/${file_t1}_labels-disc_step2_output.nii.gz" ]]; then
    echo "Found vertebral labels!"
  else
    echo "Manual intervertebral discs not found. Proceeding with automatic labeling."
    # Generate vertebral labeling using the totalspineseg model
    sct_deepseg totalspineseg -i ${file_t1}.nii.gz -o ${VERTLABEL_PATH} -qc ${QC_PATH} -qc-subject ${SUBJECT}
  fi
}

# Label the SC mask if it does not exist (using the vertebral level labels)
label_SC_mask_if_does_not_exist(){
  # Input
  SEG_FILE="${file_t1}_label-SC_mask"
  SEG_PATH="${PATH_DERIVATIVES}/labels/${SUBJECT}/anat/${SEG_FILE}.nii.gz"
  VERTLABEL_FILE="${file_t1}_labels-disc_step1_levels"
  VERTLABEL_PATH="${PATH_DERIVATIVES}/labels/${SUBJECT}/anat/${VERTLABEL_FILE}.nii.gz"
  # Output
  OFOLDER="${PATH_DERIVATIVES}/labels/${SUBJECT}/anat"
  T1_LABEL_SEG="${OFOLDER}/${file_t1}_label-SC_mask_labeled.nii.gz"

  if [[ -e "${T1_LABEL_SEG}" ]]; then
    echo "Found labeled segmentation."
  else
    echo "Labeled segmentation not found. Proceeding with sct_label_vertebrae."
    sct_label_vertebrae -i ${file_t1}.nii.gz -s ${SEG_PATH} -c t1 -discfile ${VERTLABEL_PATH} -ofolder ${OFOLDER}
  fi
}

get_vertebral_levels_labels(){
  # Input
  OFOLDER="${PATH_DERIVATIVES}/labels/${SUBJECT}/anat"
  T1_LABEL_SEG="${OFOLDER}/${file_t1}_label-SC_mask_labeled.nii.gz"
  # Output
  VERT_LABEL_FILE="${OFOLDER}/${file_t1}_labels-vert.nii.gz"
  if [[ -e ${VERT_LABEL_FILE} ]]; then
    echo "Found vertebral labels!"
  else
    echo "Vertebral labels not found. Proceeding with vertebral level labeling."
    # Generate vertebral levels labels
    sct_label_utils -i ${T1_LABEL_SEG} -vert-body 3,7 -o ${VERT_LABEL_FILE}
  fi
}

# SCRIPT STARTS HERE
# ==============================================================================
# Display useful info for the log, such as SCT version, RAM and CPU cores available
sct_check_dependencies -short

# Go to folder where data will be copied and processed
cd $PATH_DATA_DERIVATIVES

# Copy source images
# Note: we copy only T1w to save space
rsync -Ravzh ${PATH_DATA}/./${SUBJECT}/anat/${SUBJECT//[\/]/_}_*T1w.* .

# Go to anat folder where all structural data are located
cd ${SUBJECT}/anat

# Define the name of the acq-top T1w file
file_t1_top=${SUBJECT}_acq-top_run-1_T1w

# Check if acq-top T1w file exists
if [ -f ${file_t1_top}.nii.gz ]; then
  file_t1+=("${file_t1_top}")
  echo "Top T1w file found. Proceeding with processing for acq-top T1w file."
else
  echo "acq-top T1w file not found. Skipping."
fi

# Segment spinal cord (only if it does not exist)
echo "------------------ Performing segmentation for ${SUBJECT} ------------------ "
segment_sc_if_does_not_exist ${file_t1}.nii.gz

# Run totalspineseg for vertebral labeling
echo "------------------ Performing vertebral labeling for ${SUBJECT} ------------------ "
label_if_does_not_exist ${file_t1}.nii.gz

# Generate the labeled segmentation (with the vertebral disc labels)
echo "------------------ Generating the labeled segmentation for ${SUBJECT} ------------------ "
label_SC_mask_if_does_not_exist ${file_t1}.nii.gz

# Generate the vertebral levels labels
echo "------------------ Generating vertebral levels labels for ${SUBJECT} ------------------ "
get_vertebral_levels_labels ${file_t2}.nii.gz


# Display useful info for the log
end=`date +%s`
runtime=$((end-start))
echo
echo "~~~"
echo "SCT version: `sct_version`"
echo "Ran on:      `uname -nsr`"
echo "Duration:    $(($runtime / 3600))hrs $((($runtime / 60) % 60))min $(($runtime % 60))sec"
echo "~~~"