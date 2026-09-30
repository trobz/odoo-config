"""Refresh the schema snapshot embedded in the 3 web tools.

Each page under site-docs/docs/artifacts/ carries a `<script id="schema-data">`
JSON copy of the merged option schema, so it works as a plain static page.
Run `make tools-data` after editing odoo_config/options.toml or overlay.toml;
`--check` exits 1 when a page is stale. The "source" stamp is ignored when
comparing, since a committed page can never hold its own commit hash.
"""

import json
import re
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

from odoo_config.schema import _fmt, _merge, _read_toml, canon, default_for, valid_for_version

ROOT = Path(__file__).resolve().parent.parent
VERSIONS = _read_toml("options.toml")["versions"]
PAGES = [
    ROOT / f"site-docs/docs/artifacts/{slug}/index.html"
    for slug in ("odoo-option-lookup", "odoo-option-matrix", "odoo-conf-builder")
]
BLOCK = re.compile(r'(?<=id="schema-data">)(.*?)(?=</script>)', re.DOTALL)
FIELDS = ("section", "help", "comment", "mandatory", "edition", "commented", "min_version", "max_version")


def per_version(meta):
    # Ignore edition: the page shows the value and gates on "edition" itself.
    return {v: _fmt(default_for(meta, v)) if valid_for_version(meta, v, enterprise=True) else None for v in VERSIONS}


def build_data():
    core = _read_toml("options.toml")["options"]
    overlay = _read_toml("overlay.toml")

    options = []
    for key, meta in _merge(core, overlay["options"]).items():
        in_core = key in core
        entry = {"key": key}
        if "default" in meta:
            entry["default"] = _fmt(meta["default"])
        entry |= {f: meta[f] for f in FIELDS if f in meta}
        if meta.get("by_version"):
            entry["by_version"] = {v: _fmt(val) for v, val in meta["by_version"].items()}
        entry |= {
            "type": type(meta.get("default", "")).__name__,
            "in_core": in_core,
            "in_overlay": key in overlay["options"],
            "trobz": not in_core or canon(default_for(meta, None)) != canon(default_for(core[key], None)),
            "core_default": _fmt(default_for(core[key], None)) if in_core else None,
            "versions": per_version(meta),
        }
        if in_core:
            entry["core_versions"] = per_version(core[key])
        options.append(entry)

    commit = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True)  # noqa: S607
    return {
        "source": {"repo": "trobz/odoo-config", "commit": commit.strip(), "describe": f"v{version('odoo-config')}"},
        "versions": VERSIONS,
        "presets": {name: {k: _fmt(v) for k, v in p.items()} for name, p in overlay.get("presets", {}).items()},
        "options": options,
    }


def main(check):
    data = build_data()
    payload = json.dumps(data, separators=(",", ":"))
    for path in PAGES:
        head, old, tail = BLOCK.split(path.read_text(), maxsplit=1)
        if {**json.loads(old), "source": data["source"]} != data:
            print(f"{'stale' if check else 'updated'}: {path.relative_to(ROOT)}")
            if check:
                sys.exit("run `make tools-data` to refresh")
            path.write_text(head + payload + tail)


if __name__ == "__main__":
    main("--check" in sys.argv[1:])
