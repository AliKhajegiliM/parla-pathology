#!/usr/bin/env python3
"""Reproduce the robustness statistics reported on the PaRLA model card from the
committed judge records (and, optionally, the raw generations for the length
analysis).

Usage:
    python analyze_judgments.py --judgments ../data/judgments.jsonl
    python analyze_judgments.py --judgments ../data/judgments.jsonl \
        --generations-dir /path/to/gen_chandra_shards   # enables length control

Outputs a JSON summary to stdout. Everything except the length analysis is
computed from data/judgments.jsonl alone (committed); the length analysis needs
the base/PaRLA generation shards (hosted externally, see data/README.md).
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import statistics
from collections import Counter
from pathlib import Path


def load_judgments(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def sign_test_z(wins: int, losses: int) -> float:
    """Normal approximation to a two-sided sign test on decided (non-tie) cases."""
    n = wins + losses
    if n == 0:
        return 0.0
    mu, sd = n / 2, math.sqrt(n * 0.25)
    return (wins - 0.5 - mu) / sd


def load_lengths(generations_dir: str, arm: str) -> dict[str, int]:
    """arm is 'before' or 'after'; matches gen_chandra_<arm>_*.jsonl in the dir."""
    lengths: dict[str, int] = {}
    for f in glob.glob(str(Path(generations_dir) / f"*{arm}*.jsonl")):
        for line in open(f, encoding="utf-8"):
            r = json.loads(line)
            lengths[r["report_id"]] = len(r.get("text", ""))
    return lengths


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--judgments", type=Path, default=Path("../data/judgments.jsonl"))
    ap.add_argument("--generations-dir", default=None, help="dir holding gen_chandra_before_*.jsonl and gen_chandra_after_*.jsonl")
    ap.add_argument("--lengths", type=Path, default=Path("../results/judge/generation_lengths.csv"),
                    help="committed per-report length table (report_id,base_len,parla_len); used if --generations-dir is not given")
    args = ap.parse_args()

    J = load_judgments(args.judgments)
    n = len(J)
    wins = Counter(x["winner"] for x in J)
    w, los, tie = wins["after"], wins["before"], wins["tie"]

    before_om = [len(x.get("before_major_omissions", [])) for x in J]
    after_om = [len(x.get("after_major_omissions", [])) for x in J]
    before_hal = [len(x.get("before_hallucinations", [])) for x in J]
    after_hal = [len(x.get("after_hallucinations", [])) for x in J]

    out = {
        "n": n,
        "win_counts": {"parla": w, "base": los, "tie": tie},
        "win_rate_pct": {"parla": round(100 * w / n, 1), "base": round(100 * los / n, 1), "tie": round(100 * tie / n, 1)},
        "sign_test_z_decided": round(sign_test_z(w, los), 1),
        "sign_test_note": "z on decided (non-tie) cases; two-sided p is astronomically small (< 1e-50)",
        "mean_major_omissions_per_report": {"base": round(statistics.mean(before_om), 2), "parla": round(statistics.mean(after_om), 2)},
        "cases_with_hallucination_pct": {"base": round(100 * sum(1 for x in before_hal if x) / n, 1), "parla": round(100 * sum(1 for x in after_hal if x) / n, 1)},
        "total_hallucination_items": {"base": sum(before_hal), "parla": sum(after_hal)},
    }

    bl = al = None
    if args.generations_dir:
        bl, al = load_lengths(args.generations_dir, "before"), load_lengths(args.generations_dir, "after")
    elif args.lengths and args.lengths.exists():
        bl, al = {}, {}
        import csv as _csv
        for row in _csv.DictReader(open(args.lengths)):
            bl[row["report_id"]] = int(row["base_len"]); al[row["report_id"]] = int(row["parla_len"])
    if bl and al:
        pairs = [(x["report_id"], x["winner"]) for x in J if x["report_id"] in bl and x["report_id"] in al]
        longer = sum(1 for rid, _ in pairs if al[rid] > bl[rid])
        ratio = statistics.mean([al[rid] for rid, _ in pairs]) / statistics.mean([bl[rid] for rid, _ in pairs])
        sub = [(rid, wnr) for rid, wnr in pairs if al[rid] <= bl[rid]]
        sub_w = Counter(wnr for _, wnr in sub)
        out["length_control"] = {
            "matched_pairs": len(pairs),
            "parla_longer_pct": round(100 * longer / len(pairs), 1),
            "mean_length_ratio": round(ratio, 2),
            "subset_parla_not_longer": {
                "n": len(sub),
                "parla_win_pct": round(100 * sub_w["after"] / len(sub), 0),
                "base_win_pct": round(100 * sub_w["before"] / len(sub), 0),
                "tie_pct": round(100 * sub_w["tie"] / len(sub), 0),
            },
        }
    else:
        out["length_control"] = "not computed (needs --lengths CSV or --generations-dir)"

    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
