# Starter prompts

Copy-paste prompts to bootstrap your agent with brand-gen. These use full GitHub links so the agent can inspect docs immediately. After cloning, agents should use local paths.

## 1. Clone, install, and set up

```text
I want you to set up brand-gen from scratch and make it ready for agent-driven brand material work.

Clone `https://github.com/velinussage/brand-gen`, install it, validate the environment, and then read the usage skills so you know how to operate it:

- https://github.com/velinussage/brand-gen/blob/main/skills/brand-gen-setup/SKILL.md
- https://github.com/velinussage/brand-gen/blob/main/skills/brand-gen/SKILL.md
- https://github.com/velinussage/brand-gen/blob/main/skills/brand-gen-reference/SKILL.md
- https://github.com/velinussage/brand-gen/blob/main/skills/brand-gen-orchestration/SKILL.md

After setup, run:

- `bgen context-snapshot --format json`
- `bgen workspace-status --format json`
- `bgen capabilities --format json`

Then tell me whether brand-gen is ready, what workspace is active, and what my next best step is to create or connect a brand.
```

## 2. Create a first brand from conversation

```text
I want to establish my first brand in brand-gen and generate the first illustrations with you.

Read these files first:

- https://github.com/velinussage/brand-gen/blob/main/skills/brand-gen/SKILL.md
- https://github.com/velinussage/brand-gen/blob/main/skills/brand-gen-orchestration/SKILL.md
- https://github.com/velinussage/brand-gen/blob/main/skills/brand-content-ideation/SKILL.md
- https://github.com/velinussage/brand-gen/blob/main/prompts/brand-reverse-interview-intake.md
- https://github.com/velinussage/brand-gen/blob/main/prompts/brand-concept-exploration.md
- https://github.com/velinussage/brand-gen/blob/main/prompts/non-interface-brand-brief.md

Start by interviewing me to create a strong first brand brief. Then either:

- create a durable saved brand with `bgen create-brand`, or
- start a testing session with `bgen start-testing` if that is safer

After that, follow the planning-first orchestration flow: explorer > router > planner > critic > generator. Propose 2-3 first material directions, help me choose one, and only then generate the first branded illustration or social asset.
```

## 3. Connect existing materials

```text
I already have a repo, docs bundle, or existing brand materials and I want to connect them to brand-gen instead of starting from scratch.

Read these files first:

- https://github.com/velinussage/brand-gen/blob/main/skills/brand-gen/SKILL.md
- https://github.com/velinussage/brand-gen/blob/main/skills/brand-gen-reference/SKILL.md
- https://github.com/velinussage/brand-gen/blob/main/prompts/brand-description-extraction.md
- https://github.com/velinussage/brand-gen/blob/main/prompts/product-presentation-reference-brief.md

Inspect the current workspace with `bgen context-snapshot --format json`.

If no saved brand exists yet, extract one from my project or materials. If a brand already exists, connect to it and summarize what the system already knows.

Then follow explorer > router > planner > critic > generator, recommend the best first asset, and generate it.
```

## 4. Use Pi as default host

```text
I want Pi to be my default host for brand-gen.

First install Pi itself by following:
- https://github.com/badlogic/pi-mono/blob/main/packages/coding-agent/README.md

Then follow:
- https://github.com/velinussage/brand-gen/blob/main/README.md
- https://github.com/velinussage/brand-gen/blob/main/packages/pi-brand-gen/README.md
- https://github.com/velinussage/brand-gen/blob/main/skills/brand-gen/SKILL.md

Make sure the Pi extension is configured correctly, then verify with:

- `/brand-gen status`
- `/brand-gen brands`
- `/brand-gen summary`

After verification, generate a first asset through the Pi workflow.
```

## 5. Returning session (already installed)

```text
I want to work on brand materials using brand-gen.

Read https://github.com/velinussage/brand-gen/blob/main/skills/brand-gen/SKILL.md, then run:

  bgen context-snapshot --format json

to inspect the current workspace. If no brand exists yet, help me create one.
If a brand or testing session is already active, ask what I want to generate,
review, or iterate on.
```
