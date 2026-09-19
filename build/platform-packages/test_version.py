import unittest

from version import distribution_version


class VersionTests(unittest.TestCase):
    def test_stable_source(self):
        self.assertEqual(distribution_version(
            '<Project xmlns="http://schemas.microsoft.com/developer/msbuild/2003"><PropertyGroup><Version>12.1.2</Version></PropertyGroup></Project>', 8),
            '12.1.2-platform.8')

    def test_prerelease_source(self):
        self.assertEqual(distribution_version('<Project><Version>13.0.0-preview.1</Version></Project>', 9),
                         '13.0.0-preview.1.platform.9')

    def test_invalid_source_is_rejected(self):
        for value in ('', '$(VersionPrefix)', '1.2', '1.2.3+metadata', '1.2.3\nBAD=value'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                distribution_version(f'<Project><Version>{value}</Version></Project>', 1)

    def test_invalid_run_is_rejected(self):
        for value in ('0', '-1', '1\nBAD=value'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                distribution_version('<Project><Version>12.1.2</Version></Project>', value)


if __name__ == '__main__':
    unittest.main()
