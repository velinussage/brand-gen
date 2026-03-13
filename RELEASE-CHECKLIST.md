# Release checklist

Before publishing or tagging a release:

- review `plans/OPEN-SOURCE-PREP.md`
- run `make lint`
- run `make test`
- confirm `.brand-gen/` and `brand-materials/` are excluded
- scan tracked files for secrets, personal paths, and third-party assets you should not publish
