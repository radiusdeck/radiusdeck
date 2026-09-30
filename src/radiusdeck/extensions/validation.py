from __future__ import annotations

from pathlib import Path
from types import MappingProxyType

from jinja2 import Environment, FileSystemLoader, TemplateError, meta

from radiusdeck.extensions.api import (
    RADIUSDECK_EXTENSION_API,
    ExtensionDefinition,
)
from radiusdeck.extensions.contributions import (
    AuthenticationProvider,
    BrowserAuthenticationProvider,
    CollectedContributions,
    ConfigurationContribution,
    NavigationItem,
    RouterContribution,
    StaticMountContribution,
    StatusContribution,
    StructuralContributions,
    UIContribution,
)
from radiusdeck.extensions.errors import (
    ExtensionCompatibilityError,
    ExtensionConfigurationError,
    ExtensionConflictError,
)


def collect_contributions(
    extensions: tuple[ExtensionDefinition, ...],
) -> CollectedContributions:
    names: set[str] = set()
    routers: list[RouterContribution] = []
    providers: list[AuthenticationProvider] = []
    template_paths: list[Path] = []
    static_mounts: list[StaticMountContribution] = []
    navigation: list[NavigationItem] = []
    status: list[StatusContribution] = []
    configuration: list[ConfigurationContribution] = []
    ui: list[UIContribution] = []
    preserve_history = False
    browser_provider: BrowserAuthenticationProvider | None = None
    settings_by_extension: dict[str, object | None] = {}

    for extension in extensions:
        if extension.name in names:
            raise ExtensionConflictError(
                f"Duplicate runtime extension name: {extension.name}"
            )
        names.add(extension.name)
        if (
            type(extension.extension_api_version) is not int
            or extension.extension_api_version != RADIUSDECK_EXTENSION_API
        ):
            raise ExtensionCompatibilityError(
                f"Extension {extension.name!r} requires API "
                f"{extension.extension_api_version}; base supports exactly "
                f"{RADIUSDECK_EXTENSION_API}"
            )

        try:
            extension_settings = (
                extension.settings_loader()
                if extension.settings_loader is not None
                else None
            )
        except Exception as exc:
            raise ExtensionConfigurationError(
                f"Extension {extension.name!r} settings are invalid: {exc}"
            ) from exc

        try:
            contribution = extension.structural_contributions(extension_settings)
        except Exception as exc:
            raise ExtensionConfigurationError(
                f"Extension {extension.name!r} contributions are invalid: {exc}"
            ) from exc
        if not isinstance(contribution, StructuralContributions):
            raise ExtensionConfigurationError(
                f"Extension {extension.name!r} did not return StructuralContributions"
            )

        routers.extend(contribution.routers)
        ui.extend(contribution.ui_contributions)
        settings_by_extension[extension.name] = extension_settings
        if contribution.browser_authentication is not None:
            if browser_provider is not None:
                raise ExtensionConflictError(
                    "Duplicate browser authentication provider"
                )
            browser_provider = contribution.browser_authentication
        providers.extend(contribution.authentication_providers)
        template_paths.extend(contribution.template_search_paths)
        static_mounts.extend(contribution.static_mounts)
        navigation.extend(contribution.navigation_items)
        status.extend(contribution.status_contributors)
        configuration.extend(contribution.configuration_contributors)
        preserve_history = (
            preserve_history or contribution.preserve_external_backup_history
        )

    _require_unique("authentication provider", [item.provider_id for item in providers])
    _require_unique("static mount name", [item.name for item in static_mounts])
    _require_unique("static mount path", [item.path for item in static_mounts])
    _require_unique("navigation item", [item.item_id for item in navigation])
    _require_unique("status contributor", [item.contributor_id for item in status])
    _require_unique(
        "configuration contributor",
        [item.contributor_id for item in configuration],
    )

    _require_unique("UI contribution", [item.contribution_id for item in ui])
    allowed_slots = {
        "backups.toolbar",
        "backups.sections",
        "logs.toolbar",
        "logs.sections",
    }
    env = Environment(
        loader=FileSystemLoader(
            [str(p) for p in template_paths]
            + [str(Path(__file__).parent.parent / "templates")]
        )
    )

    def validate_template(name: str, seen: set[str]) -> None:
        if name in seen:
            return
        seen.add(name)
        assert env.loader is not None
        source, _, _ = env.loader.get_source(env, name)
        parsed = env.parse(source)
        env.get_template(name)
        for reference in meta.find_referenced_templates(parsed):
            if reference is not None:
                validate_template(reference, seen)

    for item in ui:
        if item.slot not in allowed_slots:
            raise ExtensionConfigurationError(f"Unknown UI slot: {item.slot}")
        try:
            validate_template(item.template, set())
        except TemplateError as exc:
            raise ExtensionConfigurationError(
                f"Invalid UI template {item.template}: {exc}"
            ) from exc

    return CollectedContributions(
        routers=tuple(routers),
        ui_contributions=tuple(
            sorted(ui, key=lambda item: (item.order, item.contribution_id))
        ),
        authentication_providers=tuple(providers),
        template_search_paths=tuple(template_paths),
        static_mounts=tuple(static_mounts),
        navigation_items=tuple(
            sorted(navigation, key=lambda item: (item.order, item.item_id))
        ),
        status_contributors=tuple(status),
        configuration_contributors=tuple(configuration),
        preserve_external_backup_history=preserve_history,
        extension_names=tuple(extension.name for extension in extensions),
        browser_authentication=browser_provider,
        extension_settings=MappingProxyType(settings_by_extension),
    )


def validate_auth_method(
    auth_method: str,
    contributions: CollectedContributions,
) -> None:
    base_methods = {"none", "local"}
    extension_methods = {
        provider.provider_id for provider in contributions.authentication_providers
    }
    if contributions.browser_authentication is not None:
        extension_methods.add(contributions.browser_authentication.provider_id)
    if auth_method not in base_methods | extension_methods:
        raise ExtensionConfigurationError(
            f"APP_AUTH_METHOD={auth_method!r} has no registered authentication provider"
        )


def _require_unique(kind: str, values: list[str]) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    if duplicates:
        rendered = ", ".join(sorted(duplicates))
        raise ExtensionConflictError(f"Duplicate {kind} identifiers: {rendered}")
