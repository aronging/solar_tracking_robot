"""Method #4: conditioning and accuracy of the refine-scan cosine fit vs scan spread S.

Isc(d) = a cos d + b sin d + c fitted by normal equations + own LU (numerics.leastsq.fit_cosine).
Shows why +-2 / +-5 deg scans are noise-limited and +-10..20 deg is the operating range.
Outputs: cond_vs_spread.png + .csv, theta_scatter_vs_spread.png + .csv, fit_examples.png
"""
import csv

import numpy as np

from _common import plt, save, setup, write_csv
from solar_tracker.numerics.leastsq import cosine_design, fit_cosine

SPREADS = (2.0, 5.0, 10.0, 15.0, 20.0)
KS = (5, 6, 7)
AMP_MA, BASE_MA, NOISE_MA, LSB_MA = 200.0, 40.0, 0.4, 0.1
TRUE_DELTA_DEG = 1.0                       # true peak offset inside every window


def add_args(p):
    p.add_argument("--log", help="hardware scan_fit.csv to overlay (spread_deg, delta_star_deg)")
    p.add_argument("--trials", type=int, default=500, help="Monte Carlo trials per spread")


def scan(rng, S, K):
    d = np.linspace(-S, S, K)
    y = AMP_MA * np.cos(np.radians(d - TRUE_DELTA_DEG)) + BASE_MA + rng.normal(0.0, NOISE_MA, K)
    return d, np.round(y / LSB_MA) * LSB_MA                 # INA219 quantisation


def main():
    args = setup(__file__, __doc__, add_args)
    rng = np.random.default_rng(args.seed)

    # 1. conditioning: own cond2(MtM) vs numpy SVD, cond2(MtM) = cond2(M)^2
    fig, ax = plt.subplots(figsize=(7, 4.6))
    rows, worst = [], 0.0
    for K in KS:
        own = []
        for S in SPREADS:
            d = np.linspace(-S, S, K)
            c_own = fit_cosine(list(d), list(scan(rng, S, K)[1])).cond2
            sv = np.linalg.svd(np.array(cosine_design(d)), compute_uv=False)
            c_svd = (sv[0] / sv[-1]) ** 2
            worst = max(worst, abs(c_own - c_svd) / c_svd)
            own.append(c_own)
            rows.append([K, S, f"{c_own:.6e}", f"{c_svd:.6e}", f"{abs(c_own - c_svd) / c_svd:.2e}"])
        ax.semilogy(SPREADS, own, "o-", label=f"K = {K} (own power/inverse iteration)")
    ax.semilogy([r[1] for r in rows[-len(SPREADS):]], [float(r[3]) for r in rows[-len(SPREADS):]],
                "kx", ms=9, label=f"numpy SVD cond2(M)^2, K = {KS[-1]}")
    ax.axhline(1e4, color="gray", ls="--", lw=0.8, label="spec default gate max_cond = 1e4")
    ax.set_xlabel("scan spread S (deg)")
    ax.set_ylabel("cond2(MtM)  (-)")
    ax.set_title("Conditioning of the cosine-fit normal equations")
    ax.grid(True, which="major", alpha=0.3)
    ax.legend(fontsize=8)
    save(fig, args.out / "cond_vs_spread.png")
    write_csv(args.out / "cond_vs_spread.csv", ["K", "spread_deg", "cond2_own", "cond2_svd", "rel_diff"], rows)
    print("K  S_deg  cond2(MtM) own   numpy SVD^2")
    for r in rows:
        print(f"{r[0]}  {r[1]:>5.0f}  {r[2]}  {r[3]}")
    print(f"max relative disagreement own vs SVD: {worst:.2e}")

    # 2. Monte Carlo scatter of delta* vs theory sigma (K = 7)
    K = 7
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 4.6))
    stats = []
    for S in SPREADS:
        fits = [fit_cosine(*map(list, scan(rng, S, K))) for _ in range(args.trials)]
        err = np.array([f.delta_star_deg for f in fits]) - TRUE_DELTA_DEG
        sig = np.array([f.sigma_delta_deg for f in fits])
        q16, q84 = np.percentile(err, [16, 84])
        swing = AMP_MA * (1 - np.cos(np.radians(S)))                  # signal change centre -> edge
        stats.append([S, float(np.std(err)), float((q84 - q16) / 2), float(np.median(sig)),
                      float(np.sqrt(np.mean(sig ** 2))), float(np.mean(np.abs(err) > S)), float(swing)])
        ax1.plot(S + rng.uniform(-0.6, 0.6, len(err)), err, ".", ms=2.5, alpha=0.4, color="C0")
        ax1.errorbar(S, 0, yerr=stats[-1][3], color="k", capsize=6, lw=1.5, zorder=5)
    ax1.plot([], [], ".", color="C0", label=f"Monte Carlo delta* - truth ({args.trials} scans each)")
    ax1.errorbar([], [], yerr=[], color="k", capsize=6, label="+-1 sigma from fit covariance (median)")
    if args.log:
        with open(args.log, newline="") as fh:
            hw = [(float(r["spread_deg"]), float(r["delta_star_deg"])) for r in csv.DictReader(fh)]
        ax1.plot(*zip(*hw), "r+", ms=8, label=f"hardware scans delta* ({len(hw)})")
    ax1.set_yscale("symlog", linthresh=1.0)
    ax1.set_xlabel("scan spread S (deg)")
    ax1.set_ylabel("delta* error (deg), symlog")
    ax1.set_title(f"Scatter of the fitted peak, K = {K}, noise {NOISE_MA} mA, LSB {LSB_MA} mA")
    ax1.grid(alpha=0.3)
    ax1.legend(fontsize=8, loc="upper right")
    ax2.semilogy(SPREADS, [s[1] for s in stats], "o-", label="Monte Carlo std")
    ax2.semilogy(SPREADS, [s[2] for s in stats], "o:", color="C0", label="Monte Carlo half 16-84% width")
    ax2.semilogy(SPREADS, [s[3] for s in stats], "ks--", label="theory sigma (median of fits)")
    ax2.axhline(3.0, color="gray", ls="--", lw=0.8, label="gate max_sigma_deg = 3")
    ax2.axvspan(10, 20, color="green", alpha=0.08, label="operating range")
    ax2.set_xlabel("scan spread S (deg)")
    ax2.set_ylabel("sigma of delta* (deg)")
    ax2.set_title("Accuracy vs spread")
    ax2.grid(True, which="both", alpha=0.3)
    ax2.legend(fontsize=8)
    save(fig, args.out / "theta_scatter_vs_spread.png")
    write_csv(args.out / "theta_scatter_vs_spread.csv",
              ["spread_deg", "mc_std_deg", "mc_half_16_84_deg", "theory_sigma_median_deg",
               "theory_sigma_rms_deg", "frac_peak_outside_window", "signal_swing_mA"],
              [[s[0]] + [f"{v:.4f}" for v in s[1:]] for s in stats])
    print("S_deg  MC_std  MC_half68  theory_med  theory_rms  outside_win  swing_mA")
    for s in stats:
        print(f"{s[0]:>5.0f}  {s[1]:>6.2f}  {s[2]:>9.3f}  {s[3]:>10.3f}  {s[4]:>10.3f}  {s[5]:>11.3f}  {s[6]:>8.2f}")

    # 3. example scans
    fig, axes = plt.subplots(1, 4, figsize=(16, 4.2))
    for ax, S in zip(axes, (2.0, 5.0, 15.0, 20.0)):
        d, y = scan(rng, S, K)
        f = fit_cosine(list(d), list(y))
        g = np.linspace(-S, S, 200)
        ax.plot(d, y, "ko", label="samples")
        ax.plot(g, f.a * np.cos(np.radians(g)) + f.b * np.sin(np.radians(g)) + f.c, "C0-", label="fit")
        ax.plot(g, AMP_MA * np.cos(np.radians(g - TRUE_DELTA_DEG)) + BASE_MA, "C2--", lw=1, label="truth")
        ax.axvline(TRUE_DELTA_DEG, color="C2", lw=0.8)
        if abs(f.delta_star_deg) <= S:
            ax.axvline(f.delta_star_deg, color="C0", lw=0.8)
        ax.set_title(f"S = +-{S:.0f} deg: delta* = {f.delta_star_deg:.2f} +- {f.sigma_delta_deg:.2f} deg\n"
                     f"(truth {TRUE_DELTA_DEG} deg), cond = {f.cond2:.1e}", fontsize=9)
        ax.set_xlabel("scan offset delta (deg)")
        ax.ticklabel_format(useOffset=False)
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("Isc (mA)")
    axes[0].legend(fontsize=8)
    save(fig, args.out / "fit_examples.png")


if __name__ == "__main__":
    main()
