# Frontend state-change regression fixture

`fixtures/frontend_hook_regression.tsx` mounts the real time graph, detail view,
and recorded-offset histogram with small synthetic inputs. Copy it to
`sifter_vis_d3/sifter/src/app/hook-regression/page.tsx` **in a temporary test copy**,
then build and serve that copy. Do not add this route to a release build.

Check these transitions in `/hook-regression`:

1. Set time to 75%: the cursor moves from SVG x=225 to x=575.
2. Replace trace without unmounting the components: the existing `node` curve
   changes shape, its vertical scale changes from 20 to 400 bytes, and the time
   axis changes from 0–100 ticks to 0–4 seconds (absolute time 200–600).
3. Change colour: both the existing curve and histogram bars change colour.
4. Replace alignment data: three bars at offsets 0/8/16 become two at 0/32;
   old bars disappear. Hide/show the new size and check the existing bars update.
5. Change detail geometry: the x-axis changes from 64 to 128 bytes. Zoom the
   detail view, then change geometry or selected region: the old zoom resets.
6. Drag the time cursor to 75% after replacing the trace: absolute time is about
   500, not a value from the previous range. Zoom the graph: selected time stays
   unchanged. Drag within the zoomed view: time follows the visible interval.
7. Toggle empty lines and restore them: neither an exception nor stale curves
   should appear.

Also test the normal saved EFRB/Valkey route: edit settings without applying them,
click an already-selected cache-line size (it must remain selected), resample,
drag/zoom, and switch trace. Settings apply on Resample; a different trace starts
with its own initial state. Inspect browser errors and the backend request log:
editing settings must not trigger another `init-app` request.

The offset histogram uses the capture-time `ALIGNMENT` table. Its labels show
recorded offsets; changing simulated cache geometry must not reinterpret those
precomputed counts as measurements at a different capture cache-line size.

November 2 acceptance: 18 focused DOM assertions passed, along with the normal
saved-trace interactions, typecheck, production build, and five frontend helper
suites. No hook warnings were suppressed.
