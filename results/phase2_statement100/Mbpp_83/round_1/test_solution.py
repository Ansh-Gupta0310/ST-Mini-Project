from solution import get_Char

def test_single_char():
    assert get_Char("a") == "a"

def test_multiple_chars():
    assert get_Char("abc") == "f"

def test_empty_string():
    assert get_Char("") == "a"

def test_all_lowercase():
    assert get_Char("xyz") == "v"

def test_large_string():
    assert get_Char("a" * 100) == "a"

def test_mixed_length():
    assert get_Char("ab") == "c"
