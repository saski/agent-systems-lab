## ADDED Requirements

### Requirement: paired saved-trace demo

The system SHALL provide a self-contained G02 demonstration using verified saved
numerical results. It SHALL compare FIFO and correction priority on one logical
clock, show selected-task attempts and all 24 paired outcomes, and distinguish
full-cohort latency summaries from snapshot counts. The existing A/B/C replay
and its anchor SHALL remain usable.

#### Scenario: seek to a correction and inspect both policies

- GIVEN the fixed G02 trace and task 24 selected
- WHEN the clock reaches tick 182
- THEN correction priority shows that task executing its correction
- AND its reviewer has no ready work
- AND both displayed policy counts reconcile with their saved traces

#### Scenario: use a narrow screen or reduced motion

- GIVEN a mobile viewport or a reduced-motion preference
- WHEN the reader opens the demo
- THEN controls and task details remain reachable without page-level overflow
- AND reduced motion disables animated playback while preserving manual seeking
- AND replay makes no network requests or operational writes
