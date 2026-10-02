---
icon: lucide/rocket
description: Install odoo-config and generate your first Odoo config file.
tags:
  - installation
  - quickstart
---

# Getting Started

## Installation

```bash
uv tool install odoo-config
odoo-config --version
```

Or with pip:

```bash
pip install odoo-config
```

## Quick example

```bash
# Generate a production config for Odoo 17.0
odoo-config create --version 17.0 --preset production

# See what changed between two versions
odoo-config compare --version 16.0,17.0
```

Continue to [Config](config.md) for the full reference.

## Schema

Two files shipped with the package drive everything:

- **Options**: every key Odoo accepts across versions 13.0 to 20.0,
  with types, defaults, and version availability.
- **Overlay**: the Trobz-specific layer of preset definitions,
  per-version tweaks, and mandatory key baselines (e.g. `production`).

You rarely need to read them directly, but they explain why a key
appears, disappears, or has a different default across versions.
See [Schema](reference/schema.md) for links to both files.
