import unittest
from dataclasses import make_dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from rod.libs.py.bazel.rc import (
    bazelrc_obj_to_str,
    bazelrc_parse,
    bazelrc_str_to_obj,
)


class TestBazelrcStrToObj(unittest.TestCase):
    def test_parses_command_and_options(self):
        result = bazelrc_str_to_obj("build --config ci --jobs 8")

        self.assertTrue(result.build)
        self.assertEqual(result.o_config, "ci")
        self.assertEqual(result.o_jobs, "8")

    def test_replaces_dashes_in_command_names(self):
        result = bazelrc_str_to_obj("test-fast --test_output errors")

        self.assertTrue(result.test_fast)
        self.assertEqual(result.o_test_output, "errors")

    def test_respects_shell_quoted_values(self):
        result = bazelrc_str_to_obj('build --repo_env "KEY=value with spaces"')

        self.assertTrue(result.build)
        self.assertEqual(result.o_repo_env, "KEY=value with spaces")

    def test_parses_equals_options(self):
        result = bazelrc_str_to_obj("build --config=ci --jobs=8")

        self.assertTrue(result.build)
        self.assertEqual(result.o_config, "ci")
        self.assertEqual(result.o_jobs, "8")

    def test_parses_try_import_value(self):
        result = bazelrc_str_to_obj("try-import %workspace%/.bazelrc.user")

        self.assertEqual(result.try_import, "%workspace%/.bazelrc.user")


class TestBazelrcObjToStr(unittest.TestCase):
    def test_writes_command_and_options(self):
        obj = bazelrc_str_to_obj("build --config ci --jobs 8")

        result = bazelrc_obj_to_str(obj)

        self.assertEqual(result, "build --config ci --jobs 8")

    def test_ignores_false_boolean_fields(self):
        BazelRc = make_dataclass(
            "BazelRc",
            [
                ("build", bool),
                ("test", bool),
                ("o_config", str),
            ],
        )
        obj = BazelRc(build=True, test=False, o_config="ci")

        result = bazelrc_obj_to_str(obj)

        self.assertEqual(result, "build --config ci")

    def test_shell_quotes_values_with_spaces(self):
        obj = bazelrc_str_to_obj('build --repo_env "KEY=value with spaces"')

        result = bazelrc_obj_to_str(obj)

        self.assertEqual(result, "build --repo_env 'KEY=value with spaces'")

    def test_writes_try_import_value(self):
        obj = bazelrc_str_to_obj("try-import %workspace%/.bazelrc.user")

        result = bazelrc_obj_to_str(obj)

        self.assertEqual(result, "try-import %workspace%/.bazelrc.user")


class TestBazelrcParse(unittest.TestCase):
    def test_ignores_comments_and_empty_lines(self):
        with TemporaryDirectory() as tmp_dir:
            bazelrc_file = Path(tmp_dir) / ".bazelrc"
            bazelrc_file.write_text(
                "\n"
                "# comment only\n"
                "build --config=ci # inline comment\n"
                "try-import %workspace%/.bazelrc.user\n",
                encoding="utf-8",
            )

            result = bazelrc_parse(str(bazelrc_file))

        self.assertEqual(len(result), 2)
        self.assertTrue(result[0].build)
        self.assertEqual(result[0].o_config, "ci")
        self.assertEqual(result[1].try_import, "%workspace%/.bazelrc.user")


if __name__ == "__main__":
    unittest.main()
