#!/usr/bin/env python3
"""Update the channels/tg chart's Chart.yaml in a checked-out copy of
qalby-tech/livellm_cloud_charts after a channels_tg release.

The channel image is tagged `tg-<version>` where <version> is the project
version parsed from channels_tg's pyproject.toml. The chart defaults
image.tag to `tg-<appVersion>`, so writing appVersion IS the release of the
new image into the chart — values.yaml is not touched.

What this does:

    1. appVersion := <version from pyproject.toml>
       This is what rolls the pod (deployment image tag is tg-<appVersion>).

    2. version (chart) := PATCH +1, but only when appVersion actually
       changed. A component-only release is a chart patch — Helm/ArgoCD need
       a new chart version to recognise the rollout. MINOR is reserved for
       chart-code changes (handled by livellm_cloud_charts' own bump-minor
       workflow); MAJOR is preserved (humans bump it).

If appVersion already equals <version> the file is left untouched and the
caller (CI) sees no diff to commit — re-runs are idempotent.

Usage:
    bump-chart.py <charts-repo-root> <version>
"""
from __future__ import annotations

import pathlib
import re
import sys

CHART_REL_PATH = "charts/channels/tg/Chart.yaml"
SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def parse_semver(v: str) -> tuple[int, int, int]:
    m = SEMVER_RE.match(v.strip().strip('"').strip("'"))
    if not m:
        sys.exit(f"not semver MAJOR.MINOR.PATCH: {v!r}")
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def find(pat: str, text: str, label: str) -> re.Match[str]:
    m = re.search(pat, text, flags=re.MULTILINE)
    if not m:
        sys.exit(f"no {label} found")
    return m


def update_chart(path: pathlib.Path, version: str) -> dict[str, str] | None:
    text = path.read_text()

    chart_v = find(r"^version:\s*(\S+)\s*$", text, "top-level `version:`").group(1)
    app_v = find(
        r'^appVersion:\s*"?([^"\s]+)"?\s*$', text, "top-level `appVersion:`"
    ).group(1)

    parse_semver(chart_v)
    parse_semver(app_v)

    if app_v == version:
        return None  # nothing to do — already at this release

    # 1. appVersion = <version>.
    text, n = re.subn(
        r'^(appVersion:\s*)"?[^"\s]+"?(\s*)$',
        rf'\g<1>"{version}"\g<2>',
        text, count=1, flags=re.MULTILINE,
    )
    if n != 1:
        sys.exit("could not rewrite top-level `appVersion:`")

    # 2. chart version PATCH +1.
    cmaj, cmin, cpatch = parse_semver(chart_v)
    new_chart = f"{cmaj}.{cmin}.{cpatch + 1}"
    text, n = re.subn(
        r"^(version:\s*)\S+(\s*)$",
        rf"\g<1>{new_chart}\g<2>",
        text, count=1, flags=re.MULTILINE,
    )
    if n != 1:
        sys.exit("could not rewrite top-level `version:`")

    path.write_text(text)
    return {"version": new_chart, "appVersion": version}


def main() -> int:
    if len(sys.argv) != 3:
        sys.exit("usage: bump-chart.py <charts-repo-root> <version>")
    root = pathlib.Path(sys.argv[1])
    version = sys.argv[2]
    parse_semver(version)  # validate input early
    chart_path = root / CHART_REL_PATH
    if not chart_path.exists():
        sys.exit(f"{chart_path} not found")
    result = update_chart(chart_path, version)
    if result is None:
        print(f"channels/tg chart already at appVersion {version} — no change")
    else:
        print(
            "channels/tg chart updated: "
            + ", ".join(f"{k} -> {v}" for k, v in result.items())
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
