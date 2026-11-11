# G02 demo verification — 11 November 2026

The saved demo now contains the G02 correction-order experiment and the original
A/B/C replay. The new section is available at
[the existing public demo URL with the G02 anchor](https://www.saski.com/notes/assets/review-capacity-demo-g01.html#rework-section).
No Notes article or LinkedIn post was published by this change.

## Checks

- `make check`: lint, formatting, **206 passed**, five opt-in container tests
  skipped, Compose configuration valid. The complete run used local test-server
  access and completed in 55.91 seconds.
- `make review-rework-demo-test`: two Python tests passed. One runs five Node
  tests against a fresh numerical report; these cover every state at ticks
  0–192, both visits, timeline continuity, all paired outcomes and a deliberately
  inconsistent saved state. The other checks the final HTML's embedded data and
  preservation of the original anchor. The initial test failed before the
  browser projection existed.
- `make spec-check`: nine changes/specifications passed before archival; eight
  passed after the new requirement was synchronized into the canonical G02 spec.
- `git diff --check`: passed.
- Website `npm run build` and `npm test`: nine existing notes built; **43 tests
  passed**. The new deployment test initially failed against the old demo, then
  passed after the verified artifact was copied.

## Browser evidence

On the local page and again on the public page, G02 displayed mean turnaround
79.50 versus 76.67 and the complete split of five earlier, fifteen later and four
unchanged tasks. At tick 182, FIFO has one active review; correction priority
has one executing correction and an idle reviewer. Both have 23 accepted tasks.
The end control gives 24 accepted and zero unfinished tasks for both policies.
Task 23 shows acceptance at 152 versus 176, with a 24-tick delay under priority.

Play advanced the clock and Pause stopped it. Keyboard Home and ArrowRight
worked. Reduced-motion emulation disabled playback while preserving manual
seeking, and the override was reset afterward. At a 390 px viewport, document
width was exactly 390 px; tables and timelines retain their own horizontal
scrolling. Both policy cards and controls remained reachable. Desktop inspection
used 1280 × 1000, with the viewport override reset afterward.

Replaying, seeking and selecting tasks produced zero network requests in the
browser observer. The original controls still showed B's 15-task review queue
and C's one-task review queue at tick 60, with eight decisions in both. G02
controls did not alter that clock. Screenshots are retained locally under
`.lab/g02-demo-2026-11-11/` (`desktop.jpg`, `mobile.jpg`, `public-demo.jpg`).

## Publication

Website commit: `a55e08972009bde2ad8094e5dbc917b4f0237443`.
[Deployment](https://github.com/saski/saskiweb/actions/runs/42984015951) succeeded.
The production page returned HTTP 200 and matched the lab and website copies
byte for byte:

`c447b619ee41111949d7a63a1084f3ff6a7b6893ab482c7361981bb3e663efea`

The numerical report remains unchanged at SHA-256
`3f1f1dff0790d109c7f814377cb0acf3088829d2c0ecff78317b7e7eb9577097`.
The original Notes link and its analytics attributes were preserved. No new
tracking was introduced and no analytics click was claimed as campaign traffic.
Website changes were limited to the demo asset and its test; unrelated local
configuration was excluded.

The Notes and LinkedIn proposals are retained in ignored
`.lab/g02-demo-2026-11-11/notes-draft.md` and `linkedin-draft.md` for author review.
They focus on the new result and omit the earlier project justification and
repeated reading references.
