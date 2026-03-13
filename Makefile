.PHONY: setup test lint dev demo help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

setup: ## First-time setup (copy .env, validate)
	@cp -n .env.example .env 2>/dev/null || true
	@python3 scripts/validate_setup.py

test: ## Run all tests
	python3 -m pytest tests/ -v

lint: ## Compile-check all Python modules
	@python3 -m py_compile mcp/brand_iterate.py
	@python3 -m py_compile mcp/brand_iterate_mcp.py
	@python3 -m py_compile mcp/pipeline_runner.py
	@python3 -m py_compile mcp/pipeline_types.py
	@python3 -m py_compile mcp/route_predicates.py
	@python3 -m py_compile mcp/generate.py
	@echo "All modules compile cleanly."

dev: ## Start the MCP server (stdio)
	python3 mcp/brand_iterate_mcp.py

demo: ## Print the quickstart demo command
	@echo "Run this to generate your first social card:"
	@echo ""
	@echo "  python3 mcp/brand_iterate.py pipeline \\"
	@echo "    --material-type x-feed \\"
	@echo "    --mode hybrid \\"
	@echo "    --prompt-seed 'Product dashboard with clean branded field' \\"
	@echo "    --format json"
