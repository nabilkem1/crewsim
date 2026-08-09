---
name: design-system
description: Establish and maintain a consistent design system for the simulator web application, including design tokens, typography, spacing, colors, status semantics, components, forms, tables, charts, and interaction patterns.
---

# Design System — Simulator Web Application

## Purpose

Create a consistent visual and interaction language across the entire simulator.

Do not create one-off UI patterns when an existing component or token can be reused.

## Design Tokens

Centralize:

- Colors
- Typography
- Spacing
- Border radius
- Shadows
- Borders
- Control heights
- Breakpoints
- Motion durations

Prefer semantic tokens over hard-coded values.

## Semantic Colors

Define semantic states such as:

- Primary
- Neutral
- Success
- Warning
- Error
- Information

Status colors must be supplemented by text or icons.

## Typography

Define a clear hierarchy:

- Application title
- Page title
- Section heading
- Subsection heading
- Body
- Caption
- Technical/monospace text where appropriate

Numerical simulation outputs should be easy to scan.

## Spacing

Use a consistent spacing scale.

Avoid arbitrary spacing values introduced component by component.

## Components

Build reusable components for:

- Buttons
- Inputs
- Selects
- Form fields
- Cards
- Panels
- Tabs
- Tables
- Status badges
- Alerts
- Progress indicators
- Dialogs
- Tooltips
- Navigation
- Charts
- Empty states
- Loading states

## Buttons

Define clear hierarchy:

- Primary action
- Secondary action
- Tertiary action
- Destructive action

Only one action should normally receive primary emphasis within a focused section.

## Status Components

Use a common status component across:

- Calibration
- Processing
- Simulation
- Reports

Do not invent different status designs for every page.

## Forms

Form components should share:

- Label positioning
- Help text
- Error presentation
- Required-state presentation
- Focus treatment
- Disabled-state behavior

## Data Visualization

Charts should share:

- Typography
- Axis conventions
- Units
- Tooltip behavior
- Legend behavior
- Empty-state behavior

## Component States

Every reusable interactive component should consider:

- Default
- Hover
- Focus
- Active
- Disabled
- Loading
- Error
- Success where applicable

## Consistency Rule

If two components perform substantially the same function, they should look and behave substantially the same.

## Engineering Application Aesthetic

The design system should feel:

- Precise
- Calm
- Technical
- Trustworthy
- Information-rich
- Professional

Avoid unnecessary visual novelty.
