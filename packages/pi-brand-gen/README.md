# pi-brand-gen

Pi extension for `<brand-gen-repo>`, inspired by native scheduled-assistant extension patterns.

## Features
- Native Pi extension entrypoint
- brand-gen MCP bridge to `brand_iterate_mcp.py`
- Tools: `brand_search`, `brand_execute`, `brand_status`
- `/brand-gen` command surface
- Sidebar/widget-style status panel compatibility hooks
- Session lifecycle integration
- Heartbeat scheduling + prompt-triggered heartbeat
- Persistent journal + learnings in `.brand-gen/brands/<brand>/`

## `/brand-gen` commands
- `/brand-gen status`
- `/brand-gen heartbeat`
- `/brand-gen switch <brand>`
- `/brand-gen reviews`
- `/brand-gen generate <materialType> <goal...>`
- `/brand-gen widget [show|hide]`
