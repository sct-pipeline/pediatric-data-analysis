#!/bin/bash
set -e  # Exit if any command fails

# Wrapper to run `rootlets.py`` per subject for use with `sct_run_batch`

# Usage : 
#
# cd /path/to/pediatric_SC_morphometrics
#
# sct_run_batch \
#   -config config/config.json
#   -script wrappers/wrapper_rootlets.sh \

# Variables provided by sct_run_batch:
# - PATH_DATA
# - SUBJECT
# - ROOTLETS_MODEL_DIR

# Get subject
SUBJECT=$1

# Get rootlets model directory
ROOTLETS_MODEL_DIR=$2

echo "Running subject: ${SUBJECT}"
echo "Using data path: ${PATH_DATA}"

# Check for required vars
if [[ -z "${SUBJECT}" ]]; then
    echo "ERROR: SUBJECT variable is not set."
    exit 1
fi

if [ -z "${ROOTLETS_MODEL_DIR}" ]; then
  echo "ERROR: ROOTLETS_MODEL_DIR is not set."
  exit 1
fi

# Define paths
SUBJECT_DIR="${PATH_DATA}/derivatives/labels/${SUBJECT}/anat"

# Define T2 acq-top file prefix
T2_FILE=${SUBJECT}_acq-top_run-1_T2w

# Run rootlets.py
python "scripts/analysis/rootlets.py" \
    --subject "${SUBJECT}" \
    --subject-dir "${SUBJECT_DIR}" \
    --data-path "${PATH_DATA}" \
    --file-t2 "${T2_FILE}" \
    --rootlets-model-dir "${ROOTLETS_MODEL_DIR}"
