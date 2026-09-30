from solution import word_len

def test_word_len_even_length():
    assert word_len("Hadoop") == False
    assert word_len("Python") == False

def test_word_len_odd_length():
    assert word_len("a") == True
    assert word_len("ab") == True

def test_word_len_empty_string():
    assert word_len("") == True

def test_word_len_single_char():
    assert word_len("x") == True

def test_word_len_long_even():
    assert word_len("abcdefgh") == False

def test_word_len_long_odd():
    assert word_len("abcdefghi") == True
