# Oracle mobile price-ladder glare

Base: current main `94037b9c9773c0ee032c5a2704288a36a346ca17`. This focused PR hides only the distant bright entablature ring below 601px, preserving the price column and surrounding columns; widening restores it.

PR #232's merged fallback semantics remain intact: the failed WebGL canvas is hidden, LAST SEEN has no active beacons, demo replay is labelled honestly, `fallback.js?v=oracle-fallback-honesty-1` stays pinned, and the combined page cache tag is `ofst3`.

Automated 390×844 browser checks cover HIGH/LITE crown transitions, no overflow, minimum visible control sizing, DOM/ARIA fallback attributes, and forced no-WebGL recovery. A physical VoiceOver/TalkBack spot-check is separate and unavailable in this environment. Do not combine with frame-recovery PR #315.

No trading, Zlarior, LIT, ATLAS, worker, publisher, or data paths are changed.
