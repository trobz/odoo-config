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
* `compact`: Remove options equal to odoo&#x27;s native...
* `expand`: Add every option valid for the version,...
* `clean`: Remove options unknown to the schema or...
* `explain`: Show each option&#x27;s value, help and default.

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
* `--instance-dir PATH`: Instance home directory; derives data_dir, logfile and sentry_odoo_dir (lowest priority).
* `--from TEXT`: Source config glob(s); additive
* `--from-env`
* `--env-prefix TEXT`
* `--output-format TEXT`: bare = only given keys; explicit = given + mandatory keys; all = every option valid for the version (optional ones commented).  [default: explicit]
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
* `--instance-dir PATH`: Instance home directory; derives data_dir, logfile and sentry_odoo_dir (lowest priority).
* `--from-env`
* `--env-prefix TEXT`
* `--output-format TEXT`: bare = only given keys; explicit = given + mandatory keys; all = every option valid for the version (optional ones commented).  [default: bare]
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

## `odoo-config compact`

Remove options equal to odoo&#x27;s native default (trobz-overlay values kept), or invalid for the version.

**Usage**:

```console
$ odoo-config compact [OPTIONS] [CONFIG]
```

**Arguments**:

* `[CONFIG]`: Config file to transform  [default: odoo.conf]

**Options**:

* `--version TEXT`: Odoo version for defaults/validity; newest if omitted
* `--diff`: Show only the keys the action adds/removes, as a table, not the full config
* `-i, --inplace`: Write the result back to the input file
* `--help`: Show this message and exit.

## `odoo-config expand`

Add every option valid for the version, keeping existing values.

**Usage**:

```console
$ odoo-config expand [OPTIONS] [CONFIG]
```

**Arguments**:

* `[CONFIG]`: Config file to transform  [default: odoo.conf]

**Options**:

* `--version TEXT`: Odoo version for defaults/validity; newest if omitted
* `--diff`: Show only the keys the action adds/removes, as a table, not the full config
* `-i, --inplace`: Write the result back to the input file
* `--help`: Show this message and exit.

## `odoo-config clean`

Remove options unknown to the schema or invalid for the version.

**Usage**:

```console
$ odoo-config clean [OPTIONS] [CONFIG]
```

**Arguments**:

* `[CONFIG]`: Config file to transform  [default: odoo.conf]

**Options**:

* `--version TEXT`: Odoo version for defaults/validity; newest if omitted
* `--diff`: Show only the keys the action adds/removes, as a table, not the full config
* `-i, --inplace`: Write the result back to the input file
* `--help`: Show this message and exit.

## `odoo-config explain`

Show each option&#x27;s value, help and default.

**Usage**:

```console
$ odoo-config explain [OPTIONS] [CONFIG]
```

**Arguments**:

* `[CONFIG]`: Config file to transform  [default: odoo.conf]

**Options**:

* `--version TEXT`: Odoo version for defaults/validity; newest if omitted
* `--help`: Show this message and exit.
