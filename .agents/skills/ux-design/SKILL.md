---
name: ux-design
description: Design and evaluate the user experience of the simulator web application, including information architecture, workflows, navigation, forms, dashboards, long-running operations, validation, feedback, and reporting.
---

# UX Design — Simulator Web Application

## Purpose

Design a clear, predictable, engineering-oriented UX for interacting with the simulator through a web interface.

The application should make the simulator understandable without requiring the user to operate the CLI directly.

## Core Information Architecture

Organize the application around the simulator lifecycle:

1. Configuration
2. Calibration
3. Processing
4. Simulation
5. Results
6. Reports

Do not force users to understand internal implementation details before they can operate the system.

## Primary UX Principles

- Make the current simulator state immediately visible.
- Clearly distinguish configuration, execution, and results.
- Never hide destructive or expensive operations behind ambiguous controls.
- Make long-running operations visibly asynchronous.
- Always show progress, current state, and errors.
- Preserve user inputs when validation fails.
- Prefer explicit actions over implicit behavior.
- Avoid unnecessary navigation between related workflow steps.
- Use consistent terminology throughout the application.
- Treat CLI functionality as a backend capability exposed through a usable UI.

## Simulator State

Represent important states explicitly:

- Idle
- Configured
- Validating
- Running
- Completed
- Failed
- Cancelled
- Warning
- Calibration required
- Configuration invalid

The UI should never leave the user wondering whether an operation is still running.

## Configuration UX

Configuration pages should:

- Group related parameters logically.
- Display parameter descriptions.
- Display defaults and current values.
- Identify required versus optional parameters.
- Validate values before execution.
- Provide clear error messages.
- Allow users to review changes before expensive operations.

Avoid presenting a large YAML-like configuration as the primary interface.

## Calibration UX

Calibration should expose:

- Calibration status
- Start calibration action
- Progress
- Current stage
- Logs or diagnostic information
- Validation results
- Generated reports
- Failure explanations

Users should be able to distinguish between "calibration has not been run", "calibration is running", and "calibration completed successfully".

## Processing and Simulation UX

For long-running operations:

- Show an operation status panel.
- Display elapsed time where useful.
- Display progress when measurable.
- Provide logs without overwhelming the primary interface.
- Clearly distinguish warnings from failures.
- Prevent accidental duplicate execution.
- Provide cancellation when technically supported.

## Results UX

Results should prioritize interpretation over raw data.

Use:

- Summary metrics
- Tables
- Charts
- Distribution views
- Percentiles
- Risk indicators
- Scenario comparisons
- Expandable technical details

Always provide a path from a high-level result to the underlying data.

## Error Handling

Errors should answer:

1. What happened?
2. Why did it happen?
3. What can the user do next?

Avoid generic messages such as:

"Something went wrong."

Prefer:

"Calibration failed because the input dataset contains 37 records with missing crew identifiers."

## Workflow

A typical user journey should be:

Configuration → Validate → Calibrate → Review calibration → Process → Run simulation → Review results → Generate report.

Do not require unnecessary page transitions.

## UX Review Checklist

Before considering a workflow complete, verify:

- Can a new user understand what to do next?
- Is the current simulator state obvious?
- Are expensive operations clearly identified?
- Are errors actionable?
- Are loading and completion states visible?
- Can users recover from validation errors?
- Can users inspect technical details when necessary?
- Is the terminology consistent?
