from solution import remove_Occ

def test_remove_Occ_no_occurrence():
    assert remove_Occ("hello", "x") == "hello"

def test_remove_Occ_single_occurrence():
    assert remove_Occ("hello", "e") == "hello"

def test_remove_Occ_two_occurrences():
    assert remove_Occ("hello", "l") == "heo"

def test_remove_Occ_multiple_occurrences_more_than_two():
    assert remove_Occ("abracadabra", "a") == "brcdbr"

def test_remove_Occ_empty_string():
    assert remove_Occ("", "a") == ""

def test_remove_Occ_character_at_start_and_end():
    assert remove_Occ("aba", "a") == "b"

def test_remove_Occ_character_at_start_only():
    assert remove_Occ("abca", "a") == "bca"

def test_remove_Occ_character_at_end_only():
    assert remove_Occ("abca", "a") == "bca"

def test_remove_Occ_all_same_characters():
    assert remove_Occ("aaaa", "a") == "aa"
