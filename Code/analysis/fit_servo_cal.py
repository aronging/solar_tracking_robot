"""Method #2: linear least-squares servo calibration, angle_deg = m*(pulse_us - 1500) + c.

Fits the up and the down sweep of each servo separately (numerics.leastsq.fit_line),
reports slope, intercept, residual RMS and hysteresis (mean gap between the two lines
over the measured pulse range) and writes config/servo_cal.json (mean of the two lines).
Outputs: servo_cal_fit_<servo>.png, servo_cal_summary.csv, config/servo_cal.json
Usage: fit_servo_cal.py logs/<run>/servo_cal.csv     or     fit_servo_cal.py --demo
"""
import csv
import json
import math
import random
from pathlib import Path

from _common import CODE, plt, save, setup, write_csv
from solar_tracker.numerics.leastsq import fit_line


def add_args(p):
    p.add_argument("csv", nargs="?", help="servo_cal.csv (servo,direction,pulse_us,measured_deg)")
    p.add_argument("--demo", action="store_true",
                   help="generate a synthetic CSV in the output dir; does not write the config")
    p.add_argument("--config", default=str(CODE / "config" / "servo_cal.json"))


def make_demo(path, seed):
    """Synthetic sweep: 0.092 deg/us, zero error, 1.5 deg backlash, 0.5 deg reading noise."""
    rng = random.Random(seed)
    pulses = list(range(1000, 2001, 50))
    rows = []
    for servo in ("pan", "tilt"):
        for direction, seq, lag in (("up", pulses, -0.75), ("down", pulses[::-1], +0.75)):
            for p in seq:                       # the output lags the command by half the backlash
                rows.append([servo, direction, p, f"{0.092 * (p - 1500) + lag + rng.gauss(0, 0.5):.1f}"])
    write_csv(path, ["servo", "direction", "pulse_us", "measured_deg"], rows)


def main():
    args = setup(__file__, __doc__, add_args)
    if args.demo:
        args.csv = str(args.out / "servo_cal_demo.csv")
        make_demo(args.csv, args.seed)
    if not args.csv:
        raise SystemExit("give a servo_cal.csv path or --demo")

    data = {}                                   # servo -> direction -> [(pulse - 1500, angle)]
    with open(args.csv, newline="") as fh:
        for r in csv.DictReader(fh):
            try:
                pt = (float(r["pulse_us"]) - 1500.0, float(r["measured_deg"]))
            except (TypeError, ValueError):
                continue                        # operator skipped this reading
            data.setdefault(r["servo"].strip(), {}).setdefault(r["direction"].strip(), []).append(pt)

    summary, cal = [], {}
    for servo, sweeps in data.items():
        if set(sweeps) != {"up", "down"}:
            raise SystemExit(f"{servo}: need both 'up' and 'down' sweeps, got {sorted(sweeps)}")
        fits = {d: fit_line(*zip(*sweeps[d])) for d in ("up", "down")}
        xs = [x for d in sweeps.values() for x, _ in d]
        x_lo, x_hi = min(xs), max(xs)
        grid = [x_lo + (x_hi - x_lo) * i / 100 for i in range(101)]
        up, dn = fits["up"], fits["down"]
        hyst = sum(abs((dn.m - up.m) * x + dn.c - up.c) for x in grid) / len(grid)
        res = up.residuals + dn.residuals
        rms = math.sqrt(sum(r * r for r in res) / len(res))
        for d in ("up", "down"):
            summary.append([servo, d, fits[d].n, f"{fits[d].m:.6f}", f"{fits[d].c:.4f}",
                            f"{fits[d].rms:.4f}", f"{hyst:.4f}"])
        cal[servo] = {"m": 0.5 * (up.m + dn.m), "c": 0.5 * (up.c + dn.c), "hysteresis_deg": hyst,
                      "pulse_min_us": x_lo + 1500.0, "pulse_max_us": x_hi + 1500.0, "rms_deg": rms}

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(7.5, 7), sharex=True,
                                       gridspec_kw={"height_ratios": [3, 1.3]})
        for d, color, mk in (("up", "C0", "^"), ("down", "C3", "v")):
            px = [x + 1500 for x, _ in sweeps[d]]
            ax1.plot(px, [y for _, y in sweeps[d]], mk, color=color, label=f"{d} sweep data")
            ax1.plot([x_lo + 1500, x_hi + 1500], [fits[d].m * x + fits[d].c for x in (x_lo, x_hi)],
                     "-", color=color, label=f"{d} fit: m={fits[d].m:.4f} deg/us, c={fits[d].c:+.2f} deg")
            ax2.plot(px, fits[d].residuals, mk, color=color, label=f"{d} (RMS {fits[d].rms:.2f} deg)")
        ax1.set_ylabel("measured angle (deg)")
        ax1.set_title(f"{servo} servo calibration: hysteresis {hyst:.2f} deg, RMS {rms:.2f} deg")
        ax1.grid(alpha=0.3)
        ax1.legend(fontsize=8)
        ax2.axhline(0, color="k", lw=0.8)
        ax2.set_xlabel("pulse width (us)")
        ax2.set_ylabel("residual (deg)")
        ax2.grid(alpha=0.3)
        ax2.legend(fontsize=8)
        save(fig, args.out / f"servo_cal_fit_{servo}.png")

    write_csv(args.out / "servo_cal_summary.csv",
              ["servo", "direction", "n", "slope_deg_per_us", "intercept_deg", "rms_deg",
               "hysteresis_deg"], summary)
    for s in summary:
        print(f"{s[0]:<5} {s[1]:<5} n={s[2]:>3}  m={s[3]} deg/us  c={s[4]} deg  rms={s[5]} deg  "
              f"hysteresis={s[6]} deg")
    if args.demo:
        print("demo mode: config/servo_cal.json NOT written (truth: m=0.092, c=0, backlash=1.5)")
        return
    cfg = Path(args.config)
    merged = json.loads(cfg.read_text()) if cfg.exists() else {}
    merged.update(cal)
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps(merged, indent=2) + "\n")
    print(f"wrote {cfg} for {sorted(cal)}")


if __name__ == "__main__":
    main()
