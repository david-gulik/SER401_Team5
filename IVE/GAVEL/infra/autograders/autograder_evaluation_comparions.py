import json
import random
from pathlib import Path

import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


def load_submission_results(folder: Path) -> dict[str, dict]:
    results = {}

    for json_file in folder.glob("submission_*.json"):
        with open(json_file, encoding="utf-8") as f:
            data = json.load(f)

        submission_id = json_file.stem.removeprefix("submission_")

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

    reference_scores = load_submission_results(reference_folder)

    candidate_scores = load_submission_results(candidate_folder)

    if simulate_changes:
        reference_scores = perturb_scores(
            reference_scores,
            probability=0.25,
        )
        candidate_scores = perturb_scores(
            reference_scores,
            probability=0.15,
        )

    submission_ids = sorted(set(reference_scores) | set(candidate_scores))

    criteria = set()

    for scores in reference_scores.values():
        criteria.update(key for key in scores.keys() if key != "total")

    for scores in candidate_scores.values():
        criteria.update(key for key in scores.keys() if key != "total")

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

        row["difference"] = row[f"{reference_name}_total"] - row[f"{candidate_name}_total"]

        row["abs_difference"] = abs(row["difference"])

        for criterion in criteria:
            ref_score = reference.get(
                criterion,
                0,
            )

            cand_score = candidate.get(
                criterion,
                0,
            )

            row[f"{criterion}_{reference_name}"] = ref_score

            row[f"{criterion}_{candidate_name}"] = cand_score

            row[f"{criterion}_delta"] = cand_score - ref_score

        rows.append(row)

    return pd.DataFrame(rows)




class MatplotlibWidget(FigureCanvas):
    def __init__(self) -> None:
        self.figure = Figure(figsize=(8, 6))

        super().__init__(self.figure)

    def get_axis(self):
        self.figure.clear()
        return self.figure.add_subplot(111)


def plot_score_distribution(
    ax,
    df: pd.DataFrame,
    reference_name: str,
    candidate_name: str,
) -> None:
    ref_col = f"{reference_name}_total"
    cand_col = f"{candidate_name}_total"

    sns.boxplot(
        data=df[[ref_col, cand_col]],
        ax=ax,
    )

    sns.stripplot(
        data=df[[ref_col, cand_col]],
        ax=ax,
        color="black",
        alpha=0.3,
        jitter=True,
        size=3,
    )

    ax.set_title("Autograder Score Distribution")


def plot_scatter_comparison(
    ax,
    df: pd.DataFrame,
    reference_name: str,
    candidate_name: str,
) -> None:
    ref_col = f"{reference_name}_total"
    cand_col = f"{candidate_name}_total"

    scatter = ax.scatter(
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

    ax.fill_between(
        x,
        x - 1,
        x + 1,
        alpha=0.15,
        color="green",
        label="±1 point",
    )

    ax.plot(
        [0, maximum],
        [0, maximum],
        "r--",
        label="Perfect agreement",
    )

    r = np.corrcoef(
        df[ref_col],
        df[cand_col],
    )[0, 1]

    ax.text(
        maximum * 0.05,
        maximum * 0.95,
        f"Correlation: {r:.3f}",
    )

    top = df.nlargest(
        5,
        "abs_difference",
    )

    for _, row in top.iterrows():
        annotation = ax.annotate(
            row["submission"],
            (
                row[ref_col],
                row[cand_col],
            ),
            arrowprops={
                "arrowstyle": "->",
                "color": "red",
            },
            size=8,
        )
        annotation.set_picker(5)

    ax.figure.colorbar(
        scatter,
        ax=ax,
        label="Score Difference",
    )

    ax.set_xlabel(f"{reference_name} Score")
    ax.set_ylabel(f"{candidate_name} Score")
    ax.set_title("Autograder Comparison")
    ax.legend()


def plot_difference_histogram(
    ax,
    df: pd.DataFrame,
) -> None:
    counts, bins, patches = ax.hist(
        df["difference"],
        bins=20,
        edgecolor="black",
    )

    for patch, left_edge in zip(
        patches,
        bins[:-1], strict=False,
    ):
        patch.set_facecolor("crimson" if left_edge < 0 else "steelblue")

    mean_diff = df["difference"].mean()
    std_diff = df["difference"].std()

    ax.text(
        0.98,
        0.95,
        (f"Total Submissions = {len(df)}\nMean = {mean_diff:.2f}\nStd = {std_diff:.2f}"),
        transform=ax.transAxes,
        ha="right",
        va="top",
        bbox={
            "facecolor": "white",
            "alpha": 0.8,
        },
    )

    ax.axvspan(
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
        ax=ax,
    )

    ax.axvline(
        0,
        color="red",
        linestyle="--",
    )

    within_one = (np.abs(df["difference"]) <= 1).mean() * 100

    ax.set_xlabel("Score Difference")
    ax.set_ylabel("Count")

    ax.set_title(f"Distribution of Grading Differences\n{within_one:.1f}% within ±1 point")

    ax.legend()


def plot_bland_altman(
    ax,
    df: pd.DataFrame,
    reference_name: str,
    candidate_name: str,
) -> None:
    ref_col = f"{reference_name}_total"
    cand_col = f"{candidate_name}_total"

    mean_score = (df[ref_col] + df[cand_col]) / 2

    difference = df[ref_col] - df[cand_col]

    mean_diff = difference.mean()
    std_diff = difference.std()

    upper_loa = mean_diff + 1.96 * std_diff
    lower_loa = mean_diff - 1.96 * std_diff

    abs_diff = np.abs(difference)

    ax.axhspan(
        lower_loa,
        upper_loa,
        alpha=0.15,
        color="green",
        label="95% Agreement Region",
    )

    scatter = ax.scatter(
        mean_score,
        difference,
        c=abs_diff,
        cmap="coolwarm",
        s=90,
        edgecolors="black",
        alpha=0.8,
    )

    ax.axhline(
        mean_diff,
        color="red",
        linestyle="--",
        linewidth=2,
        label=f"Bias = {mean_diff:.2f}",
    )

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

    coeffs = np.polyfit(
        mean_score,
        difference,
        1,
    )

    trend_x = np.linspace(
        mean_score.min(),
        mean_score.max(),
        100,
    )

    trend_y = np.polyval(
        coeffs,
        trend_x,
    )

    ax.plot(
        trend_x,
        trend_y,
        color="black",
        linewidth=2,
        alpha=0.75,
        label="Trend",
    )

    outlier_mask = (difference > upper_loa) | (difference < lower_loa)

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
        annotation = ax.annotate(
            df.iloc[idx]["submission"],
            (
                mean_score.iloc[idx],
                difference.iloc[idx],
            ),
            xytext=(5, 5),
            textcoords="offset points",
            fontsize=8,
            bbox={
                "boxstyle": "round,pad=0.2",
                "fc": "white",
                "alpha": 0.7,
            },
        )

        annotation.set_picker(True)

    agreement_pct = (~outlier_mask).sum() / len(df) * 100

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
        bbox={
            "boxstyle": "round",
            "facecolor": "white",
            "alpha": 0.9,
        },
    )

    cbar = ax.figure.colorbar(
        scatter,
        ax=ax,
    )

    cbar.set_label("Absolute Difference")

    ax.set_xlabel("Average Score")
    ax.set_ylabel(f"{reference_name} - {candidate_name}")
    ax.set_title(f"Bland-Altman: {reference_name} vs {candidate_name}")

    ax.grid(
        alpha=0.3,
        linestyle="--",
    )

    ax.legend()


def plot_criterion_heatmap(
    ax,
    df: pd.DataFrame,
) -> None:
    delta_columns = [col for col in df.columns if col.endswith("_delta")]

    heatmap_df = df.set_index("submission")[delta_columns]

    sns.heatmap(
        heatmap_df,
        ax=ax,
        cmap="RdYlGn",
        center=0,
        fmt=".2f",
        cbar=False,
        square=True,
        linecolor="black",
        linewidth=0.5,
    )

    ax.set_title("Per-Criterion Differences")

    ax.set_xlabel("Criterion")
    ax.set_ylabel("Submission")




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

        row["total"] = sum(value for key, value in row.items() if key != "total")

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
        simulate_changes=True,
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
