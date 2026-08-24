#!/usr/bin/env python

# The script is used to generate figures showing the difference between
# the midpoint of pairs of vertebral and spinal levels.
#
# Usage:
#     python generate_figure_level_midpoint_differences.py \
#         --csv_file /path/to/distance_by_participant_and_level.csv \
#         --output_dir /path/to/output
#
# Author : Samuelle St-Onge

import argparse
import os

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import statsmodels.formula.api as smf


def plot_midpoint_distance_relationships(csv_file, output_dir):
    """
    Generate figures showing the relationship between vertebral/spinal
    level midpoint distance and age, and midpoint distance and height.

    One subplot is generated for each vertebral/spinal level pair.

    Models:
        1. Midpoint distance ~ age
        2. Midpoint distance ~ height + age
    """

    # =========================================================
    # Create output directory
    # =========================================================

    os.makedirs(output_dir, exist_ok=True)

    # =========================================================
    # Load data
    # =========================================================

    df = pd.read_csv(csv_file)

    # Make sure columns are numeric
    df["age"] = pd.to_numeric(df["age"], errors="coerce")
    df["height"] = pd.to_numeric(df["height"], errors="coerce")
    df["midpoint_distance"] = pd.to_numeric(
        df["midpoint_distance"],
        errors="coerce"
    )

    # Remove rows with missing values
    df = df.dropna(
        subset=[
            "age",
            "height",
            "midpoint_distance"
        ]
    ).copy()

    print(f"Number of observations: {len(df)}")

    # =========================================================
    # Define level pairs
    # =========================================================

    level_pairs = [
        ("Vertebral level C2", "Spinal level C3"),
        ("Vertebral level C3", "Spinal level C4"),
        ("Vertebral level C4", "Spinal level C5"),
        ("Vertebral level C5", "Spinal level C6"),
        ("Vertebral level C6", "Spinal level C7"),
        ("Vertebral level C7", "Spinal level C8"),
        ("Vertebral level T1", "Spinal level T1"),
    ]

    # =========================================================
    # Plotting style
    # =========================================================

    sns.set_theme(
        style="whitegrid",
        context="talk"
    )

    # =========================================================
    # FIGURE 1: MIDPOINT DISTANCE VS AGE
    # =========================================================

    fig, axes = plt.subplots(
        nrows=4,
        ncols=2,
        figsize=(14, 22)
    )

    axes = axes.flatten()

    print("\n")
    print("==============================================")
    print("OLS MODELS: MIDPOINT DISTANCE ~ AGE")
    print("==============================================")

    for i, (vertebral_level, spinal_level) in enumerate(level_pairs):

        ax = axes[i]

        # -----------------------------------------------------
        # Select the current level pair
        # -----------------------------------------------------

        pair_df = df[
            (df["vertebral_level"] == vertebral_level)
            & (df["spinal_level"] == spinal_level)
        ].copy()

        # -----------------------------------------------------
        # Check that data exist
        # -----------------------------------------------------

        if len(pair_df) < 3:
            ax.text(
                0.5,
                0.5,
                "Not enough data",
                ha="center",
                va="center",
                transform=ax.transAxes
            )

            ax.set_title(
                f"{vertebral_level.replace('Vertebral level ', '')} "
                f"/ "
                f"{spinal_level.replace('Spinal level ', '')}"
            )

            continue

        # -----------------------------------------------------
        # OLS model
        # -----------------------------------------------------

        model_age = smf.ols(
            formula="midpoint_distance ~ age",
            data=pair_df
        ).fit()

        print(
            f"\n{vertebral_level} vs {spinal_level}"
        )
        print(
            f"N = {len(pair_df)}"
        )
        print(
            f"p-age = {model_age.pvalues['age']:.4g}"
        )

        # -----------------------------------------------------
        # Plot
        # -----------------------------------------------------

        sns.regplot(
            data=pair_df,
            x="age",
            y="midpoint_distance",
            scatter_kws={
                "alpha": 0.5,
                "s": 40
            },
            line_kws={
                "color": "red",
                "linewidth": 2
            },
            ax=ax
        )

        # -----------------------------------------------------
        # Labels
        # -----------------------------------------------------

        ax.set_xlabel("Age")
        ax.set_ylabel("Midpoint distance")

        ax.set_title(
            f"{vertebral_level.replace('Vertebral level ', '')} "
            f"/ "
            f"{spinal_level.replace('Spinal level ', '')}"
        )

        # -----------------------------------------------------
        # Statistics
        # -----------------------------------------------------

        text = (
            f"N = {len(pair_df)}\n"
            f"p = {model_age.pvalues['age']:.3g}"
        )

        ax.text(
            0.05,
            0.95,
            text,
            transform=ax.transAxes,
            verticalalignment="top",
            bbox=dict(
                boxstyle="round",
                facecolor="white",
                alpha=0.8
            )
        )

    # Remove unused subplot
    axes[-1].axis("off")

    fig.suptitle(
        "Midpoint distance vs Age",
        fontsize=22,
        y=0.995
    )

    plt.tight_layout()

    age_figure = os.path.join(
        output_dir,
        "midpoint_distance_vs_age_by_level.png"
    )

    plt.savefig(
        age_figure,
        dpi=300,
        bbox_inches="tight"
    )

    plt.close()

    print(
        f"\nSaved figure: {age_figure}"
    )

    # =========================================================
    # FIGURE 2: MIDPOINT DISTANCE VS HEIGHT + AGE
    # =========================================================

    fig, axes = plt.subplots(
        nrows=4,
        ncols=2,
        figsize=(14, 22)
    )

    axes = axes.flatten()

    print("\n")
    print("====================================================")
    print("OLS MODELS: MIDPOINT DISTANCE ~ HEIGHT + AGE")
    print("====================================================")

    for i, (vertebral_level, spinal_level) in enumerate(level_pairs):

        ax = axes[i]

        # -----------------------------------------------------
        # Select current level pair
        # -----------------------------------------------------

        pair_df = df[
            (df["vertebral_level"] == vertebral_level)
            & (df["spinal_level"] == spinal_level)
        ].copy()

        # -----------------------------------------------------
        # Check data
        # -----------------------------------------------------

        if len(pair_df) < 3:
            ax.text(
                0.5,
                0.5,
                "Not enough data",
                ha="center",
                va="center",
                transform=ax.transAxes
            )

            ax.set_title(
                f"{vertebral_level.replace('Vertebral level ', '')} "
                f"/ "
                f"{spinal_level.replace('Spinal level ', '')}"
            )

            continue

        # -----------------------------------------------------
        # OLS model
        # -----------------------------------------------------

        model_height = smf.ols(
            formula="midpoint_distance ~ height + age",
            data=pair_df
        ).fit()

        print(
            f"\n{vertebral_level} vs {spinal_level}"
        )
        print(
            f"N = {len(pair_df)}"
        )
        print(
            f"p-height = {model_height.pvalues['height']:.4g}"
        )
        print(
            f"p-age = {model_height.pvalues['age']:.4g}"
        )

        # -----------------------------------------------------
        # Scatterplot
        # -----------------------------------------------------

        sns.scatterplot(
            data=pair_df,
            x="height",
            y="midpoint_distance",
            alpha=0.5,
            s=40,
            ax=ax
        )

        # -----------------------------------------------------
        # Generate age-adjusted predictions
        # -----------------------------------------------------

        height_range = np.linspace(
            pair_df["height"].min(),
            pair_df["height"].max(),
            100
        )

        prediction_df = pd.DataFrame({
            "height": height_range,
            "age": pair_df["age"].mean()
        })

        predictions = model_height.get_prediction(
            prediction_df
        ).summary_frame(alpha=0.05)

        # -----------------------------------------------------
        # Plot adjusted regression line
        # -----------------------------------------------------

        ax.plot(
            height_range,
            predictions["mean"],
            color="red",
            linewidth=2,
            label="Adjusted for age"
        )

        # 95% confidence interval
        ax.fill_between(
            height_range,
            predictions["mean_ci_lower"],
            predictions["mean_ci_upper"],
            color="red",
            alpha=0.15
        )

        # -----------------------------------------------------
        # Labels
        # -----------------------------------------------------

        ax.set_xlabel("Height")
        ax.set_ylabel("Midpoint distance")

        ax.set_title(
            f"{vertebral_level.replace('Vertebral level ', '')} "
            f"/ "
            f"{spinal_level.replace('Spinal level ', '')}"
        )

        # -----------------------------------------------------
        # Statistics
        # -----------------------------------------------------

        text = (
            f"N = {len(pair_df)}\n"
            f"p-height = {model_height.pvalues['height']:.3g}\n"
            f"p-age = {model_height.pvalues['age']:.3g}"
        )

        ax.text(
            0.05,
            0.95,
            text,
            transform=ax.transAxes,
            verticalalignment="top",
            bbox=dict(
                boxstyle="round",
                facecolor="white",
                alpha=0.8
            )
        )

    # Remove unused subplot
    axes[-1].axis("off")

    fig.suptitle(
        "Midpoint distance vs Height (adjusted for Age)",
        fontsize=22,
        y=0.995
    )

    plt.tight_layout()

    height_figure = os.path.join(
        output_dir,
        "midpoint_distance_vs_height_by_level_adjusted_for_age.png"
    )

    plt.savefig(
        height_figure,
        dpi=300,
        bbox_inches="tight"
    )

    plt.close()

    print(
        f"\nSaved figure: {height_figure}"
    )


def main():

    parser = argparse.ArgumentParser(
        description=(
            "Generate plots of midpoint distances versus age "
            "and height for each vertebral/spinal level pair."
        )
    )

    parser.add_argument(
        "--csv_file",
        type=str,
        required=True,
        help=(
            "Path to the CSV file containing distances "
            "between vertebral/spinal level midpoints."
        )
    )

    parser.add_argument(
        "--output_dir",
        type=str,
        required=True,
        help="Directory where figures will be saved."
    )

    args = parser.parse_args()

    plot_midpoint_distance_relationships(
        csv_file=args.csv_file,
        output_dir=args.output_dir
    )


if __name__ == "__main__":
    main()