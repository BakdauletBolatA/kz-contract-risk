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


def _corpus_audit(_: argparse.Namespace) -> int:
    from contract_risk.corpus.audit import (
        audit_balance,
        audit_coverage,
        audit_leakage,
        balance_table,
    )
    from contract_risk.corpus.manifest import corpus_hash, load_corpus
    from contract_risk.evaluation.dataset import SPLITS, load_split
    from contract_risk.ingestion import parse_text

    clauses = load_corpus(DATA / "corpus")
    print(f"корпус: {len(clauses)} формулировок, версия {corpus_hash(clauses)}")
    print(f"{'тип/категория':32} нейтр.  сторона А  сторона Б")
    for row in balance_table(clauses):
        print(
            f"{row.contract_type + '/' + row.category:32} {row.neutral:6} "
            f"{row.side_a:10} {row.side_b:10}"
        )
    eval_texts = [
        (f"{d.doc_id}:{c.id}", c.text)
        for split in SPLITS
        for d in load_split(DATA / "eval", split)
        for c in parse_text(d.text, d.doc_id).analysable_clauses
    ]
    problems = audit_balance(clauses) + audit_coverage(clauses)
    problems += audit_leakage(clauses, eval_texts)
    print(f"проблем: {len(problems)}")
    for p in problems:
        print("  " + p)
    return 1 if problems else 0


def _corpus_load(args: argparse.Namespace) -> int:
    from contract_risk.config import get_settings
    from contract_risk.corpus.manifest import load_corpus
    from contract_risk.retrieval.embeddings import build_embedder
    from contract_risk.retrieval.index import load_into_pgvector

    settings = get_settings()
    if not settings.database_url:
        print("KZCR_DATABASE_URL не задан (см. .env.example)", file=sys.stderr)
        return 2
    embedder = build_embedder(settings.embedder)
    n = load_into_pgvector(
        load_corpus(DATA / "corpus"), embedder, settings.database_url, args.rebuild
    )
    print(f"в pgvector {n} формулировок, эмбеддер {embedder.name}")
    return 0


def _corpus_search(args: argparse.Namespace) -> int:
    from contract_risk.corpus.manifest import load_corpus
    from contract_risk.retrieval.embeddings import build_embedder
    from contract_risk.retrieval.index import ReferenceIndex

    index = ReferenceIndex.in_memory(load_corpus(DATA / "corpus"), build_embedder("hashing"))
    for hit in index.similar(
        args.text, contract_type=args.type, category=args.category, lang=args.lang, k=args.k
    ):
        print(f"{hit.score:.3f}  {hit.clause.id:24} [{hit.clause.favours}]  {hit.clause.text}")
    return 0


def _train(args: argparse.Namespace) -> int:
    from contract_risk.config import get_settings
    from contract_risk.evaluation.dataset import load_split
    from contract_risk.ingestion import parse_text
    from contract_risk.ml.model import ClauseRiskModel, load_or_train

    settings = get_settings()
    if args.if_stale:
        # Сохранённая модель годится, если совпадают dev-срез, версия признаков
        # (MODEL_VERSION) и scikit-learn; иначе — обучение заново.
        model = load_or_train(settings.models_dir, settings.data_dir, parse_text)
    else:
        model = ClauseRiskModel.train(load_split(settings.data_dir / "eval", "dev"), parse_text)
        model.save(settings.models_dir / "clause_risk.joblib")
    print(f"out-of-fold: {model.oof}")
    print(
        f"порог ML {model.threshold}, выдача в гибриде {model.emit_threshold}, "
        f"маршрутизация в LLM {model.route_threshold}"
    )
    return 0


def _analyze(args: argparse.Namespace) -> int:
    from contract_risk.pipeline import Analyzer
    from contract_risk.report.render import render_html, render_pdf
    from contract_risk.schemas import Language, PartyRole

    path = Path(args.path)
    report = Analyzer.from_settings().analyze_bytes(
        path.read_bytes(), path.name, PartyRole(args.role), Language(args.lang)
    )
    if args.format == "pdf":
        payload: bytes | str = render_pdf(report)
    elif args.format == "html":
        payload = render_html(report)
    else:
        payload = report.model_dump_json(indent=2)
    if args.out:
        out = Path(args.out)
        if isinstance(payload, bytes):
            out.write_bytes(payload)
        else:
            out.write_text(payload, encoding="utf-8")
        counts = report.count_by_level()
        print(
            f"{out}: высокий {counts['high']}, средний {counts['medium']}, низкий {counts['low']}"
        )
    elif isinstance(payload, bytes):
        sys.stdout.buffer.write(payload)
    else:
        print(payload)
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
    run.add_argument("--split", default="dev", choices=["dev", "test", "handwritten", "stress"])
    run.add_argument("--out", default=str(RESULTS))
    run.set_defaults(func=_eval_run)
    table = ev.add_parser("table", help="таблица прогонов")
    table.add_argument("--out", default=str(RESULTS))
    table.set_defaults(func=_eval_table)

    corpus = sub.add_parser("corpus", help="эталонный корпус").add_subparsers(
        dest="action", required=True
    )
    corpus.add_parser("audit", help="лицензии, баланс, утечка").set_defaults(func=_corpus_audit)
    load = corpus.add_parser("load", help="загрузить в pgvector")
    load.add_argument("--rebuild", action="store_true")
    load.set_defaults(func=_corpus_load)
    search = corpus.add_parser("search", help="похожие эталоны")
    search.add_argument("text")
    search.add_argument("--type", default=None)
    search.add_argument("--category", default=None)
    search.add_argument("--lang", default=None)
    search.add_argument("-k", type=int, default=5)
    search.set_defaults(func=_corpus_search)

    train = sub.add_parser("train", help="обучить ML на dev-срезе")
    train.add_argument(
        "--if-stale", action="store_true", help="не обучать, если сохранённая модель актуальна"
    )
    train.set_defaults(func=_train)

    analyze = sub.add_parser("analyze", help="проверить договор и выдать отчёт")
    analyze.add_argument("path")
    analyze.add_argument(
        "--role",
        required=True,
        choices=["landlord", "tenant", "supplier", "buyer", "contractor", "customer"],
    )
    analyze.add_argument("--format", default="html", choices=["json", "html", "pdf"])
    analyze.add_argument("--lang", default="ru", choices=["ru", "kk"])
    analyze.add_argument("--out", default=None)
    analyze.set_defaults(func=_analyze)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
