#!/usr/bin/env python3
"""Dry-run: the list of requests of stages 1 and 2 against the cache, the estimate without and with the reserve, and
(with --missing) every answer that is not in the cache.  Never sends a paid request."""
import bl_common as bl


def main():
    ap = bl.parser(__doc__.split("\n")[0])
    ap.add_argument("--stage", default="all", choices=["1", "2", "all"])
    ap.add_argument("--candidates", default="", help="кандидати етапу 2 через кому (інакше — з stage1.json або умовні N+1)")
    ap.add_argument("--missing", action="store_true", help="перелічити відповіді, яких бракує в кеші")
    a = ap.parse_args()
    if not a.run:
        raise SystemExit("потрібен --run")
    run = bl.Run(a)
    if not run.input:
        raise SystemExit(f"Немає {run.path('input.json')}: спершу stage0.py --input <файл>")
    P = []
    cands = None
    if a.stage in ("1", "all"):
        P += bl.plan_stage1(run)
    if a.stage in ("2", "all"):
        P2, cands = bl.plan_stage2(run, [bl.norm_domain(x) for x in a.candidates.split(",") if x.strip()] or None)
        P += P2
    print(f"Запуск {run.name}: кеш {run.cache}" + (" (офлайн: TTL не враховується)" if run.offline else f" (TTL {bl.TTL_DAYS} днів, сьогодні {run.today})"))
    total, with_reserve = bl.print_plan(P, run.budget, run.spent(), show_missing=a.missing)
    if cands:
        print(f"  кандидати етапу 2 ({len(cands)}): {', '.join(cands)}")
    full = sum(p["est"] for p in P)
    print(f"  повна вартість без кешу: {full:.4f} $ без запасу, {full * (1 + bl.RESERVE):.4f} $ із запасом")
    print("  платних запитів не виконано (dry-run)")
    return total, with_reserve, full


if __name__ == "__main__":
    main()
