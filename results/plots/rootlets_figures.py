import sys
import subprocess
import argparse
import numpy as np
import os
import shutil
import pandas as pd
from spinalcordtoolbox.scripts import sct_label_utils
from spinalcordtoolbox.image import Image

"""
This script generates figures to compare the correspondence between spinal and vertebral levels, by running the following scripts using the csv files inside `results/tables/rootlets` (which are obtained by running
the `rootlets.py` script inside `scripts/analysis`): 

- `generate_figure_rootlets_and_vertebral_spinal_levels.py`
- `get_distributions_and_sizes_vertebral_spinal_levels.py`

Usage : 
        python results/plots/rootlets_figures.py -participants path/to/participants.tsv 

Author: Samuelle St-Onge

"""

def main(participants):
    #Generate figure for all subjects (male + female)
    subprocess.run([
        sys.executable,
        os.path.join(f'results/plots/', "generate_figure_rootlets_and_vertebral_spinal_levels.py"),
        "-i", 'results/tables/rootlets', # path to pmj distance csv files
        "-participants", participants
    ], check=True)

    # Generate figure for female subjects only
    subprocess.run([
        sys.executable,
        os.path.join(f'results/plots/', "generate_figure_rootlets_and_vertebral_spinal_levels.py"),
        "-i", 'results/tables/rootlets', # path to pmj distance csv files
        "-participants", participants,
        '-sex', 'F'
    ], check=True)

    # Generate figure for male subjects only 
    subprocess.run([
        sys.executable,
        os.path.join(f'results/plots/', "generate_figure_rootlets_and_vertebral_spinal_levels.py"),
        "-i", 'results/tables/rootlets', # path to pmj distance csv files
        "-participants", participants,
        '-sex', 'M'
    ], check=True)

    # Generate figure illustrating spinal and vertebral levels distribution 
    subprocess.run([
        sys.executable,
        os.path.join(f'results/plots/', "get_distributions_and_sizes_vertebral_spinal_levels.py"),
        "-i", 'results/tables/rootlets', # path to pmj distance csv files
        "-o", 'results/figures', 
        "-participants", participants,
        "-normalised", "n"
    ], check=True)

    # Generate figure showing vertebral/spinal level midpoint distance vs. Age, and vs. Height
    subprocess.run([
        sys.executable,
        os.path.join(f'results/plots/', "generate_figure_level_midpoint_differences.py"),
        "--csv_file", 'results/tables/rootlets/distance_by_participant_and_level.csv', 
        "--output_dir", 'results/figures', 
    ], check=True)
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run rootlets processing for one subject")
    parser.add_argument("--participants", required=True, help="Path to participants.tsv file")
    args = parser.parse_args()

    main(args.participants)