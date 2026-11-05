# Data City readable fallback

When the 3D renderer cannot start, Data City now renders the decoded published research as an accessible text view, with district filters, idea search, research grade, sample count, and historical dollars per trade. The same model loaded for the city is used; sample data is labeled and the view cannot trade. This avoids a dead-end error and keeps the dashboard usable on devices without working WebGL.

`node --check datacitycheck/city.js` passed. Browser rendering and the full Data City test suite were unavailable in this connector-only private checkout; CI and phone QA remain necessary. The app's other 3D paths are untouched.
