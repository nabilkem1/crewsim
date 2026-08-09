# Quick Start

## MVP Implementation Status (Epics 00 to 04)

The MVP covering Epics 00 through 04 (Phases 0 through 1d) is **almost entirely implemented**. 

Out of the 49 stories across these epics, **48 are fully completed**. 
The only incomplete item is a single **blocked** story in Epic 03 (Phase 1c):
- `S1c-04b`: Parked pending real Air Transat data to verify whether a 23.5% failure rate in the rolling 7-day rule (L5) is a real operational issue, or just an artifact of the synthetic data generator.

## How to Test a Policy for a Set of Scenarios

To test a specific policy (e.g., `R6`) across a number of scenarios (e.g., `500`) and output the aggregated KPIs, use the `run` command:

```bash
crewsim run --policy R6 --scenarios 500 --kpis
```
*Note: This runs the simulation and aggregates KPIs accurately over the measurement window (discarding the first 7 days of "warm-up" noise) to ensure metrics are comparable.*

## How to Compare Multiple Policies

To run multiple policies and generate a visual comparison, use the `report` command. You can list multiple policies and optionally specify the number of scenarios:

```bash
crewsim report --policies R4 R6 R8 R10 R14 --scenarios 500 --open
```

This will run the scenarios for each policy and generate a single, self-contained HTML artifact at `output/reports/policy_report.html`. It includes cost distributions, a U-shaped trade-off curve with the optimum marked, and the $\lambda$ curve. The `--open` flag will automatically open this report in your browser.

## Drilling Down into Costs

If you need to analyze specific costs for a single scenario, you can use the `explain-cost` command:

```bash
crewsim explain-cost --policy R6 --scenario 0 --category RESERVE_STAFFING
```
