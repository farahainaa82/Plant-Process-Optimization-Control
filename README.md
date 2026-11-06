# Process Optimisation Control Tower

A Streamlit prototype for an operations team reviewing production, energy, quality and process stability together. The demo uses three synthetic mineral-processing lines with grinding and flotation. It runs without credentials, paid AI services or plant data.

## Start locally

Use Python 3.12. Open a terminal inside the extracted project folder and run:

```shell
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## Walk through the demo

1. Start in **Live Monitor** on **North Plant · Line 01**. Turn off auto-scan to keep the initial demo values, or advance one 15-minute sample manually. With auto-scan on, the monitor advances one sample every 10 seconds while the session is active and the page is open.
2. Open **Scenario Lab**. The baseline stays fixed here. On the initial scan, **Lift feed with blend** ranks first among feasible options at about **+RM 1,499 over eight hours**. **Push maximum throughput** has higher projected value and breaches several operating limits.
3. Under **Operating limits and financial assumptions**, set maximum power to **2,250 kW** and apply the settings. The preferred option becomes **Stabilise feed blend**, with about **365 kWh less electricity** over the eight-hour horizon and **+RM 128** estimated net impact.
4. Select a review outcome and enter a note. In **Decision Log**, download the CSV to keep the outcome, baseline, projections and assumptions. One decision can be recorded per line per scan. To review a new scan, return to the monitor and advance. The log and edited settings are session-scoped.

## How the agent decides

- The baseline aggregates four 15-minute samples. The model calculates concentrate output from ore feed, feed grade, recovery and concentrate grade, and divides circuit power by concentrate output to get energy intensity.
- The agent simulates five operating changes plus holding current settings. It filters candidates against maximum feed and power and minimum concentrate grade, metal recovery and process stability. It ranks feasible candidates by estimated net impact. If none pass, the agent escalates for operator review.
- Estimated net impact equals the change in concentrate value less changes in variable feed and electricity costs and the one-off trial cost. The scenario holds projected rates steady over the selected horizon. The range varies product value and electricity tariff by ±20%.
- Telemetry, stability index, model coefficients, limits and prices are illustrative. The estimate excludes contract quality penalties, downtime and realised savings. Approval records an operator's choice for the simulated trial. The prototype uses a deterministic agent and does not connect to plant controls.

## Publish with GitHub Desktop and Streamlit Community Cloud

1. Create a repository named `process-optimisation-control-tower` in GitHub Desktop and copy the contents of the extracted project folder into the repository root, including `.streamlit`.
2. Commit and publish the repository to GitHub. Choose its visibility for the intended audience.
3. In Streamlit Community Cloud, choose the GitHub repository and branch. Set the entrypoint to `app.py` and the Python version to 3.12. Deploy.

[Streamlit Community Cloud deployment guide](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy)
