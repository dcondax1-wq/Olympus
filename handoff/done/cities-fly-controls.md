# Cities flight controls

Added keyboard navigation to the existing 3D camera rig: W/A/S/D or arrows move, Q/E descend/ascend, Shift accelerates. The movement follows yaw, clamps the elapsed frame after a background tab resumes, respects the existing target clamp hook, and ignores typing in form controls. Touch orbit/pinch/pan remain unchanged. `node --check` passed.

The blank world was due in part to the hub opening at a world scale where islands project as only a few pixels; the separate atlas PR addresses readable first-screen navigation. This controls PR does not claim to fix rendering failures or verify a 390x844 screenshot. Full page tests need a private checkout/browser environment and CI.
