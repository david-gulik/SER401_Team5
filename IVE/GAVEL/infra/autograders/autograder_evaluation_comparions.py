import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


def load_submission_results(folder: Path) -> dict[str, dict]:
    results = {}

    for json_file in folder.glob("submission_*.json"):
        with open(json_file, encoding="utf-8") as f:
            data = json.load(f)

        submission_id = json_file.stem.removeprefix(
            "submission_"
        )

        row = {}
        total = 0.0

        for test in data.get("tests", []):
            criterion = test["number"]
            score = test["score"]

            row[criterion] = score
            total += score

        row["total"] = total

        results[submission_id] = row

    return results


def compare_evaluations(
    reference_folder: Path,
    candidate_folder: Path,
    reference_name: str = "reference",
    candidate_name: str = "candidate",
    simulate_changes: bool = False,
) -> pd.DataFrame:

    reference_scores = load_submission_results(
        reference_folder
    )

    candidate_scores = load_submission_results(
        candidate_folder
    )

    if simulate_changes:
        reference_scores = perturb_scores(
            reference_scores,
            probability=0.25,
        )
        candidate_scores = perturb_scores(
            reference_scores,
            probability=0.15,
        )

    submission_ids = sorted(
        set(reference_scores)
        | set(candidate_scores)
    )

    criteria = set()

    for scores in reference_scores.values():
        criteria.update(
            key
            for key in scores.keys()
            if key != "total"
        )

    for scores in candidate_scores.values():
        criteria.update(
            key
            for key in scores.keys()
            if key != "total"
        )

    criteria = sorted(criteria)

    rows = []

    for submission_id in submission_ids:

        reference = reference_scores.get(
            submission_id,
            {},
        )

        candidate = candidate_scores.get(
            submission_id,
            {},
        )

        row = {
            "submission": submission_id,
            f"{reference_name}_total": reference.get(
                "total",
                0,
            ),
            f"{candidate_name}_total": candidate.get(
                "total",
                0,
            ),
        }

        row["difference"] = (
            row[f"{reference_name}_total"]
            - row[f"{candidate_name}_total"]
        )

        row["abs_difference"] = abs(
            row["difference"]
        )

        for criterion in criteria:

            ref_score = reference.get(
                criterion,
                0,
            )

            cand_score = candidate.get(
                criterion,
                0,
            )

            row[f"{criterion}_{reference_name}"] = (
                ref_score
            )

            row[f"{criterion}_{candidate_name}"] = (
                cand_score
            )

            row[f"{criterion}_delta"] = (
                cand_score - ref_score
            )

        rows.append(row)

    return pd.DataFrame(rows)


def plot_score_distribution(
    df: pd.DataFrame,
    reference_name: str,
    candidate_name: str,
) -> None:

    plt.figure(figsize=(8, 6))

    sns.boxplot(
        data=df[
            [
                f"{reference_name}_total",
                f"{candidate_name}_total",
            ]
        ]
    )

    sns.stripplot(
        data=df[
            [
                f"{reference_name}_total",
                f"{candidate_name}_total",
            ]
        ],
        color="black",
        alpha=0.3,
        jitter=True,
        size=3,
    )

    plt.title(
        "Autograder Score Distribution"
    )

    plt.show()


def plot_scatter_comparison(
    df: pd.DataFrame,
    reference_name: str,
    candidate_name: str,
) -> None:

    ref_col = f"{reference_name}_total"
    cand_col = f"{candidate_name}_total"

    plt.figure(figsize=(8, 6))

    scatter = plt.scatter(
        df[ref_col],
        df[cand_col],
        c=df["difference"],
        cmap="viridis",
    )

    maximum = max(
        df[ref_col].max(),
        df[cand_col].max(),
    )

    x = np.arange(
        0,
        maximum + 2,
    )

    plt.fill_between(
        x,
        x - 1,
        x + 1,
        alpha=0.15,
        color="green",
        label="±1 point",
    )

    plt.plot(
        [0, maximum],
        [0, maximum],
        "r--",
        label="Perfect agreement",
    )

    r = np.corrcoef(
        df[ref_col],
        df[cand_col],
    )[0, 1]

    plt.text(
        maximum * 0.05,
        maximum * 0.95,
        f"Correlation: {r:.3f}",
    )

    top = df.nlargest(
        5,
        "abs_difference",
    )

    for _, row in top.iterrows():
        plt.annotate(
            row["submission"],
            (
                row[ref_col],
                row[cand_col],
            ),
            size=8,
        )

    plt.colorbar(
        scatter,
        label="Score Difference",
    )

    plt.xlabel(
        f"{reference_name} Score"
    )

    plt.ylabel(
        f"{candidate_name} Score"
    )

    plt.title(
        "Autograder Comparison"
    )

    plt.legend()

    plt.show()


def plot_difference_histogram(
    df: pd.DataFrame,
) -> None:

    plt.figure(figsize=(10, 6))

    counts, bins, patches = plt.hist(
        df["difference"],
        bins=20,
        edgecolor="black",
    )

    for patch, left_edge in zip(
        patches,
        bins[:-1],
    ):
        patch.set_facecolor(
            "crimson"
            if left_edge < 0
            else "steelblue"
        )

    mean_diff = (
        df["difference"]
        .mean()
    )

    std_diff = (
        df["difference"]
        .std()
    )

    plt.text(
        0.98,
        0.95,
        f"Total Submissions = {len(df)}\n"
        f"Mean = {mean_diff:.2f}\n"
        f"Std = {std_diff:.2f}",
        transform=plt.gca().transAxes,
        ha="right",
        va="top",
        bbox=dict(
            facecolor="white",
            alpha=0.8,
        ),
    )

    plt.axvspan(
        -1,
        1,
        alpha=0.15,
        color="green",
        label="Acceptable Range",
    )

    sns.histplot(
        df["difference"],
        bins=20,
        kde=True,
    )

    plt.axvline(
        0,
        color="red",
        linestyle="--",
    )

    within_one = (
        np.abs(
            df["difference"]
        ) <= 1
    ).mean() * 100

    plt.xlabel(
        "Score Difference"
    )

    plt.ylabel(
        "Count"
    )

    plt.title(
        "Distribution of Grading Differences\n"
        f"{within_one:.1f}% within ±1 point"
    )

    plt.show()


def plot_bland_altman(
    df,
    reference_name: str,
    candidate_name: str,
) -> None:
    ref_col = f"{reference_name}_total"
    cand_col = f"{candidate_name}_total"

    mean_score = (
        df[ref_col]
        + df[cand_col]
    ) / 2

    difference = (
        df[ref_col]
        - df[cand_col]
    )

    # Bland-Altman statistics
    mean_diff = difference.mean()
    std_diff = difference.std()

    upper_loa = mean_diff + 1.96 * std_diff
    lower_loa = mean_diff - 1.96 * std_diff

    abs_diff = np.abs(difference)

    fig, ax = plt.subplots(figsize=(10, 7))

    # Agreement region
    ax.axhspan(
        lower_loa,
        upper_loa,
        alpha=0.15,
        color="green",
        label="95% Agreement Region",
    )

    # Points colored by disagreement magnitude
    scatter = ax.scatter(
        mean_score,
        difference,
        c=abs_diff,
        cmap="coolwarm",
        s=90,
        edgecolors="black",
        alpha=0.8,
    )

    # Mean bias line
    ax.axhline(
        mean_diff,
        color="red",
        linestyle="--",
        linewidth=2,
        label=f"Bias = {mean_diff:.2f}",
    )

    # Limits of agreement
    ax.axhline(
        upper_loa,
        color="orange",
        linestyle=":",
        linewidth=2,
        label=f"+1.96 SD = {upper_loa:.2f}",
    )

    ax.axhline(
        lower_loa,
        color="orange",
        linestyle=":",
        linewidth=2,
        label=f"-1.96 SD = {lower_loa:.2f}",
    )

    # Optional trend line
    coeffs = np.polyfit(mean_score, difference, 1)
    trend_x = np.linspace(
        mean_score.min(),
        mean_score.max(),
        100,
    )
    trend_y = np.polyval(coeffs, trend_x)

    ax.plot(
        trend_x,
        trend_y,
        color="black",
        linewidth=2,
        alpha=0.75,
        label="Trend",
    )

    # Highlight outliers
    outlier_mask = (
        (difference > upper_loa)
        | (difference < lower_loa)
    )

    ax.scatter(
        mean_score[outlier_mask],
        difference[outlier_mask],
        s=150,
        color="red",
        edgecolors="black",
        zorder=5,
        label="Outlier",
    )

    for idx in np.where(outlier_mask)[0]:
        ax.annotate(
            df.iloc[idx]["submission"],
            (
                mean_score.iloc[idx],
                difference.iloc[idx],
            ),
            xytext=(5, 5),
            textcoords="offset points",
            fontsize=8,
            bbox=dict(
                boxstyle="round,pad=0.2",
                fc="white",
                alpha=0.7,
            ),
        )

    # Summary statistics box
    agreement_pct = (
        (~outlier_mask).sum()
        / len(df)
        * 100
    )

    stats_text = (
        f"N = {len(df)}\n"
        f"Bias = {mean_diff:.2f}\n"
        f"SD = {std_diff:.2f}\n"
        f"Within LoA = {agreement_pct:.1f}%"
    )

    ax.text(
        0.02,
        0.98,
        stats_text,
        transform=ax.transAxes,
        fontsize=10,
        verticalalignment="top",
        bbox=dict(
            boxstyle="round",
            facecolor="white",
            alpha=0.9,
        ),
    )

    cbar = plt.colorbar(
        scatter,
        ax=ax,
    )
    cbar.set_label(
        "Absolute Difference"
    )

    ax.set_xlabel(
        "Average Score"
    )

    ax.set_ylabel(
        f"{reference_name} - {candidate_name}"
    )

    ax.set_title(
        f"Bland-Altman: {reference_name} vs {candidate_name}"
    )

    ax.grid(
        alpha=0.3,
        linestyle="--",
    )

    ax.legend()

    plt.tight_layout()
    plt.show()

def plot_criterion_heatmap(
    df: pd.DataFrame,
) -> None:

    delta_columns = [
        col
        for col in df.columns
        if col.endswith("_delta")
    ]

    heatmap_df = (
        df
        .set_index("submission")
        [delta_columns]
    )

    plt.figure(
        figsize=(
            16,
            max(
                6,
                len(df) * 0.3,
            ),
        )
    )

    sns.heatmap(
        heatmap_df,
        cmap="RdYlGn",
        center=0,
        fmt=".2f",
        cbar=False,
        square=True,
        linecolor="black",
        linewidth=0.5,
    )

    plt.title(
        "Per-Criterion Differences"
    )

    plt.xlabel(
        "Criterion"
    )

    plt.ylabel(
        "Submission"
    )

    plt.tight_layout()

    plt.show()

import random


import random


def perturb_scores(
    results: dict[str, dict],
    probability: float = 0.05,
) -> dict[str, dict]:
    """
    Randomly increase or decrease criterion scores.

    Most criteria stay unchanged.
    A small percentage are modified to simulate
    autograder revisions.
    """

    modified = {}

    for submission_id, scores in results.items():

        row = scores.copy()

        for criterion, score in row.items():

            if criterion == "total":
                continue

            if random.random() >= probability:
                continue

            delta = random.choice(
                [
                    -1.0,
                    -0.5,
                    0.0,
                    0.5,
                    1.0,
                ]
            )

            row[criterion] = max(
                0.0,
                score + delta,
            )

        row["total"] = sum(
            value
            for key, value in row.items()
            if key != "total"
        )

        modified[submission_id] = row

    return modified

def main():

    reference_name = "Reference"
    candidate_name = "Candidate"

    df = compare_evaluations(
        reference_folder=Path(
            r"C:\Users\dcgul\Downloads\GAVEL\courses\trn226_26sc_12345\anonymized\evaluations\m3\ser222_01_03_hw02b_autograder_2"
        ),
        candidate_folder=Path(
            r"C:\Users\dcgul\Downloads\GAVEL\courses\trn226_26sc_12345\anonymized\evaluations\m3\ser222_01_03_hw02b_autograder"
        ),
        reference_name=reference_name,
        candidate_name=candidate_name,
        simulate_changes=True
    )

    # print(df.head())

    plot_score_distribution(
        df,
        reference_name,
        candidate_name,
    )

    plot_scatter_comparison(
        df,
        reference_name,
        candidate_name,
    )

    plot_difference_histogram(df)

    plot_bland_altman(
        df,
        reference_name,
        candidate_name,
    )

    plot_criterion_heatmap(df)


if __name__ == "__main__":
    main()