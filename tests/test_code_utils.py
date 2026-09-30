"""Offline tests for agents/code_utils.py."""
from agents.code_utils import defines_function, extract_python_code, number_lines, remove_example_usage

FUNC = "def add(a, b):\n    return a + b\n"


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
