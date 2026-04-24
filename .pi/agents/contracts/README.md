# Pi agent contracts

Pi agent files are intentionally short. Detailed runtime contracts live in:

- `docs/architecture/README.md`
- `docs/architecture/runtime-agent-contract.md`
- `docs/architecture/tool-groups/orchestration.md`
- `docs/architecture/tool-groups/mutation.md`
- `docs/architecture/tool-groups/inspection-policy.md`
- `docs/architecture/gepa-dspy-optimization.md`

Pi agents should call typed tools from frontmatter and should not embed shell workflows. GEPA/DSPy reflection data belongs in the disagreement dataset fields documented in `docs/architecture/gepa-dspy-optimization.md`, not in long Pi prompt bodies.
