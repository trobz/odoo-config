# odoo-config

A small CLI that generates an Odoo config file, adapted for the target Odoo
version. Replaces the hand-maintained `server.conf` template in remoteoi and is
meant to be called as a configuration step by
[deploy.py](https://github.com/trobz/deploy.py), with per-instance values coming
from `deploy.yml`.

## Local development

Standard template tooling (uv + make):

```bash
make install   # uv sync + pre-commit install
make check     # lock check + pre-commit + ty
make test      # pytest
```

Other tasks: regenerate the CLI reference with
`uv run typer odoo_config.main utils docs --name odoo-config --output CLI.md`,
and the schema with `uv run python scripts/build_schema.py` (see Schema below).

## Commands

- `create` — generate a new config for a target version.
- `compare` — show a value comparison table across files, versions or presets.
- `update` — update a config in place, preserving existing keys and sections.

The full flag reference is generated from the code — see [CLI.md](CLI.md) or
`odoo-config <command> --help`.

Beyond the documented flags, **any** `--<key>=<value>` overrides a single
option, e.g. `--max-cron-threads=0`; keys map to config options with dashes
turned into underscores.

## Output formats (`--output-format`)

- **bare** — only the keys that were given (preset / `--from` / env / overrides).
- **explicit** — given keys plus all mandatory keys (filled from defaults). Default.
- **all** — every option valid for the version; optional examples emitted
  commented. Reproduces the full `server.conf` for that version.

Merge precedence, low to high: preset → `--from` files → environment → `--*`
overrides.

## Schema

The schema is two files, merged at runtime by `schema.load_schema()`:

- **[`odoo_config/options.toml`](odoo_config/options.toml)** — the *odoo
  standard*: option set, defaults, version availability (`min`/`max_version`)
  and per-version default drift (`by_version`), mined from Odoo's
  `tools/config.py` across 13.0–19.0. It is **generated** (a vendored snapshot,
  like a lockfile) — do not edit by hand. Regenerate it only when the supported
  odoo version set changes:

  ```bash
  uv run python scripts/build_schema.py --odoo /path/to/odoo   # or set ODOO_PATH
  ```

  The odoo root is a parameter, but its layout is fixed: one numeric version
  directory per version, each holding `odoo/tools/config.py`. Limit the set with
  `--versions 17.0,18.0,19.0`.

- **[`odoo_config/overlay.toml`](odoo_config/overlay.toml)** — the *trobz layer*:
  customized defaults, comments, sections (`ir.config_parameter`, `queue_job`),
  presets, and non-core extras (`sentry_*`, legacy networking, etc.). Edit this
  freely; changes take effect immediately, **no regeneration needed**.

Overlay values win. A pinned overlay `default` forces that value on every
version (the mined `by_version` is dropped); to keep per-version trobz values,
add a `[options.<key>.by_version]` table in the overlay.
