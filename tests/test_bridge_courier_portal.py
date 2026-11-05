"""Bridge visual/plain-word pass without changing its jobs or connector contract."""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
PAGE=ROOT/'tools/web_public/bridge/index.html'


class BridgeCourierPortalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.page=PAGE.read_text(encoding='utf-8')

    def test_job_and_connector_contract_is_intact(self):
        ids=re.findall(r"\{ id: '([a-z0-9-]+)', t:",self.page)
        self.assertEqual(ids,['icons','skies','textures','me','persona','labours','lore','deals','obsidian','ascend','codex-portal'])
        self.assertIn('Poseidon (Fed liquidity)',self.page)
        self.assertEqual(sorted(set(re.findall(r"fetch\('([^'?]+)",self.page))),['deliveries.json','jobs.json','status.json'])
        self.assertNotRegex(self.page,r"sendBeacon|XMLHttpRequest|method:\s*'POST'|WebSocket")
        self.assertIn("var WORD = 'KESTREL'",self.page)
        self.assertIn("var KEY = 'bridge.done'",self.page)
        self.assertIn("var WK = 'bridge.wizard'",self.page)
        self.assertIn('https://chatgpt.com/codex',self.page)

    def test_portal_and_plain_word_explanation_are_mobile_safe(self):
        self.assertIn('class="courier"',self.page)
        self.assertIn('Plain word: liquidity',self.page)
        self.assertIn('Liquidity</b> means how much money is available and moving in a market',self.page)
        self.assertIn('No live orders',self.page)
        self.assertIn('@media(max-width:560px)',self.page)
        self.assertIn('@media(prefers-reduced-motion:reduce)',self.page)
        self.assertIn('.chips button { min-height:44px; }',self.page)
        self.assertNotIn('innerHTML',self.page)

    def test_inline_javascript_still_parses(self):
        # The text/plain payload is selected separately because attributes are outside the capture.
        plain=re.search(r'<script type="text/plain" id="onboardText">.*?</script>',self.page,re.S)
        source=self.page[:plain.start()]+self.page[plain.end():] if plain else self.page
        scripts=re.findall(r'<script(?:\s[^>]*)?>(.*?)</script>',source,re.S)
        for i,script in enumerate(scripts):
            with tempfile.NamedTemporaryFile('w',suffix=f'-{i}.js',encoding='utf-8') as f:
                f.write(script);f.flush()
                subprocess.run(['node','--check',f.name],check=True,capture_output=True)


if __name__=='__main__': unittest.main()
