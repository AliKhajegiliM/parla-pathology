#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".matplotlib_cache"))
try:  # prefer an installed scientific stack (see requirements.txt); fall back to vendored deps
    import numpy as _numpy_probe  # noqa: F401
except ImportError:
    sys.path.insert(0, str(ROOT / ".plot_deps"))

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


JUDGMENTS_PATH = ROOT / "judgments.jsonl"

MODEL_LABELS = {
    "after": "PaRLA",
    "before": "Llama 70B",
    "tie": "Tie",
}

MODEL_COLORS = {
    "PaRLA": "#0072B2",
    "Llama 70B": "#C9C9C9",
    "Tie": "#7A7A7A",
}

SCORE_CATEGORIES = [
    ("Diagnostic essence", "Diagnostic\nessence", "diagnostic_essence"),
    ("Hallucination control", "Hallucination\ncontrol", "faithfulness"),
    ("Prognostic/staging capture", "Prognostic/\nstaging capture", "prognostic_staging_capture"),
    ("Reasoning quality", "Reasoning\nquality", "reasoning_quality"),
    ("Conclusion quality", "Conclusion\nquality", "conclusion_quality"),
    ("Overall usefulness", "Overall\nusefulness", "overall_usefulness"),
    ("Reasoning prognostic features", "Reasoning:\nprognostic\nfeatures", "reasoning_prognostic_feature_score"),
    ("Conclusion prognostic features", "Conclusion:\nprognostic\nfeatures", "conclusion_prognostic_feature_score"),
    ("Reasoning hallucination control", "Reasoning:\nhallucination\ncontrol", "reasoning_faithfulness_score"),
    ("Conclusion hallucination control", "Conclusion:\nhallucination\ncontrol", "conclusion_faithfulness_score"),
]


def load_judgments() -> list[dict]:
    with JUDGMENTS_PATH.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def mean(values: list[float]) -> float:
    return float(np.mean(values))


def ci95(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return float(1.96 * np.std(values, ddof=1) / math.sqrt(len(values)))


def set_publication_style() -> None:
    sns.set_theme(style="whitegrid", context="paper")
    plt.rcParams.update(
        {
            "font.family": "Arial",
            "font.size": 9,
            "axes.titlesize": 13,
            "axes.labelsize": 10,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.fontsize": 9,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
            "axes.linewidth": 0.9,
            "grid.linewidth": 0.6,
            "grid.color": "#D9D9D9",
            "axes.edgecolor": "#222222",
            "text.color": "#111111",
            "axes.labelcolor": "#111111",
            "xtick.color": "#111111",
            "ytick.color": "#111111",
        }
    )


def build_win_rate_df(judgments: list[dict]) -> pd.DataFrame:
    total = len(judgments)
    counts = {
        "after": sum(item["winner"] == "after" for item in judgments),
        "before": sum(item["winner"] == "before" for item in judgments),
        "tie": sum(item["winner"] == "tie" for item in judgments),
    }
    rows = [
        {
            "Outcome": MODEL_LABELS[key],
            "winner_key": key,
            "Count": counts[key],
            "Win rate (%)": 100 * counts[key] / total,
            "n_total": total,
        }
        for key in ["after", "before", "tie"]
    ]
    return pd.DataFrame(rows)


def build_score_df(judgments: list[dict]) -> tuple[pd.DataFrame, pd.DataFrame]:
    summary_rows = []
    long_rows = []
    for category, plot_label, score_key in SCORE_CATEGORIES:
        for model_key, score_group, model_label in [
            ("before", "before_scores", "Llama 70B"),
            ("after", "after_scores", "PaRLA"),
        ]:
            values = [float(item[score_group][score_key]) for item in judgments]
            summary_rows.append(
                {
                    "Category": category,
                    "Plot label": plot_label,
                    "Criterion": score_key,
                    "Model": model_label,
                    "Mean": mean(values),
                    "CI95": ci95(values),
                    "n": len(values),
                }
            )
            for value in values:
                long_rows.append(
                    {
                        "Category": category,
                        "Plot label": plot_label,
                        "Criterion": score_key,
                        "Model": model_label,
                        "Score": value,
                    }
                )
    summary = pd.DataFrame(summary_rows)
    long = pd.DataFrame(long_rows)
    return summary, long


def save_all(fig: plt.Figure, stem: str) -> None:
    for suffix in ["pdf", "svg", "png"]:
        path = ROOT / f"{stem}.{suffix}"
        kwargs = {"bbox_inches": "tight"}
        if suffix == "png":
            kwargs["dpi"] = 600
        fig.savefig(path, **kwargs)


def plot_win_rates(win_df: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(6.8, 4.3))
    order = ["PaRLA", "Llama 70B", "Tie"]
    sns.barplot(
        data=win_df,
        x="Outcome",
        y="Win rate (%)",
        order=order,
        hue="Outcome",
        palette=MODEL_COLORS,
        dodge=False,
        width=0.62,
        edgecolor="none",
        ax=ax,
    )
    legend = ax.get_legend()
    if legend is not None:
        legend.remove()

    ax.set_ylim(0, 100)
    ax.set_xlabel("")
    ax.set_ylabel("Win rate (%)")
    ax.set_title("Pairwise win rate — GPT-5.5 Extra High (Codex) judge", weight="bold", pad=18)
    ax.text(
        0.5,
        1.02,
        f"TCGA external validation set  ·  n = {int(win_df['n_total'].iloc[0])} reports",
        transform=ax.transAxes,
        ha="center",
        va="bottom",
        fontsize=9.5,
        color="#555555",
    )

    for patch, (_, row) in zip(ax.patches, win_df.set_index("Outcome").loc[order].reset_index().iterrows()):
        height = patch.get_height()
        x = patch.get_x() + patch.get_width() / 2
        ax.text(x, height + 4.2, f"{height:.1f}%", ha="center", va="bottom", fontsize=10, weight="bold")
        ax.text(x, height + 1.7, f"n={int(row['Count'])}", ha="center", va="bottom", fontsize=8.5, color="#555555")

    sns.despine(ax=ax)
    fig.tight_layout()
    save_all(fig, "fig1_win_rate_barplot")
    plt.close(fig)


def plot_category_scores(summary: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(12.6, 5.7))
    order = [category for category, _, _ in SCORE_CATEGORIES]
    plot_labels = {category: plot_label for category, plot_label, _ in SCORE_CATEGORIES}
    hue_order = ["Llama 70B", "PaRLA"]

    sns.barplot(
        data=summary,
        x="Category",
        y="Mean",
        hue="Model",
        order=order,
        hue_order=hue_order,
        palette=MODEL_COLORS,
        errorbar=None,
        width=0.78,
        edgecolor="none",
        ax=ax,
    )

    x_positions = {label.get_text(): idx for idx, label in enumerate(ax.get_xticklabels())}
    offsets = {"Llama 70B": -0.195, "PaRLA": 0.195}
    cap_half_width = 0.045
    for _, row in summary.iterrows():
        x = x_positions[row["Category"]] + offsets[row["Model"]]
        mean_value = row["Mean"]
        ci = row["CI95"]
        ax.errorbar(
            x,
            mean_value,
            yerr=ci,
            fmt="none",
            ecolor="#111111",
            elinewidth=1.0,
            capsize=3,
            capthick=1.0,
            zorder=5,
        )
        ax.text(
            x,
            min(5.04, mean_value + ci + 0.055),
            f"{mean_value:.2f}",
            ha="center",
            va="bottom",
            fontsize=7.8,
            weight="bold",
        )

    ax.set_ylim(0, 5.08)
    ax.set_ylabel("Mean score")
    ax.set_xlabel("")
    fig.suptitle("Mean category ratings — GPT-5.5 Extra High (Codex) judge", weight="bold", fontsize=13, y=0.985)
    fig.text(
        0.5,
        0.925,
        "Bars show mean score on a 0–5 scale; error bars show 95% CI",
        ha="center",
        va="bottom",
        fontsize=9.5,
        color="#555555",
    )
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels([plot_labels[item] for item in order], rotation=0, ha="center")
    ax.legend(
        title=None,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.13),
        ncol=2,
        frameon=False,
        handlelength=1.2,
        columnspacing=2.5,
    )

    sns.despine(ax=ax)
    fig.subplots_adjust(left=0.07, right=0.995, bottom=0.24, top=0.78)
    save_all(fig, "fig2_category_avg_scores_barplot")
    plt.close(fig)


def main() -> None:
    set_publication_style()
    judgments = load_judgments()

    win_df = build_win_rate_df(judgments)
    score_summary, _ = build_score_df(judgments)

    win_df.to_csv(ROOT / "figure_win_rates.csv", index=False)
    score_wide = (
        score_summary.pivot(index=["Category", "Criterion", "n"], columns="Model", values=["Mean", "CI95"])
        .reset_index()
    )
    score_wide.columns = [
        "_".join(str(part).strip().lower().replace(" ", "_") for part in col if part)
        for col in score_wide.columns.to_flat_index()
    ]
    score_wide["category"] = pd.Categorical(score_wide["category"], [category for category, _, _ in SCORE_CATEGORIES], ordered=True)
    score_wide = score_wide.sort_values("category")
    score_wide["parla_minus_llama_70b"] = score_wide["mean_parla"] - score_wide["mean_llama_70b"]
    score_wide.to_csv(ROOT / "figure_category_scores.csv", index=False)

    plot_win_rates(win_df)
    plot_category_scores(score_summary)

    for name in [
        "fig1_win_rate_barplot.pdf",
        "fig1_win_rate_barplot.svg",
        "fig1_win_rate_barplot.png",
        "fig2_category_avg_scores_barplot.pdf",
        "fig2_category_avg_scores_barplot.svg",
        "fig2_category_avg_scores_barplot.png",
        "figure_win_rates.csv",
        "figure_category_scores.csv",
    ]:
        print(ROOT / name)


if __name__ == "__main__":
    main()
