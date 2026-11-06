# Kalshi City 2D atlas caption on a tall phone

At 390×844 in the no-WebGL atlas, the district caption started at y748 and its first 44px district button was y788–832, behind the fixed views dock (y720–832). The initial screen obscured the text and buttons. The caption now sits in a readable glass panel above the dock: y588–710, button y653–697, dock begins y720. Its district navigation remains scrollable and the map remains visible behind it.

Verified the actual public static app with branch CSS/index overlay in headless Chromium, high and low 2D atlas; the first district opens its dialog, no JavaScript errors or horizontal overflow, and before/after screenshots were visually inspected. High and low WebGL views still render without errors and the six tabs remain 83×44 px. `KC_NO_BROWSER=1 tests.test_kalshicity_page` passed 37/37. Physical iPhone Safari and the original full Python browser suite remain unverified. This changes only CSS/index cache tag, no bot or betting code.
