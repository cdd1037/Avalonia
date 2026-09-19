"""Restore, build, publish and execute the actual packages using an empty cache."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile

from package import RIDS, ROOT, read_package


def run(args, cwd, env, succeeds=True):
    print("+", " ".join(map(str, args)), flush=True)
    result = subprocess.run(args, cwd=cwd, env=env)
    if (result.returncode == 0) != succeeds:
        raise RuntimeError(f"Unexpected exit code {result.returncode}: {args}")


def check_archive(path, rid):
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if name.lower().endswith(".pdb"):
                raise AssertionError(f"PDB shipped in {path.name}: {name}")
            if name.startswith("runtimes/") and name.split("/")[1] != rid:
                raise AssertionError(f"Foreign runtime in {path.name}: {name}")


def check_restore(project, cache, rid):
    assets = json.loads((project / "obj/project.assets.json").read_text())
    for library, details in assets["libraries"].items():
        name = library.split("/")[0]
        if name.startswith("Cdd.") and not name.endswith("." + rid):
            raise AssertionError(f"Foreign package downloaded: {library}")
        if name.startswith(("SkiaSharp", "HarfBuzzSharp")) or (
                name.startswith("Avalonia") and name != "Avalonia.BuildServices"):
            raise AssertionError(f"Upstream multi-platform dependency: {library}")
        if name.startswith("Cdd."):
            for archive in (cache / details["path"]).glob("*.nupkg"):
                check_archive(archive, rid)
    # Include the physical cache, not just the selected runtime assets.
    for archive in cache.glob("cdd.*/*/*.nupkg"):
        if not archive.name.startswith("cdd.avalonia.sdk."):
            check_archive(archive, rid)


def verify(feed, version, platform, host_rid):
    for archive in feed.glob("*.nupkg"):
        spec, _ = read_package(archive)
        name = spec.findtext("metadata/id")
        if name != "Cdd.Avalonia.Sdk":
            rid = next((rid for rid in RIDS[platform] if name.endswith("." + rid)), None)
            if rid is None:
                raise AssertionError(f"Unexpected package: {name}")
            check_archive(archive, rid)
    for rid in RIDS[platform]:
        with tempfile.TemporaryDirectory(prefix="avalonia-package-test-") as temp:
            project = Path(temp)
            cache = project / "cache"
            shutil.copytree(ROOT / "build/platform-packages/smoke", project, dirs_exist_ok=True)
            # The smoke project is outside the source tree so it cannot accidentally
            # use repository project references, package versions or build imports.
            (project / "global.json").write_text(json.dumps({
                "sdk": json.loads((ROOT / "global.json").read_text())["sdk"],
                "msbuild-sdks": {"Cdd.Avalonia.Sdk": version}}))
            configuration = ET.Element("configuration")
            sources = ET.SubElement(configuration, "packageSources")
            ET.SubElement(sources, "clear")
            ET.SubElement(sources, "add", key="local", value=str(feed.resolve()))
            ET.SubElement(sources, "add", key="nuget", value="https://api.nuget.org/v3/index.json")
            mapping = ET.SubElement(configuration, "packageSourceMapping")
            local = ET.SubElement(mapping, "packageSource", key="local")
            ET.SubElement(local, "package", pattern="Cdd.*")
            public = ET.SubElement(mapping, "packageSource", key="nuget")
            ET.SubElement(public, "package", pattern="*")
            (project / "NuGet.Config").write_bytes(ET.tostring(configuration))
            env = os.environ | {"NUGET_PACKAGES": str(cache), "DOTNET_CLI_TELEMETRY_OPTOUT": "1"}
            # Host case intentionally omits -r: verify SDK auto-selection on a
            # completely fresh restore. Every other case verifies explicit -r.
            runtime = [] if rid == host_rid else ["-r", rid]
            run(["dotnet", "build", "-c", "Release", *runtime], project, env)
            check_restore(project, cache, rid)
            run(["dotnet", "publish", "-c", "Release", *runtime, "--no-restore", "-o", "publish"], project, env)
            for path in (project / "publish").rglob("*"):
                if path.name.lower().endswith(".pdb") and path.name != "Smoke.pdb":
                    raise AssertionError(f"Dependency PDB copied to publish: {path}")
                if path.is_file() and "runtimes" in path.parts:
                    raise AssertionError(f"Unresolved runtime tree in publish: {path}")
            if rid == host_rid:
                run(["dotnet", "publish/Smoke.dll"], project, env)
                run(["dotnet", "publish/Smoke.dll", "--desktop"], project, env)
                run(["dotnet", "restore", "-r", "browser-wasm"], project, env, succeeds=False)
                run(["dotnet", "restore", "-p:RuntimeIdentifiers=win-x64"], project, env, succeeds=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feed", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--platform", choices=RIDS, required=True)
    parser.add_argument("--host-rid", required=True)
    args = parser.parse_args()
    verify(args.feed, args.version, args.platform, args.host_rid)
