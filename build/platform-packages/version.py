"""Derive a distribution version from the source revision being built."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]
VERSION_FILE = "build/SharedVersion.props"


def distribution_version(source_xml, run_number):
    if not re.fullmatch(r"[1-9][0-9]*", str(run_number)):
        raise ValueError("Run number must be a positive integer")
    root = ET.fromstring(source_xml)
    versions = [node.text.strip() for node in root.iter()
                if node.tag.rsplit("}", 1)[-1] == "Version" and node.text]
    if len(versions) != 1 or not re.fullmatch(
            r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?",
            versions[0]):
        raise ValueError("Expected one literal source Version in build/SharedVersion.props")
    version = versions[0]
    separator = "." if "-" in version else "-"
    return f"{version}{separator}platform.{run_number}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-number", required=True)
    parser.add_argument("--ref", help="Read the version from this exact Git commit instead of the working tree")
    parser.add_argument("--github-env", action="store_true")
    args = parser.parse_args()
    if args.ref:
        if not re.fullmatch(r"[0-9a-fA-F]{40}", args.ref):
            parser.error("--ref must be a full commit SHA")
        xml = subprocess.check_output(["git", "show", f"{args.ref}:{VERSION_FILE}"], cwd=ROOT)
    else:
        xml = (ROOT / VERSION_FILE).read_bytes()
    version = distribution_version(xml, args.run_number)
    print(version)
    if args.github_env:
        with open(os.environ["GITHUB_ENV"], "a", encoding="utf-8") as output:
            output.write(f"PACKAGE_VERSION={version}\n")


if __name__ == "__main__":
    main()
