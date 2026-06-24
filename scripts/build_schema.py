"""Generate odoo_config/options.toml: the odoo-mined option standard.

Mines `tools/config.py` across Odoo versions for config-file options (names,
defaults, version availability) and writes them to options.toml. Pure AST
parse, no Odoo execution. This file is a vendored snapshot of odoo's schema —
regenerate it only when the supported version set changes (a new odoo release).

Trobz customization lives in overlay.toml and is merged on top at runtime
(see schema.load_schema); the overlay is *not* an input to this generator.

The odoo root is passed in (--odoo or the ODOO_PATH env var) but its layout is
fixed: one numeric version directory per supported version, each holding
`odoo/tools/config.py`:

    <odoo-root>/
    ├── 13.0/odoo/tools/config.py
    ├── 14.0/odoo/tools/config.py
    └── ...  (through 19.0)

Usage: python scripts/build_schema.py [--odoo PATH] [--versions 13.0,14.0,...]
"""

import argparse
import ast
import json
import operator
import os
import re
import sys
from pathlib import Path

_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Pow: operator.pow,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
}

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "odoo_config" / "options.toml"

DEFAULT_VERSIONS = ["13.0", "14.0", "15.0", "16.0", "17.0", "18.0", "19.0"]

# CLI-only / operational dests Odoo never persists as config values.
SKIP = {
    "version",
    "language",
    "translate_out",
    "translate_in",
    "overwrite_existing_translations",
    "init",
    "update",
    "demo",
    "config",
    "save",
    "reinit",
    "test_file",
    "test_tags",
    "test_enable",
    "screencasts",
    "screenshots",
    "import_partial",
    "stop_after_init",
    "dev_mode",
    "shell_interface",
    "load_language",
    "pre_upgrade_scripts",
    "publisher_warranty_url",
    "root_path",
}

_SENTINEL = object()


def _arith(node):
    """Evaluate a numeric literal expression (e.g. 10 * 1024 * 1024) without eval."""
    if isinstance(node, ast.Constant):
        return node.value

    if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
        return _BINOPS[type(node.op)](_arith(node.left), _arith(node.right))

    raise ValueError(node)


def _literal(node):
    try:
        return ast.literal_eval(node)

    except Exception:
        try:
            return _arith(node)
        except Exception:
            return _SENTINEL


def _blacklist(tree):
    out = set()

    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and any(
            isinstance(t, ast.Attribute) and t.attr == "blacklist_for_save" for t in n.targets
        ):
            out |= {e.value for e in ast.walk(n.value) if isinstance(e, ast.Constant) and isinstance(e.value, str)}

    return out


def _options_dict(tree):
    """Keys of `self.options = {...}` — config values not exposed on the CLI."""
    for n in ast.walk(tree):
        if (
            isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Attribute) and t.attr == "options" for t in n.targets)
            and isinstance(n.value, ast.Dict)
        ):
            pairs = zip(n.value.keys, n.value.values, strict=True)

            return {k.value: _literal(v) for k, v in pairs if isinstance(k, ast.Constant)}

    return {}


def _dest_from_args(call):
    longs = [a.value for a in call.args if isinstance(a, ast.Constant) and str(a.value).startswith("--")]
    return longs[-1].lstrip("-").replace("-", "_") if longs else None


def extract(path):
    """Return ({dest: default-or-SENTINEL}, {dest: help}) for one config.py.

    Help is captured best-effort: only plain string literals (whitespace
    collapsed); f-strings / concatenations are skipped.
    """
    tree = ast.parse(path.read_text())
    skip = SKIP | _blacklist(tree)
    opts = {k: v for k, v in _options_dict(tree).items() if k not in skip}
    helps = {}

    for n in ast.walk(tree):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "add_option"):
            continue

        inner = [n, *(a for a in n.args if isinstance(a, ast.Call))]
        kw = {}
        for arg in inner:
            kw.update({k.arg: k.value for k in arg.keywords if k.arg})

        dest = (
            _literal(kw["dest"])
            if "dest" in kw
            else next((_dest_from_args(c) for c in inner if _dest_from_args(c)), None)
        )
        if not dest or dest in skip or dest is _SENTINEL:
            continue
        if "file_exportable" in kw and _literal(kw["file_exportable"]) is False:
            continue
        action = _literal(kw["action"]) if "action" in kw else None
        if action in ("store_true", "store_false") and "my_default" not in kw:
            continue

        if "help" in kw and isinstance(h := _literal(kw["help"]), str):
            helps[dest] = " ".join(h.split())

        if "my_default" in kw:
            opts[dest] = _literal(kw["my_default"])
        elif "default" in kw:
            opts[dest] = _literal(kw["default"])
        else:
            opts.setdefault(dest, _SENTINEL)

    return opts, helps


def _norm(v):
    """Collapse empty-equivalent defaults so False/''/[] aren't treated as drift."""
    return "" if v is None or v is False or v == "" or v == [] else v


def core_schema(odoo, versions):
    """Merge per-version extractions into {dest: {default, help?, min/max_version, by_version?}}."""
    extracted = {v: extract(odoo / v / "odoo/tools/config.py") for v in versions}
    by_ver = {v: opts for v, (opts, _h) in extracted.items()}
    helps = {v: h for v, (_o, h) in extracted.items()}
    out = {}
    for dest in set().union(*by_ver.values()):
        present = [v for v in versions if dest in by_ver[v]]
        statics = {v: by_ver[v][dest] for v in present if by_ver[v][dest] not in (_SENTINEL, None)}
        meta = {}
        if statics:
            default = statics[present[-1] if present[-1] in statics else max(statics)]
            # Odoo stores some defaults as Python lists (addons_path, log_handler);
            # config files write them comma-joined, not as `[...]` repr.
            meta["default"] = ",".join(map(str, default)) if isinstance(default, list) else default

        # Help from the newest version that documents it (descriptions evolve).
        for v in reversed(versions):
            if dest in helps[v]:
                meta["help"] = helps[v][dest]
                break

        if versions[0] not in present:
            meta["min_version"] = min(present)
        if versions[-1] not in present:
            meta["max_version"] = max(present)

        # Per-version defaults only when they genuinely differ (ignoring empties).
        if len({repr(_norm(d)) for d in statics.values()}) > 1:
            meta["by_version"] = statics
        out[dest] = meta

    return out


def _toml_value(v):
    if isinstance(v, bool):
        return "true" if v else "false"

    if isinstance(v, int | float):
        return str(v)

    return json.dumps(str(v))


def _toml_key(k):
    return k if re.fullmatch(r"[A-Za-z0-9_-]+", k) else json.dumps(k)


def emit(options):
    lines = [
        "# GENERATED by scripts/build_schema.py — do not edit by hand.",
        "# Vendored snapshot of odoo's option schema; regenerate only when the",
        "# supported odoo version set changes. Trobz customization is in",
        "# overlay.toml, merged on top at runtime (schema.load_schema).",
        "",
    ]

    for key in sorted(options):
        meta = options[key]
        lines.append(f"[options.{_toml_key(key)}]")
        for field in ("default", "help", "min_version", "max_version"):
            if field in meta:
                lines.append(f"{field} = {_toml_value(meta[field])}")
        lines.append("")

        if meta.get("by_version"):
            lines.append(f"[options.{_toml_key(key)}.by_version]")
            for ver, val in meta["by_version"].items():
                lines.append(f"{_toml_key(ver)} = {_toml_value(val)}")
            lines.append("")

    OUT.write_text("\n".join(lines).rstrip() + "\n")


def build(odoo, versions):
    missing = [v for v in versions if not (odoo / v / "odoo/tools/config.py").is_file()]
    if missing:
        print(f"error: missing {odoo}/<version>/odoo/tools/config.py for: {', '.join(missing)}", file=sys.stderr)
        raise SystemExit(1)

    core = core_schema(odoo, versions)
    emit(core)
    print(f"Wrote {OUT.relative_to(ROOT)}: {len(core)} options from {odoo}")


def _parse_args():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--odoo",
        default=os.environ.get("ODOO_PATH"),
        type=Path,
        help="Odoo root holding one <version>/odoo/tools/config.py per version (or set ODOO_PATH).",
    )
    ap.add_argument(
        "--versions",
        default=",".join(DEFAULT_VERSIONS),
        help=f"Comma-separated versions to mine (default: {','.join(DEFAULT_VERSIONS)}).",
    )
    args = ap.parse_args()
    if args.odoo is None:
        ap.error("no odoo path: pass --odoo PATH or set ODOO_PATH")

    return args.odoo, [v.strip() for v in args.versions.split(",") if v.strip()]


if __name__ == "__main__":
    build(*_parse_args())
