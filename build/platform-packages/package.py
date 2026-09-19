"""Produce a closed, RID-specific desktop NuGet graph from the source build.

Third-party binaries are redistributed, not recompiled. Their license files and
metadata are retained; original signatures are not applicable to derived packages.
Only the build machine downloads the upstream multi-platform archives.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[2]
RIDS = {"win": ["win-x64", "win-arm64", "win-x86"],
        "linux": ["linux-x64", "linux-arm64"], "osx": ["osx-x64", "osx-arm64"]}
PREFIX = "Cdd."


def read_package(path):
    with zipfile.ZipFile(path) as archive:
        files = {n: archive.read(n) for n in archive.namelist() if not n.endswith("/")}
    spec = ET.fromstring(files[next(n for n in files if n.endswith(".nuspec"))])
    for element in spec.iter():
        element.tag = element.tag.split("}")[-1]
    return spec, files


def package_id(spec):
    return spec.findtext("metadata/id")


def rid_id(name, rid):
    return f"{PREFIX}{name}.{rid}"


def write_package(output, spec, files):
    name = package_id(spec)
    version = spec.findtext("metadata/version")
    files = {n: b for n, b in files.items() if not (
        n.endswith(".nuspec") or n == ".signature.p7s" or n == "[Content_Types].xml"
        or n.startswith(("_rels/", "package/")))}
    spec.set("xmlns", "http://schemas.microsoft.com/packaging/2013/05/nuspec.xsd")
    files[f"{name}.nuspec"] = ET.tostring(spec, encoding="utf-8", xml_declaration=True)
    types = ET.Element("Types", xmlns="http://schemas.openxmlformats.org/package/2006/content-types")
    for ext in sorted({Path(n).suffix.lstrip(".") for n in files} | {"rels"}):
        if ext:
            ET.SubElement(types, "Default", Extension=ext, ContentType=(
                "application/vnd.openxmlformats-package.relationships+xml" if ext == "rels"
                else "application/octet-stream"))
    files["[Content_Types].xml"] = ET.tostring(types, encoding="utf-8")
    rels = ET.Element("Relationships", xmlns="http://schemas.openxmlformats.org/package/2006/relationships")
    ET.SubElement(rels, "Relationship", Id="manifest", Target=f"/{name}.nuspec",
                  Type="http://schemas.microsoft.com/packaging/2010/07/manifest")
    files["_rels/.rels"] = ET.tostring(rels, encoding="utf-8")
    output.mkdir(parents=True, exist_ok=True)
    destination = output / f"{name}.{version}.nupkg"
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for path, data in sorted(files.items()):
            info = zipfile.ZipInfo(path, (2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    return destination


def desktop_framework(tfm):
    # We distribute the portable managed desktop API; platform-specific mobile
    # and WinUI assemblies must never take precedence during framework reduction.
    return "-" not in tfm and tfm.lower().startswith(("net", ".net"))


def filter_files(files, rid):
    result = {}
    for name, data in files.items():
        parts = name.split("/")
        if name.lower().endswith((".pdb", ".mdb")):
            continue
        if parts[0] in ("lib", "ref") and not desktop_framework(parts[1]):
            continue
        if parts[0] == "runtimes":
            if parts[1] not in (rid, rid.split("-")[0]):
                continue
            # macOS upstream native libraries may be universal. Thin them to the
            # selected architecture before distribution, including Avalonia.Native.
            if rid.startswith("osx-") and name.endswith(".dylib"):
                arch = {"osx-x64": "x86_64", "osx-arm64": "arm64"}[rid]
                with tempfile.TemporaryDirectory() as temp:
                    source = Path(temp) / "input.dylib"
                    target = Path(temp) / "output.dylib"
                    source.write_bytes(data)
                    arches = subprocess.check_output(["lipo", "-archs", str(source)], text=True).split()
                    if arch not in arches:
                        raise ValueError(f"{name} has no {arch} slice")
                    if len(arches) > 1:
                        subprocess.run(["lipo", str(source), "-thin", arch, "-output", str(target)], check=True)
                        data = target.read_bytes()
                parts[1] = rid
                name = "/".join(parts)
        result[name] = data
    return result


def download(name, version, cache, provenance):
    path = cache / f"{name.lower()}.{version}.nupkg"
    url = f"https://api.nuget.org/v3-flatcontainer/{name.lower()}/{version}/{path.name}"
    if not path.exists():
        cache.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".download")
        urllib.request.urlretrieve(url, temporary)
        temporary.replace(path)
    provenance[name] = {"version": version, "url": url,
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    return read_package(path)


def rename(spec, files, rid, version, mapping):
    old_id = package_id(spec)
    new_id = rid_id(old_id, rid)
    spec.find("metadata/id").text = new_id
    spec.find("metadata/version").text = version
    for dependency in spec.findall(".//dependency"):
        name = dependency.get("id")
        if name in mapping:
            dependency.set("id", rid_id(name, rid))
            dependency.set("version", f"[{version}]")
        elif name.startswith(("Avalonia", "SkiaSharp", "HarfBuzzSharp")) and name != "Avalonia.BuildServices":
            raise ValueError(f"Unresolved distribution dependency: {old_id} -> {name}")
    # NuGet only imports build assets whose basename matches the package ID.
    # Preserve existing relative imports by leaving the original files in place.
    for path in list(files):
        parts = path.split("/")
        if parts[0] in ("build", "buildTransitive", "buildMultiTargeting"):
            if parts[-1] in (old_id + ".props", old_id + ".targets"):
                extension = Path(path).suffix
                wrapper = "/".join(parts[:-1] + [new_id + extension])
                files[wrapper] = (f'<Project><Import Project="$(MSBuildThisFileDirectory){parts[-1]}" /></Project>').encode()
    return spec, files


def make_sdk(output, version):
    spec = ET.Element("package")
    metadata = ET.SubElement(spec, "metadata")
    for key, value in {"id": "Cdd.Avalonia.Sdk", "version": version, "authors": "cdd1037",
                       "description": "Selects a RID-specific Avalonia desktop distribution before restore."}.items():
        ET.SubElement(metadata, key).text = value
    ET.SubElement(metadata, "license", type="expression").text = "MIT"
    ET.SubElement(metadata, "licenseUrl").text = "https://licenses.nuget.org/MIT"
    ET.SubElement(metadata, "readme").text = "README.md"
    files = {"Sdk/" + path.name: path.read_bytes().replace(b"@VERSION@", version.encode())
             for path in (ROOT / "build/platform-packages/sdk").glob("*")}
    files["README.md"] = (ROOT / "build/platform-packages/README.nuget.md").read_bytes().replace(
        b"@VERSION@", version.encode())
    write_package(output, spec, files)


def build(platform, version, source, output, cache):
    avalonia = {}
    for path in source.glob("*.nupkg"):
        spec, files = read_package(path)
        avalonia[package_id(spec)] = (spec, files)
    if "Avalonia.Desktop" not in avalonia or "Avalonia" not in avalonia:
        raise ValueError("BuildPlatformPackages must run before packaging")
    versions = {p.get("Include"): p.get("Version") for p in
                ET.parse(ROOT / "Directory.Packages.props").findall(".//PackageVersion")}
    provenance = {}
    third_party = {}
    for name in ("SkiaSharp", "HarfBuzzSharp"):
        spec, files = download(name, versions[name], cache, provenance)
        native_name = name + ".NativeAssets." + {"win": "Win32", "linux": "Linux", "osx": "macOS"}[platform]
        native_spec, native_files = download(native_name, versions[name], cache, provenance)
        dependencies = spec.find("metadata/dependencies")
        for group in list(dependencies):
            if not desktop_framework(group.get("targetFramework", "")):
                dependencies.remove(group)
                continue
            for dependency in list(group):
                if dependency.get("id", "").startswith(name + ".NativeAssets."):
                    group.remove(dependency)
        # .NET 8+ consumes runtimes assets directly. Legacy native build targets
        # would reintroduce unconditional copies and are intentionally not shipped.
        files = {n: b for n, b in files.items() if not n.startswith(("build/", "buildTransitive/", "interactive-extensions/"))}
        for n, data in native_files.items():
            if n.startswith("runtimes/"):
                files[n] = data
            elif any(word in n.lower() for word in ("license", "notice")):
                files["licenses/" + native_name + "/" + n] = data
        third_party[name] = spec, files
    if platform == "win":
        name = "Avalonia.Angle.Windows.Natives"
        third_party[name] = download(name, versions[name], cache, provenance)
    packages = avalonia | third_party
    sizes = []
    for rid in RIDS[platform]:
        for name, (original_spec, original_files) in sorted(packages.items()):
            files = filter_files(original_files, rid)
            if name in third_party and not any(n.startswith("runtimes/") for n in files):
                raise ValueError(f"No native assets for {name}/{rid}")
            spec, files = rename(copy.deepcopy(original_spec), files, rid, version, packages)
            path = write_package(output, spec, files)
            sizes.append({"package": path.name, "bytes": path.stat().st_size})
    make_sdk(output, version)
    (output / f"provenance-{platform}.json").write_text(json.dumps({
        "platform": platform, "version": version, "upstream": provenance, "packages": sizes}, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=RIDS, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--source", type=Path, default=ROOT / "artifacts/nuget")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/platform-nuget")
    parser.add_argument("--cache", type=Path, default=ROOT / "artifacts/upstream")
    args = parser.parse_args()
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:-[a-zA-Z0-9.-]+)?", args.version):
        parser.error("version must be a three-part NuGet version with an optional prerelease suffix")
    build(args.platform, args.version, args.source, args.output, args.cache)
