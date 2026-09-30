from solution import remove_Occ

def test_remove_Occ_normal_case():
    assert remove_Occ("hello", "l") == "heo"

def test_remove_Occ_char_not_found():
    assert remove_Occ("hello", "z") == "hello"

def test_remove_Occ_single_occurrence():
    assert remove_Occ("hello", "e") == "hello"

def test_remove_Occ_empty_string():
    assert remove_Occ("", "a") == ""

def test_remove_Occ_multiple_occurrences():
    assert remove_Occ("abracadabra", "a") == "brcdbr"

def test_remove_Occ_first_and_last_same_position():
    assert remove_Occ("a", "a") == "a"

def test_remove_Occ_two_occurrences():
    assert remove_Occ("banana", "n") == "banaa"
