#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

PUBLIC_NAMES = (
    "site_public",
    "public",
    "public_html",
    "website_public",
)

UNREDACTED_NAMES = (
    "site_unredacted",
    "unredacted",
    "website_unredacted",
)

TEST_NAMES = (
    "site_test",
    "test",
    "website_test",
    "staging",
)


def remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def safe_extract(zip_path: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path) as zf:
        destination_resolved = destination.resolve()

        for member in zf.infolist():
            target = (destination / member.filename).resolve()
            if not str(target).startswith(str(destination_resolved)):
                raise RuntimeError(f"Unsafe ZIP path blocked: {member.filename}")

        zf.extractall(destination)


def find_first_folder(root: Path, names: tuple[str, ...]) -> Path | None:
    matches: list[Path] = []

    for name in names:
        for path in root.rglob(name):
            if path.is_dir():
                matches.append(path)

    if not matches:
        return None

    matches.sort(key=lambda p: (len(p.parts), str(p)))
    return matches[0]


def find_single_site_root(root: Path) -> Path | None:
    candidates = [p.parent for p in root.rglob("index.html") if p.is_file()]

    if not candidates:
        return None

    candidates.sort(key=lambda p: (len(p.parts), str(p)))
    return candidates[0]


def copy_folder(source: Path, destination: Path) -> None:
    if not source.exists():
        return

    if destination.exists():
        shutil.rmtree(destination)

    destination.parent.mkdir(parents=True, exist_ok=True)

    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns(
            ".git",
            ".github",
            "__pycache__",
            "*.pyc",
            ".DS_Store",
            ".htpasswd",
        ),
    )


def write_unredacted_protection(unredacted_dir: Path, remote_public_html: str) -> None:
    username = os.environ.get("SCC_UNREDACTED_USERNAME", "").strip()
    password = os.environ.get("SCC_UNREDACTED_PASSWORD", "").strip()

    if not unredacted_dir.exists():
        print("No unredacted folder found; skipping password protection.")
        return

    if not username or not password:
        raise RuntimeError(
            "Unredacted folder exists but SCC_UNREDACTED_USERNAME or "
            "SCC_UNREDACTED_PASSWORD is missing."
        )

    htpasswd_path = unredacted_dir / ".htpasswd"
    htaccess_path = unredacted_dir / ".htaccess"

    subprocess.run(
        ["htpasswd", "-bc", str(htpasswd_path), username, password],
        check=True,
    )

    remote_htpasswd = remote_public_html.rstrip("/") + "/unredacted/.htpasswd"

    htaccess_path.write_text(
        "\n".join(
            [
                "AuthType Basic",
                'AuthName "AirQuality26 unredacted evidence archive"',
                f"AuthUserFile {remote_htpasswd}",
                "Require valid-user",
                "Options -Indexes",
                "",
            ]
        ),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True)
    parser.add_argument("--output", default="build_hostinger/public_html")
    parser.add_argument("--work", default="build_hostinger/extracted")
    args = parser.parse_args()

    zip_path = Path(args.zip)
    output_root = Path(args.output)
    work_root = Path(args.work)

    remote_public_html = os.environ.get("AIRQUALITY_HOSTINGER_PUBLIC_HTML_DIR", "").strip()

    if not remote_public_html:
        raise RuntimeError("Missing AIRQUALITY_HOSTINGER_PUBLIC_HTML_DIR secret.")

    if not zip_path.exists():
        raise RuntimeError(f"ZIP file not found: {zip_path}")

    remove_path(output_root.parent)
    work_root.mkdir(parents=True, exist_ok=True)

    safe_extract(zip_path, work_root)

    public_source = find_first_folder(work_root, PUBLIC_NAMES)
    unredacted_source = find_first_folder(work_root, UNREDACTED_NAMES)
    test_source = find_first_folder(work_root, TEST_NAMES)

    if public_source is None:
        public_source = find_single_site_root(work_root)

    if public_source is None:
        raise RuntimeError(
            "Could not find a public website folder. "
            "Expected site_public/, public/, public_html/, or an index.html."
        )

    print(f"Public source: {public_source}")
    copy_folder(public_source, output_root)

    if unredacted_source:
        print(f"Unredacted source: {unredacted_source}")
        copy_folder(unredacted_source, output_root / "unredacted")

    if test_source:
        print(f"Test source: {test_source}")
        copy_folder(test_source, output_root / "test")

    if not (output_root / "index.html").exists():
        raise RuntimeError("Prepared public site is missing index.html.")

    write_unredacted_protection(output_root / "unredacted", remote_public_html)

    print(f"Prepared Hostinger upload folder: {output_root}")

    for child in sorted(output_root.iterdir()):
        print(f" - {child.name}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
