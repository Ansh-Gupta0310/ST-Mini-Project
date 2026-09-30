"""Offline tests for agents/code_utils.py."""
from agents.code_utils import (check_test_file, defines_function, describe_missing, extract_python_code,
                              merge_test_files, number_lines, remove_example_usage)

FUNC = "def add(a, b):\n    return a + b\n"

# The worked example from PROJECT_PLAN.md §2.3, covered by sign(5) only.
SIGN = "def sign(x):\n    if x > 0:\n        return 1\n    elif x < 0:\n        return -1\n    return 0\n"
MISSING_LINES = [4, 5, 6]
MISSING_BRANCHES = [[2, 4], [4, 5], [4, 6]]


def test_fenced_python_block_with_text_around_it():
    assert extract_python_code(f"Here you go:\n```python\n{FUNC}```\nHope this helps!") == FUNC


def test_fence_language_tag_variants():
    for tag in ("py", "Python", "python3", ""):
        assert extract_python_code(f"```{tag}\n{FUNC}```") == FUNC, tag


def test_first_python_block_wins():
    reply = f"```python\n{FUNC}```\nUsage:\n```python\nassert add(1, 2) == 3\n```"
    assert extract_python_code(reply) == FUNC


def test_unfenced_code_is_accepted():
    assert extract_python_code(FUNC) == FUNC


def test_windows_line_endings_are_normalised():
    assert extract_python_code("```python\r\n" + FUNC.replace("\n", "\r\n") + "```") == FUNC


def test_indented_block_is_dedented():
    indented = "".join("    " + line + "\n" for line in FUNC.splitlines())
    assert extract_python_code(f"```python\n{indented}```") == FUNC


def test_reply_cut_off_before_the_closing_fence():
    assert extract_python_code(f"```python\n{FUNC}") == FUNC


def test_truncated_code_is_rejected():
    assert extract_python_code("```python\ndef add(a, b):\n    return (a +\n") is None


def test_prose_or_empty_reply_is_rejected():
    assert extract_python_code("I cannot help with that request.") is None
    assert extract_python_code("") is None
    assert extract_python_code("```python\n```") is None


def test_remove_example_usage():
    code = ("import math\n\nLIMIT = 10\n\n\n" + FUNC
            + '\n\nprint(add(1, 2))\nassert add(2, 2) == 4\n\nif __name__ == "__main__":\n    print(add(3, 4))\n')
    assert remove_example_usage(code) == "import math\n\nLIMIT = 10\n\n\n" + FUNC


def test_remove_example_usage_handles_reversed_main_guard():
    assert remove_example_usage(FUNC + "\nif '__main__' == __name__:\n    add(1, 2)\n") == FUNC


def test_remove_example_usage_leaves_clean_code_untouched():
    code = '"""Module docstring."""\n\n\n' + FUNC
    assert remove_example_usage(code) == code


def test_defines_function():
    assert defines_function(FUNC, "add")
    assert not defines_function(FUNC, "sub")
    assert not defines_function("class A:\n    def add(self):\n        pass\n", "add")  # a method is not enough
    assert not defines_function("def broken(:\n", "broken")


def test_number_lines():
    assert number_lines("a = 1\nb = 2\n") == "  1 | a = 1\n  2 | b = 2"


# --- Phase 2 helpers ---------------------------------------------------------------------

def test_describe_missing_names_every_uncovered_line_and_branch():
    described = describe_missing(SIGN, MISSING_LINES, MISSING_BRANCHES)
    assert described.splitlines() == [
        "- line 4 `elif x < 0:` was never run",
        "- line 5 `return -1` was never run",
        "- line 6 `return 0` was never run",
        "- line 2 `if x > 0:` never went to line 4 `elif x < 0:`",
        "- line 4 `elif x < 0:` never went to line 5 `return -1`",
        "- line 4 `elif x < 0:` never went to line 6 `return 0`",
    ]


def test_describe_missing_explains_a_negative_target_as_never_exiting():
    loop = "def count(n):\n    while n:\n        n -= 1\n    return n\n"
    assert describe_missing(loop, [], [[2, -1]]) == "- line 2 `while n:` never exited the function from there"


def test_describe_missing_with_nothing_missing_says_so():
    assert "nothing" in describe_missing(SIGN, [], [])


def test_describe_missing_survives_line_numbers_outside_the_code():
    assert describe_missing(SIGN, [99], [[1, 99]]) == ("- line 99 `?` was never run\n"
                                                       "- line 1 `def sign(x):` never went to line 99 `?`")


def test_merge_renames_a_new_test_whose_name_already_exists():
    first = "from solution import sign\nimport pytest\n\n\ndef test_a():\n    assert sign(1) == 1\n"
    second = "from solution import sign\n\n\ndef test_a():\n    assert sign(-1) == -1\n\n\ndef test_b():\n    pass\n"
    merged = merge_test_files(first, second, 2)
    assert merged == ("from solution import sign\nimport pytest\n\n\n"
                      "def test_a():\n    assert sign(1) == 1\n\n\n"
                      "def test_a_r2():\n    assert sign(-1) == -1\n\n\n"
                      "def test_b():\n    pass\n")
    assert check_test_file(merged, "sign") is None


def test_merge_keeps_helpers_decorators_and_every_import_once():
    first = ("import pytest\nfrom solution import sign\n\n\nCASES = [1, 2]\n\n\n"
             "@pytest.mark.parametrize('x', CASES)\ndef test_positive(x):\n    assert sign(x) == 1\n")
    second = ("from solution import sign\nimport math\n\n\ndef helper():\n    return math.floor(-0.5)\n\n\n"
              "def test_negative():\n    assert sign(helper()) == -1\n")
    merged = merge_test_files(first, second, 2)
    assert merged.count("from solution import sign") == 1
    assert merged.index("import math") < merged.index("CASES = [1, 2]")  # imports stay at the top
    assert "@pytest.mark.parametrize('x', CASES)" in merged
    assert merged.index("def test_positive") < merged.index("def helper")  # round 1 first, then round 2
    compile(merged, "test_solution.py", "exec")


def test_merge_ignores_a_new_file_that_does_not_parse():
    good = "from solution import sign\n\n\ndef test_a():\n    assert sign(1) == 1\n"
    assert merge_test_files(good, "def test_b(:\n", 2) == good


def test_check_test_file_accepts_a_file_that_follows_the_rules():
    assert check_test_file("from solution import sign\n\n\ndef test_zero():\n    assert sign(0) == 0\n",
                           "sign") is None
    assert check_test_file("import solution\n\n\ndef test_zero():\n    assert solution.sign(0) == 0\n",
                           "sign") is None


def test_check_test_file_rejects_a_file_that_defines_the_function_under_test():
    own_copy = ("from solution import sign\n\n\ndef sign(x):\n    return 0\n\n\n"
                "def test_zero():\n    assert sign(0) == 0\n")
    assert "defines sign" in check_test_file(own_copy, "sign")
    rebound = "from solution import sign\n\n\nsign = lambda x: 0\n\n\ndef test_zero():\n    assert sign(0) == 0\n"
    assert "defines sign" in check_test_file(rebound, "sign")


def test_check_test_file_rejects_the_other_broken_rules():
    assert "does not parse" in check_test_file("def test_a(:\n", "sign")
    assert "test_" in check_test_file("from solution import sign\n\n\ndef helper():\n    pass\n", "sign")
    assert "solution" in check_test_file("def test_a():\n    assert True\n", "sign")
    randomised = ("import random\nfrom solution import sign\n\n\n"
                  "def test_a():\n    assert sign(random.randint(1, 9)) == 1\n")
    assert "random" in check_test_file(randomised, "sign")
