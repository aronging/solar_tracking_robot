"""Tracking gain over a virtual fixed panel (spec 6.7): gain = int I_n dt / int I_fixed dt,
by the trapezoid rule and by Simpson's rule (own implementations in numerics.integrate).

I_n = measured Isc in the TRACK state; I_fixed = I_n * max(0, cos i_fixed) for a panel
facing fixed_panel_az at the fixed tilt. Times with the sun under 25 deg are shaded in
the plot (possible shading by the robot body).
Outputs isc_tracked_vs_fixed.png, gain_summary.csv, fixed_check_validation.png.
"""
import json

from _common import fnum, log_arg, plt, read_csv, save, setup, sim_session, write_csv
from solar_tracker.geometry import incidence_cos
from solar_tracker.numerics.integrate import simpson, trapezoid

args = setup(__file__, __doc__, log_arg)
d = args.log or sim_session(args.seed)
tr = json.load(open(d / "session.json"))["config"]["track"]
az_f, el_f = tr["fixed_panel_az_deg"], 90.0 - tr["fixed_panel_tilt_from_horizontal_deg"]
cyc = [r for r in read_csv(d / "cycle.csv") if r["state"] == "TRACK" and r["isc_mA"] and r["sun_el_deg"]]
t = [fnum(r["t_mono_s"]) for r in cyc]
i_n = [fnum(r["isc_mA"]) for r in cyc]
i_f = [i * max(0.0, incidence_cos(fnum(r["sun_az_deg"]), fnum(r["sun_el_deg"]), az_f, el_f))
       for i, r in zip(i_n, cyc)]

H = 10.0                                   # uniform grid for Simpson (linear interpolation)
grid, gn, gf, j = [], [], [], 0
x = t[0]
while x <= t[-1]:
    while t[j + 1] < x:
        j += 1
    w = (x - t[j]) / (t[j + 1] - t[j]) if t[j + 1] > t[j] else 0.0
    grid.append(x)
    gn.append(i_n[j] + w * (i_n[j + 1] - i_n[j]))
    gf.append(i_f[j] + w * (i_f[j + 1] - i_f[j]))
    x += H
res = {"trapezoid (raw samples)": (trapezoid(i_n, t), trapezoid(i_f, t)),
       "trapezoid (10 s grid)": (trapezoid(gn, grid), trapezoid(gf, grid)),
       "simpson (10 s grid)": (simpson(gn, H), simpson(gf, H))}
rows = []
for name, (a, b) in res.items():
    rows.append([name, a / 3600.0, b / 3600.0, a / b])
    print("%-24s tracked %.2f mAh  fixed %.2f mAh  gain %.4f" % (name, a / 3600, b / 3600, a / b))
g = [r[3] for r in rows]
print("Simpson - trapezoid gain difference: %.2e" % (g[2] - g[1]))
write_csv(args.out / "gain_summary.csv", ["rule", "tracked_mAh", "fixed_mAh", "gain"], rows)

hrs = [(x - t[0]) / 3600.0 for x in t]
fig, ax = plt.subplots(figsize=(9, 4))
ax.plot(hrs, i_n, lw=0.8, label="tracked (measured Isc)")
ax.plot(hrs, i_f, lw=0.8, label="virtual fixed panel (south, %g deg from horizontal)"
        % tr["fixed_panel_tilt_from_horizontal_deg"])
low = [h for h, r in zip(hrs, cyc) if fnum(r["sun_el_deg"]) < 25.0]
if low:
    ax.axvspan(min(low), max(low), color="0.9", label="sun < 25 deg (possible shading)")
ax.set_xlabel("time since start of tracking (h)")
ax.set_ylabel("Isc (mA)")
ax.set_title("Tracked vs fixed panel, gain = %.3f" % g[2])
ax.legend(fontsize=8)
save(fig, args.out / "isc_tracked_vs_fixed.png")

if (d / "fixed_check.csv").exists():
    fc = read_csv(d / "fixed_check.csv")
    meas = [fnum(r["isc_fixed_meas_mA"]) for r in fc]
    pred = [fnum(r["isc_fixed_pred_mA"]) for r in fc]
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.plot(pred, meas, "o")
    lim = [0, max(meas + pred) * 1.05]
    ax.plot(lim, lim, "k--", lw=0.8, label="measured = predicted")
    ax.set_xlabel("predicted fixed-panel Isc (mA)")
    ax.set_ylabel("measured at the fixed pose (mA)")
    bias = sum(m - p for m, p in zip(meas, pred)) / len(fc)
    ax.set_title("Fixed-panel check: mean (meas - pred) = %+.1f mA" % bias)
    ax.legend()
    save(fig, args.out / "fixed_check_validation.png")
    print("fixed checks: %d, mean measured - predicted = %+.2f mA "
          "(diffuse light + cosine-model error)" % (len(fc), bias))
