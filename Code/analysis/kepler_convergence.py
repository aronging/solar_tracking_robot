"""Method #1 convergence: fixed-point vs Newton-Raphson on Kepler's equation E - e sin E = M.

Error |E_k - E_ref| vs iteration at Earth's e and at stress eccentricities 0.5 and 0.9.
Fixed-point is linear with rate e|cos E*|; Newton is quadratic.
Outputs: kepler_error_vs_iter.png, kepler_iter_table.csv
"""
import math

from _common import plt, save, setup, write_csv
from solar_tracker.solar.position import solve_kepler

ECCS = (0.0167, 0.5, 0.9)
M_DEGS = (20.0, 75.0, 130.0, 317.0)       # 317 deg ~ mid-November mean anomaly
TOL = 1e-12


def errors(res, E0, E_ref):
    """|E_k - E_ref| for k = 0..iterations (floored at 1e-17 so it shows on a log axis)."""
    return [max(abs(x - E_ref), 1e-17) for x in [E0] + [h["x"] for h in res.history]]


def observed_rate(err):
    """Geometric-mean ratio err[k+1]/err[k] over the last steps still above round-off."""
    r = [b / a for a, b in zip(err, err[1:]) if b > 1e-11]
    r = r[-5:]
    return math.exp(sum(math.log(x) for x in r) / len(r)) if r else float("nan")


def main():
    args = setup(__file__, __doc__)
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6), sharey=True)
    rows = []
    for ax, e in zip(axes, ECCS):
        for i, M_deg in enumerate(M_DEGS):
            M = math.radians(M_deg)
            E0 = M if e < 0.8 else math.pi              # same start rule as solve_kepler
            E_ref = solve_kepler(M, e, "newton", tol=1e-15, max_iter=100).value
            nr = solve_kepler(M, e, "newton", TOL)
            fp = solve_kepler(M, e, "fixed_point", TOL)
            e_nr, e_fp = errors(nr, E0, E_ref), errors(fp, E0, E_ref)
            theory = e * abs(math.cos(E_ref))
            rows.append([e, M_deg, nr.iterations, nr.converged, fp.iterations, fp.converged,
                         f"{observed_rate(e_fp):.4f}", f"{theory:.4f}",
                         f"{abs(nr.value - fp.value):.2e}"])
            c = f"C{i}"
            ax.semilogy(range(len(e_fp)), e_fp, "o-", color=c, ms=3, lw=1,
                        label=f"fixed-point, M={M_deg:.0f} deg")
            ax.semilogy(range(len(e_nr)), e_nr, "s--", color=c, ms=5, lw=1.5,
                        label=f"Newton, M={M_deg:.0f} deg")
            if i == 0:                                   # reference slope for the linear rate
                ks = range(len(e_fp))
                ax.semilogy(ks, [max(e_fp[0] * theory ** k, 1e-17) for k in ks], "k:", lw=1,
                            label=f"(e|cos E*|)^k = {theory:.3f}^k, M={M_deg:.0f} deg")
        ax.axhline(TOL, color="gray", lw=0.8)
        ax.set_title(f"e = {e}")
        ax.set_xlabel("iteration k")
        ax.set_ylim(1e-17, 10)
        ax.grid(True, which="major", alpha=0.3)
        ax.legend(fontsize=6.5)
    axes[0].set_ylabel("|E_k - E_ref|  (rad)")
    fig.suptitle("Kepler's equation: fixed-point (linear) vs Newton-Raphson (quadratic); "
                 f"gray line = tolerance {TOL:g} rad")
    save(fig, args.out / "kepler_error_vs_iter.png")
    header = ["e", "M_deg", "newton_iters", "newton_converged", "fixed_point_iters",
              "fixed_point_converged", "fp_observed_rate", "fp_theory_rate_e_abs_cosE",
              "abs_diff_rad"]
    write_csv(args.out / "kepler_iter_table.csv", header, rows)

    print(f"{'e':>7} {'M_deg':>6} {'Newton':>7} {'fixed-pt':>9} {'fp rate':>8} {'e|cosE|':>8}")
    for r in rows:
        print(f"{r[0]:>7} {r[1]:>6.0f} {r[2]:>7} {r[4]:>9} {r[6]:>8} {r[7]:>8}")
    for e in ECCS:
        sub = [r for r in rows if r[0] == e]
        print(f"e={e}: Newton {min(r[2] for r in sub)}-{max(r[2] for r in sub)} iterations, "
              f"fixed-point {min(r[4] for r in sub)}-{max(r[4] for r in sub)}")


if __name__ == "__main__":
    main()
