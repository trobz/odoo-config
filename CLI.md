# `odoo-config`

odoo-config: generate, compare and update Odoo config files per version.

**Usage**:

```console
$ odoo-config [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--install-completion`: Install completion for the current shell.
* `--show-completion`: Show completion for the current shell, to copy it or customize the installation.
* `--help`: Show this message and exit.

**Commands**:

* `create`: Create a new config file for the target...
* `update`: Update a config file in place from the...
* `compare`: Show a comparison table of values across...

## `odoo-config create`

Create a new config file for the target version.

**Usage**:

```console
$ odoo-config create [OPTIONS]
```

**Options**:

* `--version TEXT`: Target Odoo version, e.g. 19.0  [required]
* `-c, --config PATH`: [default: odoo.conf]
* `--preset TEXT`
* `--from TEXT`: Source config glob(s); additive
* `--from-env`
* `--env-prefix TEXT`
* `--output-format TEXT`: [default: explicit]
* `--help`: Show this message and exit.

## `odoo-config update`

Update a config file in place from the given values, preserving existing keys.

**Usage**:

```console
$ odoo-config update [OPTIONS]
```

**Options**:

* `-c, --config PATH`: [default: odoo.conf]
* `--version TEXT`
* `--preset TEXT`
* `--from-env`
* `--env-prefix TEXT`
* `--output-format TEXT`: [default: bare]
* `--help`: Show this message and exit.

## `odoo-config compare`

Show a comparison table of values across files, versions and/or presets.

File columns show the config as written; version columns show that version&#x27;s
full defaults (with any preset overlaid). A `-` cell means the key is absent
from that column.

Only rows that differ between columns are shown by default (so version
columns surface options introduced or removed between versions); pass
`--all` to list every option. Differing rows are highlighted, and options
whose default the trobz overlay overrides (differ from odoo) are marked `*`.

**Usage**:

```console
$ odoo-config compare [OPTIONS] [FILES]...
```

**Arguments**:

* `[FILES]...`

**Options**:

* `--version TEXT`: Version(s), comma-separated
* `--preset TEXT`: Preset(s), comma-separated
* `-a, --all`: Show every option, not just differing rows
* `--help`: Show this message and exit.
