# Cities keyboard flight direction

Corrected the sign of forward/back movement in the desktop flight rig. At yaw zero the camera sits south of the city (positive Z), so W must move the target toward negative Z. The prior control moved toward the viewer. Added a focused Node regression that checks W, D, and typing inside the search input. `node --check tools/web_public/cities/rig.js` and `node tests/test_cities_keyboard.mjs` passed locally. Browser/phone QA remains separate.
