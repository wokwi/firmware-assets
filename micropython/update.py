"""Download the latest (or a given) MicroPython release for the boards this repo tracks.

Usage:
    python update.py                       # download the latest stable release and commit
    python update.py --release 20250415-v1.25.0
    python update.py --no-commit           # download only, don't git add/commit
"""

import argparse
import os
import re
import subprocess
import sys

import requests

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))

ESP32_BOARDS = (
    "ESP32_GENERIC",
    "ESP32_GENERIC_C3",
    "ESP32_GENERIC_C5",
    "ESP32_GENERIC_C6",
    "ESP32_GENERIC_S3",
    "ESP32_GENERIC_P4",
)

# Upstream name -> local filename prefix. Pico binaries are renamed to the
# legacy lowercase rp2-pico* convention already used in this directory.
PICO_BOARDS = {
    "RPI_PICO": "rp2-pico",
    "RPI_PICO_W": "rp2-pico-w",
    "RPI_PICO2": "rp2-pico2",
    "RPI_PICO2_W": "rp2-pico2-w",
}


def get_latest_release() -> str:
    """Scrape micropython.org for the most recent stable ESP32_GENERIC build."""
    url = "https://micropython.org/download/ESP32_GENERIC/"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    matches = re.findall(r"ESP32_GENERIC-(\d{8}-v[\d.]+)\.bin", r.text)
    stable = sorted(set(matches))
    if not stable:
        raise RuntimeError(f"Could not find any stable releases at {url}")
    return stable[-1]


def download_firmware(upstream_name: str, local_name: str) -> str:
    url = f"https://micropython.org/resources/firmware/{upstream_name}"
    dest = os.path.join(SCRIPT_DIR, local_name)
    if os.path.exists(dest):
        print(f"⏭️  Skipping {local_name} (already exists)")
        return dest
    r = requests.get(url, timeout=120)
    if r.status_code == 404:
        raise FileNotFoundError(local_name)
    if r.status_code != 200:
        raise RuntimeError(f"Failed to download {url}: HTTP {r.status_code}")
    with open(dest, "wb") as f:
        f.write(r.content)
    print(f"✅ Downloaded {local_name}")
    return dest


def git_commit(files: list[str], release: str) -> None:
    version = release.split("-v", 1)[1] if "-v" in release else release
    subprocess.run(["git", "add", "--", *files], check=True, cwd=SCRIPT_DIR)
    status = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--", *files],
        check=True,
        cwd=SCRIPT_DIR,
        capture_output=True,
        text=True,
    )
    if not status.stdout.strip():
        print("ℹ️  Nothing new to commit")
        return
    message = f"feat(micropython): {version} release binaries"
    subprocess.run(["git", "commit", "-m", message], check=True, cwd=SCRIPT_DIR)
    print(f"📝 Committed: {message}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--release",
        help="Release to download, e.g. 20250415-v1.25.0. Defaults to the latest stable.",
    )
    parser.add_argument(
        "--no-commit",
        dest="commit",
        action="store_false",
        help="skip the git add + commit step",
    )
    args = parser.parse_args()

    release = args.release or get_latest_release()
    print(f"📦 MicroPython release: {release}")

    targets = [(f"{b}-{release}.bin", f"{b}-{release}.bin") for b in ESP32_BOARDS]
    targets += [(f"{b}-{release}.uf2", f"{p}-{release}.uf2") for b, p in PICO_BOARDS.items()]

    downloaded: list[str] = []
    for upstream, local in targets:
        try:
            downloaded.append(download_firmware(upstream, local))
        except FileNotFoundError:
            print(f"➖ {local} not built for this release")
        except RuntimeError as e:
            print(f"❌ {upstream}: {e}", file=sys.stderr)

    if not downloaded:
        print("No firmwares downloaded.", file=sys.stderr)
        return 1

    if args.commit:
        git_commit(downloaded, release)

    return 0


if __name__ == "__main__":
    sys.exit(main())
