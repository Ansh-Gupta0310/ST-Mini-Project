from solution import get_Char

def test_empty_string():
    assert get_Char("") == "a"

def test_single_char():
    assert get_Char("a") == "b"

def test_two_chars():
    assert get_Char("ab") == "c"

def test_three_chars():
    assert get_Char("abc") == "f"

def test_loop_skip_body():
    assert get_Char("aaaa") == "a"

def test_loop_one_iteration():
    assert get_Char("z") == "z"

def test_loop_multiple_iterations():
    assert get_Char("xyz") == "d"
