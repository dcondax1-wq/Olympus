# LEAD_WIRES: caller portal (day-a11y 2026-11-21)

1. **day-cities3, `tools/site_factory.py` `load_leads()`** also reads the businesses callers add (public facts only). After the existing loop, before `return out`:
   ```python
   added = os.path.join(ROOT, "tools", "agency_added_leads.json")    # day-a11y caller portal: businesses a caller found on Google Maps
   if os.path.exists(added):
       have = {L["id"] for L in out}
       out += [L for L in json.load(open(added, encoding="utf-8")).get("leads", []) if isinstance(L, dict) and L.get("id") and L["id"] not in have and str(L.get("name", "")).strip()]
   ```
2. **day-cities3, the public_base export** copies `tools/web_public/agency/portal/` to the neutral host: `index.html`, `portal.css`, `portal.js`, `portalcore.js`, `portal.json`, `calllist.json`. Nothing else is needed.
   - `tools/site_factory_agency.json` gets `"public_base"` and `"agency_number"`.
   - Then `python -m agency.portal setup` copies both into `portal.json`, and `python -m agency.portal build` refreshes the list.
3. **No APPS / sw.js entry.** The portal is for the caller, not an owner app. If you want it reachable from Olympus, one link on the Agency hub: `<a href="portal/">Caller portal</a>`.
