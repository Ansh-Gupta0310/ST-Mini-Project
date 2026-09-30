from solution import remove_Occ

def test_remove_Occ_first_and_last_occurrence():
    assert remove_Occ("hello", "l") == "heo"

def test_remove_Occ_character_not_found():
    assert remove_Occ("hello", "z") == "hello"

def test_remove_Occ_only_one_occurrence():
    assert remove_Occ("hello", "h") == "hello"

def test_remove_Occ_multiple_occurrences():
    assert remove_Occ("abracadabra", "a") == "brcdbr"

def test_remove_Occ_empty_string():
    assert remove_Occ("", "a") == ""

def test_remove_Occ_character_at_start_and_end():
    assert remove_Occ("xabc", "x") == "abc"

def test_remove_Occ_character_at_end_only():
    assert remove_Occ("abc", "c") == "abc"

def test_remove_Occ_character_at_start_only():
    assert remove_Occ("abc", "a") == "abc"

def test_remove_Occ_single_character_string():
    assert remove_Occ("a", "a") == "a"

def test_remove_Occ_two_characters_same():
    assert remove_Occ("aa", "a") == "aa"
