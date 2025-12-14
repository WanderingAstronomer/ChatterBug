#!/usr/bin/env python3
"""
Dependency verification script for Vociferous.
Checks that all required packages are installed and importable.
"""

import sys

# Define required packages and their import names
REQUIRED_PACKAGES: dict[str, str] = {
    "faster-whisper": "faster_whisper",
    "ctranslate2": "ctranslate2",
    "numpy": "numpy",
    "sounddevice": "sounddevice",
    "webrtcvad": "webrtcvad",
    "PyQt5": "PyQt5",
    "pynput": "pynput",
    "evdev": "evdev",
    "PyYAML": "yaml",
    "pyperclip": "pyperclip",
    "huggingface-hub": "huggingface_hub",
    "httpx": "httpx",
}

OPTIONAL_PACKAGES: dict[str, str] = {}

DEV_PACKAGES: dict[str, str] = {
    "pytest": "pytest",
    "ruff": "ruff",
}


def check_imports(packages: dict[str, str]) -> tuple[list[str], list[str]]:
    """Check if packages can be imported."""
    success = []
    failed = []

    for package_name, import_name in packages.items():
        try:
            __import__(import_name)
            success.append(package_name)
        except ImportError:
            failed.append(package_name)

    return success, failed


def main():
    print("=" * 60)
    print("Vociferous Dependency Check")
    print("=" * 60)
    print()

    # Check required packages
    print("Required Packages:")
    print("-" * 60)
    success, failed = check_imports(REQUIRED_PACKAGES)

    for pkg in success:
        print(f"  ✓ {pkg}")

    for pkg in failed:
        print(f"  ✗ {pkg} - MISSING")

    print()

    # Check optional packages
    print("Optional Packages:")
    print("-" * 60)
    opt_success, opt_failed = check_imports(OPTIONAL_PACKAGES)

    for pkg in opt_success:
        print(f"  ✓ {pkg}")

    for pkg in opt_failed:
        print(f"  ⚠ {pkg} - not installed (optional)")

    print()

    # Check dev packages
    print("Development Packages:")
    print("-" * 60)
    dev_success, dev_failed = check_imports(DEV_PACKAGES)

    for pkg in dev_success:
        print(f"  ✓ {pkg}")

    for pkg in dev_failed:
        print(f"  ⚠ {pkg} - not installed (dev only)")

    print()
    print("=" * 60)

    if failed:
        print(f"❌ {len(failed)} required package(s) missing!")
        print()
        print("Install missing packages with:")
        print("  pip install -r requirements.txt")
        print()
        print("Or use the installation script:")
        print("  ./install.sh")
        sys.exit(1)
    else:
        print("✅ All required dependencies installed!")
        if opt_failed:
            opt_count = len(opt_failed)
            print(f"(i) {opt_count} optional package(s) not installed (OK)")
        sys.exit(0)


if __name__ == "__main__":
    main()
