"""Hardware abstraction layer: base interfaces, simulator, real Raspberry Pi backend."""
from __future__ import annotations


def make_rig(cfg, clock=None, **sim_kwargs):
    """Build the Rig for cfg.hardware.backend. The real backend is imported lazily."""
    if cfg.hardware.backend == "sim":
        from .sim import SimParams, make_sim_rig
        return make_sim_rig(cfg, sim_kwargs.get("params") or SimParams())
    from .real import make_real_rig
    return make_real_rig(cfg)
