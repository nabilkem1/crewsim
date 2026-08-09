---
name: frontend-design
description: Implement high-quality frontend interfaces for the simulator web application using the project's existing framework, architecture, components, APIs, and design system while maintaining maintainability and usability.
---

# Frontend Design — Simulator Web Application

## Purpose

Translate UX and UI requirements into production-quality frontend implementation.

The frontend must be a real operational interface to the simulator, not a static mockup.

## Before Coding

Inspect the existing project:

- Framework
- Routing
- Component architecture
- Styling system
- State management
- API layer
- Existing components
- Configuration model
- CLI capabilities
- Backend endpoints

Reuse existing infrastructure whenever appropriate.

Do not introduce a new framework or major dependency without justification.

## Architecture

Separate:

- Presentation
- UI state
- Application state
- API communication
- Data transformation
- Domain logic

Avoid putting simulator/business logic directly into visual components.

## API Integration

The UI should clearly represent:

- Request initiated
- Request running
- Request completed
- Request failed
- Request cancelled

Do not fake backend operations with timers when real APIs are available.

## Configuration

Represent backend configuration using typed frontend models where possible.

Do not duplicate configuration definitions unnecessarily.

If the backend exposes metadata, use it to generate appropriate controls.

## Long-Running Operations

Calibration, processing, and simulation may take significant time.

Implement an operation model containing concepts such as:

- Operation ID
- Status
- Start time
- Progress
- Current stage
- Logs
- Error
- Completion result

The UI should survive navigation or refresh when the backend supports persistent operation state.

## State Management

Clearly separate:

- Server state
- Local form state
- UI state

Avoid unnecessary global state.

## Forms

Forms should:

- Validate input
- Show errors close to the relevant field
- Preserve user input
- Prevent invalid submissions
- Clearly indicate saving/running state

## Error Handling

Handle:

- Network errors
- Backend validation errors
- Authentication errors where applicable
- Server errors
- Timeout errors
- Malformed responses
- Empty datasets

Never silently ignore API failures.

## Loading

Use contextual loading indicators.

Avoid replacing an entire page with a spinner when only one component is loading.

## Performance

Avoid:

- Unnecessary rerenders
- Excessive API calls
- Rendering huge datasets unnecessarily
- Blocking the main thread with expensive transformations

Use pagination, virtualization, memoization, or server-side aggregation when justified.

## Charts and Results

Keep analytical calculations on the backend when appropriate.

The frontend should primarily:

- Request data
- Transform presentation-specific structures
- Render visualizations
- Allow exploration

Do not silently change scientific or statistical values in the frontend.

## Maintainability

Prefer:

- Small composable components
- Explicit types
- Reusable hooks/utilities
- Consistent naming
- Clear boundaries

Avoid:

- Giant page components
- Duplicated API calls
- Copy-pasted UI
- Magic constants
- Inline business rules

## Testing

Important workflows should have tests covering:

- Configuration validation
- Calibration initiation
- Processing initiation
- Simulation initiation
- Error handling
- Result rendering
- Critical navigation
- Responsive behavior

## Implementation Principle

Build the smallest production-quality implementation that faithfully represents the defined UX and connects to the actual simulator capabilities.

Do not sacrifice correctness for visual polish.
