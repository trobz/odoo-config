---
icon: lucide/database
description: Options and overlay schemas; keys, defaults, version ranges,
  and trobz overrides.
---

# Schema

## Options

All supported config keys across Odoo 13.0 to 20.0, with their types,
defaults, and version availability. Generated from Odoo's source, so
do not edit by hand.

[`options.toml` on GitHub](https://github.com/trobz/odoo-config/blob/main/odoo_config/options.toml)

## Overlay

Trobz-specific overrides layered on top of Odoo defaults: preset
definitions, per-version tweaks, and mandatory key baselines.

[`overlay.toml` on GitHub](https://github.com/trobz/odoo-config/blob/main/odoo_config/overlay.toml)

## Web tools

The [web tools](../web-tools/index.md) embed a snapshot of this schema.
After changing either toml above, run `make tools-data` to refresh it
(CI fails otherwise).
