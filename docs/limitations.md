# Limitations

Known limitations:
- version allocation races can still happen with parallel generation into one workspace
- `mcp/brand_iterate.py` is still a large monolithic file
- generation test coverage is mostly structural/unit level; external model execution is not fully mocked end-to-end
- some policy/default behavior is still hardcoded in Python instead of fully data-driven config
