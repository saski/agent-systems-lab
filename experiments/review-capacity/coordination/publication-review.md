# Publication Review: Add review-capacity simulation and illustrated learning guide

## Deliverables

- Pure deterministic simulation with exclusive hashed exports
- CLI and offline illustrated A/B/C task replay

## Verified Observations

By model tick 60, policy A had decided 6/24 tasks. Policies B and C had each
decided 8/24 tasks.

Policies B and C each have 16 unfinished tasks. Of those, 15 are waiting for
review under B and 1 under C. B has no tasks waiting for admission; C has 13.
Work in progress (WIP) admitted under the cap is 16 for B and 3 for C.

Each task has the same decision tick under B and C. To complete the full
workload, A requires 198 ticks; B and C each require 152 ticks.

In this scenario, the WIP cap moves waiting upstream to admission. These
synthetic results do not establish a universal optimum or gains in quality,
cost or productivity.

## Quality Checks

- Local `make check`: PASSED (Ruff lint/format, 83 tests passed, 5 container tests skipped, Compose valid)
- Local `make spec-check`: PASSED (4 items)
- Browser guide: Inspected on desktop and mobile

## Notes

- v0.2 OpenSpec change remains in progress (not complete or archived)
- Pending within same v0.2: Experiments API/dashboard, Make demo target, model horizon maximum alignment (selected design 10000 vs implementation 50000)
- Excluded API test draft preserved in original worktree
- This publication note is based on coordinator-supplied evidence; analytical foundation is not claimed complete

## Commit and PR

**Proposed commit title:** `Add review-capacity simulation with illustrated A/B/C replay guide`

**PR description:**

Introduces deterministic review-capacity simulation with hashed exports and offline task replay. Includes illustrated browser guide for A/B/C coordination patterns. All local checks pass. OpenSpec v0.2 remains in progress with pending dashboard and API work.
