#!/bin/bash
#
# This script performs the following preprocessing steps on the DWI data of the philadelphia-pediatric dataset:
# - Generate the mean DWI image
# - Spinal cord segmentation
# - Motion correction 
# - Compute DTI metrics 
# - Registration of T2w (or T1w) data to the PAM50 template (to generate initialization warping fields for DWI registration). 
# - Registration of the PAM50 template to the DWI space
# - Extract DTI metrics using the PAM50 atlas registered to the DWI space
#
# The script can be run across multiple subjects using `sct_run_batch` by the following command:
#   sct_run_batch -path-data /path/to/data/ -path-output /path/to/output -script DWI_data_preprocessing.sh
#
# Author: Samuelle St-Onge
#

# Verbose
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
QC_PATH=${PATH_DERIVATIVES}/QC/QC_DWI/SCT_QC_Report_DWI

echo "SCT DIR : ${SCT_DIR}"

# Path to `exclude.yml` file
EXCLUDE_FILE="${PATH_DATA}/exclude.yml"
EXCLUDE_KEY="dwi"

# get starting time:
start=`date +%s`

# FUNCTIONS
# ==============================================================================

# Generate the mean DWI image if it does not exist
generate_mean_DWI(){
  # Inputs 
  DWI_DATA_FOLDER="${PATH_DATA}/${SUBJECT}/dwi"
  DWI_FILE=${DWI_DATA_FOLDER}/${file_dwi}
  # Outputs 
  MEAN_DWI_FILE="${file_dwi}_mean.nii.gz"
  MEAN_DWI_FOLDER="${PATH_DERIVATIVES}/labels/${SUBJECT}/dwi"
  MEAN_DWI_FILE_PATH="${MEAN_DWI_FOLDER}/${MEAN_DWI_FILE}"
  echo "Looking for mean DWI image: ${MEAN_DWI_FILE_PATH}"
  if [[ -e ${MEAN_DWI_FILE_PATH} ]]; then
    echo "Found! Using $MEAN_DWI_FILE as the mean image."
  else
    echo "Not found. Proceeding with sct_dmri_separate_b0_and_dwi"
    # Generate the mean DWI image
    sct_dmri_separate_b0_and_dwi -i ${DWI_FILE}.nii.gz -bvec ${DWI_FILE}.bvec -bval ${DWI_FILE}.bval -ofolder ${MEAN_DWI_FOLDER}
  fi
}

# Segment spinal cord if it does not exist
segment_spinal_cord(){
  # Input
  MEAN_DWI_FILE="${PATH_DERIVATIVES}/labels/${SUBJECT}/dwi/${file_dwi}_dwi_mean.nii.gz"
  # Output
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

# Perform motion correction 
motion_correction(){
  # Inputs
  DWI_DATA_FOLDER="${PATH_DATA}/${SUBJECT}/dwi/"
  DWI_FILE=${DWI_DATA_FOLDER}/${file_dwi}
  SEG_FILE="${file_dwi}_label-SC_mask.nii.gz"
  SEG_PATH="${PATH_DERIVATIVES}/labels/${SUBJECT}/dwi/${SEG_FILE}"
  # Outputs
  MOCO_DWI_PATH="${PATH_DERIVATIVES}/motion_correction/${SUBJECT}/dwi/"
  echo "Looking for motion corrected files"
  if [[ -e "${PATH_DERIVATIVES}/motion_correction/${SUBJECT}/dwi/${SUBJECT}_dwi_moco.nii.gz" ]]; then
    echo "Found! Using motion corrected files."
  else
    echo "Not found. Proceeding with sct_deepseg spinalcord."
    # Perform motion correction
    sct_dmri_moco -i ${DWI_FILE}.nii.gz -bvec ${DWI_FILE}.bvec -bval ${DWI_FILE}.bval -qc ${QC_PATH} -qc-seg ${SEG_PATH} -o ${MOCO_DWI_PATH}
  fi
}

# Compute DTI on the motion-corrected DWI data
compute_DTI(){
  # Inputs 
  MOCO_DWI_DATA_FOLDER="${PATH_DERIVATIVES}/motion_correction/${SUBJECT}/dwi/"
  MOCO_DWI_FILE=${MOCO_DWI_DATA_FOLDER}/${file_dwi}_moco
  DWI_DATA_FOLDER="${PATH_DATA}/${SUBJECT}/dwi/"
  DWI_FILE=${DWI_DATA_FOLDER}/${file_dwi}
  # Outputs
  DTI_DATA_FOLDER="${PATH_DERIVATIVES}/DTI/${SUBJECT}/"
  
  echo "Looking for motion-corrected DTI files"
  if [[ -e "${DTI_DATA_FOLDER}/FA.nii.gz" ]]; then
    echo "Found motion-corrected DTI files in $DTI_DATA_FOLDER."
  else
    echo "Not found. Computing motion-corrected DTI metrics."
    mkdir -p "${DTI_DATA_FOLDER}"
    sct_dmri_compute_dti -i ${MOCO_DWI_FILE}.nii.gz -bval ${DWI_FILE}.bval -bvec ${DWI_FILE}.bvec -o ${DTI_DATA_FOLDER}
  fi
}

# Segment motion-corrected spinal cord if it does not exist
segment_moco_spinal_cord(){
  # Input
  MEAN_MOCO_DWI_FILE="${PATH_DERIVATIVES}/motion_correction/${SUBJECT}/dwi/${file_dwi}_moco_dwi_mean.nii.gz"
  # Output
  MOCO_SEG_FILE="${file_dwi}_moco_label-SC_mask.nii.gz"
  MOCO_SEG_PATH="${PATH_DERIVATIVES}/labels/${SUBJECT}/dwi/${MOCO_SEG_FILE}"
  
  echo "Looking for segmentation of motion-corrected DWI data: $MOCO_SEG_PATH"
  if [[ -e $MOCO_SEG_PATH ]]; then
    echo "Found! Using $MOCO_SEG_FILE as the segmentation."
  else
    echo "Not found. Proceeding with motion correction."
    # Segment motion-corrected spinal cord using the contrast-agnostic model from sct_deepseg
    sct_deepseg spinalcord -i ${MEAN_MOCO_DWI_FILE} -c dwi -qc ${QC_PATH} -qc-subject ${SUBJECT} -o ${MOCO_SEG_PATH}
  fi
}

# Register T2w data to PAM50 (to get T2w <--> PAM50 warping fields)
register_T2w_to_PAM50(){
  # Inputs
  T2w_DATA_FOLDER="${PATH_DATA}/${SUBJECT}/anat/"
  T2_FILE=${T2w_DATA_FOLDER}/${file_t2}
  SEG_FILE="${file_t2}_label-SC_mask"
  SEG_PATH="${PATH_DERIVATIVES}/labels/${SUBJECT}/anat/${SEG_FILE}.nii.gz"
  VERTLABEL_FILE="${file_t2}_labels-vert"
  VERTLABEL_PATH="${PATH_DERIVATIVES}/labels/${SUBJECT}/anat/${VERTLABEL_FILE}.nii.gz"
  # Outputs
  O_FOLDER_ANAT_REG="${PATH_DERIVATIVES}/PAM50_registration/${SUBJECT}/anat/"
  
  if [[ -e "${O_FOLDER_ANAT_REG}/template2anat.nii.gz" ]]; then
    echo "Found T2w registration files. Skipping."
    sct_register_to_template -i ${T2_FILE}.nii.gz -s ${SEG_PATH} -l ${VERTLABEL_PATH} -c t2 -o ${O_FOLDER_ANAT_REG} -qc ${QC_PATH} 

  else
    echo "Not found. Performing registration of T2w with PAM50 template"
    mkdir -p "${O_FOLDER_ANAT_REG}"
    sct_register_to_template -i ${T2_FILE}.nii.gz -s ${SEG_PATH} -l ${VERTLABEL_PATH} -c t2 -o ${O_FOLDER_ANAT_REG} -qc ${QC_PATH} 
  fi
}

# Register T1w data to PAM50 (to get T1w <--> PAM50 warping fields)
register_T1w_to_PAM50(){
  # Inputs
  T1w_DATA_FOLDER="${PATH_DATA}/${SUBJECT}/anat/"
  T1_FILE=${T1w_DATA_FOLDER}/${file_t1}
  SEG_FILE="${file_t1}_label-SC_mask"
  SEG_PATH="${PATH_DERIVATIVES}/labels/${SUBJECT}/anat/${SEG_FILE}.nii.gz"
  VERTLABEL_FILE="${file_t1}_labels-vert"
  VERTLABEL_PATH="${PATH_DERIVATIVES}/labels/${SUBJECT}/anat/${VERTLABEL_FILE}.nii.gz"
  # Outputs
  O_FOLDER_ANAT_REG="${PATH_DERIVATIVES}/PAM50_registration/${SUBJECT}/anat/"
  
  if [[ -e "${O_FOLDER_ANAT_REG}/template2anat.nii.gz" ]]; then
    echo "Found T1w registration files. Skipping."
  else
    echo "Not found. Performing registration of T1w with PAM50 template"
    mkdir -p "${O_FOLDER_ANAT_REG}"
    sct_register_to_template -i ${T1_FILE}.nii.gz -s ${SEG_PATH} -l ${VERTLABEL_PATH} -c t1 -o ${O_FOLDER_ANAT_REG} -qc ${QC_PATH} 
  fi
}

# Generate DWI <--> PAM50 warping fields and register PAM50 template to DWI space 
register_PAM50_to_DWI(){
  # Inputs
  MEAN_MOCO_DWI_FILE="${PATH_DERIVATIVES}/motion_correction/${SUBJECT}/dwi/${file_dwi}_moco_dwi_mean.nii.gz"
  DWI_MOCO_SEG_FILE="${file_dwi}_moco_label-SC_mask"
  DWI_MOCO_SEG_PATH="${PATH_DERIVATIVES}/labels/${SUBJECT}/dwi/${DWI_MOCO_SEG_FILE}.nii.gz"
  WARP_T2="${PATH_DERIVATIVES}/PAM50_registration/${SUBJECT}/anat/warp_template2anat.nii.gz"
  WARP_INV_T2="${PATH_DERIVATIVES}/PAM50_registration/${SUBJECT}/anat/warp_anat2template.nii.gz"
  # Outputs
  WARP_DWI="${PATH_DERIVATIVES}/PAM50_registration/${SUBJECT}/dwi/warp_template2dmri.nii.gz"
  WARP_INV_DWI="${PATH_DERIVATIVES}/PAM50_registration/${SUBJECT}/dwi/warp_dmri2template.nii.gz"
  
  if [[ -e "${PATH_DERIVATIVES}/PAM50_registration/${SUBJECT}/dwi/reg.nii.gz" ]]; then
    echo "Found DWI registration files. Skipping."
  else
    # Generate the DWI <--> PAM50 warping fields (with the T2w <--> PAM50 warping fields as initialization)
    echo "Not found. Generating warping fields for DWI with PAM50 template"
    sct_register_multimodal -i "${SCT_DIR}/data/PAM50/template/PAM50_t1.nii.gz" \
                            -iseg "${SCT_DIR}/data/PAM50/template/PAM50_cord.nii.gz" \
                            -d ${MEAN_MOCO_DWI_FILE} \
                            -dseg ${DWI_MOCO_SEG_PATH} \
                            -initwarp ${WARP_T2} \
                            -initwarpinv ${WARP_INV_T2} \
                            -owarp ${WARP_DWI} \
                            -owarpinv ${WARP_INV_DWI} \
                            -param step=1,type=seg,algo=centermass:step=2,type=seg,algo=bsplinesyn,slicewise=1,iter='5'  \
                            -qc ${QC_PATH} \
                            -ofolder "${PATH_DERIVATIVES}/PAM50_registration/${SUBJECT}/dwi/"
  
    # Register PAM50 template to the DWI subject space (to extract metrics in the subject space with the PAM50 atlas)
    echo "Registering the PAM50 template to the DWI subject space"
    sct_warp_template -d ${MEAN_MOCO_DWI_FILE} -w ${WARP_DWI} -qc ${QC_PATH} -o "${PATH_DERIVATIVES}/PAM50_registration/${SUBJECT}/dwi/"
  
  fi
}

# Extract DTI metrics using the PAM50 atlas
extract_DTI_metrics(){

  # Define output directory to save extracted metrics
  REPO_ROOT=$(git rev-parse --show-toplevel)
  mkdir -p "${REPO_ROOT}/results/tables/DTI_metrics/"

  # Check if the subject is in the exclusion list under the 'dwi' key (by checking if the entries start with '${SUBJECT}_')
  if yq e ".${EXCLUDE_KEY}[]" "$EXCLUDE_FILE" | cut -d'_' -f1 | grep -qx "$SUBJECT"; then
    echo "Skipping ${SUBJECT} (listed under ${EXCLUDE_KEY} key)"
  else
    # Extract each DTI metric and save in a CSV file
    for DTI_metric in FA MD RD AD; do

      # Extract metrics for separate vertebral levels
      sct_extract_metric -i "${PATH_DERIVATIVES}/DTI/${SUBJECT}/${DTI_metric}.nii.gz" \
                        -f "${PATH_DERIVATIVES}/PAM50_registration/${SUBJECT}/dwi/atlas" \
                        -l 1,2,3,4,34,35,50,51,52,53,54,55 \
                        -vert 2:6 \
                        -vertfile "${PATH_DERIVATIVES}/PAM50_registration/${SUBJECT}/dwi/template/PAM50_levels.nii.gz" \
                        -perlevel 1 \
                        -perslice 0 \
                        -method wa \
                        -append 1 \
                        -o "${REPO_ROOT}/results/tables/DTI_metrics/${DTI_metric}/${SUBJECT}_${DTI_metric}.csv"

    # Extract metrics for all vertebral levels combined and append to the same CSV file as the previous step
    sct_extract_metric -i "${PATH_DERIVATIVES}/DTI/${SUBJECT}/${DTI_metric}.nii.gz" \
                        -f "${PATH_DERIVATIVES}/PAM50_registration/${SUBJECT}/dwi/atlas" \
                        -l 1,2,3,4,34,35,50,51,52,53,54,55 \
                        -vert 3:5 \
                        -vertfile "${PATH_DERIVATIVES}/PAM50_registration/${SUBJECT}/dwi/template/PAM50_levels.nii.gz" \
                        -perlevel 0 \
                        -perslice 0 \
                        -method wa \
                        -append 1 \
                        -o "${REPO_ROOT}/results/tables/DTI_metrics/${DTI_metric}/${SUBJECT}_${DTI_metric}.csv"
    done
  fi
}

# SCRIPT STARTS HERE
# ==============================================================================
# Display useful info for the log, such as SCT version, RAM and CPU cores available
sct_check_dependencies -short

# Define the suffix for the DWI files (with `run-1` or `run-2`)
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

# Perform motion correction
echo "------------------ Performing motion correction for ${SUBJECT} ------------------ "
motion_correction ${file_dwi}

# Compute DTI metrics on the motion-corrected DWI image
echo "------------------ Computing DTI metrics for ${SUBJECT}------------------"
compute_DTI ${file_dwi}

# Segment the mean motion-corrected DWI image
echo "------------------ Performing segmentation of mean motion-corrected DWI image for ${SUBJECT} ------------------ "
segment_moco_spinal_cord ${file_dwi}

# Perform registration of T2w data to PAM50 (to use the warping fields as init for the DWI to PAM50 registration)
echo "------------------ Registration of T2w (or T1w) data with PAM50 template for ${SUBJECT} ------------------ "

# Define the name of the acq-top T2w file
file_t2=${SUBJECT}_acq-top_run-1_T2w

# Define the name of the acq-top T1w file
file_t1=${SUBJECT}_acq-top_run-1_T1w

# Check if file_t2_top exists
if [[ -f "${PATH_DATA}/${SUBJECT}/anat/${file_t2}.nii.gz" ]]; then

  # Check if the T2 file is inside the exclude list
  if yq e ".t2w[]" "$EXCLUDE_FILE" | cut -d'_' -f1 | grep -qx "$SUBJECT"; then
    echo "Skipping ${SUBJECT} (listed under "t2w" key)"
    # If T2w is excluded, check if T1w exists
    if [[ -f "${PATH_DATA}/${SUBJECT}/anat/${file_t1}.nii.gz" ]]; then
      echo "T1w found. Using acq-top T1w."
      register_T1w_to_PAM50 ${file_t1}.nii.gz
    else
      echo "T2w excluded and T1w not found. Skipping subject ${SUBJECT}."
      continue
    fi

  # If T2w is not in the exclude list, proceed with T2w registration
  else
    echo "Proceeding registration to PAM50 with top T2w file."
    #register_T2w_to_PAM50 ${file_t2}.nii.gz
  fi

# If top T2w does not exist, check if top T1w exists
elif [[ -f "${PATH_DATA}/${SUBJECT}/anat/${file_t1}.nii.gz" ]]; then
  echo "No top T2w file found for subject ${SUBJECT}. Using top T1w instead."
  register_T1w_to_PAM50 ${file_t1}.nii.gz

# Skip subject if no top T1w or T2w file found
else
  echo "No top T2w or T1w file found for subject ${SUBJECT}. Skipping."
  continue
fi

# Perform registration of mean moco DTI data to and from the PAM50 template
echo "------------------ Registration of DTI data with PAM50 template for ${SUBJECT} ------------------ "
register_PAM50_to_DWI ${file_dwi}.nii.gz

# Extract DTI metrics using the PAM50 atlas
echo "------------------ Extracting DTI metrics using the PAM50 atlas for ${SUBJECT} ------------------ "
extract_DTI_metrics ${file_dwi}.nii.gz

# Display useful info for the log
end=`date +%s`
runtime=$((end-start))
echo
echo "~~~"
echo "SCT version: `sct_version`"
echo "Ran on:      `uname -nsr`"
echo "Duration:    $(($runtime / 3600))hrs $((($runtime / 60) % 60))min $(($runtime % 60))sec"
echo "~~~"