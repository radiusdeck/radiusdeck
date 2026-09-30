from __future__ import annotations

import pytest

from radiusdeck.cli.main import main


def test_version_contract(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as raised:
        main(["--version"])

    assert raised.value.code == 0
    assert capsys.readouterr().out == "radiusdeck 0.1.0\n"


def test_serve_defaults_match_production_uvicorn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def fake_run(target: str, **kwargs: object) -> None:
        calls.append((target, kwargs))

    monkeypatch.setattr("radiusdeck.cli.main.uvicorn.run", fake_run)

    assert main(["serve"]) == 0
    assert calls == [
        (
            "radiusdeck.main:app",
            {
                "host": "0.0.0.0",
                "port": 8000,
                "proxy_headers": True,
                "forwarded_allow_ips": "*",
            },
        )
    ]


def test_serve_forwards_explicit_network_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "radiusdeck.cli.main.uvicorn.run",
        lambda _target, **kwargs: calls.append(kwargs),
    )

    assert (
        main(
            [
                "serve",
                "--host",
                "127.0.0.1",
                "--port",
                "9000",
                "--no-proxy-headers",
                "--forwarded-allow-ips",
                "127.0.0.1",
            ]
        )
        == 0
    )
    assert calls == [
        {
            "host": "127.0.0.1",
            "port": 9000,
            "proxy_headers": False,
            "forwarded_allow_ips": "127.0.0.1",
        }
    ]
