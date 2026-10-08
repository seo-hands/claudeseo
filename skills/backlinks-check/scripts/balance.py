#!/usr/bin/env python3
"""Manual balance check (appendix/user_data, free).  The stages take the balance themselves before the first paid
request and at the end; this script is for a check in between.  Prints only the balance - never the login."""
import bl_common as bl


def main():
    ap = bl.parser(__doc__.split("\n")[0])
    ap.add_argument("--label", default="manual")
    a = ap.parse_args()
    if not a.run:
        raise SystemExit("потрібен --run")
    run = bl.Run(a)
    bal = run.balance(a.label)
    log = run.balances()
    print(f"баланс: {bal} $")
    if len(log) > 1:
        print(f"від початку запуску ({log[0]['label']}, {log[0]['balance']} $): витрачено {log[0]['balance'] - log[-1]['balance']:.6f} $; за полями cost: {run.spent():.6f} $")


if __name__ == "__main__":
    main()
