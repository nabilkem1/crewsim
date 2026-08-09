---
name: responsive-design
description: Design responsive layouts for the simulator web application across desktop, laptop, tablet, and smaller screens while preserving usability of configuration, calibration, processing, simulation, results, tables, charts, and reports.
---

# Responsive Design — Simulator Web Application

## Purpose

The simulator is primarily an engineering application and may be used on large monitors, laptops, and tablets.

Responsive behavior must preserve functionality rather than merely shrinking the desktop layout.

## Layout Strategy

Use a fluid layout with meaningful maximum widths.

Prefer:

- CSS Grid
- Flexbox
- Responsive containers
- Fluid spacing
- Responsive typography

Avoid hard-coded layouts that only work at one viewport size.

## Desktop

Desktop layouts may use:

- Persistent sidebar
- Multi-column dashboards
- Large analytical charts
- Dense tables
- Configuration panels

Use available screen width intelligently.

## Tablet

On medium screens:

- Collapse secondary navigation when appropriate.
- Reduce multi-column layouts.
- Stack configuration sections when necessary.
- Preserve chart readability.
- Avoid excessively narrow form controls.

## Small Screens

On small screens:

- Stack major sections.
- Collapse secondary information.
- Keep primary actions accessible.
- Avoid horizontal page overflow.
- Allow tables to scroll horizontally when necessary.
- Preserve readable chart dimensions.

Do not simply scale the entire desktop interface down.

## Configuration Forms

Forms should transition from multi-column to single-column layouts when width becomes constrained.

Labels and controls must remain understandable.

## Dashboards

Desktop:

- Summary cards may appear in rows.
- Charts can share horizontal space.

Small screens:

- Stack summary metrics.
- Stack charts.
- Keep important metrics near the top.

## Tables

Do not force large analytical tables into tiny columns.

Use:

- Horizontal scrolling
- Column prioritization
- Expandable rows
- Responsive table patterns

Never hide critical data without providing an alternative.

## Charts

Charts must maintain usable dimensions.

Avoid charts that become so narrow that axes and labels become unreadable.

## Navigation

Navigation should remain predictable at all sizes.

Potential responsive behavior:

Desktop:
Sidebar → full navigation

Tablet:
Collapsed sidebar → navigation drawer

Small screen:
Navigation drawer → compact header

## Touch

Interactive targets should be sufficiently large for touch interaction.

Do not rely on hover for essential functionality.

## Responsive Testing

Evaluate at minimum:

- Large desktop
- Standard laptop
- Tablet
- Small mobile viewport

Check:

- Navigation
- Configuration
- Calibration controls
- Processing status
- Charts
- Tables
- Reports
- Dialogs
- Error messages

## Principle

Responsive design means adapting information hierarchy and interaction patterns, not merely reducing dimensions.
