# Data analysis pipeline for the pediatric spinal cord

## Project description

This repository contains a pipeline for pediatric spinal cord data analysis. 

For this project, MRI data from the [philadelphia-pediatric](https://data.neuro.polymtl.ca/datasets/philadelphia-pediatric) dataset was used, which includes typically-developing subjects aged 6 to 17. 

## Dependencies

To run the scripts in this repository, you will need the following installed or cloned on your local computer:
- The [Spinal Cord Toolbox (SCT)](https://spinalcordtoolbox.com/), version 7.0
- A local clone of the [spinal cord rootlet segmentation model](https://github.com/ivadomed/model-spinal-rootlets) (release [r20250318](https://github.com/ivadomed/model-spinal-rootlets/releases/tag/r20250318))

## Usage

### 1. Modify the contents of the configuration files

To execute the scripts in this repo, you will need the following configuration files, located inside the `config` folder :
- `config_morphometrics.yaml` : configuration file to process morphometrics
- `config_rootlets.yaml` : configuration file to process spinal rootlets

Templates versions of these configuration files are provided in the `config` folder, with a `_template` suffix. Before running the scripts, rename each config file by removing the `_template` suffix. Inside each configuration file, you will need to set the following parameters:

- `path_data` : the path to your local copy of the dataset
- `path_output` : the path to where you want the output results saved
- `jobs` : the number of cores you want to use to run subjects in parallel
- `script_args` : the path to your local clone of the [spinal cord rootlet segmentation model (r20250318)](https://github.com/ivadomed/model-spinal-rootlets)
- `include_list`: the list of subjects you want to process

### 2. Activate SCT's virtual environment and change directory
To run the scripts in this repository, you first need to activate the Spinal Cord Toolbox (SCT) virtual environment named venv_sct. You can activate it with the following command:
```
conda activate /path/to/your/venv_sct
```
*To find the exact path to venv_sct on your system, run `conda env list` to display all conda environments

To run the scripts described in the following sections, make sure to change your directory to the project’s repository in your terminal:
```
cd path/to/your/local/clone/pediatric_SC_morphometrics
```

### 3. T2w data preprocessing

The script `T2w_data_preprocessing.sh` (inside `scripts/preprocessing`) performs the following preprocessing steps on the dataset : 
- Segmentation of spinal cord from T2w data (sct_deepseg_sc)
- Detection of PMJ from T2w data (sct_detect_pmj)
- Labeling of vertebral levels from T2w data (sct_label_vertebrae)
- Segmentation of rootlets from T2w data (model-spinal-rootlets_ventral_D106_r20250318)

In order to run the script in parallel, the `sct_run_batch` command can be used as follows :
```
sct_run_batch -config config/config_preprocessing.yaml -script scripts/preprocessing/pediatric_data_preprocessing.sh
```

### 4. Extract morphometrics

The script `morphometrics.py` (inside `scripts/extract_metrics`) allows to :
- Get the labeled segmentation from the disc labels (using [`sct_label_vertebrae`](https://spinalcordtoolbox.com/stable/user_section/tutorials/vertebral-labeling/sct_label_vertebrae.html))
- Run sct_process_segmentation to compute spinal cord morphometrics (cross-sectional area, diameter, etc.)

To run this python script in pararallel, you can use the bash wrapper called `wrapper_morphometrics.sh` inside the `sct_run_batch` command :
```
sct_run_batch -config config/config.yaml -script wrappers/wrapper_morphometrics.sh
```

### 5. Process rootlets

The script `rootlets.py` (inside `scripts/extract_metrics`) :
- Runs `zeroing_false_positive_rootlets.py` from the model-spinal-rootlets/pediatric_rootlets directory to remove false positive rootlets below the Th1 level.
- Runs `02a_rootlets_to_spinal_levels.py` from the model-spinal-rootlets/inter-rater_variability directory to extract spinal levels from the rootlets segmentation
- Extracts the center of mass of each spinal level and saves it in a CSV file

The `wrapper_rootlets.sh` wrapper can be used to run the `rootlets.py` script in parallel with `sct_run_batch` : 
```
sct_run_batch -config config/config.yaml -script wrappers/wrapper_rootlets.sh
```