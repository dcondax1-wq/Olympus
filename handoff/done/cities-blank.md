# Cities first-screen atlas

Added a readable, immediately visible atlas over the 3D world. The three featured places open their real city scenes, and the tour and find controls use the existing flight and search systems. The city count is updated from the validated catalogue at boot. The atlas hides when a data sheet or city opens. The existing 3D world, data, and controls remain in place.

Checks: `node --check citiescheck/app.js` passed against the exact updated source. Verified changed markers and route IDs against the 170-city catalogue. Full app suite and 390x844 visual screenshots were unavailable from this connector-only checkout; pending CI and phone QA.
