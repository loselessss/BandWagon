import os
from pathlib import Path
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt5.QtWidgets import QApplication
from bandwagon.app import Analyzer
from bandwagon.meta import PRIVACY_POLICY_URL
from bandwagon import i18n

ROOT = Path(__file__).resolve().parents[1]


class PrivacyPolicyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_policy_matches_published_route_and_contact(self):
        text = (ROOT / 'docs/privacy.md').read_text(encoding='utf-8')
        self.assertIn('permalink: /privacy/', text)
        self.assertIn('layout: policy', text)
        self.assertIn('## 한국어', text)
        self.assertIn('## English', text)
        self.assertIn('loseless@naver.com', text)
        self.assertEqual(PRIVACY_POLICY_URL, 'https://loselessss.github.io/BandWagon/privacy/')
        config = (ROOT / 'docs/_config.yml').read_text(encoding='utf-8')
        self.assertIn('baseurl: /BandWagon', config)
        for filename in ('README.md', 'PRIVACY.md', 'docs/MSIX.md'):
            self.assertIn(PRIVACY_POLICY_URL, (ROOT / filename).read_text(encoding='utf-8'))

    def test_page_has_no_scripts_or_external_assets(self):
        html = (ROOT / 'docs/_layouts/policy.html').read_text(encoding='utf-8')
        self.assertNotIn('<script', html.lower())
        self.assertNotIn('src=', html.lower())
        self.assertNotIn('rel="stylesheet"', html.lower())
        self.assertIn('{{ content }}', html)

    def test_options_action_opens_only_policy_url_in_both_languages(self):
        for language in ('ko', 'en'):
            with patch.object(i18n, 'CURRENT_LANG', language):
                win = Analyzer()
                try:
                    self.assertIn(win.privacy_action, win.options_menu.actions())
                    self.assertEqual(win.privacy_action.text(), i18n.tr('toolbar_privacy'))
                    self.assertFalse(win.privacy_action.icon().isNull())
                    self.assertTrue(win.privacy_action.toolTip())
                    with patch('bandwagon.app.QDesktopServices.openUrl', return_value=True) as launch:
                        win.privacy_action.trigger()
                    self.assertEqual(launch.call_args.args[0].toString(), PRIVACY_POLICY_URL)
                finally:
                    win.close(); win.deleteLater()

    def test_browser_failure_shows_copyable_url_in_status(self):
        win = Analyzer()
        try:
            with patch('bandwagon.app.QDesktopServices.openUrl', return_value=False):
                win._show_privacy()
            self.assertIn(PRIVACY_POLICY_URL, win.status.currentMessage())
        finally:
            win.close(); win.deleteLater()


if __name__ == '__main__':
    unittest.main()
