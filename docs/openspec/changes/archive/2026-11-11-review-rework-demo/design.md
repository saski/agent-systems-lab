# G02 demo design

The page contains two distinct numerical experiments. Navigation and the
`#rework-section` anchor lead to G02; `#replay-section` continues to identify the
original A/B/C replay. Neither experiment's controls change the other's data.

Extend the G02 figure evidence projection with task attempts and state samples.
The existing report hash still identifies the unmodified raw report. The combined
page generator checks both frozen projections against the current pure models,
embeds data, styles, JavaScript and images, and needs no runtime API or model.

A small browser projection maps each attempt's inclusive timestamps to task
states. Every displayed snapshot reconciles with the saved stock counts. One
slider drives both policy cards and a selected task's timeline. Full-cohort
metrics stay visibly separate from the current tick's counts. A per-task table
retains all 24 outcomes. Playback respects reduced motion and pauses when the
page is hidden. Python invokes Node's built-in tests against an actual model
report; browser checks cover the rendered controls and desktop/mobile layout.

The website copy remains one static public asset. Existing Notes links and their
analytics attributes are preserved. No new tracking, API permission or live
simulation is introduced. The new prose is stored outside public site output.
