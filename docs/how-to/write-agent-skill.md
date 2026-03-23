# Write an agent skill for brand-gen

Keep skills short, tool-first, and host-neutral by default.

A good skill should answer:

- which command/tool to call when
- what comes back
- which gotchas matter
- when to switch from saved-brand mode to testing-session mode

Prefer:

- one routing decision tree
- compact command reference entries
- on-demand reference files for tables/specs
- env vars or placeholders instead of machine-specific paths

If you need host-specific steps, keep them in a short isolated section instead of making the whole skill depend on one host.

See the current public skill set:

- `skills/brand-gen-setup/SKILL.md`
- `skills/brand-gen/SKILL.md`
- `skills/brand-gen-reference/SKILL.md`
- `skills/brand-gen-logo/SKILL.md`
- `skills/brand-content-ideation/SKILL.md`
