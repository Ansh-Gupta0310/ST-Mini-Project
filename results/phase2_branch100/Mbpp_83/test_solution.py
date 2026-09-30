from solution import get_Char

def test_single_char():
    assert get_Char("a") == "a"

def test_multiple_chars():
    assert get_Char("abc") == "f"

def test_empty_string():
    assert get_Char("") == "a"

def test_all_letters():
    assert get_Char("abcdefghijklmnopqrstuvwxyz") == "a"

def test_modulo_wrap():
    assert get_Char("z") == "z"

def test_large_string():
    assert get_Char("a" * 100) == "a"
