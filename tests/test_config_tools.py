from tools.config_tools import load_config, parse_config


def test_load_default_config():
    config = load_config("configs/default.yaml")

    assert config.version == 1
    assert config.paths.db_path == "data/processed/papers.sqlite"
    assert config.pipeline.max_statements_per_type_per_paper == 30
    assert config.evaluation.min_golden_pass_rate == 1.0
    assert config.ui.max_search_results == 30


def test_config_to_dict_is_serializable():
    config = load_config("configs/default.yaml")

    payload = config.to_dict()

    assert payload["paths"]["papers_dir"] == "data/papers"
    assert payload["pipeline"]["max_gaps"] == 10


def test_parse_config_rejects_invalid_score():
    config = load_config("configs/default.yaml").to_dict()
    config["evaluation"]["min_overall_score"] = 2

    try:
        parse_config(config)
    except ValueError as exc:
        assert "score between 0 and 1" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_parse_config_rejects_missing_required_path():
    config = load_config("configs/default.yaml").to_dict()
    config["paths"]["db_path"] = ""

    try:
        parse_config(config)
    except ValueError as exc:
        assert "non-empty string" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
