#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from textwrap import fill

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


PARLA_BLUE = "#0072B2"
LIGHT_GRAY = "#C9C9C9"
DARK_GRAY = "#555555"
TEXT = "#111111"


def read_metadata(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str).fillna("")


def invert_center_mapping(path: Path) -> dict[str, str]:
    mapping = json.loads(path.read_text())
    code_to_center: dict[str, str] = {}
    duplicate_codes: dict[str, list[str]] = defaultdict(list)
    for center, codes in mapping.items():
        for code in codes:
            code = str(code)
            if code in code_to_center:
                duplicate_codes[code].append(center)
            else:
                code_to_center[code] = center
    if duplicate_codes:
        examples = ", ".join(f"{code}: {centers}" for code, centers in list(duplicate_codes.items())[:5])
        raise ValueError(f"TSS codes mapped to multiple centers: {examples}")
    return code_to_center


def save_plot(fig: plt.Figure, out_dir: Path, stem: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for suffix in ["pdf", "png", "svg"]:
        kwargs = {"bbox_inches": "tight"}
        if suffix == "png":
            kwargs["dpi"] = 600
        fig.savefig(out_dir / f"{stem}.{suffix}", **kwargs)
    plt.close(fig)


def count_table(counter: Counter[str], total: int, key_name: str) -> pd.DataFrame:
    rows = [
        {key_name: key, "n_reports": count, "percent": 100.0 * count / total}
        for key, count in counter.most_common()
    ]
    return pd.DataFrame(rows)


def write_counts(df: pd.DataFrame, path: Path) -> None:
    df.to_csv(path, index=False, float_format="%.1f")


def wrap_labels(labels: list[str], width: int = 28) -> list[str]:
    return [fill(label, width=width) for label in labels]


def annotate_hbars(ax: plt.Axes, values: list[int], x_pad: float = 0.6) -> None:
    for patch, value in zip(ax.patches, values):
        ax.text(
            patch.get_width() + x_pad,
            patch.get_y() + patch.get_height() / 2,
            str(value),
            va="center",
            ha="left",
            fontsize=8,
            color=TEXT,
            weight="bold",
        )


def plot_project_distribution(project_counts: pd.DataFrame, out_dir: Path) -> None:
    df = project_counts.sort_values("n_reports", ascending=True).copy()
    labels = [f"{row.project_id.replace('TCGA-', '')}: {row.project_name}" for row in df.itertuples()]

    fig_height = max(7.5, 0.24 * len(df) + 1.6)
    fig, ax = plt.subplots(figsize=(10.8, fig_height))
    ax.barh(range(len(df)), df["n_reports"], color=PARLA_BLUE, edgecolor="none")
    ax.set_yticks(range(len(df)))
    ax.set_yticklabels(wrap_labels(labels, 34), fontsize=7.8)
    ax.set_xlabel("Number of reports")
    ax.set_ylabel("TCGA cancer cohort")
    ax.set_title("Cancer cohorts represented in the 500-report TCGA external validation set", weight="bold")
    annotate_hbars(ax, list(df["n_reports"]), x_pad=0.45)
    ax.set_xlim(0, max(df["n_reports"]) * 1.18)
    ax.grid(axis="x", color="#DDDDDD", linewidth=0.7)
    sns.despine(ax=ax, left=True)
    save_plot(fig, out_dir, "tcga_validation_cancer_cohort_distribution")


def plot_primary_site_distribution(primary_site_counts: pd.DataFrame, out_dir: Path) -> None:
    df = primary_site_counts.sort_values("n_reports", ascending=True).copy()

    fig_height = max(7.5, 0.23 * len(df) + 1.4)
    fig, ax = plt.subplots(figsize=(10.4, fig_height))
    ax.barh(range(len(df)), df["n_reports"], color=LIGHT_GRAY, edgecolor="none")
    ax.set_yticks(range(len(df)))
    ax.set_yticklabels(wrap_labels(list(df["primary_site"]), 32), fontsize=7.8)
    ax.set_xlabel("Number of reports")
    ax.set_ylabel("GDC primary site")
    ax.set_title("Primary-site diversity in the sampled TCGA reports", weight="bold")
    annotate_hbars(ax, list(df["n_reports"]), x_pad=0.45)
    ax.set_xlim(0, max(df["n_reports"]) * 1.18)
    ax.grid(axis="x", color="#DDDDDD", linewidth=0.7)
    sns.despine(ax=ax, left=True)
    save_plot(fig, out_dir, "tcga_validation_primary_site_distribution")


def plot_disease_type_distribution(disease_type_counts: pd.DataFrame, out_dir: Path) -> None:
    df = disease_type_counts.sort_values("n_reports", ascending=True).copy()

    fig_height = max(5.6, 0.28 * len(df) + 1.4)
    fig, ax = plt.subplots(figsize=(10.4, fig_height))
    ax.barh(range(len(df)), df["n_reports"], color=LIGHT_GRAY, edgecolor="none")
    ax.set_yticks(range(len(df)))
    ax.set_yticklabels(wrap_labels(list(df["disease_type"]), 34), fontsize=8)
    ax.set_xlabel("Number of reports")
    ax.set_ylabel("GDC disease type")
    ax.set_title("Disease-type diversity in the sampled TCGA reports", weight="bold")
    annotate_hbars(ax, list(df["n_reports"]), x_pad=0.45)
    ax.set_xlim(0, max(df["n_reports"]) * 1.18)
    ax.grid(axis="x", color="#DDDDDD", linewidth=0.7)
    sns.despine(ax=ax, left=True)
    save_plot(fig, out_dir, "tcga_validation_disease_type_distribution")


def plot_center_diversity(center_counts: pd.DataFrame, tss_count: int, out_dir: Path) -> None:
    counts = center_counts["n_reports"].tolist()
    top_df = center_counts.head(20).sort_values("n_reports", ascending=True)

    fig, axes = plt.subplots(
        1,
        2,
        figsize=(15.8, 6.6),
        gridspec_kw={"width_ratios": [1.0, 1.65], "wspace": 0.52},
    )
    fig.suptitle("Institutional diversity of the TCGA external validation set", weight="bold", fontsize=14, y=0.99)
    fig.text(
        0.5,
        0.93,
        f"500 reports across {len(center_counts)} centers and {tss_count} distinct TSS codes",
        ha="center",
        va="bottom",
        fontsize=10,
        color=DARK_GRAY,
    )

    ax = axes[0]
    bins = range(1, max(counts) + 3)
    ax.hist(counts, bins=bins, color=PARLA_BLUE, edgecolor="white", linewidth=0.8)
    ax.axvline(pd.Series(counts).median(), color=TEXT, linestyle="--", linewidth=1.2)
    ax.set_xlabel("Reports contributed per center")
    ax.set_ylabel("Number of centers")
    ax.set_title("Reports per center (all centers)", fontsize=11, weight="bold")
    ax.text(
        0.06,
        0.95,
        f"Centers = {len(center_counts)}\nMedian = {pd.Series(counts).median():.0f}\nMax = {max(counts)}",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=10,
        bbox={"boxstyle": "round,pad=0.35", "facecolor": "white", "edgecolor": "#DDDDDD"},
    )
    ax.grid(axis="y", color="#DDDDDD", linewidth=0.7)
    sns.despine(ax=ax)

    ax = axes[1]
    ax.barh(range(len(top_df)), top_df["n_reports"], color=PARLA_BLUE, edgecolor="none")
    ax.set_yticks(range(len(top_df)))
    ax.set_yticklabels(wrap_labels(list(top_df["center"]), 30), fontsize=8)
    ax.set_xlabel("Number of reports")
    ax.set_ylabel("")
    ax.set_title("Largest represented centers", fontsize=11, weight="bold")
    annotate_hbars(ax, list(top_df["n_reports"]), x_pad=0.35)
    ax.set_xlim(0, max(top_df["n_reports"]) * 1.24)
    ax.grid(axis="x", color="#DDDDDD", linewidth=0.7)
    sns.despine(ax=ax, left=True)
    save_plot(fig, out_dir, "tcga_validation_center_diversity")


def plot_summary_tiles(summary: dict[str, int], out_dir: Path) -> None:
    tiles = [
        ("TCGA cases", summary["cases"], PARLA_BLUE),
        ("Cancer cohorts", summary["projects"], PARLA_BLUE),
        ("Centers", summary["centers"], PARLA_BLUE),
        ("TSS codes", summary["tss_codes"], LIGHT_GRAY),
        ("Primary sites", summary["primary_sites"], LIGHT_GRAY),
        ("Disease types", summary["disease_types"], LIGHT_GRAY),
    ]

    fig, ax = plt.subplots(figsize=(11.4, 3.2))
    ax.set_axis_off()
    ax.set_title(
        "Breadth of the TCGA external validation cohort",
        weight="bold",
        fontsize=14,
        pad=16,
    )
    ax.text(
        0.5,
        0.88,
        "All 500 reports matched GDC metadata",
        transform=ax.transAxes,
        ha="center",
        va="center",
        fontsize=9.5,
        color=DARK_GRAY,
    )

    tile_width = 0.148
    gap = 0.014
    start_x = (1 - (tile_width * len(tiles) + gap * (len(tiles) - 1))) / 2
    for index, (label, value, color) in enumerate(tiles):
        x = start_x + index * (tile_width + gap)
        rect = plt.Rectangle(
            (x, 0.16),
            tile_width,
            0.56,
            transform=ax.transAxes,
            facecolor=color,
            edgecolor="none",
            alpha=1.0,
        )
        ax.add_patch(rect)
        label_color = "white" if color == PARLA_BLUE else TEXT
        ax.text(
            x + tile_width / 2,
            0.50,
            str(value),
            transform=ax.transAxes,
            ha="center",
            va="center",
            fontsize=24,
            weight="bold",
            color=label_color,
        )
        ax.text(
            x + tile_width / 2,
            0.30,
            label,
            transform=ax.transAxes,
            ha="center",
            va="center",
            fontsize=9.5,
            weight="bold",
            color=label_color,
        )
    save_plot(fig, out_dir, "tcga_validation_diversity_summary")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metadata-csv", type=Path, default=Path("tcga_external_validation_metadata.csv"))
    parser.add_argument(
        "--center-map-json",
        type=Path,
        default=None,
        help="center->[tss_code] mapping. Optional if --metadata-csv already has a cleaned_center column.",
    )
    parser.add_argument("--out-dir", type=Path, default=Path("."))
    args = parser.parse_args()

    sns.set_theme(style="whitegrid", font="Arial")
    plt.rcParams.update(
        {
            "axes.titlesize": 12,
            "axes.labelsize": 10,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "figure.dpi": 160,
            "savefig.dpi": 600,
        }
    )

    metadata = read_metadata(args.metadata_csv)
    if args.center_map_json is not None:
        code_to_center = invert_center_mapping(args.center_map_json)
        metadata["cleaned_center"] = metadata.apply(
            lambda row: code_to_center.get(row["tss_code"], row["tss_source_site"] or "Unmapped"),
            axis=1,
        )
    elif "cleaned_center" not in metadata.columns:
        raise SystemExit(
            "Provide --center-map-json, or pass a --metadata-csv that already has a cleaned_center column."
        )

    total = len(metadata)
    project_counter = Counter(metadata["project_id"])
    project_names = metadata.drop_duplicates("project_id").set_index("project_id")["project_name"].to_dict()
    project_counts = count_table(project_counter, total, "project_id")
    project_counts["project_name"] = project_counts["project_id"].map(project_names)

    center_counts = count_table(Counter(metadata["cleaned_center"]), total, "center")
    tss_counts = count_table(Counter(metadata["tss_code"]), total, "tss_code")
    primary_site_counts = count_table(Counter(metadata["primary_site"]), total, "primary_site")
    disease_type_counts = count_table(Counter(metadata["disease_type"]), total, "disease_type")

    write_counts(project_counts, args.out_dir / "tcga_external_validation_project_counts_cleaned.csv")
    write_counts(center_counts, args.out_dir / "tcga_external_validation_cleaned_center_counts.csv")
    write_counts(tss_counts, args.out_dir / "tcga_external_validation_tss_counts_cleaned.csv")
    write_counts(primary_site_counts, args.out_dir / "tcga_external_validation_primary_site_counts_cleaned.csv")
    write_counts(disease_type_counts, args.out_dir / "tcga_external_validation_disease_type_counts_cleaned.csv")
    metadata.to_csv(args.out_dir / "tcga_external_validation_metadata_cleaned_centers.csv", index=False)

    summary = {
        "cases": total,
        "projects": project_counts.shape[0],
        "centers": center_counts.shape[0],
        "tss_codes": tss_counts.shape[0],
        "primary_sites": primary_site_counts.shape[0],
        "disease_types": disease_type_counts.shape[0],
    }
    with (args.out_dir / "tcga_external_validation_cleaned_diversity_summary.json").open("w") as handle:
        json.dump(summary, handle, indent=2)

    plot_summary_tiles(summary, args.out_dir)
    plot_project_distribution(project_counts, args.out_dir)
    plot_center_diversity(center_counts, tss_counts.shape[0], args.out_dir)
    plot_primary_site_distribution(primary_site_counts, args.out_dir)
    plot_disease_type_distribution(disease_type_counts, args.out_dir)


if __name__ == "__main__":
    main()
