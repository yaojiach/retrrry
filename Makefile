test:
	pipenv run pytest -o log_cli=true --log-cli-level=DEBUG tests.py 

package:
	rm -rf dist
	pipenv run python setup.py sdist bdist_wheel

release:
	pipenv run python -m twine upload dist/*