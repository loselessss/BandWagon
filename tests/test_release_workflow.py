import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"


class ReleaseWorkflowStructureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        cls.process = (ROOT / "RELEASE_PROCESS.md").read_text(encoding="utf-8")

    def test_source_preparation_is_a_required_dependency(self):
        self.assertIn("prepare-source:", self.workflow)
        self.assertIn("build-windows:\n    name: Build Windows installers\n    needs: prepare-source", self.workflow)
        self.assertIn("- prepare-source\n      - build-windows", self.workflow)

    def test_source_assets_are_prepared_before_binary_assets(self):
        source_pos = self.workflow.index("git archive")
        binary_pos = self.workflow.index("Build the application directory")
        self.assertLess(source_pos, binary_pos)
        self.assertIn("actions/upload-artifact@v4", self.workflow)
        self.assertIn("name: release-source-assets", self.workflow)
        self.assertIn('(cd release-assets && sha256sum "BandWagon_Source_${VERSION}.zip"', self.workflow)

    def test_stable_release_has_required_asset_names(self):
        required_patterns = (
            r'BandWagon_Setup_\$\{VERSION\}\.exe',
            r"BandWagon_Setup_latest\.exe",
            r'BandWagon_Portable_\$\{VERSION\}\.zip',
            r"BandWagon_Portable_latest\.zip",
            r'BandWagon_Source_\$\{VERSION\}\.zip',
            r'BandWagon_Source_\$\{VERSION\}\.zip\.sha256',
            r'BandWagon_Dependencies_Build_\$\{VERSION\}\.md',
        )
        for pattern in required_patterns:
            self.assertRegex(self.workflow, pattern)

    def test_no_source_prerelease_or_source_tag_is_created(self):
        self.assertNotRegex(self.workflow, r"(?i)source[-_]?(?:pre)?release")
        self.assertNotRegex(self.workflow, r"v(?:\$\{\{[^}]+\}\}|\$\{VERSION\})-source")
        self.assertIn("prerelease: false", self.workflow)
        self.assertIn("별도 릴리스가 아니라", self.workflow)

    def test_process_document_points_to_normal_release_page(self):
        self.assertIn("releases/tag/vX.Y.Z", self.process)
        self.assertIn("vX.Y.Z-source", self.process)
        self.assertIn("기존 릴리스와 Assets는", self.process)


if __name__ == "__main__":
    unittest.main()
