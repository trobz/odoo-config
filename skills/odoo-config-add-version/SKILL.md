---
name: odoo-config-add-version
description: "Add an Odoo major version to odoo-config, either the next release above the supported range (e.g. 21.0) or the next older one below it (e.g. 11.0): regenerate options.toml from Odoo's tools/config.py, check the overlay, refresh the web tools, update the documented range, verify, and prepare the commit and PR. Use when asked to 'add Odoo 21.0 support to odoo-config', 'support Odoo 11.0 in odoo-config', 'support a new Odoo version in odoo-config', or 'regenerate the odoo-config schema for a new Odoo release'."
---

# odoo-config: Add an Odoo Version

Adds one Odoo major version to this repository, either right above the
supported range (**newer**) or right below it (**older**). The range is the
`versions` list in `odoo_config/options.toml`, never this file. Examples come
from adding 20.0 (newer) and 12.0 (older).

Each step says first what to do in both directions, then the parts marked
**newer** or **older**. Do only the parts for your direction.

## Terms

| Name | Meaning | 20.0 (newer) | 12.0 (older) |
|---|---|---|---|
| `N` | The version to add | 20.0 | 12.0 |
| `DIR` | `newer` or `older` | newer | older |
| `OLD_BOUND` | The range end that `N` extends: the old last version (newer) or the old first version (older) | 19.0 | 13.0 |
| `FIRST`, `LAST` | The range after the change | 13.0, 20.0 | 12.0, 20.0 |
| `W`, `ROOT` | The work directory, and the fetched sources inside it | | |

Step 0 computes these and saves them to `$W/env`. Your shell may not keep
variables between commands, so every later snippet starts by loading that
file.

## Rules

- `odoo_config/options.toml` is generated. Never edit it by hand; rerun
  `scripts/build_schema.py`.
- Change only what `N` needs.
- At each **Ask**, stop and let the user decide. Overlay values, the web
  tools' UI defaults (the versions the matrix compares, the builder's start
  version) and tests change only on their answer.
- Don't touch `CHANGELOG.md` or the package version: semantic-release owns
  them.
- Every change you report (commit, PR) names the exact version and its effect,
  checked in Odoo's source. Leave out changes with no effect on the generated
  config, such as help wording.
- Don't add tests pinned to the range ends (`versions[-1] == "21.0"`): they
  break at the next added version.
- Push and open the PR only when the user asks.
- Keep this skill version-agnostic: versions come from the repo, and concrete
  versions are examples only. If a step stops matching the repo, update this
  skill in the same PR.

## Step 0: Set up

Needs: a branch from `main`, the repo set up with `make install`
([uv](https://docs.astral.sh/uv/)), `git`, `curl`, a POSIX shell, and network
access to GitHub. Run every command from the repo root.

Set `N` on the first line, then run:

```sh
N=21.0                                     # the version to add
W=${TMPDIR:-/tmp}/odoo-config-add-version  # the work directory
rm -f "$W/env"
V=$(uv run python -c 'from odoo_config.schema import _read_toml; print(*_read_toml("options.toml")["versions"])' 2>/dev/null)
OLD_FIRST=${V%% *} OLD_LAST=${V##* } DIR= n=${N%%.*}
case " $V " in *" $N "*) SUPPORTED=yes ;; *) SUPPORTED= ;; esac
if [ -z "$V" ]; then
  echo "STOP: can't read options.toml; run make install"
elif [ -n "$SUPPORTED" ]; then
  echo "STOP: $N is already supported ($OLD_FIRST to $OLD_LAST)"
elif [ "$n" -eq $((${OLD_LAST%%.*} + 1)) ]; then
  DIR=newer OLD_BOUND=$OLD_LAST FIRST=$OLD_FIRST LAST=$N
elif [ "$n" -eq $((${OLD_FIRST%%.*} - 1)) ] && [ "$n" -ge 11 ]; then
  DIR=older OLD_BOUND=$OLD_FIRST FIRST=$N LAST=$OLD_LAST
else
  echo "STOP: $N must be right above or below $OLD_FIRST to $OLD_LAST, and 11.0 or later"
fi
if [ -n "$DIR" ]; then
  if git ls-remote --exit-code --heads https://github.com/odoo/odoo.git "$N" >/dev/null; then
    mkdir -p "$W"
    echo "N=$N DIR=$DIR OLD_BOUND=$OLD_BOUND FIRST=$FIRST LAST=$LAST W='$W' ROOT='$W/src'" > "$W/env"
    cat "$W/env"
  else
    echo "STOP: Odoo has no $N branch yet (never mine master)"
  fi
fi
```

If it prints `STOP`, stop and tell the user. The 11.0 floor comes from the
generator: 10.0's `config.py` is Python 2 and fails `ast.parse`, and 9.0 and
older keep it under `openerp/`.

## Step 1: Fetch config.py for every version

`scripts/build_schema.py` reads `<root>/<version>/odoo/tools/config.py` for
every version from `FIRST` to `LAST`. Download them fresh from GitHub:

```sh
. "${TMPDIR:-/tmp}/odoo-config-add-version/env"
rm -rf "$ROOT"
for major in $(seq "${FIRST%%.*}" "${LAST%%.*}"); do
  v="$major.0"
  mkdir -p "$ROOT/$v/odoo/tools"
  curl -fsSL -o "$ROOT/$v/odoo/tools/config.py" \
    "https://raw.githubusercontent.com/odoo/odoo/$v/odoo/tools/config.py" || echo "STOP: can't fetch $v"
done
```

Fetch every version, not only `N`: Odoo backports options to stable branches,
and an outdated copy gives wrong version bounds. The 20.0 run moved
`log_config` to 16.0+ (an Odoo backport) and `skip_auto_install` to 17.0+ (the
previous snapshot came from outdated checkouts). A local clone of odoo/odoo
works too: run `git fetch origin`, then use
`git show "origin/$v:odoo/tools/config.py"` in the same loop.

## Step 2: Regenerate options.toml

Edit `scripts/build_schema.py`:

- **newer:** append `N` to `DEFAULT_VERSIONS`, and set the docstring's
  `(through N)`.
- **older:** put `N` first in `DEFAULT_VERSIONS`, and start the docstring's
  example tree and its `--versions` usage line at `N`.

Regenerate, then read the diff:

```sh
. "${TMPDIR:-/tmp}/odoo-config-add-version/env"
uv run python scripts/build_schema.py --odoo "$ROOT"
git diff odoo_config/options.toml
```

Classify each change with the table for your direction.

**newer:**

| Diff | Meaning | 20.0 example |
|---|---|---|
| New `[options.X]` with `min_version = "N"` | New option | `db_system`, `gevent_workers`, `unsafe_policy` |
| New `max_version = "OLD_BOUND"` | Option removed in `N` | none |
| `by_version` gains `"N"`, value differs from `OLD_BOUND` | Default changed; the top-level `default` changes with it | `http_interface`: `0.0.0.0` → `127.0.0.1` |
| `by_version` gains `"N"`, same value as `OLD_BOUND` | No change | `limit_request` |
| Bounds changed on other versions, or a new option whose bounds don't touch `N` | Correction of older data (an Odoo backport, or a stale snapshot); report it separately | `log_config` (new, from 16.0), `skip_auto_install` (17.0+, was 18.0 only) |
| `help` text only | Wording, no effect; don't report it | — |

**older:**

| Diff | Meaning | 12.0 example |
|---|---|---|
| New `[options.X]` with `max_version = "N"` | Option removed after `N` | `logrotate` |
| New `min_version = "OLD_BOUND"` | Option added in `OLD_BOUND`, absent in `N` | `upgrade_path` |
| `by_version` gains `"N"`, value differs from `OLD_BOUND` | `N` has its own default; the top-level `default` stays | none |
| `by_version` gains `"N"`, same value as `OLD_BOUND` | No change | `limit_request` |
| Bounds changed on other versions | Correction of older data; report it separately | none |
| `help` text only | Wording, no effect; don't report it | — |

Then check:

- Every new option is a config-file option. The generator skips options Odoo
  marks `file_exportable=False` and the CLI-only names in `SKIP`. **Ask**
  before adding a CLI-only option that slipped through to `SKIP` (adding 11.0
  would surface `test_commit` and `test_report_directory`).
- Each change you report is in the source, e.g.
  `grep -n -- '--db-system' "$ROOT/$N/odoo/tools/config.py"` (load the env
  file first).

## Step 3: Check the overlay

`odoo_config/overlay.toml` is the Trobz layer, merged over `options.toml` at
runtime (`schema.load_schema`). Overlay values win: a pinned `default` applies
to every version and drops the mined `by_version`, and a hand-set
`min_version` / `max_version` replaces the mined one.

Update the range in the overlay's comment (`present FIRST-LAST`, majors only).
**older:** also change "pre-`OLD_BOUND` legacy options" to `FIRST`.

Then list the overlay entries that `N` affects:

```sh
. "${TMPDIR:-/tmp}/odoo-config-add-version/env"
uv run python - "$N" "$OLD_BOUND" <<'EOF'
import sys
from odoo_config.schema import _read_toml
n, old = sys.argv[1:]
mined = _read_toml("options.toml")["options"]
for key, ov in _read_toml("overlay.toml")["options"].items():
    m = mined.get(key)
    if m is None:
        continue
    by = m.get("by_version", {})
    if "default" in ov and n in by and old in by and by[n] != by[old]:
        print(f"pinned default: {key} = {ov['default']!r}; Odoo {old}: {by[old]!r}, {n}: {by[n]!r}")
    for bound in ("min_version", "max_version"):
        if bound in ov and ov[bound] != m.get(bound):
            print(f"hand-set bound: {key} {bound} = {ov[bound]}; mined: {m.get(bound, 'none')}")
EOF
```

**Ask** about each line it prints:

- **pinned default:** keep the pin, or give `N` its own value with an
  `[options.<key>.by_version]` table in the overlay. 20.0: `http_interface` is
  pinned to `""`, which Odoo reads as `0.0.0.0` up to 19.0 and as `127.0.0.1`
  on 20.0. The pin was kept.
- **hand-set bound:** propose dropping the overlay bound so the mined one
  applies. 12.0: `logrotate` had `max_version = "11.0"`, but Odoo 12.0 has
  `--logrotate`. The bound was dropped, giving the mined `max_version = "12.0"`.

## Step 4: Refresh the web tools

The three pages in `site-docs/docs/web-tools/` embed a JSON copy of the schema.
Refresh it, then list the lines to edit by hand:

```sh
. "${TMPDIR:-/tmp}/odoo-config-add-version/env"
make tools-data
grep -n -E 'repeat\(|data-versions>' site-docs/docs/web-tools/odoo-option-lookup/index.html
git grep -n -F "$OLD_BOUND" -- 'site-docs/docs/web-tools/*/index.html' | grep -v 'id="schema-data"'
```

- The two `repeat(` counts (`.dots`, `.vgrid`) and the `<b data-versions>`
  count go up by one (20.0: 7 → 8). Without this, the new version wraps to a
  new grid row.
- `<span data-vrange>` in the lookup and matrix pages becomes `FIRST to LAST`.
  The pages' JS overwrites these fallbacks at load; keep the HTML in sync
  anyway.
- **older:** the other `OLD_BOUND` hits are the legacy wording ("Only valid
  before Odoo 13.0", "Legacy (before 13.0)", "dropped for 13.0+", ...). Change
  each to `N`.
- Leave the versions in `RENAMES` as they are. **Ask** before adding an entry:
  only when `N` replaces an option, so that one option ends next to `N` and its
  successor starts at `N`. 20.0 and 12.0 had none.

## Step 5: Update the documented range

```sh
. "${TMPDIR:-/tmp}/odoo-config-add-version/env"
git grep -n -w -F "$OLD_BOUND" -- . ':!odoo_config/options.toml' ':!site-docs/docs/web-tools/*/index.html' \
  ':!tests' ':!skills' ':!CHANGELOG.md' ':!uv.lock'
```

Skip the false hits: dependency pins (`pre-commit>=2.20.0`,
`gh-action-pypi-publish@v1.13.0`) and the sample version in the `schema.py`
docstring. `scripts/build_schema.py` and `odoo_config/overlay.toml` were done
in steps 2 and 3.

- The range becomes `FIRST–LAST` in `README.md`, and `FIRST to LAST` in
  `site-docs/docs/getting-started.md`, `site-docs/docs/reference/schema.md` and
  `site-docs/docs/web-tools/index.md`.
- **newer:** append `N` to the README's `--versions` example, keeping the
  others so the diff is a pure addition. Set the `--version` help in
  `odoo_config/main.py` to `e.g. N`, then regenerate `CLI.md` with
  `uv run typer odoo_config.main utils docs --name odoo-config --output CLI.md`.
- **older:** leave the README example, `odoo_config/main.py` and `CLI.md`
  alone: they show the newest versions.

Leave `tests/` alone: the versions there are samples, not range ends.

## Step 6: Verify

```sh
. "${TMPDIR:-/tmp}/odoo-config-add-version/env"
make test && make check && make tools-data-check
uv run odoo-config create --version "$OLD_BOUND" --output-format all -c "$W/old.conf"
uv run odoo-config create --version "$N" --output-format all -c "$W/new.conf"
diff "$W/old.conf" "$W/new.conf"
git status --short
```

- The `diff` shows only the step 2 changes and the overlay changes the user
  accepted in step 3. 20.0: three new options. 12.0: `logrotate` added,
  `upgrade_path` gone.
- `git status --short` lists:
  - **newer:** 12 files: `odoo_config/options.toml`,
    `odoo_config/overlay.toml`, `scripts/build_schema.py`, the three
    web-tools `index.html` pages, `README.md`, `CLI.md`,
    `odoo_config/main.py`, `site-docs/docs/getting-started.md`,
    `site-docs/docs/reference/schema.md` and `site-docs/docs/web-tools/index.md`.
  - **older:** the same files without `CLI.md` and `odoo_config/main.py`: 10.
- Run `make docs-serve`, open the option lookup and check that the `N` column
  sits on the same row as the others.

## Step 7: Commit and PR

Make one commit. semantic-release reads the `feat` prefix and handles the
version and `CHANGELOG.md` on merge. Replace the `<...>` placeholders, drop the
lines with nothing to report, and drop `Forge-ID` when there is no Forge
ticket.

**newer:**

```text
feat(schema): add Odoo <N> support

- Regenerate options.toml for <FIRST>–<LAST> from Odoo's config.py
  - new in <N>: <options>
  - <option> default is now <value>
- Refresh the schema data embedded in the 3 web tools (lookup grid: <count> columns)
- Update the supported range to <FIRST>–<LAST> in docs, CLI help and build script

Regenerating also corrects older versions:
- <option>: valid from <version>

Forge-ID: <id>
```

**older:**

```text
feat(schema): add Odoo <N> support

- Regenerate options.toml for <FIRST>–<LAST> from Odoo's config.py
  - <option>: valid up to <N>
  - <option>: valid from <OLD_BOUND>
- Drop <option>'s hand-set <bound> (<value>) from the overlay, so <N> configs keep it
- Refresh the schema data embedded in the 3 web tools (lookup grid: <count> columns)
- Update the supported range to <FIRST>–<LAST> in docs, web tools and build script

Forge-ID: <id>
```

PR description. List only the checks you actually ran:

```markdown
## Summary

Add Odoo <N> support. The supported range is now <FIRST>–<LAST>.

- **Schema:** regenerate `options.toml` with `scripts/build_schema.py` (added <N> to `DEFAULT_VERSIONS`). Not hand-edited.
  - <one line per reported change, with its version>
- **Overlay:** <the overlay change the user accepted>
- **Web tools:** refresh the embedded schema JSON (`make tools-data`); the lookup grid now has <count> version columns.
- **Docs/CLI:** update the version range in the README and site docs (newer: also the `--version` help and `CLI.md`).

## Test plan

- [x] `make test`
- [x] `make check`
- [x] `make tools-data-check`
- [x] `odoo-config create --output-format all` for <OLD_BOUND> and <N> differ only by the changes above

Forge-ID: <id>
```
