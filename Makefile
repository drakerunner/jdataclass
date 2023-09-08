SRC_CORE=jdataclass
POETRY=poetry


help: ## Print help for each target
	$(info jdataclass)
	$(info =============================)
	$(info )
	$(info Available commands:)
	$(info )
	@grep '^[[:alnum:]_-]*:.* ##' $(MAKEFILE_LIST) \
		| sort | awk 'BEGIN {FS=":.* ## "}; {printf "%-25s %s\n", $$1, $$2};'

lint:
	@echo "Linting $(SRC_CORE)..."
	@echo "linting with black:"
	@echo ""
	@$(POETRY) run black --check $(SRC_CORE)
	@echo ""
	@echo ""
	@echo "linting with pyright:"
	@$(POETRY) run python -m pyright $(SRC_CORE)
	@echo ""
	@echo ""
	@echo "linting with pylint:"
	@$(POETRY) run python -m pylint $(SRC_CORE)
	@echo ""
	@echo ""

test: ## Test the code
	@$(POETRY) run python -m pytest

doc: ## Document the code
	@poetry run sphinx-build -M clean "docs/" "docs/_build"
	@rm docs/jdataclass.rst
	@poetry run sphinx-apidoc -o docs/ jdataclass/
	@poetry run sphinx-build -M html "docs/" "docs/_build"

clean: ## Cleanup
	@rm -rf .venv
	@rm -rf .mypy_cache
	@rm -rf .pytest_cache
	@rm -rf dist
	@rm -rf htmldoc
	@rm -rf htmlcov
	@find -name *.pyc -prune -exec rm -rf {} \;
	@find -name __pycache__ -prune -exec rm -rf {} \;
	@find -name *.egg-info -prune -exec rm -rf {} \;
	@find -name .coverage -prune -exec rm -rf {} \;
