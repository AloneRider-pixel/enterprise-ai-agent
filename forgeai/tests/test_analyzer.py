from forgeai.services.analyzer import analyze
from forgeai.services.github_client import PullRequestSnapshot


def build_snapshot(files: list[str]) -> PullRequestSnapshot:
    return PullRequestSnapshot(
        repository="acme/api",
        number=7,
        title="change",
        body="",
        additions=120,
        deletions=20,
        changed_files=len(files),
        filenames=files,
    )


def test_security_change_is_flagged() -> None:
    findings, factors = analyze(build_snapshot(["src/auth/router.py"]))
    assert any(item.category == "security" for item in findings)
    assert any(item.name == "security_surface" for item in factors)


def test_source_change_without_tests_is_flagged() -> None:
    findings, _ = analyze(build_snapshot(["src/orders/service.py"]))
    assert any(item.category == "testing" for item in findings)


def test_source_change_with_tests_has_no_test_warning() -> None:
    findings, _ = analyze(
        build_snapshot(
            [
                "src/orders/service.py",
                "tests/test_orders.py",
            ]
        )
    )
    assert not any(item.category == "testing" for item in findings)


def test_dependency_and_infra_changes_are_detected() -> None:
    findings, factors = analyze(
        build_snapshot(
            [
                "pyproject.toml",
                ".github/workflows/ci.yml",
            ]
        )
    )
    categories = {item.category for item in findings}
    factor_names = {factor.name for factor in factors}
    assert "dependencies" in categories
    assert "operations" in categories
    assert "dependency_change" in factor_names
    assert "infrastructure_change" in factor_names
