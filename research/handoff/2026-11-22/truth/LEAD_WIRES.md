# LEAD_WIRES (night-truth field audit)

mffumodel.js changed (coach reads the PC's mf `lt` / `f.ft`). Cache bump for the two pages that load it with ?v=:
- tools/web_public/business/mffu.html:111   `<script src="mffumodel.js?v=4"></script>`  ->  `<script src="mffumodel.js?v=5"></script>`
- tools/web_public/board/index.html:83      `<script src="../business/mffumodel.js?v=4"></script>`  ->  `<script src="../business/mffumodel.js?v=5"></script>`
(sw.js has no mffumodel entry: no sw.js change.)

Optional Python side (tools/pc_report.py `_life`): keep `"why"` (cut ~80 chars) per account so mffucenter.js's `life_why` line can show.
