.PHONY: audit coverage demo eval validate preflight samples trace secrets lint lint-style typecheck ci test ui stats brief mcp

audit:
	uv run python -m scripts.dependency_audit

coverage:
	uv run --extra dev python -m scripts.coverage_report

demo:
	uv run python -m scripts.run_demo --reset

eval:
	uv run python -m scripts.run_golden_evals

validate:
	uv run python -m scripts.validate_submission

preflight:
	uv run python -m scripts.preflight

samples:
	uv run python -m scripts.generate_sample_outputs

trace:
	uv run python -m scripts.export_agent_trace

secrets:
	uv run python -m scripts.check_no_secrets

lint:
	uv run ruff check . --select F

lint-style:
	uv run ruff check .

typecheck:
	uv run mypy tools scripts app --ignore-missing-imports --no-warn-return-any --disable-error-code var-annotated --disable-error-code misc --disable-error-code assignment

ci: audit lint typecheck test eval validate

test:
	uv run --extra dev pytest

ui:
	uv run streamlit run ui/streamlit_app.py

stats:
	uv run python -m scripts.project_stats --db-path data/processed/papers.sqlite --graph-path data/processed/research_graph.graphml

brief:
	uv run python -c "from app.adk_tools import generate_local_research_brief; print(generate_local_research_brief())"

mcp:
	uv run python -m scripts.run_mcp_server
