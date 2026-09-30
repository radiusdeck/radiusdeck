from __future__ import annotations

from pathlib import Path

DEPLOY_DIR = Path("deploy")


def _deploy_text() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(DEPLOY_DIR.rglob("*"))
        if path.is_file()
    )


def test_https_examples_do_not_mount_docker_socket() -> None:
    assert "/var/run/docker.sock" not in _deploy_text()


def test_caddy_examples_proxy_to_radiusdeck() -> None:
    for path in Path("deploy/caddy").glob("Caddyfile.*.example"):
        assert "reverse_proxy radiusdeck:8000" in path.read_text(encoding="utf-8")


def test_compose_examples_use_app_environment_names() -> None:
    for path in Path("deploy/compose").glob("docker-compose.https-*.example.yml"):
        text = path.read_text(encoding="utf-8")
        assert "APP_PUBLIC_URL" in text
        assert "APP_AUTH_METHOD" in text
        assert "RADIUSDECK_" not in text

        if 'APP_AUTH_METHOD: "local"' in text:
            assert "APP_SESSION_SECRET_KEY" in text
            assert "APP_LOCAL_USERS_PATH" in text


def test_default_compose_and_dockerfile_use_app_environment_names() -> None:
    compose = Path("docker-compose.yml").read_text(encoding="utf-8")
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")

    assert "RADIUSDECK_" not in compose
    assert "RADIUSDECK_" not in dockerfile
    assert "APP_RADIUS_CLIENTS_PATH" in compose
    assert "APP_SIDECAR_RELOAD_ENABLED" in compose
    assert "APP_SIDECAR_RELOAD_URL" in compose
    assert "APP_SIDECAR_RELOAD_TOKEN" in compose
    assert "APP_RADIUS_CLIENTS_PATH" in dockerfile


def test_default_compose_starts_in_explicit_open_mode() -> None:
    compose = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert "APP_AUTH_METHOD: ${APP_AUTH_METHOD:-none}" in compose


def test_default_compose_mounts_existing_host_clients_file() -> None:
    compose = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert "HOST_RADIUS_CLIENTS_CONF" in compose
    assert "create_host_path: false" in compose
    assert "touch /data/clients.conf" not in compose


def test_compose_examples_do_not_expose_radiusdeck_ports() -> None:
    for path in Path("deploy/compose").glob("docker-compose.https-*.example.yml"):
        lines = path.read_text(encoding="utf-8").splitlines()
        radiusdeck_block: list[str] = []
        in_radiusdeck = False
        for line in lines:
            if line.startswith("  radiusdeck:"):
                in_radiusdeck = True
                continue
            if in_radiusdeck and line.startswith("  ") and not line.startswith("    "):
                break
            if in_radiusdeck:
                radiusdeck_block.append(line)

        assert any("expose:" in line for line in radiusdeck_block)
        assert not any("ports:" in line for line in radiusdeck_block)


def test_mounted_cert_example_mounts_certs_only_into_caddy() -> None:
    text = Path(
        "deploy/compose/docker-compose.https-mounted-cert.example.yml"
    ).read_text(encoding="utf-8")
    radiusdeck_text, caddy_text = text.split("  caddy:", maxsplit=1)

    assert ":/certs:ro" not in radiusdeck_text
    assert ":/certs:ro" in caddy_text


def test_mounted_cert_example_uses_explicit_open_mode() -> None:
    text = Path(
        "deploy/compose/docker-compose.https-mounted-cert.example.yml"
    ).read_text(encoding="utf-8")

    assert 'APP_AUTH_METHOD: "none"' in text
    assert 'APP_FREERADIUS_LOG_VIEWER_ENABLED: "true"' in text
    assert "APP_LOCAL_USERS_PATH" not in text
    assert "APP_SESSION_SECRET_KEY" not in text
    assert "HOST_RADIUS_CLIENTS_CONF" in text
    assert ":/data/clients.conf" in text
    assert "HOST_FREERADIUS_LOG" in text
    assert ":/logs/radius.log:ro" in text
    assert "touch /data/clients.conf" not in text


def test_readme_references_certificate_docs() -> None:
    text = Path("README.md").read_text(encoding="utf-8")
    assert "deploy/certs/README.md" in text
