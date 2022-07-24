test:
	poetry run pytest -o log_cli=true --log-cli-level=DEBUG

build:
	rm -r dist
	poetry build

release:
	poetry publish
