from odoo_config.main import _compare_columns, _row_differs
from odoo_config.schema import (
    _merge,
    build,
    default_for,
    drop_defaults,
    drop_outdated,
    explain_rows,
    load_schema,
    overlay_overrides,
    read_conf,
    render,
    resolve_given,
    valid_for_version,
)


def test_overlay_overrides():
    overrides = overlay_overrides()
    assert {"proxy_mode", "unaccent", "workers", "max_cron_threads"} <= overrides  # trobz policy
    assert {"sentry_dsn", "running_env"} <= overrides  # trobz-only, absent from odoo
    assert "db_maxconn" not in overrides  # overlay default matches odoo


def test_merge_overlay_precedence():
    core = {"a": {"default": 1, "by_version": {"13.0": 1, "19.0": 9}, "max_version": "19.0"}}

    # overlay silent -> inherits mined default, by_version and bounds
    merged = _merge(core, {})
    assert merged["a"] == {"default": 1, "by_version": {"13.0": 1, "19.0": 9}, "max_version": "19.0"}

    # overlay pins a default -> wins and drops the mined by_version
    merged = _merge(core, {"a": {"default": 5}})
    assert merged["a"]["default"] == 5 and "by_version" not in merged["a"]

    # overlay supplies its own by_version -> wins over the mined one
    merged = _merge(core, {"a": {"by_version": {"18.0": 7}}})
    assert merged["a"]["by_version"] == {"18.0": 7}

    # odoo help is inherited into the merged schema (even when overlay touches the key)
    merged = _merge({"a": {"help": "odoo help"}}, {"a": {"default": 5}})
    assert merged["a"]["help"] == "odoo help"


def test_version_filtering():
    schema, _ = load_schema()
    assert valid_for_version(schema["gevent_port"], "19.0")
    assert not valid_for_version(schema["gevent_port"], "15.0")
    assert valid_for_version(schema["longpolling_port"], "15.0")
    assert not valid_for_version(schema["longpolling_port"], "16.0")


def test_precedence():
    _, presets = load_schema()
    given = resolve_given(
        presets,
        preset="integration",
        sources=[{"workers": "4"}],
        env={"workers": "8"},
        overrides={"workers": "0"},
    )
    assert given["max_cron_threads"] == 0
    assert given["workers"] == "0"


def test_output_formats():
    schema, _ = load_schema()
    given = {"workers": "8"}

    bare = build(schema, "19.0", "bare", given)
    assert set(bare) == {"workers"}

    explicit = build(schema, "19.0", "explicit", given)
    assert "admin_passwd" in explicit and "db_sslmode" not in explicit  # mandatory vs not

    full = build(schema, "19.0", "all", given)
    assert "db_maxconn" in full and "gevent_port" in full and "longpolling_port" not in full


def test_render_round_trip():
    schema, presets = load_schema()
    given = resolve_given(presets, "production", [{"db_password": "secret"}], {}, {})
    text = render(build(schema, "19.0", "explicit", given), schema, given)
    assert "[options]" in text
    assert "max_cron_threads = 2" in text
    assert "db_password = secret" in text


def test_default_for_by_version():
    meta = {"default": 65536, "by_version": {"13.0": 8192, "16.0": 65536}}
    assert default_for(meta, "15.0") == 8192
    assert default_for(meta, "19.0") == 65536
    assert default_for(meta, None) == 65536  # no version -> newest
    assert default_for({"default": 7}, "19.0") == 7  # no by_version -> plain default


def test_transforms():
    schema, _ = load_schema()
    admin_default = default_for(schema["admin_passwd"], "19.0")
    values = {"admin_passwd": admin_default, "workers": "8", "bogus_opt": "x"}

    compact = drop_defaults(values, schema, "19.0")
    assert "admin_passwd" not in compact  # equals default -> dropped
    assert compact["workers"] == "8"  # differs from default -> kept
    assert compact["bogus_opt"] == "x"  # unknown -> kept (no default to compare)

    cleaned = drop_outdated(values, schema, "19.0")
    assert "bogus_opt" not in cleaned  # unknown -> dropped
    assert "workers" in cleaned
    assert "longpolling_port" not in drop_outdated({"longpolling_port": "8072"}, schema, "19.0")  # invalid >15

    rows = {k: (help_text, default) for k, _v, help_text, default in explain_rows(values, schema, "19.0")}
    assert rows["workers"][1] == default_for(schema["workers"], "19.0")  # default surfaced
    assert rows["bogus_opt"] == ("", "")  # unknown -> empty help/default

    # overlay comment overrides odoo help; help is the fallback when no comment
    fake = {"a": {"help": "odoo help", "comment": "trobz note"}, "b": {"help": "odoo help"}}
    helps = {k: h for k, _v, h, _d in explain_rows({"a": "1", "b": "2"}, fake, None)}
    assert helps == {"a": "trobz note", "b": "odoo help"}


def test_compare_columns():
    schema, presets = load_schema()
    cols = _compare_columns(schema, presets, {"a.conf": {"workers": "8"}}, ["19.0"], ["production"])

    assert set(cols) == {"a.conf", "19.0+production"}
    assert cols["a.conf"] == {"workers": "8"}  # file shown as written, not padded
    assert cols["19.0+production"]["max_cron_threads"] == 2  # preset overlay
    assert "gevent_port" in cols["19.0+production"]  # full version defaults
    assert "longpolling_port" not in cols["19.0+production"]  # version-filtered


def test_row_differs():
    cols = {"a": {"x": "1", "same": "z"}, "b": {"x": "2", "same": "z"}}
    names = list(cols)
    assert _row_differs(cols, names, "x", set())  # differing values
    assert not _row_differs(cols, names, "same", set())  # identical

    # presence diff counts between same-kind columns (file/file, version/version)
    assert _row_differs({"a": {"k": "1"}, "b": {}}, ["a", "b"], "k", {"a", "b"})
    assert _row_differs({"18.0": {}, "19.0": {"k": "1"}}, ["18.0", "19.0"], "k", set())

    # a key absent from a sparse file but present in version columns is NOT a diff
    cols = {"f.conf": {}, "19.0": {"k": "1"}, "18.0": {"k": "1"}}
    assert not _row_differs(cols, list(cols), "k", {"f.conf"})

    # string file value vs typed built default are equal after normalisation
    cols = {"f.conf": {"db_port": "5432", "workers": "4"}, "19.0": {"db_port": 5432, "workers": 4}}
    assert not _row_differs(cols, list(cols), "db_port", {"f.conf"})
    assert not _row_differs({"f.conf": {"v": "False"}, "19.0": {"v": False}}, ["f.conf", "19.0"], "v", {"f.conf"})

    # bool casing is normalised: "False" == "false", "True" == "true"
    assert not _row_differs({"f.conf": {"v": "False"}, "19.0": {"v": "false"}}, ["f.conf", "19.0"], "v", {"f.conf"})
    assert not _row_differs({"f.conf": {"v": "True"}, "19.0": {"v": "true"}}, ["f.conf", "19.0"], "v", {"f.conf"})


def test_read_conf(tmp_path):
    conf_file = tmp_path / "odoo.conf"
    conf_file.write_text("[options]\nworkers = 4\n[other]\ncustom_val = x\n")

    # Test reading with pathlib.Path
    values, sections = read_conf(conf_file)
    assert values == {"workers": "4", "custom_val": "x"}
    assert sections == {"workers": "options", "custom_val": "other"}

    # Test reading with str path
    values, sections = read_conf(str(conf_file))
    assert values == {"workers": "4", "custom_val": "x"}
    assert sections == {"workers": "options", "custom_val": "other"}


def test_read_conf_remote(monkeypatch):
    # Mock read_remote to return a dummy config content
    def mock_read_remote(path):
        assert path == "remote-host:/path/to/odoo.conf"
        return "[options]\nworkers = 8\n"

    import odoo_config.schema

    monkeypatch.setattr(odoo_config.schema, "read_remote", mock_read_remote)

    # Test with string path containing ":"
    values, sections = read_conf("remote-host:/path/to/odoo.conf")
    assert values == {"workers": "8"}
    assert sections == {"workers": "options"}
