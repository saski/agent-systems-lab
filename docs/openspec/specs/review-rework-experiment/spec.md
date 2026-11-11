# review-rework-experiment Specification

## Purpose
Study who waits when corrected tasks return for review. Compare FIFO with
priority for returning corrections over the same finite, synthetic workload.
Keep final acceptance, first-review waiting and full-cohort completion separate,
and preserve enough evidence to explain each task's result.

## Requirements

### Requirement: paired deterministic review-order experiment

The system SHALL run FIFO and corrections-first review over identical validated
tasks, arrivals, capacities, service times and predetermined correction needs.
Each selected task SHALL require exactly two reviews with one correction between
them. Priority SHALL apply only when the reviewer is free, with FIFO order
inside each class and deterministic ties. Inputs SHALL be bounded and versioned.

#### Scenario: a correction returns while first reviews wait

- GIVEN a corrected task and a first-pass task are both ready for review
- WHEN the reviewer becomes free
- THEN FIFO selects the oldest ready attempt
- AND corrections-first selects the returning correction
- AND neither policy interrupts a review already in progress

#### Scenario: no corrections are required

- GIVEN identical tasks that all pass their first review
- WHEN both policies run
- THEN their task timelines, state counts and metrics are identical

### Requirement: complete task accounting and honest latency metrics

The system SHALL retain tasks as unfinished through correction and rereview,
record each review decision separately from final acceptance, and report paired
per-task acceptance and first-review delays. It SHALL distinguish tasks not yet
arrived from arrived unfinished work. Cohort latency summaries SHALL remain
unavailable when any member lacks its endpoint, with observed and pending counts.

#### Scenario: correction requested at the observation horizon

- GIVEN a review requests changes exactly at the horizon
- WHEN the horizon state is recorded
- THEN that task is unfinished and has no final acceptance
- AND its correction remains in execution or the execution queue

#### Scenario: the deadline arrives before all tasks finish

- GIVEN a bounded deadline that prevents the full cohort from finishing
- WHEN the report is produced
- THEN drain is incomplete and unobserved acceptance times remain null
- AND the report does not substitute accepted-only averages for full-cohort latency

### Requirement: reproducible local evidence without runtime actions

The system SHALL expose a CLI and Make entry point for the fixed G02 scenario,
save scenario and report hashes in an exclusive local attempt, and label all
results as synthetic logical time. It SHALL preserve existing Review Capacity
behavior and report access boundaries. Documentation SHALL state the learning
question, hypothesis, boundary, inputs, observations and limitations.

#### Scenario: repeat the same scenario

- GIVEN the fixed scenario and two distinct attempt IDs
- WHEN both runs are exported
- THEN their report hashes match and their attempt directories differ
- AND no gateway, worker, model provider or operational approval is invoked

#### Scenario: reuse an attempt ID

- GIVEN an existing attempt directory
- WHEN an export requests the same ID
- THEN it fails without changing the saved evidence
