# Data analysis pipeline for the pediatric spinal cord

## Project description

This repository contains pipelines for pediatric spinal cord data analysis. It includes both a pipeline to extract and analyze spinal cord morphometrics (using T2w and T2*w data), as well as a pipeline for DTI analysis using DWI data.  

For this project, MRI data from the [philadelphia-pediatric](https://data.neuro.polymtl.ca/datasets/philadelphia-pediatric) dataset was used, which includes typically-developing subjects aged 6 to 17. 

## Dependencies

To run the scripts in this repository, you will need the following installed or cloned on your local computer:
- The [Spinal Cord Toolbox (SCT)](https://spinalcordtoolbox.com/), version 7.0
- A local clone of the [spinal cord rootlet segmentation model](https://github.com/ivadomed/model-spinal-rootlets) (release [r20250318](https://github.com/ivadomed/model-spinal-rootlets/releases/tag/r20250318))
- [`yq`](https://github.com/mikefarah/yq), to process an `exclude.yml` file to exclude subjects from the analysis

## Usage

### 1. Modify the contents of the configuration files

To execute the scripts in this repo, you will need the following configuration files, located inside the `config` folder :
- `config_morphometrics.yaml` : configuration file to process morphometrics
- `config_rootlets.yaml` : configuration file to process spinal rootlets

> [!Note]
> Template versions of these configuration files are provided in the `config` folder, with a `_template` suffix. Before running the scripts, rename each config file by removing the `_template` suffix.

Inside the configuration files, you will need to set the following parameters:

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
> [!Tip]
> To find the exact path to `venv_sct` on your system, run `conda env list` to display all conda environments

To run the scripts described in the following sections, make sure to change your directory to the project’s repository in your terminal:
```
cd path/to/your/local/clone/pediatric_data-analysis
```

# Morphometric analysis 

### 1. T2w data preprocessing

The script `T2w_data_preprocessing.sh` (inside `scripts/preprocessing`) performs the following preprocessing steps on the T2w data : 
- Segmentation of spinal cord from T2w data (sct_deepseg_sc)
- Detection of PMJ from T2w data (sct_detect_pmj)
- Labeling of vertebral levels from T2w data (sct_label_vertebrae)
- Segmentation of rootlets from T2w data (model-spinal-rootlets_ventral_D106_r20250318)

In order to run the script in parallel, the `sct_run_batch` command can be used as follows :
```
sct_run_batch -config config/config_preprocessing.yaml -script scripts/preprocessing/T2w_data_preprocessing.sh
```

### 2. Extract morphometrics

The script `morphometrics.py` (inside `scripts/analysis`) allows to :
- Get the labeled segmentation from the disc labels on the preprocessed T2w data (using [`sct_label_vertebrae`](https://spinalcordtoolbox.com/stable/user_section/tutorials/vertebral-labeling/sct_label_vertebrae.html))
- Run sct_process_segmentation to compute spinal cord morphometrics (cross-sectional area, diameter, etc.)

To run this python script in pararallel, you can use the bash wrapper called `wrapper_morphometrics.sh` inside the `sct_run_batch` command :
```
sct_run_batch -config config/config.yaml -script wrappers/wrapper_morphometrics.sh
```

### 3. Process rootlets

The script `rootlets.py` (inside `scripts/analysis`) :
- Runs `zeroing_false_positive_rootlets.py` from the model-spinal-rootlets/pediatric_rootlets directory to remove false positive rootlets below the Th1 level.
- Runs `02a_rootlets_to_spinal_levels.py` from the model-spinal-rootlets/inter-rater_variability directory to extract spinal levels from the rootlets segmentation
- Extracts the center of mass of each spinal level and saves it in a CSV file

The `wrapper_rootlets.sh` wrapper can be used to run the `rootlets.py` script in parallel with `sct_run_batch` : 
```
sct_run_batch -config config/config.yaml -script wrappers/wrapper_rootlets.sh
```

### 4. Gray matter and white matter distribution with T2*w data

The script `GM_WM_distribution.py` (inside `scripts/analysis`) extracts the CSA of GM and WM in the native T2*w space, at each spinal level along the spinal cord. 

It requires as inputs (in the native T2*w space):
- T2*-weighted image (in the native space)
- The spinal cord segmentation 
- The gray matter segmentation
- The white matter segmentation 
- Single-voxel point labels for the start and end of each spinal level (registered from the spinal levels in the T2w space)

To extract GM and WM CSA in the native T2*w, the script:
- Gets the slices corresponding to the start and end (inferior and superior limits) of each spinal level from the single-voxel point labels
- Computes the slices between these start and end slices for each spinal level to get the slice range corresponding to each spinal level in the T2*w space
- Runs `sct_process_segmentation` (for each spinal level) to compute the CSA of GM, WM and SC (using the `-z` flag to define the slice range)

For each subject, an output CSV file are saved in `results/tables/GM_WM_distribution/` within folders `WM`, `GM` and `SC`. 

The `wrapper_GM_WM_distribution.sh` wrapper can be used to run the `GM_WM_distribution.py` script in parallel with `sct_run_batch` : 
```
sct_run_batch -config config/config.yaml -script wrappers/wrapper_GM_WM_distribution.sh
```

### 5. Plots

Inside `results/plots`, the following jupyter notebooks contain code to generate figures related to pediatric spinal cord morphometrics:
- `morphometrics.ipynb` : figures for CSA analysis, right-left (RL) and antero-posterior (AP) diameters, etc. 
- `WMGM_distribution_figures.ipynb` : figures for WM/GM distribution analysis
- `generate_figure_rootlets_and_vertebral_spinal_levels.py` : figure to compare spinal levels with vertebral levels (with their distances from the PMJ)
- `get_distributions_and_sizes_vertebral_spinal_levels.py` : figure to plot the distribution of spinal and vertebral levels (approximated by normal distributions)

The script `generate_figure_rootlets_and_vertebral_spinal_levels.py` contains code to generate figures comparing the correspondence between vertebral and spinal levels. 


# DTI analysis 

### 1. Diffusion-weighted imaging (DWI) data preprocessing

The script `dwi_data_preprocessing.sh` (inside `scripts/preprocessing`) performs the following preprocessing steps on the DWI data: 
- Generate the mean DWI image
- Spinal cord segmentation
- Motion correction 
- Compute DTI metrics 
- Registration of T2w (or T1w) data to the PAM50 template (to generate initialization warping fields for DWI registration). 
- Registration of the PAM50 template to the DWI space
- Extract DTI metrics using the PAM50 atlas registered to the DWI space

In order to run the script in parallel, the `sct_run_batch` command can be used as follows :
```
sct_run_batch -config config/config_preprocessing.yaml -script scripts/preprocessing/dwi_data_preprocessing.sh
```

### 2. Plots

Inside `results/plots`, the jupyter notebook `DWI_figures.ipynb` contains code to generate figures related to DTI analysis. 
