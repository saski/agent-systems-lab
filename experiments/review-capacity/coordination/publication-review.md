# Publication Review: Add review-capacity simulation and illustrated learning guide

## Deliverables

- Pure deterministic simulation with exclusive hashed exports
- CLI and offline illustrated A/B/C task replay

## Verified Observations

At tick 60, decision distributions: A decides 6/24, B decides 8/24, C decides 8/24 tasks.

Unfinished work: B and C have 16 tasks each, with review queues at 15 and 1 respectively. Admission queues: B has 0, C has 13 tasks pending admission. Admitted WIP is 16 for B and 3 for C.

Decision timing is identical per-task across B and C. Full drain completion: A requires 198 ticks, B and C require 152 ticks.

The WIP cap moves waiting upstream in this scenario. These synthetic results establish neither a universal optimum nor quality, cost or productivity gains.

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
