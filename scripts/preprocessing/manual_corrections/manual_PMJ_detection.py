import os
import argparse
from spinalcordtoolbox.scripts import sct_label_utils

"""
Script to compute manual detection of PMJ using sct_label_utils. 

Example usage:
python script.py -i /path/to/data -s sub-001
"""

def main(data_path, subject):
    print(f'Manual PMJ detection for {subject}')

    output_dir = os.path.join(data_path, 'derivatives', 'labels', subject, 'anat')
    os.makedirs(output_dir, exist_ok=True)

    T2w_image = None
    PMJlabel = None

    # Possible file patterns
    candidates = [
        ("rec-composed_T2w", f"{subject}_rec-composed_T2w_label-PMJ_dlabel.nii.gz"),
        ("acq-top_T2w", f"{subject}_acq-top_T2w_label-PMJ_dlabel.nii.gz"),
        ("acq-top_run-1_T2w", f"{subject}_acq-top_run-1_T2w_label-PMJ_dlabel.nii.gz"),
    ]

    for suffix, label_name in candidates:
        t2_path = os.path.join(data_path, subject, "anat", f"{subject}_{suffix}.nii.gz")
        if os.path.exists(t2_path):
            T2w_image = t2_path
            PMJlabel = os.path.join(output_dir, label_name)
            break

    if T2w_image is None:
        raise ValueError(f"No valid T2w image found for {subject}")

    print(f"Using image: {T2w_image}")
    print(f"Output label: {PMJlabel}")

    sct_label_utils.main([
        '-i', T2w_image,
        '-create-viewer', '1',
        '-o', PMJlabel
    ])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manual PMJ detection (single subject)")
    parser.add_argument("-i", "--data-path", required=True, help="Path to dataset")
    parser.add_argument("-s", "--subject", required=True, help="Subject ID (e.g., sub-001)")

    args = parser.parse_args()

    main(args.data_path, args.subject)