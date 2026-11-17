"""Shared bits for the analysis scripts: import path, Agg backend, CLI, output folder."""
import argparse
import csv
import sys
from pathlib import Path

CODE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE))                 # so `import solar_tracker` works for `python analysis/x.py`

import matplotlib                              # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt                # noqa: E402,F401  (re-exported)

LAT_DEG, LON_DEG = 30.6280, -96.3344          # spec section 10 site (Texas A&M campus)


def setup(script_file, description, add_args=None, default_out=None):
    """Parse --seed/--out (+ script-specific args) and create the output directory."""
    p = argparse.ArgumentParser(description=description)
    p.add_argument("--seed", type=int, default=345, help="random seed (default 345)")
    p.add_argument("--out", type=Path, default=None, help="output directory")
    if add_args:
        add_args(p)
    args = p.parse_args()
    args.out = args.out or default_out or CODE / "analysis_out" / Path(script_file).stem
    args.out.mkdir(parents=True, exist_ok=True)
    return args


def write_csv(path, header, rows):
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


def save(fig, path):
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"wrote {path}")


def read_csv(path):
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


def fnum(text):
    """CSV cell -> float (nan for blank)."""
    return float(text) if text not in ("", None) else float("nan")


def sim_session(seed, hours=6.0, body="session_sun", clouds=(), static_minutes=1.0):
    """Run a simulated session (injected offsets +7/-3 deg, 2% servo gain error) and
    return its log folder. Used when a script is run without --log."""
    import random
    from solar_tracker.config import load_config
    from solar_tracker.hardware.sim import SimParams, make_sim_rig
    from solar_tracker.logging_ import SessionLogger
    from solar_tracker.supervisor import Options, Supervisor
    cfg = load_config(overrides=['hardware.backend="sim"'])
    rig = make_sim_rig(cfg, SimParams(seed=seed, true_az_offset_deg=7.0, true_el_offset_deg=-3.0,
                                      cal_gain=1.02, clouds=list(clouds),
                                      heading0_true_deg=150.0))
    log = SessionLogger(str(CODE / "analysis_out" / "_sim_logs"), "sim", rig.clock, fsync=False)
    log.log.handlers[0].setLevel(100)             # keep the console quiet
    sup = Supervisor(cfg, rig, log, Options(duration_s=hours * 3600.0, command="sim"),
                     random.Random(seed))
    sup.run((lambda: sup.static_log(static_minutes, 0.0, 30.0)) if body == "static"
            else getattr(sup, body))
    return log.dir


def log_arg(p):
    p.add_argument("--log", type=Path, default=None,
                   help="session log folder or CSV file (default: run a simulation)")
