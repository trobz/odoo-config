"""Schema loading and config resolution for odoo-config."""

import configparser
import os
import re
import shlex
import subprocess
import sys
from importlib.resources import files

import typer

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[import-unresolved]


def _read_toml(name):
    return tomllib.loads(files("odoo_config").joinpath(name).read_text())


def _merge(core, ov_opts):
    """Layer the trobz overlay on top of the odoo-mined standard (overlay wins).

    Overlay options come first (curated order), then any mined-only options. A
    pinned overlay default forces that value for every version, so it drops the
    mined per-version `by_version`; bounds and `by_version` are inherited from
    the mined standard only where the overlay stays silent.
    """
    options = {key: dict(ov_opts[key]) for key in ov_opts}
    for key in sorted(core):
        options.setdefault(key, {})

    for key, meta in options.items():
        c = core.get(key, {})
        overlay_pins_default = key in ov_opts and "default" in ov_opts[key]

        if "default" not in meta and c.get("default") is not None:
            meta["default"] = c["default"]

        if "help" not in meta and "help" in c:
            meta["help"] = c["help"]

        if not overlay_pins_default and "by_version" not in meta and "by_version" in c:
            meta["by_version"] = c["by_version"]

        if meta.pop("unbounded", False):
            meta.pop("min_version", None)
            meta.pop("max_version", None)
        else:
            for b in ("min_version", "max_version"):
                if b not in meta and b in c:
                    meta[b] = c[b]

    return options


def load_schema():
    """Return (options, presets): the odoo-mined standard merged with the overlay.

    `options.toml` is the vendored odoo schema; `overlay.toml` is the trobz
    customization layer, merged on top here at load time (not baked in).
    """
    core = _read_toml("options.toml")["options"]
    overlay = _read_toml("overlay.toml")
    return _merge(core, overlay["options"]), overlay.get("presets", {})


def canon(value):
    """Normalise a value for comparison: bool casing and typed/string form.

    File values are strings (configparser) while built defaults are typed, and
    odoo parses booleans case-insensitively, so "5432" == 5432 == 5432.0 and
    "False" == False == "false".
    """
    s = str(value).strip()
    return s.lower() if s.lower() in ("true", "false") else s


def overlay_overrides():
    """Option keys whose effective default the trobz overlay changes or adds.

    An option is flagged when it is absent from odoo's mined standard (a pure
    trobz addition) or its merged default differs from odoo's. Useful to mark
    non-stock defaults in a comparison.
    """
    core = _read_toml("options.toml")["options"]
    merged = _merge(core, _read_toml("overlay.toml")["options"])
    return {
        key
        for key, meta in merged.items()
        if key not in core or canon(default_for(meta, None)) != canon(default_for(core[key], None))
    }


def _vnum(version):
    """Parse a leading numeric Odoo version (e.g. '19.0', 'saas~16.1') to float."""
    if not version:
        return None

    m = re.search(r"(\d+(?:\.\d+)?)", str(version))
    return float(m.group(1)) if m else None


def valid_for_version(meta, version):
    """Whether an option applies to the given version (no filtering if version is None)."""
    v = _vnum(version)
    if v is None:
        return True

    if "min_version" in meta and v < _vnum(meta["min_version"]):
        return False

    return not ("max_version" in meta and v > _vnum(meta["max_version"]))


class _CaseSensitiveParser(configparser.ConfigParser):
    """ConfigParser that preserves option-name case (Odoo keys stay as written)."""

    def optionxform(self, optionstr: str) -> str:
        return optionstr


def read_remote(path):
    """Read a remote odoo.conf file from a <machine>:<path> pattern."""
    machine, file = path.split(":")
    args = ["ssh", machine, "cat", shlex.quote(file)]
    result = subprocess.run(  # noqa: S603
        args,
        shell=False,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        err = (result.stderr or "").strip()
        msg = f"Command failed (exit {result.returncode}): {path}"
        if err:
            msg = f"{msg}: {err}"
        raise typer.BadParameter(msg)
    return result.stdout


def read_conf(path):
    """Parse an odoo.conf into (flat values, key->section map) across all sections.

    Keys form a single namespace. Odoo's sections never share key names
    (`[options]` is flat, `[ir.config_parameter]` is dotted), so this is safe.
    """
    # flat key namespace; a key duplicated across sections collapses
    # (last wins). Re-key by (section, key) if Odoo ever shares a name.
    cp = _CaseSensitiveParser()
    if ":" in str(path):
        content = read_remote(path)
        cp.read_string(content)
    else:
        cp.read(path)

    values, sections = {}, {}
    for section in cp.sections():
        for key, value in cp[section].items():
            values[key] = value
            sections[key] = section

    return values, sections


def collect_env(schema, prefix):
    """Read known option values from the environment, optionally behind a prefix."""
    out = {}
    for key in schema:
        name = (f"{prefix}_{key}" if prefix else key).upper()
        if name in os.environ:
            out[key] = os.environ[name]

    return out


def default_for(meta, version):
    """The option's default for a version, honouring per-version overrides."""
    by_version = meta.get("by_version")
    if by_version:
        v = _vnum(version)
        chosen = None
        for ver in sorted(by_version, key=_vnum):
            if v is None or _vnum(ver) <= v:
                chosen = ver
        return by_version[chosen if chosen is not None else min(by_version, key=_vnum)]

    return meta.get("default", "")


def build(schema, version, fmt, given):
    """Resolve the option map to emit for a given output format.

    bare     -> only explicitly given keys
    explicit -> given keys plus all mandatory keys (filled from defaults)
    all      -> every option valid for the version
    """
    out = {}
    for key, meta in schema.items():
        if not valid_for_version(meta, version):
            continue

        if key in given:
            out[key] = given[key]
        elif fmt == "bare" or (fmt == "explicit" and not meta.get("mandatory")):
            continue
        else:
            out[key] = default_for(meta, version)

    for key, value in given.items():
        # keep unknown given keys (no schema), but not in-schema keys invalid here
        if key not in out and valid_for_version(schema.get(key, {}), version):
            out[key] = value

    return out


def _fmt(value):
    if isinstance(value, bool):
        return "True" if value else "False"

    return str(value)


def render(built, schema, given, secmap=None):
    """Render a resolved option map back to odoo.conf text, grouped by section."""
    secmap = secmap or {}
    grouped = {"options": []}
    for key, value in built.items():
        section = schema.get(key, {}).get("section") or secmap.get(key, "options")
        grouped.setdefault(section, []).append((key, value))

    lines = []
    for section, items in grouped.items():
        if lines:
            lines.append("")

        lines.append(f"[{section}]")
        for key, value in items:
            meta = schema.get(key, {})
            if meta.get("comment"):
                lines.append(f"; {meta['comment']}")

            line = f"{key} = {_fmt(value)}"
            if meta.get("commented") and key not in given:
                line = "; " + line

            lines.append(line)

    return "\n".join(lines) + "\n"


def drop_defaults(values, schema, version):
    """Drop keys whose value equals odoo's stock default for the version (compact).

    Keys invalid for the version are dropped — they don't exist in it, so no
    value is meaningful (matches `clean`/`expand`, which also honour validity).
    Keys the trobz overlay re-defaults or adds are kept: their default is not
    odoo's, so dropping them would silently fall back to odoo's stock value.
    Unknown keys (absent from the schema) are kept — no default to compare.
    """
    overridden = overlay_overrides()
    out = {}
    for key, value in values.items():
        meta = schema.get(key)
        if meta is not None and not valid_for_version(meta, version):
            continue

        if meta is not None and key not in overridden and canon(value) == canon(default_for(meta, version)):
            continue

        out[key] = value

    return out


def drop_outdated(values, schema, version):
    """Drop keys unknown to the schema or invalid for the version (clean)."""
    return {key: value for key, value in values.items() if key in schema and valid_for_version(schema[key], version)}


def explain_rows(values, schema, version):
    """(key, value, help, default) for each key present in `values`.

    Help is odoo's option description from the vendored snapshot (options.toml);
    an overlay `comment`, when present, overrides it as a trobz-specific note.
    With a version, in-schema keys invalid for it are dropped; without one
    (version None) every row is shown — valid_for_version passes everything.
    """
    rows = []
    for key, value in values.items():
        meta = schema.get(key, {})
        if meta and not valid_for_version(meta, version):
            continue

        help_text = meta.get("comment") or meta.get("help") or ""
        default = default_for(meta, version) if meta else ""
        rows.append((key, value, help_text, default))

    return rows


def resolve_given(presets, preset, sources, env, overrides):
    """Merge value sources by precedence: preset < files < env < overrides."""
    given = {}
    if preset:
        for name in str(preset).split(","):
            given.update(presets.get(name.strip(), {}))

    for source in sources:
        given.update(source)

    given.update(env)
    given.update(overrides)
    return given
