"""Convergence of the running least-squares offset estimate (methods #2/#4).

Reads scan_fit.csv from a session folder (--log) or runs a simulated day. Plots each
accepted scan's total-offset measurement, the running estimate +-1 SE, and (sim only)
the injected truth. Outputs offset_estimate_vs_scans.png, offset_error_stats.csv.
"""
import json
import math

from _common import fnum, log_arg, plt, read_csv, save, setup, sim_session, write_csv

args = setup(__file__, __doc__, log_arg)
d = args.log or sim_session(args.seed)
fits = [r for r in read_csv(d / "scan_fit.csv") if r["accepted"] == "true" and r["offset_total_deg"]]
session = json.load(open(d / "session.json")) if (d / "session.json").exists() else {}
truth = session.get("sim_truth", {})
fig, axes = plt.subplots(2, 1, figsize=(8, 7), sharex=True)
stats = []
for ax, axis, key, name in ((axes[0], "pan", "true_az_offset_deg", "az_offset"),
                            (axes[1], "tilt", "true_el_offset_deg", "el_offset")):
    rows = [r for r in fits if r["axis"] == axis]
    if not rows:
        continue
    n = list(range(1, len(rows) + 1))
    meas = [fnum(r["offset_total_deg"]) for r in rows]
    est = [fnum(r["offset_est_after_deg"]) for r in rows]
    se = [fnum(r["offset_est_se_deg"]) for r in rows]
    ax.errorbar(n, meas, yerr=[fnum(r["sigma_delta_deg"]) for r in rows], fmt="o", ms=4,
                color="0.6", label="scan measurement +- sigma")
    ax.plot(n, est, "-", color="C0", label="running weighted LS estimate")
    ax.fill_between(n, [e - s for e, s in zip(est, se)], [e + s for e, s in zip(est, se)],
                    color="C0", alpha=0.25, label="+- 1 standard error")
    t = truth.get(key)
    if t is not None:
        ax.axhline(t, color="C3", ls="--", label="injected truth (sim)")
    ax.set_ylabel("%s (deg)" % name)
    ax.legend(fontsize=8)
    scatter = math.sqrt(sum((m - est[-1]) ** 2 for m in meas) / len(meas))
    stats.append([name, len(rows), est[-1], se[-1], scatter, "" if t is None else t,
                  "" if t is None else est[-1] - t])
    print("%s: %d scans, final %.2f +- %.2f deg, scan scatter %.2f deg%s" % (
        name, len(rows), est[-1], se[-1], scatter,
        "" if t is None else ", error vs truth %+.2f deg" % (est[-1] - t)))
axes[1].set_xlabel("accepted scan number")
axes[0].set_title("Offset estimate vs number of scans (%s)" % d.name)
save(fig, args.out / "offset_estimate_vs_scans.png")
write_csv(args.out / "offset_error_stats.csv",
          ["offset", "n_scans", "final_deg", "se_deg", "scan_scatter_deg", "truth_deg", "error_deg"], stats)
