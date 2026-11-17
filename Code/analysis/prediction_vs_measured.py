"""Accuracy of the sun prediction (method #1).

1. Kepler-chain model vs the independent NOAA-series reference, every 10 min, Nov 1-30,
   sun above 5 deg: sun_model_vs_noaa.png, solar_error_stats.csv (target < 0.5 deg).
2. With --log <session folder>: where the measured power peak was relative to the pure
   prediction (each accepted scan's total offset) vs time: pointing_error_vs_time.png.
"""
import math
from datetime import datetime, timedelta, timezone

from _common import LAT_DEG, LON_DEG, fnum, log_arg, plt, read_csv, save, setup, write_csv
from solar_tracker.geometry import angdiff
from solar_tracker.solar.position import sun_position
from solar_tracker.solar.reference_noaa import noaa_azel

args = setup(__file__, __doc__, log_arg)
t0 = datetime(2026, 11, 1, tzinfo=timezone.utc)
ts, daz, del_ = [], [], []
for k in range(30 * 144):
    t = t0 + timedelta(minutes=10 * k)
    p = sun_position(t, LAT_DEG, LON_DEG)
    az, el, _ = noaa_azel(t, LAT_DEG, LON_DEG)
    if el > 5.0:
        ts.append(k / 144.0 + 1)
        daz.append(angdiff(p.az_deg, az))
        del_.append(p.el_deg - el)
rows = []
for name, e in (("azimuth", daz), ("elevation", del_)):
    rms = math.sqrt(sum(x * x for x in e) / len(e))
    rows.append([name, len(e), max(abs(x) for x in e), rms, sum(e) / len(e)])
    print("%-9s vs NOAA: max |err| %.4f deg, rms %.4f deg, mean %+.4f deg (n=%d)" % (
        name, rows[-1][2], rms, rows[-1][4], len(e)))
write_csv(args.out / "solar_error_stats.csv", ["quantity", "n", "max_abs_deg", "rms_deg", "mean_deg"], rows)
fig, ax = plt.subplots(figsize=(9, 4))
ax.plot(ts, daz, ".", ms=1.5, label="azimuth")
ax.plot(ts, del_, ".", ms=1.5, label="elevation")
ax.set_xlabel("day of November 2026 (UTC)")
ax.set_ylabel("Kepler model - NOAA reference (deg)")
ax.set_title("Sun model vs NOAA series, sun above 5 deg")
ax.legend(markerscale=6)
save(fig, args.out / "sun_model_vs_noaa.png")

if args.log:
    fits = [r for r in read_csv(args.log / "scan_fit.csv")
            if r["accepted"] == "true" and r["offset_total_deg"]]
    fig, ax = plt.subplots(figsize=(9, 4))
    for axis, name in (("pan", "azimuth"), ("tilt", "elevation")):
        rs = [r for r in fits if r["axis"] == axis]
        tt = [datetime.fromisoformat(r["t_utc"]) for r in rs]
        ax.errorbar(tt, [fnum(r["offset_total_deg"]) for r in rs],
                    yerr=[fnum(r["sigma_delta_deg"]) for r in rs], fmt="o", ms=3,
                    label="%s: measured peak - prediction" % name)
        ax.plot(tt, [fnum(r["offset_est_after_deg"]) for r in rs], "-", lw=1,
                label="%s: learned offset" % name)
        if rs:
            print("%s: measured-minus-predicted offset from %.2f to %.2f deg over %d scans" % (
                name, fnum(rs[0]["offset_total_deg"]), fnum(rs[-1]["offset_total_deg"]), len(rs)))
    ax.set_xlabel("UTC")
    ax.set_ylabel("offset (deg)")
    ax.legend(fontsize=8)
    ax.set_title("Measured power peak vs sun prediction (%s)" % args.log.name)
    fig.autofmt_xdate()
    save(fig, args.out / "pointing_error_vs_time.png")
