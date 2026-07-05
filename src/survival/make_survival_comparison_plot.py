#!/usr/bin/env python3
from __future__ import annotations

import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parent
try:  # prefer an installed scientific stack (see requirements.txt); fall back to vendored deps
    import numpy as _numpy_probe  # noqa: F401
except ImportError:
    PLOT_DEPS = WORKSPACE / "model_comparison_500" / ".plot_deps"
    sys.path.insert(0, str(PLOT_DEPS))
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".matplotlib_cache"))

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


RESULT_GROUPS = [
    {
        "label": "Full Report",
        "folder": ROOT / "all_tokens" / "model_after_bs32",
        "source": "all_tokens/model_after_bs32",
    },
    {
        "label": "Prognostic Summary by PaRLA",
        "folder": ROOT / "generated_tokens" / "model_after_base_bs32",
        "source": "generated_tokens/model_after_base_bs32",
    },
]

CANCER_ORDER = [
    "blca",
    "brca",
    "kirckirp",
    "luad",
    "sarc",
]

CANCER_LABELS = {
    "blca": "Bladder",
    "brca": "Breast",
    "kirckirp": "Kidney",
    "luad": "Lung",
    "sarc": "Sarcoma",
}

COLORS = {
    "Full Report": "#C9C9C9",
    "Prognostic Summary by PaRLA": "#0072B2",
}


def set_style() -> None:
    sns.set_theme(style="whitegrid", context="paper")
    plt.rcParams.update(
        {
            "font.family": "Arial",
            "font.size": 9,
            "axes.titlesize": 13,
            "axes.labelsize": 10,
            "xtick.labelsize": 8.5,
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


def load_fold_results() -> pd.DataFrame:
    rows = []
    for group in RESULT_GROUPS:
        for summary_path in sorted(group["folder"].glob("*/results/seed256/summary.csv")):
            cancer = summary_path.parts[-4]
            summary = pd.read_csv(summary_path)
            for _, fold_row in summary.iterrows():
                rows.append(
                    {
                        "group": group["label"],
                        "source": group["source"],
                        "cancer": cancer,
                        "cancer_label": CANCER_LABELS.get(cancer, cancer.upper()),
                        "fold": int(fold_row["folds"]),
                        "val_cindex": float(fold_row["val_cindex"]),
                        "test_cindex": float(fold_row["test_cindex"]),
                    }
                )
    if not rows:
        raise RuntimeError(f"No summary.csv files found under {ROOT}")
    return pd.DataFrame(rows)


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    records = []
    for (group, source, cancer, cancer_label), group_df in df.groupby(["group", "source", "cancer", "cancer_label"], sort=False):
        test_values = group_df["test_cindex"]
        val_values = group_df["val_cindex"]
        n = len(group_df)
        test_sd = test_values.std(ddof=1)
        val_sd = val_values.std(ddof=1)
        records.append(
            {
                "group": group,
                "source": source,
                "cancer": cancer,
                "cancer_label": cancer_label,
                "n_folds": n,
                "mean_test_cindex": test_values.mean(),
                "sd_test_cindex": test_sd,
                "sem_test_cindex": test_sd / math.sqrt(n),
                "ci95_test_cindex": 1.96 * test_sd / math.sqrt(n),
                "mean_val_cindex": val_values.mean(),
                "sd_val_cindex": val_sd,
                "sem_val_cindex": val_sd / math.sqrt(n),
                "ci95_val_cindex": 1.96 * val_sd / math.sqrt(n),
            }
        )
    summary = pd.DataFrame(records)
    summary = summary[summary["cancer"].isin(CANCER_ORDER)].copy()
    summary["cancer"] = pd.Categorical(summary["cancer"], CANCER_ORDER, ordered=True)
    summary["group"] = pd.Categorical(summary["group"], [item["label"] for item in RESULT_GROUPS], ordered=True)
    return summary.sort_values(["cancer", "group"]).reset_index(drop=True)


def save_plot(fig: plt.Figure, stem: str) -> None:
    out_dir = ROOT / "plots"
    out_dir.mkdir(exist_ok=True)
    for suffix in ["pdf", "svg", "png"]:
        path = out_dir / f"{stem}.{suffix}"
        kwargs = {"bbox_inches": "tight"}
        if suffix == "png":
            kwargs["dpi"] = 600
        fig.savefig(path, **kwargs)


def plot_test_cindex(summary: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(11.8, 5.4))
    order = [CANCER_LABELS[cancer] for cancer in CANCER_ORDER]
    plot_df = summary.copy()
    plot_df["cancer_label"] = pd.Categorical(plot_df["cancer_label"], order, ordered=True)
    plot_df["mean_test_cindex_points"] = plot_df["mean_test_cindex"] * 100.0
    plot_df["ci95_test_cindex_points"] = plot_df["ci95_test_cindex"] * 100.0

    sns.barplot(
        data=plot_df,
        x="cancer_label",
        y="mean_test_cindex_points",
        hue="group",
        order=order,
        hue_order=[item["label"] for item in RESULT_GROUPS],
        palette=COLORS,
        errorbar=None,
        width=0.78,
        edgecolor="none",
        ax=ax,
    )

    x_positions = {label.get_text(): index for index, label in enumerate(ax.get_xticklabels())}
    offsets = {"Full Report": -0.195, "Prognostic Summary by PaRLA": 0.195}
    for _, row in plot_df.iterrows():
        x = x_positions[row["cancer_label"]] + offsets[row["group"]]
        mean_value = row["mean_test_cindex_points"]
        ci = row["ci95_test_cindex_points"]
        ax.errorbar(
            x,
            mean_value,
            yerr=ci,
            fmt="none",
            ecolor="#111111",
            elinewidth=0.9,
            capsize=2.5,
            capthick=0.9,
            zorder=5,
        )
        ax.text(
            x,
            mean_value + ci + 1.2,
            f"{mean_value:.1f}",
            ha="center",
            va="bottom",
            fontsize=7.8,
            weight="bold",
            color="#111111",
        )

    ax.axhline(50, color="#555555", linewidth=1.0, linestyle="--", alpha=0.8)
    ax.text(
        0.995,
        50.5,
        "random = 50",
        transform=ax.get_yaxis_transform(),
        ha="right",
        va="bottom",
        fontsize=8,
        color="#555555",
    )
    ax.set_ylim(35, 85)
    ax.set_ylabel("Test C-index (0–100)")
    ax.set_xlabel("")
    fig.suptitle("Downstream survival prediction by cancer dataset", weight="bold", fontsize=13, y=0.985)
    fig.text(
        0.5,
        0.925,
        "Mean across 5 folds; error bars show 95% CI",
        ha="center",
        va="bottom",
        fontsize=9.5,
        color="#555555",
    )
    ax.legend(
        title=None,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.16),
        ncol=2,
        frameon=False,
        handlelength=1.2,
        columnspacing=2.5,
    )
    ax.tick_params(axis="x", rotation=35)
    for tick in ax.get_xticklabels():
        tick.set_ha("right")

    sns.despine(ax=ax)
    fig.subplots_adjust(left=0.075, right=0.995, bottom=0.23, top=0.76)
    save_plot(fig, "survival_test_cindex_by_cancer")
    plt.close(fig)


def main() -> None:
    set_style()
    fold_df = load_fold_results()
    summary = summarize(fold_df)
    out_dir = ROOT / "plots"
    out_dir.mkdir(exist_ok=True)
    fold_df.to_csv(out_dir / "survival_fold_results_long.csv", index=False)
    summary.to_csv(out_dir / "survival_test_cindex_summary.csv", index=False)

    wide = summary.pivot(index=["cancer", "cancer_label"], columns="group", values="mean_test_cindex").reset_index()
    wide["prognostic_summary_minus_full_report"] = wide["Prognostic Summary by PaRLA"] - wide["Full Report"]
    wide.to_csv(out_dir / "survival_test_cindex_wide.csv", index=False)

    plot_test_cindex(summary)

    for path in [
        out_dir / "survival_test_cindex_by_cancer.pdf",
        out_dir / "survival_test_cindex_by_cancer.svg",
        out_dir / "survival_test_cindex_by_cancer.png",
        out_dir / "survival_test_cindex_summary.csv",
        out_dir / "survival_test_cindex_wide.csv",
        out_dir / "survival_fold_results_long.csv",
    ]:
        print(path)


if __name__ == "__main__":
    main()
