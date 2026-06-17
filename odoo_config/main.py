"""odoo-config: generate, compare and update Odoo config files per version."""

import glob
from pathlib import Path
from typing import Annotated

import typer

from .schema import (
    build,
    canon,
    collect_env,
    load_schema,
    overlay_overrides,
    read_conf,
    render,
    resolve_given,
)

app = typer.Typer(help=__doc__, no_args_is_help=True)

_EXTRA = {"allow_extra_args": True, "ignore_unknown_options": True}

# Flags shared by create and update.
ConfigOpt = Annotated[Path, typer.Option("-c", "--config")]
PresetOpt = Annotated[str | None, typer.Option("--preset")]
FromEnvOpt = Annotated[bool, typer.Option("--from-env")]
EnvPrefixOpt = Annotated[str | None, typer.Option("--env-prefix")]
FormatOpt = Annotated[str, typer.Option("--output-format")]


def parse_overrides(args):
    """Turn extra `--key=value` / `--key value` CLI args into an option dict."""
    out = {}
    i = 0
    while i < len(args):
        a = args[i]
        if not a.startswith("--"):
            i += 1
            continue

        body = a[2:]
        if "=" in body:
            key, value = body.split("=", 1)
            i += 1
        elif i + 1 < len(args) and not args[i + 1].startswith("--"):
            key, value = body, args[i + 1]
            i += 2
        else:
            key, value = body, "True"
            i += 1

        out[key.replace("-", "_")] = value

    return out


def expand_from(patterns):
    """Read and merge config files matched by the given globs, in order."""
    values, secmap = {}, {}
    for pattern in patterns or []:
        for path in sorted(glob.glob(pattern)):
            vals, sec = read_conf(path)
            values.update(vals)
            secmap.update(sec)

    return values, secmap


def _generate(ctx, sources, secmap):
    """Merge value sources, build the config and write it to disk.

    Shared options are read from `ctx.params` (typer-bound flags) and `ctx.args`
    (the `--*` overrides), so new flags need wiring only into the command itself.
    """
    p = ctx.params
    schema, presets = load_schema()
    env = collect_env(schema, p["env_prefix"]) if p["from_env"] else {}
    overrides = parse_overrides(ctx.args)

    given = resolve_given(presets, p["preset"], [sources], env, overrides)
    built = build(schema, p["version"], p["output_format"], given)
    # ctx.params holds click's pre-conversion values, so config is still a str.
    Path(p["config"]).write_text(render(built, schema, given, secmap))


@app.command(context_settings=_EXTRA)
def create(
    ctx: typer.Context,
    version: Annotated[str, typer.Option("--version", help="Target Odoo version, e.g. 19.0")],
    config: ConfigOpt = Path("odoo.conf"),
    preset: PresetOpt = None,
    from_: Annotated[list[str] | None, typer.Option("--from", help="Source config glob(s); additive")] = None,
    from_env: FromEnvOpt = False,
    env_prefix: EnvPrefixOpt = None,
    output_format: FormatOpt = "explicit",
):
    """Create a new config file for the target version."""
    sources, secmap = expand_from(from_)
    _generate(ctx, sources, secmap)
    typer.echo(f"Wrote {config}")


@app.command(context_settings=_EXTRA)
def update(
    ctx: typer.Context,
    config: ConfigOpt = Path("odoo.conf"),
    version: Annotated[str | None, typer.Option("--version")] = None,
    preset: PresetOpt = None,
    from_env: FromEnvOpt = False,
    env_prefix: EnvPrefixOpt = None,
    output_format: FormatOpt = "bare",
):
    """Update a config file in place from the given values, preserving existing keys."""
    existing, secmap = read_conf(config)
    _generate(ctx, existing, secmap)
    typer.echo(f"Updated {config}")


def _compare_columns(schema, presets, file_columns, versions, preset_names):
    """Assemble the named value columns to compare.

    Files contribute their values as written; each `--version` contributes a
    column of all options valid for that version (defaults), overlaid with each
    `--preset` when given (labelled `version+preset`).
    """
    columns = dict(file_columns)
    for v in versions:
        if preset_names:
            for name in preset_names:
                columns[f"{v}+{name}"] = build(schema, v, "all", presets.get(name, {}))
        else:
            columns[v] = build(schema, v, "all", {})

    if preset_names and not versions:
        for name in preset_names:
            columns[f"preset:{name}"] = dict(presets.get(name, {}))

    return columns


@app.command()
def compare(
    files: Annotated[list[Path] | None, typer.Argument()] = None,
    version: Annotated[str | None, typer.Option("--version", help="Version(s), comma-separated")] = None,
    preset: Annotated[str | None, typer.Option("--preset", help="Preset(s), comma-separated")] = None,
    all_: Annotated[bool, typer.Option("--all", "-a", help="Show every option, not just differing rows")] = False,
):
    """Show a comparison table of values across files, versions and/or presets.

    File columns show the config as written; version columns show that version's
    full defaults (with any preset overlaid). A `-` cell means the key is absent
    from that column.

    Only rows that differ between columns are shown by default (so version
    columns surface options introduced or removed between versions); pass
    `--all` to list every option. Differing rows are highlighted, and options
    whose default the trobz overlay overrides (differ from odoo) are marked `*`.
    """
    schema, presets = load_schema()
    versions = [v.strip() for v in version.split(",")] if version else []
    preset_names = [p.strip() for p in preset.split(",")] if preset else []

    missing = [str(p) for p in files or [] if not p.is_file()]
    if missing:
        raise typer.BadParameter(f"file(s) not found: {', '.join(missing)}")  # noqa: TRY003

    file_columns = {path.name: read_conf(path)[0] for path in files or []}

    columns = _compare_columns(schema, presets, file_columns, versions, preset_names)
    if not columns:
        raise typer.BadParameter("Give file(s), --version and/or --preset")  # noqa: TRY003

    _print_table(columns, file_names=file_columns.keys(), overrides=overlay_overrides(), show_all=all_)


_CELL_MAX = 60
_MISSING = object()


def _row_differs(columns, names, key, file_names):
    """True if the columns disagree on a key.

    Differing present values always count. A missing cell counts only between
    columns of the same kind (file vs file, or version vs version): a key absent
    from a sparse config file just means "use the default", but a key present in
    one version column and absent from another is a real add/remove.
    """
    if len({canon(columns[n][key]) for n in names if key in columns[n]}) > 1:
        return True

    dense = [n for n in names if n not in file_names]
    return any(len({key in columns[n] for n in group}) > 1 for group in (file_names, dense))


def _print_table(columns, file_names=(), overrides=frozenset(), show_all=False):
    from rich import box
    from rich.console import Console
    from rich.markup import escape
    from rich.table import Table

    names = list(columns)
    keys = sorted({k for col in columns.values() for k in col})

    table = Table(box=box.ROUNDED, show_header=True, header_style="bold cyan")
    table.add_column("option", style="bold", no_wrap=True)
    for n in names:
        table.add_column(n, justify="center", overflow="fold")

    shown = marked = 0
    for k in keys:
        differs = _row_differs(columns, names, k, set(file_names))
        if not show_all and not differs:
            continue

        cells = []
        for n in names:
            value = columns[n].get(k, _MISSING)
            if value is _MISSING:
                cells.append("[dim]-[/dim]")
                continue

            s = str(value)
            s = escape(s if len(s) <= _CELL_MAX else s[: _CELL_MAX - 1] + "…")
            cells.append(f"[yellow]{s}[/yellow]" if differs else s)

        label = f"[yellow]{escape(k)}[/yellow]" if differs else escape(k)
        if k in overrides:
            label += " [magenta]*[/magenta]"
            marked += 1

        table.add_row(label, *cells)
        shown += 1

    if not shown:
        typer.echo("No options to show." if show_all else "No differences.")
        return

    console = Console()
    console.print(table)
    if marked:
        console.print("\n[magenta]*[/magenta] = default overridden by the trobz overlay (differs from odoo)")


if __name__ == "__main__":
    app()
