"""kzcr — командная строка проекта.

kzcr dataset check                 целостность eval-датасета
kzcr eval run --detector rules --split test
kzcr eval table                    таблица всех прогонов для EVALUATION.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RESULTS = ROOT / "evals/results"


def _dataset_check(_: argparse.Namespace) -> int:
    from contract_risk.evaluation.dataset import SPLITS, load_split
    from contract_risk.evaluation.integrity import check_docs, check_split_leakage
    from contract_risk.ingestion import parse_text

    splits = {s: load_split(DATA / "eval", s) for s in SPLITS}
    problems: list[str] = []
    for split, docs in splits.items():
        found = check_docs(docs, parse_text)
        print(f"{split}: {len(docs)} договоров, проблем: {len(found)}")
        problems += found
    leakage = check_split_leakage(splits["dev"], splits["test"], parse_text)
    print(f"утечка формулировок test → dev: {len(leakage)}")
    for p in problems + leakage:
        print("  " + p)
    return 1 if problems or leakage else 0


def _eval_run(args: argparse.Namespace) -> int:
    from contract_risk.detectors import build_detector
    from contract_risk.evaluation.dataset import load_split
    from contract_risk.evaluation.harness import evaluate, write_run
    from contract_risk.ingestion import parse_text

    docs = load_split(DATA / "eval", args.split)
    detector = build_detector(args.detector)
    run, results, parsed = evaluate(detector, docs, parse_text, args.split)
    json_path, errors_path = write_run(run, results, parsed, Path(args.out))
    m = run["metrics"]

    def fmt(x: float | None) -> str:
        return "—" if x is None else f"{x:.3f}"

    print(f"{run['run_id']}  датасет {run['dataset_hash']}  коммит {run['git_commit']}")
    print(
        f"detection P={fmt(m['detection']['precision'])} R={fmt(m['detection']['recall'])} "
        f"F1={fmt(m['detection']['f1'])} | strict F1={fmt(m['strict']['f1'])} | "
        f"high R={fmt(m['high_recall'])} | ложные тревоги/чистый договор="
        f"{fmt(m['clean_docs']['false_alarms_per_doc'])} | док. F1={fmt(m['document']['f1'])}"
    )
    print(f"→ {json_path.relative_to(ROOT) if json_path.is_relative_to(ROOT) else json_path}")
    print(f"→ {errors_path.name}")
    return 0


def _eval_table(args: argparse.Namespace) -> int:
    from contract_risk.evaluation.harness import load_runs, summary_table

    print(summary_table(load_runs(Path(args.out))))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kzcr", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    dataset = sub.add_parser("dataset", help="eval-датасет").add_subparsers(
        dest="action", required=True
    )
    dataset.add_parser("check", help="целостность разметки").set_defaults(func=_dataset_check)

    ev = sub.add_parser("eval", help="оценка качества").add_subparsers(dest="action", required=True)
    run = ev.add_parser("run", help="прогнать детектор по срезу")
    run.add_argument("--detector", default="rules")
    run.add_argument("--split", default="dev", choices=["dev", "test", "handwritten"])
    run.add_argument("--out", default=str(RESULTS))
    run.set_defaults(func=_eval_run)
    table = ev.add_parser("table", help="таблица прогонов")
    table.add_argument("--out", default=str(RESULTS))
    table.set_defaults(func=_eval_table)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
