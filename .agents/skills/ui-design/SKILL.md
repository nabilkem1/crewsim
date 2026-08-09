---
name: ui-design
description: Design the visual interface of the simulator web application, including dashboards, configuration forms, navigation, tables, charts, status indicators, dialogs, logs, and reports.
---

# UI Design — Simulator Web Application

## Purpose

Create a professional engineering/scientific interface rather than a generic marketing website.

The UI should communicate precision, reliability, hierarchy, and operational state.

## Visual Hierarchy

Prioritize:

1. Application state
2. Primary action
3. Key metrics
4. Important warnings
5. Detailed technical information

Avoid excessive visual decoration.

## Application Shell

Prefer a persistent application shell containing:

- Application identity
- Primary navigation
- Current environment or scenario
- System status
- User/session controls where required

Primary navigation should correspond to meaningful simulator capabilities.

## Dashboard

A dashboard should provide:

- Overall simulator status
- Current configuration/scenario
- Last calibration status
- Latest processing status
- Latest simulation status
- Important result metrics
- Recent operations
- Warnings/errors

Do not overload the dashboard with every available metric.

## Configuration UI

Use structured forms.

For each parameter consider displaying:

- Parameter name
- Human-readable label
- Description
- Current value
- Default value
- Unit
- Valid range
- Source/config file
- Validation status

Use appropriate controls:

- Boolean → switch/checkbox
- Enumerations → select
- Numeric values → number input
- Ranges → appropriate numeric controls
- Paths → path selector/input
- Complex structures → expandable sections

## Status Indicators

Use consistent status patterns.

Examples:

- Idle
- Running
- Success
- Warning
- Error
- Cancelled

Do not communicate status using color alone.

Use:

- Icon
- Label
- Color
- Optional explanatory text

## Tables

Tables should:

- Have clear column headings.
- Align numerical values appropriately.
- Support sorting when useful.
- Avoid unnecessary columns.
- Provide empty states.
- Support pagination for large datasets.
- Allow technical details to be expanded rather than permanently displayed.

## Charts

Charts should answer a specific analytical question.

Always provide:

- Axis labels
- Units
- Meaningful titles
- Legends where necessary
- Tooltips
- Accessible textual alternatives for important information

Avoid decorative charts.

## Logs

Logs should be secondary to the main operation state.

Provide:

- Timestamp
- Severity
- Message
- Optional source/component

Allow users to expand detailed logs without making logs dominate the page.

## Dialogs

Use dialogs for:

- Confirmation of destructive operations
- Important configuration decisions
- Focused technical information

Do not use dialogs for ordinary navigation or large workflows.

## Empty States

An empty state should explain:

- What is missing
- Why it matters
- What action the user can take

Example:

"No calibration results are available. Run calibration to generate the baseline metrics."

## Loading States

Never leave a blank screen.

Use:

- Skeletons for predictable content
- Progress indicators for operations
- Status messages for long-running processes

## Visual Style

Prefer:

- Strong typographic hierarchy
- Restrained color palette
- Consistent spacing
- Clear borders and surfaces
- High information density without clutter
- Professional technical aesthetics

Avoid:

- Excessive gradients
- Decorative animations
- Giant hero sections
- Marketing-style cards everywhere
- Excessive rounded containers
