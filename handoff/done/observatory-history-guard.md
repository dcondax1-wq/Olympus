# Observatory saved scan guard

Malformed older browser storage records could make every successful source fetch appear unavailable: `previous()` accessed `.sources.find()` on a record without sources, then each `load()` caught that local error as a feed failure. Stored history now keeps only records with a source list, preserving valid scans. The app cache tag moves from v2 to v3.

Checked syntax with `new Function(app)` and exact one-site replacement. Browser QA remains pending until Observatory is published.