"""Session overview figure from cycle.csv: sun position, servo commands and learned offsets,
Isc vs the clear-sky model, cloud ratio and the state timeline.
--log <session folder> (default: a simulated day with a cloud). Output session_overview.png.
"""
from _common import fnum, log_arg, plt, read_csv, save, setup, sim_session

args = setup(__file__, __doc__, log_arg)
d = args.log or sim_session(args.seed, clouds=[(9000, 10200, 0.3)])
cyc = read_csv(d / "cycle.csv")
h = [(fnum(r["t_mono_s"]) - fnum(cyc[0]["t_mono_s"])) / 3600.0 for r in cyc]


def col(key):
    return [fnum(r[key]) for r in cyc]


fig, ax = plt.subplots(5, 1, figsize=(10, 11), sharex=True)
ax[0].plot(h, col("sun_el_deg"), label="sun elevation")
ax[0].plot(h, col("sun_az_deg"), label="sun azimuth")
ax[0].set_ylabel("deg")
ax[0].legend(fontsize=8)
ax[1].plot(h, col("pan_cmd_deg"), label="pan command")
ax[1].plot(h, col("tilt_cmd_deg"), label="tilt command")
ax[1].plot(h, col("az_offset_deg"), ":", label="learned az offset")
ax[1].plot(h, col("el_offset_deg"), ":", label="learned el offset")
ax[1].set_ylabel("deg")
ax[1].legend(fontsize=8, ncol=2)
ax[2].plot(h, col("isc_mA"), lw=0.7, label="measured Isc")
ax[2].plot(h, col("clear_isc_mA"), "--", label="clear-sky model")
ax[2].set_ylabel("mA")
ax[2].legend(fontsize=8)
ax[3].plot(h, col("cloud_ratio"), lw=0.7)
ax[3].axhline(0.7, color="C3", ls=":", lw=0.8)
ax[3].set_ylabel("cloud ratio")
ax[3].set_ylim(0, 1.3)
states = sorted(set(r["state"] for r in cyc))
ax[4].plot(h, [states.index(r["state"]) for r in cyc], drawstyle="steps-post")
ax[4].set_yticks(range(len(states)))
ax[4].set_yticklabels(states)
ax[4].set_xlabel("time since first tick (h)")
ax[0].set_title("Session overview: %s" % d.name)
save(fig, args.out / "session_overview.png")
flags = sorted(set(f for r in cyc for f in r["flags"].split("|") if f))
print("%d ticks over %.2f h; states %s; flags seen %s; peak Isc %.1f mA" % (
    len(cyc), h[-1], states, flags or "none", max(v for v in col("isc_mA") if v == v)))
