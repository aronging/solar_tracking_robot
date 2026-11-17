"""PID heading loop study (method #5): integration scheme, gains, stability.

Plant (the simulator's yaw model without deadband): rate' = (K u - rate)/tau, heading' = rate,
K = 60 deg/s, tau = 0.3 s, |u| <= 1, 30 deg step.
Outputs pid_step_euler_vs_trapezoid.png, pid_metrics.csv, pid_gain_sweep.png and, with
--log turn.csv [more turn.csv ...], pid_hw_runs.png.
"""
from _common import fnum, plt, read_csv, save, setup, write_csv
from solar_tracker.config import Config
from solar_tracker.control.pid import PID

K, TAU, STEP = 60.0, 0.3, 30.0


def step_response(kp, ki, kd, mode, dt=0.05, t_end=20.0, tau_d=0.15):
    pid = PID(kp, ki, kd, mode, tau_d, 1.0)
    h = rate = 0.0
    ts, hs = [], []
    for i in range(int(t_end / dt)):
        u = pid.update(STEP - h, dt)
        for _ in range(10):                          # plant integrated 10x finer than the loop
            rate += (K * u - rate) * (dt / 10) / TAU
            h += rate * dt / 10
        ts.append((i + 1) * dt)
        hs.append(h)
    return ts, hs


def metrics(ts, hs):
    rise = next((t for t, h in zip(ts, hs) if h >= 0.9 * STEP), float("nan"))
    overshoot = max(0.0, (max(hs) - STEP) / STEP * 100.0)
    settle = 0.0
    for t, h in zip(ts, hs):
        if abs(h - STEP) > 0.02 * STEP:
            settle = t
    return rise, overshoot, settle, abs(hs[-1] - STEP)


args = setup(__file__, __doc__, lambda p: p.add_argument("--log", nargs="*", default=[]))
a = Config().align
KI = 10 * a.ki      # ki raised 10x over the default so the integral term matters in the comparison
rows = []
fig, axes = plt.subplots(1, 2, figsize=(11, 4))
for ax, (dt, title) in zip(axes, ((0.05, "20 Hz loop (as run)"), (0.25, "4 Hz loop (coarse dt)"))):
    for mode, style in (("euler", "-"), ("trapezoid", "--"), ("simpson", ":")):
        ts, hs = step_response(a.kp, KI, a.kd, mode, dt)
        m = metrics(ts, hs)
        rows.append([title, mode, a.kp, KI, a.kd] + list(m))
        ax.plot(ts, hs, style, label=mode)
        print("%-22s %-9s rise %.2f s  overshoot %.1f %%  settle %.2f s  ss err %.3f deg" % ((title, mode) + m))
    ax.axhline(STEP, color="0.7", lw=0.8)
    ax.set_xlabel("time (s)")
    ax.set_ylabel("heading (deg)")
    ax.set_title(title)
    ax.legend()
save(fig, args.out / "pid_step_euler_vs_trapezoid.png")
write_csv(args.out / "pid_metrics.csv", ["case", "integral_mode", "kp", "ki", "kd", "rise_s",
                                         "overshoot_pct", "settle_s", "ss_err_deg"], rows)

kps = [0.005 * 1.6 ** i for i in range(12)]
kis = [0.0005 * 1.9 ** i for i in range(12)]
fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
for ax, mode in zip(axes, ("euler", "trapezoid")):
    grid = [[min(metrics(*step_response(kp, ki, a.kd, mode))[2], 20.0) for kp in kps] for ki in kis]
    im = ax.pcolormesh(kps, kis, grid, shading="nearest", cmap="viridis_r")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.plot(a.kp, a.ki, "r*", ms=12, label="default gains")
    ax.set_xlabel("Kp (1/deg)")
    ax.set_ylabel("Ki (1/(deg s))")
    ax.set_title("2%% settling time, %s (20 s = not settled)" % mode)
    ax.legend()
    fig.colorbar(im, ax=ax, label="settling time (s)")
    print("%s: %d of %d gain pairs do not settle in 20 s" % (
        mode, sum(v >= 19.9 for r in grid for v in r), len(kps) * len(kis)))
save(fig, args.out / "pid_gain_sweep.png")

if args.log:
    fig, ax = plt.subplots(figsize=(8, 4))
    for path in args.log:
        t = read_csv(path)
        ax.plot([fnum(r["t_s"]) for r in t], [fnum(r["err_deg"]) for r in t],
                label="%s (%s)" % (path.replace("\\", "/").split("/")[-2], t[0]["integral_mode"]))
        print("%s: final error %.2f deg after %.1f s" % (path, fnum(t[-1]["err_deg"]), fnum(t[-1]["t_s"])))
    ax.axhline(0, color="0.7", lw=0.8)
    ax.set_xlabel("time (s)")
    ax.set_ylabel("heading error (deg)")
    ax.legend(fontsize=7)
    ax.set_title("Coarse-turn runs from turn.csv")
    save(fig, args.out / "pid_hw_runs.png")
