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

# Substract the gray matter segmentation from the spinal cord segmentation to get the white matter segmentation
get_wm_seg(){
  # Input
  SC_SEG_FILE="${PATH_DERIVATIVES}/labels/${SUBJECT}/anat/${file_t2star}_label-SC_mask.nii.gz"
  GM_SEG_FILE="${PATH_DERIVATIVES}/labels/${SUBJECT}/anat/${file_t2star}_label-GM_mask.nii.gz"
  # Output
  WM_SEG_FILE="${PATH_DERIVATIVES}/labels/${SUBJECT}/anat/${file_t2star}_label-WM_mask.nii.gz"
  echo "Looking for manual segmentation: $SEG_PATH"
  if [[ -e $WM_SEG_FILE ]]; then
    echo "Found WM segmentation."
    sct_maths -i ${SC_SEG_FILE} -sub ${GM_SEG_FILE} -o ${WM_SEG_FILE}
  else
    echo "WM segmentation not found. Proceeding with automatic segmentation."
    # Substract gray matter from spinal cord to get white matter
    sct_maths -i ${SC_SEG_FILE} -sub ${GM_SEG_FILE} -o ${WM_SEG_FILE}
  fi
}

# Generate T2*w <--> PAM50 warping fields and register PAM50 template to T2*w space 
register_PAM50_to_T2star(){
  # Inputs
  T2star_FILE="${PATH_DATA}/${SUBJECT}/anat/${file_t2star}.nii.gz"
  T2star_SEG_FILE="${file_t2star}_label-SC_mask"
  T2star_SEG_PATH="${PATH_DERIVATIVES}/labels/${SUBJECT}/anat/${T2star_SEG_FILE}.nii.gz"
  WARP_T2="${PATH_DERIVATIVES}/PAM50_registration/${SUBJECT}/anat/warp_template2anat.nii.gz"
  WARP_INV_T2="${PATH_DERIVATIVES}/PAM50_registration/${SUBJECT}/anat/warp_anat2template.nii.gz"
  # Outputs
  WARP_T2star="${PATH_DERIVATIVES}/PAM50_registration/${SUBJECT}/anat/t2star/warp_template2t2star.nii.gz"
  WARP_INV_T2star="${PATH_DERIVATIVES}/PAM50_registration/${SUBJECT}/anat/t2star/warp_t2star2template.nii.gz"
  
  if [[ -e "${PATH_DERIVATIVES}/PAM50_registration/${SUBJECT}/anat/T2star/reg.nii.gz" ]]; then
    echo "Found T2star registration files. Skipping."
  else
    # Generate the T2*w <--> PAM50 warping fields (with the T2w <--> PAM50 warping fields as initialization)
    echo "Not found. Generating warping fields for T2*w with PAM50 template"
    sct_register_multimodal -i "${SCT_DIR}/data/PAM50/template/PAM50_t2.nii.gz" \
                            -iseg "${SCT_DIR}/data/PAM50/template/PAM50_cord.nii.gz" \
                            -d ${T2star_FILE} \
                            -dseg ${T2star_SEG_PATH} \
                            -initwarp ${WARP_T2} \
                            -initwarpinv ${WARP_INV_T2} \
                            -owarp ${WARP_T2star} \
                            -owarpinv ${WARP_INV_T2star} \
                            -param step=1,type=seg,algo=centermass:step=2,type=seg,algo=bsplinesyn,slicewise=1,iter='5'  \
                            -qc ${QC_PATH} \
                            -ofolder "${PATH_DERIVATIVES}/PAM50_registration/${SUBJECT}/anat/t2star/"
  
    # Register template PAM50 to the DWI subject space (to extract metrics in the subject space with the PAM50 atlas)
    echo "Registering the PAM50 template to the T2star subject space"
    sct_warp_template -d ${T2star_FILE} -w ${WARP_T2star} -qc ${QC_PATH} -o "${PATH_DERIVATIVES}/PAM50_registration/${SUBJECT}/anat/t2star"
  
  fi
}

# Run sct_process_segmentation for the spinal cord, white matter and gray matter segmentations
compute_WMGM_CSA(){

  # Define output directory to save extracted metrics
  REPO_ROOT=$(git rev-parse --show-toplevel)
  mkdir -p "${REPO_ROOT}/results/tables/WMGM_distribution/SC"
  mkdir -p "${REPO_ROOT}/results/tables/WMGM_distribution/WM"
  mkdir -p "${REPO_ROOT}/results/tables/WMGM_distribution/GM"
  
  # Inputs
  T2STAR_SC_SEG="${PATH_DERIVATIVES}/labels/${SUBJECT}/anat/${file_t2star}_label-SC_mask.nii.gz" 
  T2STAR_WM_SEG="${PATH_DERIVATIVES}/labels/${SUBJECT}/anat/${file_t2star}_label-WM_mask.nii.gz" 
  T2STAR_GM_SEG="${PATH_DERIVATIVES}/labels/${SUBJECT}/anat/${file_t2star}_label-GM_mask.nii.gz" 
  VERT_LEVELS="${PATH_DERIVATIVES}/PAM50_registration/${SUBJECT}/anat/t2star/template/PAM50_spinal_levels.nii.gz"
  # Outputs
  CSV_SC_CSA="${REPO_ROOT}/results/tables/WMGM_distribution/SC/${SUBJECT}_SC_CSA.csv"
  CSV_WM_CSA="${REPO_ROOT}/results/tables/WMGM_distribution/WM/${SUBJECT}_WM_CSA.csv"
  CSV_GM_CSA="${REPO_ROOT}/results/tables/WMGM_distribution/GM/${SUBJECT}_GM_CSA.csv"
  
  if [[ -e "" ]]; then
    echo "Found csv files for WM and GM CSA. Skipping subject ${SUBJECT}."
  else
    # Compute CSA for the spinal cord mask
    echo "Computing spinal cord CSA for ${SUBJECT}"
    sct_process_segmentation -i ${T2STAR_SC_SEG} -o ${CSV_SC_CSA} -vert "2:5" -perlevel 1 -vertfile ${VERT_LEVELS} -append 1 -angle-corr 0      # Add C2 to C5
    sct_process_segmentation -i ${T2STAR_SC_SEG} -o ${CSV_SC_CSA} -vert "2:5" -perlevel 0 -vertfile ${VERT_LEVELS} -append 1 -angle-corr 0      # Add C2:C5 mean

    # Compute CSA for the white matter mask
    echo "Computing white matter CSA for ${SUBJECT}"
    sct_process_segmentation -i ${T2STAR_WM_SEG} -o ${CSV_WM_CSA} -vert "2:5" -perlevel 1 -vertfile ${VERT_LEVELS} -append 1 -angle-corr 0      # Add C2 to C5
    sct_process_segmentation -i ${T2STAR_WM_SEG} -o ${CSV_WM_CSA} -vert "2:5" -perlevel 0 -vertfile ${VERT_LEVELS} -append 1 -angle-corr 0      # Add C2:C5 mean

    # Compute CSA for the gray matter mask
    echo "Computing gray matter CSA for ${SUBJECT}"
    sct_process_segmentation -i ${T2STAR_GM_SEG} -o ${CSV_GM_CSA} -vert "2:5" -perlevel 1 -vertfile ${VERT_LEVELS} -append 1 -angle-corr 0      # Add C2 to C5
    sct_process_segmentation -i ${T2STAR_GM_SEG} -o ${CSV_GM_CSA} -vert "2:5" -perlevel 0 -vertfile ${VERT_LEVELS} -append 1 -angle-corr 0      # Add C2:C5 mean
  
  fi
}

# SCRIPT STARTS HERE
# ==============================================================================
# Display useful info for the log, such as SCT version, RAM and CPU cores available
sct_check_dependencies -short

# Define the suffix for the T2*w files (with `run-1` or `run-2`)
if [[ -e "${PATH_DATA}/${SUBJECT}/anat/${SUBJECT}_run-01_T2starw.nii.gz" ]]; then
  file_t2star=${SUBJECT}_run-01_T2starw
elif [[ -e "${PATH_DATA}/${SUBJECT}/anat/${SUBJECT}_T2starw.nii.gz" ]]; then
  file_t2star=${SUBJECT}_T2starw
fi

# Generate the labeled segmentation (with the vertebral disc labels)
echo "------------------ Generating the spinal cord segmentation for ${SUBJECT} ------------------ "
#segment_sc ${file_t2star}.nii.gz

# Generate the labeled segmentation (with the vertebral disc labels)
echo "------------------ Generating the gray matter segmentation for ${SUBJECT} ------------------ "
#segment_gm ${file_t2star}.nii.gz

# Substract the gray matter segmentation from the spinal cord segmentation to get the white matter segmentation
echo "------------------ Computing the white matter segmentation for ${SUBJECT} ------------------ "
#get_wm_seg ${file_t2star}.nii.gz

# Perform registration of the PAM50 template to the T2*w data
echo "------------------ Registration of PAM50 template to the T2*w data for ${SUBJECT} ------------------ "
#register_PAM50_to_T2star ${file_t2star}.nii.gz

# Compute CSA for the spinal cord, white matter and gray matter masks
echo "------------------ Computing SC, WM and GM cross-sectional area (CSA) per vertebral level for ${SUBJECT} ------------------ "
compute_WMGM_CSA ${file_t2star}.nii.gz

# Display useful info for the log
end=`date +%s`
runtime=$((end-start))
echo
echo "~~~"
echo "SCT version: `sct_version`"
echo "Ran on:      `uname -nsr`"
echo "Duration:    $(($runtime / 3600))hrs $((($runtime / 60) % 60))min $(($runtime % 60))sec"
echo "~~~"