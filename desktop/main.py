"""Build-time entry point.

The full native desktop application source is stored in main.py.xz.b64.
GitHub Actions decodes and extracts it over this file before running PyInstaller.
Extract the compressed source and the existing fgoauto source archive to inspect
or run the complete desktop application locally.
"""
raise SystemExit(
    "Download the built EXE from GitHub Actions, or extract the source bundles first."
)
