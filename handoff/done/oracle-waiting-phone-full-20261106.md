# Oracle waiting reason on a narrow phone

The last merged mobile pass allowed two lines but the actual published waiting reason needed four: 33 px visible out of 65 px content at 390×844. The hidden half explained the missing inducement swing and that a deeper leg could still take it.

This isolated Oracle change shows ordinary reasons in full against a dark readable panel on phones. Unusually long reasons scroll inside a 120 px maximum, and the region can take keyboard focus and scroll with End. The bottom dock remains scrollable. `oracle.css?v=phone2` avoids stale stylesheet reuse.

Local Chromium at 390×844 high/LITE: actual reason 77/77 px visible with 225 px clearance to the dock, no horizontal overflow or page JS errors. Synthetic fivefold reason 120 px viewport, 293 px content, keyboard End reached scrollTop 173. Physical iPhone and full repo area tests remain unverified; no trading code changed.
