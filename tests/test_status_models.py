from radiusdeck.services.status_models import (
    StatusCheck,
    StatusLevel,
    StatusSection,
    overall_status,
)


def _section(*levels: StatusLevel) -> StatusSection:
    return StatusSection(
        id="test",
        title="Test",
        checks=[
            StatusCheck(
                id=f"test.{index}",
                label="Test",
                level=level,
                message="Test",
            )
            for index, level in enumerate(levels)
        ],
    )


def test_overall_status_prioritizes_errors() -> None:
    assert overall_status([_section(StatusLevel.WARNING, StatusLevel.ERROR)]) == (
        StatusLevel.ERROR
    )


def test_overall_status_uses_warning_without_errors() -> None:
    assert overall_status([_section(StatusLevel.OK, StatusLevel.WARNING)]) == (
        StatusLevel.WARNING
    )


def test_skipped_checks_do_not_degrade_overall_status() -> None:
    assert overall_status([_section(StatusLevel.OK, StatusLevel.SKIPPED)]) == (
        StatusLevel.OK
    )
