"""Sensor noise from a static-log run (sets the simulator's noise parameters).

--log static.csv from `python -m solar_tracker static-log`; default: a simulated minute.
Outputs static_noise_hist.png, noise_stats.csv.
"""
import math

from _common import fnum, log_arg, plt, read_csv, save, setup, sim_session, write_csv

args = setup(__file__, __doc__, log_arg)
path = args.log or sim_session(args.seed, body="static") / "static.csv"
y = [fnum(r["isc_mA"]) for r in read_csv(path)]
n = len(y)
slope = (y[-1] - y[0]) / max(n - 1, 1)     # remove linear drift (the sun moves during the log)
res = [v - (y[0] + slope * i) for i, v in enumerate(y)]
mean_r = sum(res) / n
res = [r - mean_r for r in res]
std = math.sqrt(sum(r * r for r in res) / (n - 1))
ac1 = sum(a * b for a, b in zip(res, res[1:])) / sum(r * r for r in res)
steps = sorted(set(round(abs(a - b), 3) for a, b in zip(y, y[1:])) - {0.0})
stats = [["n_samples", n], ["mean_mA", sum(y) / n], ["std_mA (detrended)", std],
         ["std_of_8_sample_mean_mA", std / math.sqrt(8)], ["lag1_autocorrelation", ac1],
         ["smallest_step_mA (quantisation)", steps[0] if steps else 0.0],
         ["drift_mA_per_sample", slope]]
for k, v in stats:
    print("%-34s %.4g" % (k, v))
write_csv(args.out / "noise_stats.csv", ["quantity", "value"], stats)
fig, axes = plt.subplots(1, 2, figsize=(10, 3.8))
axes[0].plot(y, lw=0.6)
axes[0].set_xlabel("sample")
axes[0].set_ylabel("Isc (mA)")
axes[0].set_title("Static log")
axes[1].hist(res, bins=30)
axes[1].set_xlabel("detrended Isc (mA)")
axes[1].set_ylabel("count")
axes[1].set_title("Noise: std = %.3f mA" % std)
save(fig, args.out / "static_noise_hist.png")
