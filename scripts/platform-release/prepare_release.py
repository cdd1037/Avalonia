"""Validate and collect unchanged packages from one successful build run."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET
import zipfile


def inspect(path):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        specs = [n for n in names if n.endswith(".nuspec")]
        if len(specs) != 1 or len(names) != len(set(names)):
            raise ValueError(f"Invalid package archive: {path}")
        spec = ET.fromstring(archive.read(specs[0]))
        for node in spec.iter():
            node.tag = node.tag.split("}")[-1]
        name = spec.findtext("metadata/id")
        version = spec.findtext("metadata/version")
        if not name.startswith("Cdd."):
            raise ValueError(f"Refusing to publish upstream package {name}")
        if any(n.lower().endswith(".pdb") for n in names):
            raise ValueError(f"Unexpected PDB in {name}")
        # The SDK is emitted by each OS build. Windows checkout line endings
        # may differ; compare its logical content, but publish one ORIGINAL zip.
        content = {}
        for n in names:
            data = archive.read(n)
            if name == "Cdd.Avalonia.Sdk" and n.startswith("Sdk/"):
                data = data.replace(b"\r\n", b"\n")
            content[n] = hashlib.sha256(data).hexdigest()
        dependencies = {d.get("id"): d.get("version") for d in spec.findall(".//dependency")}
        return name, version, dependencies, content


def prepare(source, output, version):
    if output.exists() and any(output.iterdir()):
        raise ValueError("Release output must be empty")
    packages = {}
    for platform in ("linux", "osx", "win"):
        folder = source / f"platform-nuget-{platform}"
        provenance = json.loads((folder / f"provenance-{platform}.json").read_text())
        if provenance["version"] != version or provenance["platform"] != platform:
            raise ValueError(f"Build provenance mismatch: {platform}")
        expected = {item["package"]: item["bytes"] for item in provenance["packages"]}
        expected[f"Cdd.Avalonia.Sdk.{version}.nupkg"] = None
        actual = {p.name: p for p in folder.glob("*.nupkg")}
        if set(actual) != set(expected):
            raise ValueError(f"Incomplete or unexpected package set: {platform}")
        for filename, path in sorted(actual.items()):
            if expected[filename] is not None and path.stat().st_size != expected[filename]:
                raise ValueError(f"Package size mismatch: {path}")
            name, package_version, dependencies, content = inspect(path)
            if package_version != version or filename != f"{name}.{version}.nupkg":
                raise ValueError(f"Package identity mismatch: {path}")
            if name in packages:
                if name != "Cdd.Avalonia.Sdk" or packages[name][3] != content:
                    raise ValueError(f"Conflicting duplicate package: {name}")
            else:
                packages[name] = (path, dependencies, package_version, content)

    pending = {}
    for name, (_, dependencies, _, _) in packages.items():
        internal = {d for d in dependencies if d.startswith("Cdd.")}
        if not internal <= packages.keys():
            raise ValueError(f"Missing dependency of {name}: {internal - packages.keys()}")
        if any(dependencies[d] != f"[{version}]" for d in internal):
            raise ValueError(f"Mixed distribution versions in {name}")
        pending[name] = internal

    output.mkdir(parents=True, exist_ok=True)
    order = []
    while pending:
        ready = sorted(name for name, deps in pending.items() if not deps)
        if not ready:
            raise ValueError("Circular NuGet dependencies")
        for name in ready:
            del pending[name]
            order.append(name)
        for dependencies in pending.values():
            dependencies.difference_update(ready)
    # Expose the entry-point SDK after all of its selectable packages exist.
    order.remove("Cdd.Avalonia.Sdk")
    order.append("Cdd.Avalonia.Sdk")
    manifest = []
    for name in order:
        original = packages[name][0]
        destination = output / original.name
        shutil.copyfile(original, destination)
        digest = hashlib.sha256(original.read_bytes()).hexdigest()
        if hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
            raise ValueError(f"Copy verification failed: {name}")
        manifest.append({"id": name, "version": version, "file": original.name,
                         "sha256": digest, "source": original.parent.name})
    (output / "release-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Verified {len(manifest)} unchanged packages, version {version}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    prepare(args.source, args.output, args.version)
