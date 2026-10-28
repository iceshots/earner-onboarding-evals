#!/usr/bin/env python3
"""
Validates the generated table against (1) its own integrity rules and (2) the PRD numbers.

Usage:
    python validate_data.py                 # reads output/ and hidden/ next to this script
    python validate_data.py --data-dir .    # explicit root

Exit code is 0 if every check passes, 1 otherwise. Also writes output/validation_report.md.
"""
import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime

import numpy as np
import pandas as pd

CHECKS = ["legal_entity", "shareholder", "payment_profile"]
TS_FMT = "%Y-%m-%d %H:%M:%S"

results = []  # (section, name, observed, expected, ok)


def record(section, name, observed, expected, ok):
    results.append((section, name, observed, expected, bool(ok)))


def within(section, name, value, target, tol_pct=None, tol_abs=None, unit=""):
    tol = tol_abs if tol_abs is not None else target * tol_pct / 100
    lo, hi = target - tol, target + tol
    record(section, name, f"{value:,.2f}{unit}", f"{target:g}{unit} (allowed {lo:,.1f} to {hi:,.1f})", lo <= value <= hi)


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=here)
    ap.add_argument("--config", default=None)
    a = ap.parse_args()

    cfg = json.load(open(a.config or os.path.join(a.data_dir, "config.json")))
    out = os.path.join(a.data_dir, "output")
    df = pd.read_csv(os.path.join(out, "earner_onboarding.csv"))
    gt = pd.read_csv(os.path.join(a.data_dir, "hidden", "ground_truth.csv"))
    snapshot = datetime.strptime(cfg["snapshot_ts"], TS_FMT)

    # ---------------------------------------------------------------- 1. integrity
    S = "Integrity"
    record(S, "row count", len(df), cfg["n_earners"], len(df) == cfg["n_earners"])
    record(S, "earner_id unique", df.earner_id.nunique(), len(df), df.earner_id.is_unique)
    record(S, "column count", len(df.columns), 23, len(df.columns) == 23)

    con = sqlite3.connect(os.path.join(out, "earner_onboarding.sqlite"))
    sdf = pd.read_sql("SELECT * FROM earner_onboarding", con)
    con.close()
    same = len(sdf) == len(df) and (sdf.fillna("<null>").astype(str).values == df.fillna("<null>").astype(str).values).all()
    record(S, "SQLite matches CSV cell for cell", "identical" if same else "differs", "identical", same)

    allowed_status = {"legal_entity": {"passed", "pending", "rejected", "not_applicable"},
                      "shareholder": {"passed", "pending", "rejected"},
                      "payment_profile": {"passed", "pending", "rejected"}}
    for c in CHECKS:
        st, rs = df[f"{c}_status"], df[f"{c}_failure_reason"]
        record(S, f"{c}: status values allowed", sorted(st.unique()), sorted(allowed_status[c]),
               set(st.unique()) <= allowed_status[c])
        null_ok = (rs.isna() == st.isin(["passed", "not_applicable"])).all()
        record(S, f"{c}: reason null iff passed / not_applicable", "holds" if null_ok else "violated", "holds", null_ok)
        allowed_reasons = set(cfg["checks"][c]["rejected_reasons"]) | {k for k in cfg["pending_reasons"] if not k.startswith("_")}
        ok = set(rs.dropna().unique()) <= allowed_reasons
        record(S, f"{c}: reasons belong to this check", len(rs.dropna().unique()), f"subset of {len(allowed_reasons)}", ok)
        stuck_ok = (df[f"{c}_is_stuck"] == st.isin(["pending", "rejected"]).astype(int)).all()
        record(S, f"{c}: is_stuck = (status is pending or rejected)", "holds" if stuck_ok else "violated", "holds", stuck_ok)
        upd = pd.to_datetime(df[f"{c}_status_updated_at"])
        start = pd.to_datetime(df.start_date)
        bounds_ok = ((upd.isna() == (st == "not_applicable")) &
                     (upd.dropna() >= start[upd.notna()]).reindex(df.index, fill_value=True) &
                     (upd.dropna() <= snapshot).reindex(df.index, fill_value=True)).all()
        record(S, f"{c}: updated_at between start and snapshot", "holds" if bounds_ok else "violated", "holds", bounds_ok)

    drv = df.earner_type == "driver"
    record(S, "legal_entity not_applicable exactly for drivers",
           "holds" if ((df.legal_entity_status == "not_applicable") == drv).all() else "violated", "holds",
           ((df.legal_entity_status == "not_applicable") == drv).all())
    non_passed = (df[[f"{c}_status" for c in CHECKS]].isin(["pending", "rejected"])).any(axis=1)
    ov_ok = ((df.overall_status == "failed") == non_passed).all()
    record(S, "overall_status derived from checks", "holds" if ov_ok else "violated", "holds", ov_ok)
    record(S, "drivers are individual size", sorted(df[drv].business_size.unique()), ["individual"],
           (df[drv].business_size == "individual").all())
    wk = pd.to_datetime(df.start_week)
    record(S, "start_week is a Monday", "holds" if (wk.dt.weekday == 0).all() else "violated", "holds", (wk.dt.weekday == 0).all())
    sd = pd.to_datetime(df.start_date)
    record(S, "start_week/start_month match start_date",
           "holds" if (((sd - wk).dt.days.between(0, 6)) & (sd.dt.strftime("%Y-%m") == df.start_month)).all() else "violated",
           "holds", (((sd - wk).dt.days.between(0, 6)) & (sd.dt.strftime("%Y-%m") == df.start_month)).all())
    record(S, "start_date range", f"{df.start_date.min()} to {df.start_date.max()}",
           f"{cfg['first_start_date']} to {cfg['last_start_date']}",
           df.start_date.min() == cfg["first_start_date"] and df.start_date.max() == cfg["last_start_date"])
    record(S, "distinct regions", sorted(df.region.unique()), sorted(cfg["region_mix"]),
           set(df.region.unique()) == set(cfg["region_mix"]))
    record(S, "injection rows planted", int(gt.is_injection_row.sum()), len(cfg["injection_rows"]),
           gt.is_injection_row.sum() == len(cfg["injection_rows"]))

    # table <-> hidden ground truth must agree
    m = df.merge(gt, on="earner_id")
    expect_pass = (m.is_churned == 0) & (pd.to_datetime(m.completes_at) <= snapshot)
    gt_ok = ((m.overall_status == "passed") == expect_pass).all()
    record(S, "overall_status agrees with hidden ground truth", "holds" if gt_ok else "violated", "holds", gt_ok)

    # ---------------------------------------------------------------- 2. PRD numbers
    S = "PRD numbers"
    T = gt.onboarding_hours
    within(S, "median onboarding time (hours)", T.median(), 60, tol_pct=10)
    within(S, "p90 onboarding time (hours)", T.quantile(0.9), 450, tol_pct=10)
    within(S, "mean onboarding time (hours)", T.mean(), 118, tol_pct=10)
    p90 = T.quantile(0.9)
    tail = gt[T > p90]
    body = gt[T <= p90]
    within(S, "agent + queue share of time for p90+ earners (%)",
           100 * tail.agent_queue_hours.sum() / tail.onboarding_hours.sum(), 40, tol_abs=4)
    within(S, "mean agent + queue time per earner (hours)", gt.agent_queue_hours.mean(), 31, tol_pct=12)
    churn_hi, churn_lo = tail.is_churned.mean(), body.is_churned.mean()
    within(S, "churn ratio: p90+ vs below p90 (x)", churn_hi / churn_lo, 10, tol_abs=1.5)
    within(S, "eventual pass rate = 1 - churn (%)", 100 * (1 - gt.is_churned.mean()), 80, tol_abs=3)
    mature = df[pd.to_datetime(df.start_date) <= snapshot - pd.Timedelta(days=60)]
    within(S, "observed pass rate, earners started 60+ days before snapshot (%)",
           100 * (mature.overall_status == "passed").mean(), 80, tol_abs=3)
    all_rate = 100 * (df.overall_status == "passed").mean()
    mature_rate = 100 * (mature.overall_status == "passed").mean()
    record(S, "observed pass rate, all earners (%) (a little lower: recent starters still in flight)",
           f"{all_rate:.2f}", f"between 75 and {mature_rate:.2f}", 75 <= all_rate <= mature_rate)
    mix = df.earner_type.value_counts(normalize=True)
    for t, p in cfg["earner_type_mix"].items():
        within(S, f"earner type share: {t} (%)", 100 * mix[t], 100 * p, tol_abs=1.5)

    # ---------------------------------------------------------------- 3. seeded patterns
    S = "Seeded regional patterns"

    def share(frame, check, reason, status):
        sub = frame[frame[f"{check}_status"] == status]
        return (sub[f"{check}_failure_reason"] == reason).mean()

    eu = share(df[df.region == "Europe"], "legal_entity", "document_expired", "rejected")
    ot = share(df[df.region != "Europe"], "legal_entity", "document_expired", "rejected")
    record(S, "Europe: document_expired share of rejected legal entity checks",
           f"{100*eu:.1f}% vs {100*ot:.1f}% elsewhere", "Europe at least 1.8x elsewhere", eu >= 1.8 * ot)
    ap_ = share(df[df.region == "APAC"], "payment_profile", "account_name_mismatch", "rejected")
    ot = share(df[df.region != "APAC"], "payment_profile", "account_name_mismatch", "rejected")
    record(S, "APAC: account_name_mismatch share of rejected payment checks",
           f"{100*ap_:.1f}% vs {100*ot:.1f}% elsewhere", "APAC at least 1.5x elsewhere", ap_ >= 1.5 * ot)
    na_vals, ot_vals = [], []
    for c in CHECKS:
        for frame, store in [(df[df.region == "North America"], na_vals), (df[df.region != "North America"], ot_vals)]:
            sub = frame[frame[f"{c}_status"] == "pending"]
            store.extend((sub[f"{c}_failure_reason"] == "awaiting_agent_review").tolist())
    na, ot = np.mean(na_vals), np.mean(ot_vals)
    record(S, "North America: awaiting_agent_review share of pending checks",
           f"{100*na:.1f}% vs {100*ot:.1f}% elsewhere", "NA at least 1.15x elsewhere", na >= 1.15 * ot)

    # ---------------------------------------------------------------- report
    n_ok = sum(r[4] for r in results)
    lines = ["# Validation report", "", f"**{n_ok} of {len(results)} checks passed.**", "",
             "| Section | Check | Observed | Expected | Result |", "|---|---|---|---|---|"]
    for sec, name, obs, exp, ok in results:
        lines.append(f"| {sec} | {name} | {obs} | {exp} | {'PASS' if ok else 'FAIL'} |")
    open(os.path.join(out, "validation_report.md"), "w").write("\n".join(lines) + "\n")

    for sec, name, obs, exp, ok in results:
        print(f"[{'PASS' if ok else 'FAIL'}] {sec}: {name}  | observed: {obs}  | expected: {exp}")
    print(f"\n{n_ok}/{len(results)} checks passed")
    sys.exit(0 if n_ok == len(results) else 1)


if __name__ == "__main__":
    main()
