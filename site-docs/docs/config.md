---
icon: lucide/file-cog
description: Generate, update, and compare Odoo config files.
---

# Config

## Create

Generate a new config file for a target Odoo version.

```bash
# Minimal: mandatory keys only
odoo-config create --version 17.0

# Production preset (suppresses ribbon, no cron until go live)
odoo-config create --version 17.0 --preset production

# Derive data_dir / logfile / sentry_odoo_dir from instance home
odoo-config create --version 17.0 \
  --instance-dir /opt/odoo/myinstance \
  --preset production

# Ad-hoc overrides: any schema key as --<key>=<value>
odoo-config create --version 17.0 --preset production \
  --max-cron-threads=2 \
  --http-port=8072 \
  --log-level=info

# Full annotated output: every key, optional ones commented
odoo-config create --version 17.0 --output-format all

# Include Enterprise-edition-only options (e.g. database.expiration_*)
odoo-config create --version 17.0 --enterprise
```

Full option reference: [CLI reference](CLI.md#odoo-config-create).

## Update

Update an existing config file in place, preserving keys already set.

```bash
# Overlay a preset onto an existing config
odoo-config update --version 17.0 --preset production

# Merge values from another file
odoo-config update --version 17.0 --from base.conf

# Apply values from environment variables
odoo-config update --version 17.0 --from-env --env-prefix ODOO
```

Full option reference: [CLI reference](CLI.md#odoo-config-update).

## Compare

Show a diff table of values across files, versions, and/or presets.
Only differing rows are shown by default; rows marked `*` are
overridden by the trobz overlay.

```bash
# What changed between two Odoo versions
odoo-config compare --version 16.0,17.0

# How a live config differs from version defaults
odoo-config compare --version 17.0 myinstance.conf

# Show every option, not just differing ones
odoo-config compare --version 16.0,17.0 --all

# Compare a file against a preset
odoo-config compare --preset production myinstance.conf
```

Full option reference: [CLI reference](CLI.md#odoo-config-compare).

## Override precedence

Applies to both `create` and `update`. When the same key appears in
multiple sources, the last one wins:

```
lowest                                                      highest
  │                                                            │
  ▼                                                            ▼
preset ──► --from files ──► --from-env / --env-prefix ──► --<key>=<value>
```

Any option in the [schema](reference/schema.md) can be passed as a
flag; dashes map to underscores. For example:

| Flag | Schema key |
|------|-----------|
| `--max-cron-threads=2` | `max_cron_threads` |
| `--http-port=8072` | `http_port` |
| `--log-level=info` | `log_level` |
| `--list-db=false` | `list_db` |
| `--proxy-mode=true` | `proxy_mode` |
