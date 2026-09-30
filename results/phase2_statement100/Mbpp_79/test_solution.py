from solution import word_len

def test_word_len_even_length():
    assert word_len("Hadoop") == False

def test_word_len_odd_length():
    assert word_len("Python") == True

def test_word_len_empty_string():
    assert word_len("") == True

def test_word_len_single_character():
    assert word_len("a") == True

def test_word_len_two_characters():
    assert word_len("ab") == True
