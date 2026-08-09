---
name: accessibility
description: Ensure the simulator web application follows practical accessibility principles for keyboard navigation, screen readers, forms, status updates, contrast, focus management, charts, tables, and error handling.
---

# Accessibility — Simulator Web Application

## Purpose

Ensure the simulator is usable by people with different accessibility needs and conforms to established web accessibility practices.

Target WCAG 2.2 AA where practical.

## Keyboard Navigation

Every interactive element must be reachable using the keyboard.

Verify:

- Logical tab order
- Visible focus indicators
- No keyboard traps
- Buttons work with keyboard activation
- Dialogs manage focus correctly
- Menus can be operated without a mouse

Do not create interactions that depend exclusively on hover.

## Semantic HTML

Prefer semantic elements:

- button
- nav
- main
- header
- footer
- form
- label
- table
- section
- heading

Do not use clickable `<div>` elements when a button is appropriate.

## Forms

Every form control must have:

- A visible label
- Appropriate accessible name
- Clear validation feedback
- Required-state indication when applicable

Error messages should identify the affected field.

## Validation

Do not rely solely on red borders.

Communicate validation using:

- Text
- Icons where appropriate
- Accessible status information
- Clear association between error and field

## Color

Never communicate information using color alone.

For example, do not rely on:

- Green = success
- Red = failure

Instead use:

- "Success"
- "Failed"
- Icons
- Supporting text

Maintain sufficient contrast.

## Status Updates

Long-running simulator operations should expose status updates to assistive technologies when appropriate.

Examples:

- Calibration started
- Calibration 60% complete
- Calibration completed successfully
- Simulation failed

Avoid announcing excessive log output.

## Charts

Important chart information must have a textual representation.

For example:

"95th percentile delay: 18.4 minutes."

Do not make a chart the only way to access a critical result.

## Tables

Tables should have:

- Proper headers
- Clear relationships between headers and cells
- Appropriate captions where useful
- Consistent structure

Avoid excessively wide tables where possible.

## Focus Management

When opening a modal:

- Move focus into the modal.
- Keep focus within the modal while open.
- Return focus to the triggering element after closing.

When navigation changes content substantially, ensure the new context is discoverable.

## Motion

Do not use animation merely for decoration.

Respect reduced-motion preferences.

Avoid animations that interfere with reading or operation.

## Accessibility Review

Before shipping a screen verify:

- Keyboard operation
- Focus visibility
- Semantic structure
- Form labels
- Error messages
- Color contrast
- Non-color status indicators
- Screen-reader status announcements
- Accessible chart alternatives
- Responsive zoom behavior
