.PHONY: test lint format run

test:
	pytest -q

lint:
	flake8 src tests

format:
	black src tests

run:
	python -m src
