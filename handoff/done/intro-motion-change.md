# Dynamic reduced motion intro cleanup

If the operating system switches to reduced motion while an app intro is playing, the canvas overlay now ends immediately. This removes its invisible key capture and stops drawing. The media query listener is removed on every exit; the start path also checks the setting again after installing it.

Checked: JavaScript parses; runtime listener check verifies it ends only on the reduced-motion change, and static cleanup/race guards are present. Browser screenshots unavailable here. No bot, worker or app registration files changed.
