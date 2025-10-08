from standby.hint import Default, Required, Validated


def test_default():
    d = Default(10)
    assert d.value == 10


def test_required():
    r1 = Required()
    assert r1.is_required is True

    r2 = Required(False)
    assert r2.is_required is False


def test_validated():
    def is_even(x: int) -> bool:
        return x % 2 == 0

    v = Validated(is_even)
    assert v.validator(2) is True
    assert v.validator(3) is False
