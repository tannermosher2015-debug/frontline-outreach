from outreach.__main__ import build_parser

def test_parser_has_subcommands():
    p = build_parser()
    for cmd in ["run", "serve", "send"]:
        ns = p.parse_args([cmd])
        assert ns.command == cmd

def test_run_accepts_date():
    ns = build_parser().parse_args(["run", "--date", "2026-06-19"])
    assert ns.date == "2026-06-19"
