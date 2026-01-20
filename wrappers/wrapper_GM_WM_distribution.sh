#!/bin/bash
set -e  # Exit if any command fails

# Wrapper to run `GM_WM_distribution.py`` per subject for use with `sct_run_batch`

# Usage : 
#
# cd /path/to/pediatric_SC_morphometrics
#
# sct_run_batch \
#   -config config/config.json
#   -script wrappers/wrapper_GM_WM_distribution.sh \

# Variables provided by sct_run_batch:
# - PATH_DATA
# - PATH_OUTPUT
# - SUBJECT

# Get subject
SUBJECT=$1

echo "Running subject: ${SUBJECT}"
echo "Using data path: ${PATH_DATA}"
echo "Using output path: ${PATH_RESULTS}"

# Check for required vars
if [[ -z "${SUBJECT}" ]]; then
    echo "ERROR: SUBJECT variable is not set."
    exit 1
fi

# Define paths
SUBJECT_DIR="${PATH_DATA}/derivatives/labels/${SUBJECT}/anat"

# Define the suffix for the T2w files (with `run-01` if applicable)
if [[ -e "${PATH_DATA}/${SUBJECT}/anat/${SUBJECT}_run-01_T2starw.nii.gz" ]]; then
  T2star_FILE=${SUBJECT}_run-01_T2starw
elif [[ -e "${PATH_DATA}/${SUBJECT}/anat/${SUBJECT}_T2starw.nii.gz" ]]; then
  T2star_FILE=${SUBJECT}_T2starw
else
    echo "T2wstar file not found for subject ${SUBJECT}. Skipping."
fi

# Run GM_WM_distribution.py
python "scripts/analysis/GM_WM_distribution.py" \
    --subject "${SUBJECT}" \
    --data-path "${PATH_DATA}" \
    --path-output "${PATH_RESULTS}" \
    --subject-dir "${SUBJECT_DIR}" \
    --file-t2star "${T2star_FILE}" \