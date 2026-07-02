from scripts.check_no_secrets import scan_for_secrets


def test_no_secrets_scan_passes_safe_text(tmp_path):
    (tmp_path / "README.md").write_text(
        "This project requires no API keys. Example placeholders are allowed.",
        encoding="utf-8",
    )

    report = scan_for_secrets(tmp_path)

    assert report["ready"] is True
    assert report["summary"]["findings"] == 0


def test_no_secrets_scan_flags_real_looking_secret(tmp_path):
    fake_secret = "sk-" + "live1234567890REALKEYVALUEZZZZ"
    (tmp_path / "config.py").write_text(
        f'OPENAI_API_KEY = "{fake_secret}"\n',
        encoding="utf-8",
    )

    report = scan_for_secrets(tmp_path)

    assert report["ready"] is False
    assert report["summary"]["findings"] == 1
    assert report["findings"][0]["kind"] == "openai_api_key"


def test_no_secrets_scan_ignores_placeholders_and_generated_outputs(tmp_path):
    fake_secret = "sk-" + "live1234567890REALKEYVALUEZZZZ"
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "fixture.py").write_text(
        "api_key=example_placeholder_value",
        encoding="utf-8",
    )
    generated = tmp_path / "data" / "processed"
    generated.mkdir(parents=True)
    (generated / "report.json").write_text(
        f'{{"token": "{fake_secret}"}}',
        encoding="utf-8",
    )

    report = scan_for_secrets(tmp_path)

    assert report["ready"] is True
    assert report["summary"]["findings"] == 0
