"""Method #3: golden-section search convergence and noise sensitivity (+ parabolic step).

Outputs: golden_interval_vs_iter.png (bracket width vs iteration with the 0.618^k line),
golden_error_vs_noise.png + .csv (Monte Carlo peak error vs Isc noise, golden-only x_golden
vs golden+parabolic x_best from control.acquire.acquire_axis on a cosine Isc curve),
acquire_hw_run.png when --log <acquire.csv> is given.
"""
import csv
import math

import numpy as np

from _common import plt, save, setup, write_csv
from solar_tracker.control.acquire import acquire_axis
from solar_tracker.numerics.optimize import GOLDEN, golden_section_max

AMP_MA = 200.0
NOISES_MA = (0.0, 0.1, 0.2, 0.4, 0.8, 1.6, 3.2)


def add_args(p):
    p.add_argument("--log", help="hardware acquire.csv to plot")
    p.add_argument("--trials", type=int, default=400, help="Monte Carlo trials per noise level")


def isc(x_deg, peak_deg):
    return AMP_MA * math.cos(math.radians(x_deg - peak_deg))


def plot_hw(path, out):
    with open(path, newline="") as fh:
        rows = list(csv.DictReader(fh))
    runs = sorted({(r["acq_id"], r["axis"]) for r in rows})
    fig, axes = plt.subplots(1, len(runs), figsize=(5.5 * len(runs), 4.4), squeeze=False)
    for ax, (acq, axis) in zip(axes[0], runs):
        sub = [r for r in rows if (r["acq_id"], r["axis"]) == (acq, axis)]
        for phase, mk in (("coarse", "o"), ("golden", "x")):
            pts = [(float(r["x_deg"]), float(r["f_mA"])) for r in sub if r["phase"] == phase]
            if pts:
                ax.plot(*zip(*pts), mk, label=f"{phase} ({len(pts)})")
        for r in sub:
            if r["phase"] == "result":
                for col, style in (("x_golden_deg", "C1--"), ("x_best_deg", "C2-")):
                    try:
                        v = float(r[col])
                    except ValueError:
                        continue
                    if math.isfinite(v):
                        ax.axvline(v, color=style[:2], ls=style[2:], label=f"{col[:-4]} = {v:.2f} deg")
        ax.set_xlabel(f"{axis} angle (deg)")
        ax.set_ylabel("Isc (mA)")
        ax.set_title(f"acquire {acq}, {axis}")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)
    save(fig, out / "acquire_hw_run.png")


def main():
    args = setup(__file__, __doc__, add_args)
    rng = np.random.default_rng(args.seed)

    # 1. bracket width vs iteration (noise-free)
    res = golden_section_max(lambda x: isc(x, 3.21), -10.0, 10.0, tol=1e-6)
    k = [h["k"] for h in res.history]
    w = [h["width"] for h in res.history]
    ratios = [b / a for a, b in zip(w, w[1:])]
    fig, ax = plt.subplots(figsize=(7, 4.6))
    ax.semilogy(k, w, "o", label="golden_section_max bracket width")
    ax.semilogy(k, [w[0] * GOLDEN ** i for i in k], "k--", lw=1, label="w0 * 0.618^k")
    ax.axhline(1.5, color="gray", lw=0.8, label="acquire tol 1.5 deg")
    ax.set_xlabel("iteration k (one new Isc evaluation each)")
    ax.set_ylabel("bracket width (deg)")
    ax.set_title("Golden-section search: linear convergence, ratio 0.618")
    ax.grid(True, which="major", alpha=0.3)
    ax.legend()
    save(fig, args.out / "golden_interval_vs_iter.png")
    print(f"golden: {res.iterations} iterations, {res.evals} evals, shrink ratio mean "
          f"{np.mean(ratios):.6f} (min {min(ratios):.6f}, max {max(ratios):.6f}), "
          f"peak error {abs(res.value - 3.21):.2e} deg")

    # 2. peak error vs noise (full acquire_axis, +-40 deg window, peak uniformly in +-25 deg)
    rows = []
    for sigma in NOISES_MA:
        eg, eb, n_par, evals = [], [], 0, []
        for _ in range(args.trials):
            peak = rng.uniform(-25.0, 25.0)
            r = acquire_axis(lambda x: round(isc(x, peak) + rng.normal(0.0, sigma), 1) if sigma
                             else isc(x, peak), 0.0, 40.0, (-90.0, 90.0))
            eg.append(r.x_golden - peak)
            eb.append(r.x_best - peak)
            n_par += not math.isnan(r.x_parabolic)
            evals.append(r.evals)
        rms = lambda e: float(np.sqrt(np.mean(np.square(e))))          # noqa: E731
        rows.append([sigma, rms(eg), rms(eb), float(np.max(np.abs(eg))), float(np.max(np.abs(eb))),
                     n_par / args.trials, float(np.mean(evals))])
    fig, ax = plt.subplots(figsize=(7, 4.6))
    xs = [max(r[0], 0.05) for r in rows]                               # 0 mA drawn at 0.05 on the log axis
    ax.loglog(xs, [r[1] for r in rows], "o-", label="golden only (x_golden), RMS")
    ax.loglog(xs, [r[2] for r in rows], "s-", label="golden + parabolic (x_best), RMS")
    ax.loglog(xs, [r[3] for r in rows], "o:", color="C0", alpha=0.6, label="golden only, max")
    ax.loglog(xs, [r[4] for r in rows], "s:", color="C1", alpha=0.6, label="golden + parabolic, max")
    ax.axvline(0.4, color="gray", lw=0.8)
    ax.text(0.42, ax.get_ylim()[0] * 1.3, "INA219 noise 0.4 mA", fontsize=8)
    ax.set_xlabel("Isc noise sigma (mA); leftmost point is zero noise")
    ax.set_ylabel("peak-angle error (deg)")
    ax.set_title(f"Acquire error vs noise ({args.trials} trials, {AMP_MA:.0f} mA cosine, tol 1.5 deg)")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(fontsize=8)
    save(fig, args.out / "golden_error_vs_noise.png")
    write_csv(args.out / "golden_error_vs_noise.csv",
              ["noise_mA", "rms_err_golden_deg", "rms_err_best_deg", "max_err_golden_deg",
               "max_err_best_deg", "parabolic_used_frac", "mean_evals"],
              [[r[0]] + [f"{v:.4f}" for v in r[1:]] for r in rows])
    print("noise_mA  rms_golden  rms_best  max_golden  max_best  parab_used  evals")
    for r in rows:
        print(f"{r[0]:>8.1f}  {r[1]:>10.3f}  {r[2]:>8.3f}  {r[3]:>10.3f}  {r[4]:>8.3f}  {r[5]:>10.2f}  {r[6]:>5.1f}")

    if args.log:
        plot_hw(args.log, args.out)


if __name__ == "__main__":
    main()
