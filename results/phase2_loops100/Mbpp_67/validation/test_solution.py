from solution import bell_number


def test_bell_number_zero():
    assert bell_number(0) == 1


def test_bell_number_one():
    assert bell_number(1) == 1


def test_bell_number_two():
    assert bell_number(2) == 2


def test_bell_number_three():
    assert bell_number(3) == 5


def test_bell_number_four():
    assert bell_number(4) == 15


def test_bell_number_five():
    assert bell_number(5) == 52


def test_bell_number_six():
    assert bell_number(6) == 203


def test_bell_number_seven():
    assert bell_number(7) == 877


def test_bell_number_eight():
    assert bell_number(8) == 4140


def test_bell_number_nine():
    assert bell_number(9) == 21147


def test_bell_number_ten():
    assert bell_number(10) == 115975


def test_bell_number_eleven():
    assert bell_number(11) == 678570


def test_bell_number_twelve():
    assert bell_number(12) == 4213597


def test_bell_number_thirteen():
    assert bell_number(13) == 27644437


def test_bell_number_fourteen():
    assert bell_number(14) == 190899322


def test_bell_number_fifteen():
    assert bell_number(15) == 1382958545
