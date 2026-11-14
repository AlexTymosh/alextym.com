"""The grant operator command is explicit and inert without --apply."""

from __future__ import annotations

from scripts.manage_workforce_grant import main, parse_args


def test_grant_command_is_dry_run_by_default(monkeypatch, capsys) -> None:
    monkeypatch.setenv("PORTFOLIO_LAB_OWNER_UID", "owner")
    assert main(["admit-and-grant", "--uid", "invited-user"]) == 0
    assert "DRY RUN" in capsys.readouterr().out


def test_grant_command_rejects_missing_owner(monkeypatch) -> None:
    monkeypatch.delenv("PORTFOLIO_LAB_OWNER_UID", raising=False)
    assert main(["grant", "--uid", "invited-user"]) == 2


def test_grant_command_rejects_path_injection(monkeypatch) -> None:
    monkeypatch.setenv("PORTFOLIO_LAB_OWNER_UID", "owner")
    assert main(["revoke", "--uid", "../other"]) == 2


def test_apply_is_never_default() -> None:
    assert parse_args(["revoke", "--uid", "invited-user"]).apply is False
