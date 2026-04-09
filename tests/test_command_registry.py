import unittest
from collections import defaultdict
from pathlib import Path
import ast
from unittest import mock

from brand_gen import command_registry
from brand_gen.command_registry import COMMAND_HANDLERS, COMMAND_SPECS, CommandSpec, build_parser
from brand_gen.cli_builders import CLI_BUILDERS


class CommandRegistryTests(unittest.TestCase):
    def test_every_spec_and_alias_has_a_handler(self):
        for spec in COMMAND_SPECS:
            self.assertIn(spec.name, COMMAND_HANDLERS)
            for alias in spec.aliases:
                self.assertIn(alias, COMMAND_HANDLERS)

    def test_command_names_are_unique(self):
        names = [spec.name for spec in COMMAND_SPECS]
        self.assertEqual(len(names), len(set(names)))

    def test_parser_knows_core_commands(self):
        parser = build_parser()
        help_text = parser.format_help()
        self.assertIn("build-generation-scratchpad", help_text)
        self.assertIn("plan-draft", help_text)
        self.assertIn("generate", help_text)

    def test_parser_choices_cover_registry_names_and_aliases(self):
        parser = build_parser()
        subparsers_actions = [action for action in parser._actions if action.__class__.__name__ == "_SubParsersAction"]
        self.assertEqual(len(subparsers_actions), 1)
        choices = set(subparsers_actions[0].choices)
        expected = {spec.name for spec in COMMAND_SPECS}
        for spec in COMMAND_SPECS:
            expected.update(spec.aliases)
        self.assertTrue(expected.issubset(choices))

    def test_every_spec_has_a_cli_builder_callback(self):
        for spec in COMMAND_SPECS:
            self.assertTrue(callable(spec.cli_builder))

    def test_registry_backed_builders_cover_all_named_commands(self):
        spec_names = {spec.name for spec in COMMAND_SPECS}
        self.assertTrue(set(CLI_BUILDERS).issubset(spec_names))
        for spec in COMMAND_SPECS:
            self.assertIn(spec.name, CLI_BUILDERS)
            self.assertIs(spec.cli_builder, CLI_BUILDERS[spec.name])

    def test_command_modules_do_not_define_duplicate_cmd_handlers(self):
        commands_dir = Path(__file__).resolve().parents[1] / "brand_gen" / "commands"
        handler_owners: dict[str, list[str]] = defaultdict(list)
        for path in sorted(commands_dir.glob("*.py")):
            module = ast.parse(path.read_text())
            for node in module.body:
                if isinstance(node, ast.FunctionDef) and node.name.startswith("cmd_"):
                    handler_owners[node.name].append(path.name)
        duplicates = {name: owners for name, owners in handler_owners.items() if len(owners) > 1}
        self.assertEqual(duplicates, {})

    def test_build_parser_delegates_to_cli_adapter_with_registry_specs(self):
        sentinel = object()
        with mock.patch.object(command_registry, "build_cli_parser", return_value=sentinel) as mocked:
            result = command_registry.build_parser()
        self.assertIs(result, sentinel)
        mocked.assert_called_once_with(command_registry.COMMAND_SPECS, inspire_urls=command_registry.INSPIRE_URLS, epilog=command_registry.__doc__)

    def test_build_parser_renders_from_command_specs_metadata(self):
        synthetic = CommandSpec(
            name="synthetic-command",
            handler=lambda args: None,
            help="Synthetic command help",
            aliases=("syn",),
            cli_builder=lambda parser, *, inspire_urls: parser.add_argument("--flag", required=True),
        )
        with mock.patch.object(command_registry, "COMMAND_SPECS", [synthetic]):
            parser = command_registry.build_parser()
        subparsers_actions = [action for action in parser._actions if action.__class__.__name__ == "_SubParsersAction"]
        self.assertEqual(len(subparsers_actions), 1)
        choices = subparsers_actions[0].choices
        self.assertIn("synthetic-command", choices)
        self.assertIn("syn", choices)
        parsed = parser.parse_args(["synthetic-command", "--flag", "value"])
        self.assertEqual(parsed.command, "synthetic-command")
        self.assertEqual(parsed.flag, "value")
        self.assertIn("Synthetic command help", parser.format_help())


if __name__ == "__main__":
    unittest.main()
