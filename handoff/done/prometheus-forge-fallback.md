# Prometheus premium forge fallback

- Replaced the weak no-WebGL button list with a labelled forge: furnace, champion
  flame, anvil/ingot, generation leader, lineage trail and the four fittest variants.
- Every label and colour comes from the existing loaded generation, fitness, verdict
  and lineage data. The fallback does not calculate a new strategy or change live.
- The first-screen sentence now says plainly whether live stays or a candidate needs
  owner review. Variant and live-reference buttons still open their original cards.
- LITE, 3D-off and reduced-motion modes freeze the flame animation; all controls stay
  44 px or larger and the fallback remains inside the HUD/dock safe area.
- Generation changes now re-measure the wrapped phone HUD before positioning the
  forge. CSS viewport QA at 360 and 390 px showed zero horizontal overflow, a 5 px
  HUD/forge gap, a 6 px forge/dock gap and 44 px minimum visible controls.
- WebGL-disabled interaction QA opened the existing creature detail card from a
  fallback lineage node without changing its calculations or tools.
- Focused Node checks cover the stored-data model, verdict, heat ramp, lineage,
  fallback structure, version tags and motion fallbacks. Actual GPU rendering remains
  unverified in the cloud browser because WebGL is disabled.
