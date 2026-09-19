import copy
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from package import filter_files, make_sdk, rename, read_package, write_package


class DistributionTests(unittest.TestCase):
    def test_sdk_satisfies_nuget_org_license_metadata_requirements(self):
        with tempfile.TemporaryDirectory() as temp:
            make_sdk(Path(temp), "1.0.0-test.1")
            spec, files = read_package(next(Path(temp).glob("*.nupkg")))
        self.assertEqual(spec.findtext("metadata/license"), "MIT")
        self.assertEqual(spec.findtext("metadata/licenseUrl"), "https://licenses.nuget.org/MIT")
        self.assertIn(b"1.0.0-test.1", files["Sdk/Sdk.props"])
        self.assertNotIn(b"@VERSION@", files["Sdk/Sdk.props"])

    def test_sdk_embeds_readme_with_its_own_version(self):
        with tempfile.TemporaryDirectory() as temp:
            make_sdk(Path(temp), "1.0.0-test.2")
            spec, files = read_package(next(Path(temp).glob("*.nupkg")))
        self.assertEqual(spec.findtext("metadata/readme"), "README.md")
        readme = files["README.md"].decode("utf-8")
        self.assertIn('"Cdd.Avalonia.Sdk": "1.0.0-test.2"', readme)
        self.assertNotIn("@VERSION@", readme)

    def test_platform_and_symbols_are_removed_from_download(self):
        files = {"runtimes/win-x64/native/libSkiaSharp.dll": b"native",
                 "runtimes/win-x64/native/libSkiaSharp.pdb": b"symbols",
                 "runtimes/win-arm64/native/libSkiaSharp.dll": b"other architecture",
                 "runtimes/linux-x64/native/libSkiaSharp.so": b"other OS",
                 "lib/net9.0-android35.0/SkiaSharp.dll": b"mobile",
                 "lib/net8.0/SkiaSharp.dll": b"managed",
                 "lib/net8.0/SkiaSharp.pdb": b"managed symbols",
                 "LICENSE.txt": b"license"}
        self.assertEqual(set(filter_files(files, "win-x64")), {
            "runtimes/win-x64/native/libSkiaSharp.dll", "lib/net8.0/SkiaSharp.dll", "LICENSE.txt"})

    def test_dependency_graph_and_build_imports_survive_roundtrip(self):
        spec = ET.fromstring('''<package><metadata><id>Avalonia</id><version>1.0.0</version>
          <authors>Original author</authors><description>Original description</description>
          <license type="expression">MIT</license><dependencies><group targetFramework="net8.0">
          <dependency id="SkiaSharp" version="3.119.4" />
          <dependency id="Avalonia.BuildServices" version="11.3.2" />
          </group></dependencies></metadata></package>''')
        files = {"build/Avalonia.props": b"<Project/>", "LICENSE": b"original license",
                 ".signature.p7s": b"invalid after modification"}
        renamed, assets = rename(copy.deepcopy(spec), files, "win-x64", "1.0.0-test.1", {"SkiaSharp"})
        with tempfile.TemporaryDirectory() as temp:
            path = write_package(Path(temp), renamed, assets)
            actual, contents = read_package(path)
        self.assertEqual(actual.findtext("metadata/authors"), "Original author")
        self.assertEqual(actual.find(".//dependency").attrib,
                         {"id": "Cdd.SkiaSharp.win-x64", "version": "[1.0.0-test.1]"})
        self.assertNotIn(".signature.p7s", contents)
        self.assertIn("build/Cdd.Avalonia.win-x64.props", contents)
        self.assertEqual(contents["LICENSE"], b"original license")
        self.assertEqual(spec.findtext("metadata/id"), "Avalonia")

    def test_unknown_upstream_dependency_fails_closed(self):
        spec = ET.fromstring('''<package><metadata><id>Avalonia.Desktop</id><version>1.0.0</version>
          <dependencies><dependency id="Avalonia.UnknownBackend" version="1.0.0" /></dependencies>
          </metadata></package>''')
        with self.assertRaisesRegex(ValueError, "Unresolved distribution dependency"):
            rename(spec, {}, "linux-x64", "1.0.0", {})


if __name__ == "__main__":
    unittest.main()
