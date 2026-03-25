#!/usr/bin/env bash

SUBJECT=$1

echo "Running subject: ${SUBJECT}"
echo "Using data path: ${PATH_DATA}"

python scripts/preprocessing/manual_corrections/manual_PMJ_detection.py \
    --subject "${SUBJECT}" \
    --data-path "${PATH_DATA}"