"""Method #6 (Tier 2): bisection vs false position on elevation(t) = -0.833 deg.

Iterations to the same time tolerance for sunrise and sunset on a few November dates.
Outputs: sunrise_iterations.png, sunrise_iterations.csv
"""
from _common import LAT_DEG, LON_DEG, plt, save, setup, write_csv
from solar_tracker.solar.position import sunrise_sunset, utc

DAYS = (1, 8, 16, 23, 30)                  # November 2026
METHODS = ("bisection", "false_position")


def add_args(p):
    p.add_argument("--tol-s", type=float, default=1.0, help="root tolerance in seconds")


def main():
    args = setup(__file__, __doc__, add_args)
    rows, results = [], {}
    for day in DAYS:
        for m in METHODS:
            r = sunrise_sunset(utc(2026, 11, day, 18), LAT_DEG, LON_DEG, method=m, tol_s=args.tol_s)
            results[day, m] = r
            rows.append([f"2026-11-{day:02d}", m, r["sunrise"].strftime("%H:%M:%S"),
                         r["rise_result"].iterations, r["sunset"].strftime("%H:%M:%S"),
                         r["set_result"].iterations])

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.6))
    width = 0.2
    for j, (m, key, lab) in enumerate((m, k, l) for m in METHODS
                                      for k, l in (("rise_result", "sunrise"), ("set_result", "sunset"))):
        ax1.bar([i + (j - 1.5) * width for i in range(len(DAYS))],
                [results[d, m][key].iterations for d in DAYS], width, label=f"{m}, {lab}")
    ax1.set_xticks(range(len(DAYS)))
    ax1.set_xticklabels([f"Nov {d}" for d in DAYS])
    ax1.set_ylabel(f"iterations to {args.tol_s:g} s tolerance")
    ax1.set_title("Iterations: bisection vs false position")
    ax1.legend(fontsize=8)

    day = DAYS[len(DAYS) // 2]
    for m, style in zip(METHODS, ("o-", "s-")):
        h = results[day, m]["rise_result"].history
        ax2.semilogy([p["k"] for p in h], [max(p["residual"], 1e-12) for p in h], style, ms=4, label=m)
    ax2.set_xlabel("iteration k")
    ax2.set_ylabel("|elevation - (-0.833)|  (deg)")
    ax2.set_title(f"Sunrise root residual, 2026-11-{day:02d}")
    ax2.grid(True, which="major", alpha=0.3)
    ax2.legend()
    save(fig, args.out / "sunrise_iterations.png")
    write_csv(args.out / "sunrise_iterations.csv",
              ["date", "method", "sunrise_utc", "sunrise_iters", "sunset_utc", "sunset_iters"], rows)

    print(f"site lat {LAT_DEG}, lon {LON_DEG}; tolerance {args.tol_s:g} s")
    for r in rows:
        print(f"{r[0]}  {r[1]:<15} sunrise {r[2]} UTC ({r[3]:>2} it)   sunset {r[4]} UTC ({r[5]:>2} it)")
    worst = 0.0
    for d in DAYS:
        for k in ("sunrise", "sunset"):
            worst = max(worst, abs((results[d, METHODS[0]][k] - results[d, METHODS[1]][k]).total_seconds()))
    print(f"max |bisection - false position| root difference: {worst:.3f} s")


if __name__ == "__main__":
    main()
