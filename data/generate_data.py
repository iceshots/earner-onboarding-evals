#!/usr/bin/env python3
"""
Synthetic data generator for the Earner Onboarding Assistant.

Produces ONE wide table (one row per earner) as CSV + SQLite, a hidden ground-truth
sidecar for the validator, and a data_dictionary.md built from the generated data.

Usage:
    python generate_data.py                      # uses config.json, seed from config
    python generate_data.py --seed 7             # different seed, same config
    python generate_data.py --config my.json --out-dir out/

Everything is synthetic. No real company schema, thresholds or numbers are used.
"""
import argparse
import json
import os
import sqlite3
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

CHECKS = ["legal_entity", "shareholder", "payment_profile"]
COLUMNS = [
    "earner_id", "earner_name", "earner_type", "region", "business_size",
    "onboarding_channel", "start_date", "start_week", "start_month",
    "legal_entity_status", "legal_entity_failure_reason",
    "legal_entity_status_updated_at", "legal_entity_is_stuck",
    "shareholder_status", "shareholder_failure_reason",
    "shareholder_status_updated_at", "shareholder_is_stuck",
    "payment_profile_status", "payment_profile_failure_reason",
    "payment_profile_status_updated_at", "payment_profile_is_stuck",
    "overall_status", "data_last_updated_at",
]
TS_FMT = "%Y-%m-%d %H:%M:%S"


# --------------------------------------------------------------------------- helpers
def pick(rng, options, weights):
    w = np.asarray(weights, dtype=float)
    return options[rng.choice(len(options), p=w / w.sum())]


def weighted_series(rng, mix, n):
    keys = list(mix.keys())
    p = np.array([mix[k] for k in keys], dtype=float)
    return rng.choice(keys, size=n, p=p / p.sum())


def make_names(rng, types, cfg):
    adj = ["Casa", "Golden", "Little", "Blue", "Urban", "Royal", "Spice", "Maple", "Harbor",
           "Olive", "Silver", "Saffron", "Lotus", "Cedar", "Copper", "Amber", "Willow", "Crimson",
           "Juniper", "Sunny", "Rustic", "Velvet", "Coral", "Ivory", "Bamboo"]
    noun = ["Lumen", "Garden", "Kitchen", "Bistro", "Grill", "Table", "Tavern", "Noodle House",
            "Cafe", "Eatery", "Pantry", "Smokehouse", "Diner", "Bakery", "Canteen", "Oven",
            "Deli", "Wok", "Taqueria", "Trattoria"]
    district = ["Riverside", "Old Town", "Central", "Harbourfront", "Hillcrest", "Market Square",
                "Eastside", "Westend", "Lakeside", "Station Road", "Uptown", "Parkview"]
    f_prefix = ["Northwind", "Metro", "Alpine", "Summit", "Coastal", "Orbit", "Delta", "Pioneer",
                "Skyline", "Evergreen", "Meridian", "Beacon", "Atlas", "Vertex", "Horizon",
                "Cascade", "Ironbridge", "Sterling"]
    f_suffix = ["Fleet Services", "Logistics", "Transport", "Cabs", "Couriers", "Mobility",
                "Rides", "Freight Partners"]
    first = ["Marco", "Aisha", "Wei", "Priya", "Lucas", "Sofia", "Kenji", "Fatima", "Daniel",
             "Elena", "Rahul", "Mei", "Omar", "Anna", "Tomas", "Yuki", "Carlos", "Nadia",
             "Liam", "Hana", "Pedro", "Ingrid", "Arjun", "Zoe", "Mateo", "Leila", "Jonas",
             "Sana", "Ethan", "Mina", "Viktor", "Chloe", "Ravi", "Isabel", "Kofi", "Lena"]
    last = ["Vidal", "Khan", "Chen", "Sharma", "Silva", "Rossi", "Tanaka", "Haddad", "Murphy",
            "Petrov", "Patel", "Lin", "Nasser", "Novak", "Horvat", "Sato", "Reyes", "Ali",
            "Walker", "Kim", "Costa", "Larsen", "Nair", "Brown", "Torres", "Saleh", "Weber",
            "Iqbal", "Clark", "Park", "Orlov", "Dubois", "Rao", "Moreno", "Mensah", "Fischer"]
    names = []
    for t in types:
        if t == "restaurant":
            nm = f"{adj[rng.integers(len(adj))]} {noun[rng.integers(len(noun))]}"
            if rng.random() < 0.5:
                nm += f" - {district[rng.integers(len(district))]}"
        elif t == "fleet":
            nm = f"{f_prefix[rng.integers(len(f_prefix))]} {f_suffix[rng.integers(len(f_suffix))]}"
            if rng.random() < 0.5:
                nm += f" - {district[rng.integers(len(district))]}"
        else:
            nm = f"{first[rng.integers(len(first))]} {last[rng.integers(len(last))]}"
        names.append(nm)
    return names


def sample_onboarding_hours(rng, n, cfg):
    """Latent total onboarding time (hours) per earner. See config for the shape."""
    c = cfg["onboarding_time"]
    is_tail = rng.random(n) >= c["body_share"]
    T = np.empty(n)

    def draw(count, fn, ok):
        out, need = [], count
        while need > 0:
            x = fn(max(need * 2, 16))
            x = x[ok(x)][:need]
            out.append(x)
            need -= len(x)
        return np.concatenate(out) if out else np.empty(0)

    T[~is_tail] = draw((~is_tail).sum(),
                       lambda k: rng.lognormal(c["body_mu"], c["body_sigma"], k),
                       lambda x: x <= c["p90_hours"])
    T[is_tail] = draw(is_tail.sum(),
                      lambda k: c["p90_hours"] + rng.exponential(c["tail_theta"], k),
                      lambda x: x <= c["tail_cap_hours"])
    return np.maximum(T, 0.5), is_tail


def start_timestamps(rng, n, cfg):
    d0 = datetime.strptime(cfg["first_start_date"], "%Y-%m-%d")
    d1 = datetime.strptime(cfg["last_start_date"], "%Y-%m-%d")
    days = [d0 + timedelta(days=i) for i in range((d1 - d0).days + 1)]
    shape = cfg["start_date_shape"]
    growth = np.linspace(1.0, shape["growth_first_to_last"], len(days))
    w = np.array([shape["weekday_weights"][d.weekday()] for d in days]) * growth
    idx = rng.choice(len(days), size=n, p=w / w.sum())
    secs = rng.integers(6 * 3600, 22 * 3600, size=n)  # onboarding starts 06:00-22:00 UTC
    return [days[i] + timedelta(seconds=int(s)) for i, s in zip(idx, secs)]


def reason_weights(cfg, region, check, status):
    base = (dict(cfg["pending_reasons"]) if status == "pending"
            else dict(cfg["checks"][check]["rejected_reasons"]))
    base = {k: v for k, v in base.items() if not k.startswith("_")}
    for p in cfg["regional_patterns"]:
        if (p["region"] == region and p["status"] == status
                and p["check"] in (check, "*") and p["reason"] in base):
            base[p["reason"]] *= p["multiplier"]
    return list(base.keys()), list(base.values())


def build_timeline(rng, cfg, region, check, t_end, mode, n_rej):
    """List of (hours_since_start, status, reason). mode: 'pass' or 'blocked'."""
    def ev(t, status):
        if status == "passed":
            return (t, status, None)
        opts, w = reason_weights(cfg, region, check, status)
        return (t, status, pick(rng, opts, w))

    events = [ev(0.0, "pending")]  # submission waiting for review
    if mode == "pass":
        k = 2 * n_rej
        if k:
            ts = np.sort(rng.uniform(0.02 * t_end, 0.98 * t_end, k))
            for i, t in enumerate(ts):
                events.append(ev(float(t), "rejected" if i % 2 == 0 else "pending"))
        events.append(ev(float(t_end), "passed"))
    else:  # earner gives up at t_end; the check never passes
        k = int(rng.choice([0, 1, 2, 3], p=[0.25, 0.35, 0.25, 0.15]))
        if k:
            ts = np.sort(rng.uniform(0.02 * t_end, t_end, k))
            ts[-1] = t_end
            for i, t in enumerate(ts):
                events.append(ev(float(t), "rejected" if i % 2 == 0 else "pending"))
    return events


def state_at(events, elapsed_hours):
    cur = events[0]
    for e in events:
        if e[0] <= elapsed_hours:
            cur = e
    return cur


# --------------------------------------------------------------------------- generation
def generate(cfg, seed):
    rng = np.random.default_rng(seed)
    n = cfg["n_earners"]
    snapshot = datetime.strptime(cfg["snapshot_ts"], TS_FMT)

    ids = [f"P-{10001 + i}" for i in range(n)]
    types = weighted_series(rng, cfg["earner_type_mix"], n)
    regions = weighted_series(rng, cfg["region_mix"], n)
    sizes = [pick(rng, list(cfg["business_size_mix"][t].keys()),
                  list(cfg["business_size_mix"][t].values())) for t in types]
    channels = [pick(rng, list(cfg["onboarding_channel_mix"][t].keys()),
                     list(cfg["onboarding_channel_mix"][t].values())) for t in types]
    starts = start_timestamps(rng, n, cfg)
    names = make_names(rng, types, cfg)

    # planted prompt-injection strings live only in earner_name
    inj_idx = rng.choice(n, size=len(cfg["injection_rows"]), replace=False)
    for i, s in zip(inj_idx, cfg["injection_rows"]):
        names[i] = s
    inj_set = set(int(i) for i in inj_idx)

    T, is_tail = sample_onboarding_hours(rng, n, cfg)
    ch = cfg["churn"]
    churned = rng.random(n) < np.where(is_tail, ch["p_if_tail"], ch["p_if_body"])
    q = cfg["agent_queue_share"]
    mean = np.where(is_tail, q["tail_mean"], q["body_mean"])
    share = rng.beta(mean * q["concentration"], (1 - mean) * q["concentration"])
    queue_hours = share * T

    rej = cfg["rejections_by_onboarding_time"]

    rows, truth = [], []
    for i in range(n):
        etype, region, t_total = types[i], regions[i], float(T[i])
        applicable = [c for c in CHECKS if etype in cfg["checks"][c]["applies_to"]]
        bw = cfg["bottleneck_weights"]["driver" if etype == "driver" else "non_driver"]
        bottleneck = pick(rng, list(bw.keys()), list(bw.values()))

        blocked = set()
        if churned[i]:
            blocked.add(bottleneck)
            for c in applicable:
                if c != bottleneck and rng.random() < ch["p_second_check_also_blocked"]:
                    blocked.add(c)

        b = next(j for j, ub in enumerate(rej["bounds_hours"]) if t_total <= ub)
        timelines = {}
        for c in applicable:
            n_rej = int(rng.choice([0, 1, 2], p=rej["probs"][b]))
            if c in blocked:
                # the bottleneck check sees activity until the earner gives up; other blocked checks earlier
                t_last = t_total if c == bottleneck else max(0.5, t_total * rng.uniform(0.4, 1.0))
                timelines[c] = build_timeline(rng, cfg, region, c, t_last, "blocked", 0)
            else:
                t_k = t_total if c == bottleneck else max(0.5, t_total * rng.uniform(0.1, 0.98))
                timelines[c] = build_timeline(rng, cfg, region, c, t_k, "pass", n_rej)

        elapsed = (snapshot - starts[i]).total_seconds() / 3600.0
        row = {
            "earner_id": ids[i], "earner_name": names[i], "earner_type": etype,
            "region": region, "business_size": sizes[i], "onboarding_channel": channels[i],
            "start_date": starts[i].strftime("%Y-%m-%d"),
            "start_week": (starts[i] - timedelta(days=starts[i].weekday())).strftime("%Y-%m-%d"),
            "start_month": starts[i].strftime("%Y-%m"),
        }
        all_passed = True
        for c in CHECKS:
            if c not in applicable:
                row[f"{c}_status"] = "not_applicable"
                row[f"{c}_failure_reason"] = None
                row[f"{c}_status_updated_at"] = None
                row[f"{c}_is_stuck"] = 0
                continue
            t, status, reason = state_at(timelines[c], elapsed)
            row[f"{c}_status"] = status
            row[f"{c}_failure_reason"] = reason
            row[f"{c}_status_updated_at"] = (starts[i] + timedelta(hours=t)).strftime(TS_FMT)
            row[f"{c}_is_stuck"] = int(status != "passed")
            all_passed &= status == "passed"
        row["overall_status"] = "passed" if all_passed else "failed"
        row["data_last_updated_at"] = cfg["snapshot_ts"]
        rows.append(row)

        truth.append({
            "earner_id": ids[i],
            "onboarding_hours": round(t_total, 2),
            "agent_queue_hours": round(float(queue_hours[i]), 2),
            "is_churned": int(churned[i]),
            "completes_at": None if churned[i] else (starts[i] + timedelta(hours=t_total)).strftime(TS_FMT),
            "bottleneck_check": bottleneck,
            "blocked_checks": ",".join(sorted(blocked)),
            "is_injection_row": int(i in inj_set),
        })

    return pd.DataFrame(rows)[COLUMNS], pd.DataFrame(truth)


# --------------------------------------------------------------------------- dictionary
FIELD_META = {
    "earner_id": ("Earner profile", "Unique earner identifier; the lookup key for single-earner questions"),
    "earner_name": ("Earner profile", "Fake business or person name. Not unique. A few rows carry planted prompt-injection text (red-team test)"),
    "earner_type": ("Earner profile", "Kind of earner"),
    "region": ("Earner profile", "Operating region"),
    "business_size": ("Earner profile", "Size band of the earner. Drivers are always `individual`"),
    "onboarding_channel": ("Earner profile", "How the earner came to the platform"),
    "start_date": ("Earner profile", "Date onboarding began"),
    "start_week": ("Earner profile", "Monday of the week containing `start_date` (first and last weeks are partial)"),
    "start_month": ("Earner profile", "Calendar month of `start_date` (YYYY-MM)"),
    "overall_status": ("Overall", "`passed` if every applicable check is `passed`, otherwise `failed`. Derived from the three check statuses"),
    "data_last_updated_at": ("Metadata", "Snapshot time (UTC). The assistant must show this with every answer"),
}
CHECK_LABEL = {"legal_entity": "Check: Legal Entity", "shareholder": "Check: Shareholder",
               "payment_profile": "Check: Payment Profile"}


def field_meta(col):
    if col in FIELD_META:
        return FIELD_META[col]
    for c in CHECKS:
        if col.startswith(c + "_"):
            ctx, kind = CHECK_LABEL[c], col[len(c) + 1:]
            human = c.replace("_", " ")
            if kind == "status":
                extra = (" Not applicable to drivers." if c == "legal_entity" else " Applies to all earner types.")
                return ctx, f"Current status of the {human} check." + extra
            if kind == "failure_reason":
                return ctx, (f"Recorded reason the {human} check is not passed. Null only when the check is "
                             "`passed` (or `not_applicable`). `awaiting_agent_review` is the platform-side reason; "
                             "all others are earner-side")
            if kind == "status_updated_at":
                return ctx, f"UTC time the {human} status last changed. Null if not applicable"
            if kind == "is_stuck":
                return ctx, ("1 if the check status is `pending` or `rejected` at snapshot time, else 0. "
                             "Point-in-time only; time in state is not considered. Equivalent to "
                             "status not in (`passed`, `not_applicable`)")
    raise KeyError(col)


def values_text(df, col):
    s = df[col]
    has_null = s.isna().any()
    if col == "earner_id":
        return f"`{s.min()}` to `{s.max()}`"
    if col == "earner_name":
        return "Synthetic text, e.g. `Casa Lumen Bistro`, `Marco Vidal`"
    if col in ("start_date", "start_week", "start_month") or col.endswith("_updated_at"):
        return f"`{s.dropna().min()}` to `{s.dropna().max()}`"
    if col == "data_last_updated_at":
        return f"`{s.iloc[0]}` (same on every row)"
    vals = sorted(s.dropna().unique().tolist())
    txt = ", ".join(f"`{v}`" for v in vals)
    return txt + ("; else null" if has_null else "")


def write_dictionary(df, path, snapshot_ts):
    lines = [
        "# Data dictionary: `earner_onboarding`",
        "",
        "One wide table, one row per earner, as of the snapshot time below. All data is synthetic.",
        f"Rows: **{len(df):,}** | Columns: **{len(df.columns)}** | Snapshot: **{snapshot_ts} UTC**",
        "",
        "| Context | Field name | Description | Field values | Distinct values |",
        "|---|---|---|---|---|",
    ]
    for col in df.columns:
        ctx, desc = field_meta(col)
        nd = int(df[col].nunique(dropna=True))
        dtxt = f"{nd:,}" + (" (+ null)" if df[col].isna().any() else "")
        lines.append(f"| {ctx} | `{col}` | {desc} | {values_text(df, col)} | {dtxt} |")
    lines += [
        "",
        "## Rules that always hold",
        "",
        "- `legal_entity_status` is `not_applicable` for drivers; every other status field is one of `passed`, `pending`, `rejected`.",
        "- A failure reason is null if and only if the check is `passed` or `not_applicable`. Every `pending` or `rejected` check has a reason.",
        "- Each check only uses its own reasons (for example `bank_details_invalid` appears only under payment profile).",
        "- `*_is_stuck` is 1 exactly when the check status is `pending` or `rejected`.",
        "- `overall_status` is `passed` only if all applicable checks are `passed`.",
        "- Boolean columns are stored as 1/0. Timestamps are UTC, `YYYY-MM-DD HH:MM:SS`. Dates are `YYYY-MM-DD`.",
        "- Every status change timestamp is on or after the earner's start and on or before the snapshot time.",
        "",
    ]
    with open(path, "w") as f:
        f.write("\n".join(lines))


# --------------------------------------------------------------------------- main
def write_sqlite(df, path):
    if os.path.exists(path):
        os.remove(path)
    con = sqlite3.connect(path)
    df.to_sql("earner_onboarding", con, index=False)
    # enforce the key and add indexes for typical filters
    con.execute("CREATE UNIQUE INDEX idx_earner_id ON earner_onboarding(earner_id)")
    for c in ["region", "earner_type", "start_month", "start_week", "overall_status"]:
        con.execute(f"CREATE INDEX idx_{c} ON earner_onboarding({c})")
    con.commit()
    con.close()


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=os.path.join(here, "config.json"))
    ap.add_argument("--seed", type=int, default=None, help="override seed in config")
    ap.add_argument("--out-dir", default=here, help="root folder for output/, hidden/ and data_dictionary.md")
    a = ap.parse_args()

    with open(a.config) as f:
        cfg = json.load(f)
    seed = cfg["seed"] if a.seed is None else a.seed

    out = os.path.join(a.out_dir, "output")
    hid = os.path.join(a.out_dir, "hidden")
    os.makedirs(out, exist_ok=True)
    os.makedirs(hid, exist_ok=True)

    df, truth = generate(cfg, seed)
    df.to_csv(os.path.join(out, "earner_onboarding.csv"), index=False)
    write_sqlite(df, os.path.join(out, "earner_onboarding.sqlite"))
    truth.to_csv(os.path.join(hid, "ground_truth.csv"), index=False)
    write_dictionary(df, os.path.join(a.out_dir, "data_dictionary.md"), cfg["snapshot_ts"])
    print(f"seed={seed}  rows={len(df):,}  cols={len(df.columns)}")
    print(f"wrote {out}/earner_onboarding.csv, earner_onboarding.sqlite")
    print(f"wrote {hid}/ground_truth.csv  (validator only; do NOT expose to the chatbot)")
    print(f"wrote {a.out_dir}/data_dictionary.md")


if __name__ == "__main__":
    main()
