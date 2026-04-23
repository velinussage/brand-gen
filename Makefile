PYTHON := $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)

.PHONY: setup test lint dev demo help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

setup: ## First-time setup (copy .env, validate)
	@cp -n .env.example .env 2>/dev/null || true
	@$(PYTHON) scripts/validate_setup.py

test: ## Run all tests
	$(PYTHON) -m pytest tests/ -v

lint: ## Compile-check all Python modules
	$(PYTHON) -m compileall -q brand_gen scripts
	@echo "All modules compile cleanly."

dev: ## Start the MCP server (stdio)
	$(PYTHON) -m brand_gen.brand_iterate_mcp

demo: ## Print the quickstart demo command
	@echo "Run this to generate your first social card:"
	@echo ""
	@echo "  $(PYTHON) -m brand_gen pipeline \\"
	@echo "    --material-type x-feed \\"
	@echo "    --mode hybrid \\"
	@echo "    --prompt-seed 'Product dashboard with clean branded field' \\"
	@echo "    --format json"
