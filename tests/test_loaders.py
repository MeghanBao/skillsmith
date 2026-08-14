import json

from skillsmith.loaders import (
    can_load,
    get_loader,
    load_source,
    supported_suffixes,
)
from skillsmith.batch import discover_sources


def test_registry_covers_all_formats():
    s = supported_suffixes()
    assert {".md", ".txt", ".pdf", ".html", ".vtt", ".json"} <= s


def test_unknown_suffix_rejected(tmp_path):
    p = tmp_path / "x.xyz"
    p.write_text("hi")
    assert can_load(p) is False


def test_text_loader_passthrough(tmp_path):
    p = tmp_path / "doc.md"
    p.write_text("# Title\n\nbody", encoding="utf-8")
    assert load_source(p) == "# Title\n\nbody"


def test_vtt_strips_timing_tags_and_dedupes(tmp_path):
    vtt = """WEBVTT

NOTE this is a comment

1
00:00:01.000 --> 00:00:03.000
<v Alice>First we <c>open</c> the console

2
00:00:03.000 --> 00:00:05.000
First we open the console
Then run the reset tool
"""
    p = tmp_path / "cap.vtt"
    p.write_text(vtt, encoding="utf-8")
    out = load_source(p)
    lines = out.splitlines()
    assert lines == ["First we open the console", "Then run the reset tool"]
    assert "-->" not in out
    assert "<c>" not in out and "WEBVTT" not in out


def test_html_extracts_text_drops_boilerplate(tmp_path):
    html = """<html><head><title>Reset SOP</title>
    <style>.x{color:red}</style></head>
    <body><script>evil()</script>
    <nav>menu</nav>
    <h1>Reset a password</h1>
    <p>Verify the ticket first.</p>
    </body></html>"""
    p = tmp_path / "doc.html"
    p.write_text(html, encoding="utf-8")
    out = load_source(p)
    assert "Reset a password" in out
    assert "Verify the ticket first." in out
    assert "evil()" not in out
    assert "color:red" not in out
    assert "menu" not in out


def test_slack_export_becomes_transcript(tmp_path):
    (tmp_path / "users.json").write_text(
        json.dumps([
            {"id": "U1", "profile": {"real_name": "Alice Admin"}},
            {"id": "U2", "name": "bob"},
        ]),
        encoding="utf-8",
    )
    messages = [
        {"type": "message", "user": "U1", "ts": "1616169600.000000",
         "text": "Hey <@U2>, how do we reset a locked account?"},
        {"type": "message", "user": "U2", "subtype": "channel_join",
         "text": "has joined"},
        {"type": "message", "user": "U2", "ts": "1616169660.000000",
         "text": "Run <https://idm.corp/reset|the reset tool> after verifying the ticket."},
    ]
    p = tmp_path / "2021-03-19.json"
    p.write_text(json.dumps(messages), encoding="utf-8")

    out = load_source(p)
    assert "Alice Admin: Hey @bob, how do we reset a locked account?" in out
    assert "bob: Run the reset tool after verifying the ticket." in out
    assert "channel_join" not in out
    assert "has joined" not in out  # join subtype skipped


def test_slack_loader_falls_back_on_non_slack_json(tmp_path):
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"setting": "value"}), encoding="utf-8")
    out = load_source(p)
    assert '"setting": "value"' in out


def test_discover_skips_users_json_but_finds_sources(tmp_path):
    (tmp_path / "users.json").write_text("[]", encoding="utf-8")
    (tmp_path / "a.md").write_text("x", encoding="utf-8")
    (tmp_path / "chan").mkdir()
    (tmp_path / "chan" / "2021-01-01.json").write_text("[]", encoding="utf-8")
    (tmp_path / "ignore.xyz").write_text("x", encoding="utf-8")

    found = {p.name for p in discover_sources(tmp_path)}
    assert found == {"a.md", "2021-01-01.json"}


def test_get_loader_maps_suffix(tmp_path):
    p = tmp_path / "x.vtt"
    p.write_text("WEBVTT\n")
    assert get_loader(p).__class__.__name__ == "VttLoader"
