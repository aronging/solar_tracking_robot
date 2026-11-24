# solar_tracking_robot

MXET 345 lab final project. A two-axis solar tracker sits on the MXET 345 lab robot. The robot's Raspberry Pi turns a pan-tilt panel mount to follow the sun.

**Start here:** [`Code/README.md`](Code/README.md) gives the setup and run procedure, step by step.

## Folders

- `Code/` has the tracker software (Python, Raspberry Pi). Open this folder in VS Code with Remote-SSH on the Pi.
- `CAD/` has the current STEP parts and `Solar Tracker Assembly.step` (Nov 17).
  - `Purchased Parts/` has the models of bought parts.
  - `Test Prints/` has the fit-test prints.
  - `_superseded/` has old revisions.
- `docs/` has the project documents:
  - [`Design Overview.md`](docs/Design%20Overview.md) gives the system function, the algorithm, the conventions, the numerical methods, the test plan and the open items.
  - [`Hardware & BOM.md`](docs/Hardware%20%26%20BOM.md) gives the wiring, the I2C map, the parts and the costs.
  - [`Electrical Assembly Guide.md`](docs/Electrical%20Assembly%20Guide.md) gives the panel sensor and servo wiring procedure. A PDF copy is in the same folder.
  - [`Course Requirements.md`](docs/Course%20Requirements.md) gives the grading, the deliverables, the team roles and the lab robot data.
  - `Hardware List & Assembly Guide.pdf` is the mechanical assembly reference (exported again on Nov 17 from the live guide).
  - `Solar Tracker – Numerical Methods Summary.docx` is a one-page list of the numerical methods.
  - `Course Requirements.docx`, `Design Overview.docx`, `Hardware & BOM.docx` and `README.docx` are Word copies of older versions of the documents above.
