#!/bin/bash
set -e  # Exit if any command fails

# Wrapper to run `rootlets.py`` per subject for use with `sct_run_batch`

# Usage : 
#
# cd /path/to/pediatric_SC_morphometrics
#
# sct_run_batch \
#   -config config/config.json
#   -script wrappers/wrapper_morphometrics.sh \

# Variables provided by sct_run_batch:
# - PATH_DATA
# - PATH_OUTPUT
# - SUBJECT

# Get subject
SUBJECT=$1

echo "Running subject: ${SUBJECT}"
echo "Using data path: ${PATH_DATA}"
echo "Using output path: ${PATH_OUTPUT}"

# Check for required vars
if [[ -z "${SUBJECT}" ]]; then
    echo "ERROR: SUBJECT variable is not set."
    exit 1
fi

# Define paths
SUBJECT_DIR="${PATH_DATA}/derivatives/labels/${SUBJECT}/anat"

# Define T2 file prefixes for composed and top acquisition T2 files 
T2_FILE_COMPOSED=${SUBJECT}_rec-composed_T2w
T2_FILE_TOP=${SUBJECT}_acq-top_run-1_T2w

# Check if composed T2w file exists
if [ -f "${PATH_DATA}/${SUBJECT}/anat/${T2_FILE_COMPOSED}.nii.gz" ]; then
    T2_FILE=${T2_FILE_COMPOSED}
else
    # Check if top acquisition exists
    if [ -f "${PATH_DATA}/${SUBJECT}/anat/${T2_FILE_TOP}.nii.gz" ]; then
        T2_FILE=${T2_FILE_TOP}
        echo "Composed T2w file not found. Proceeding with top T2w file."
    else
        echo "Neither composed nor top T2w file found for subject ${SUBJECT}. Skipping."
        continue  # Skip to the next subject
    fi
fi

# Run rootlets.py
python "scripts/extract_metrics/morphometrics.py" \
    --subject "${SUBJECT}" \
    --data-path "${PATH_DATA}" \
    --output-path "${PATH_OUTPUT}" \
    --subject-dir "${SUBJECT_DIR}" \
    --file-t2 "${T2_FILE}" \