from app import shares as sh


def test_equal_split_sums_to_100():
    for n in range(1, 15):
        r = sh.equal(n)
        assert sum(r) == 100 and max(r) - min(r) <= 1


def test_add_to_equal_keeps_equal():
    assert sh.after_add([100]) == [50, 50]
    assert sh.after_add([50, 50]) == [34, 33, 33]
    assert sh.after_add([34, 33, 33]) == [25, 25, 25, 25]


def test_add_keeps_proportions():
    # 70/30 + новый → новый 33, остальные 67 в пропорции 70:30
    r = sh.after_add([70, 30])
    assert sum(r) == 100 and r[2] in (33, 34) and r[0] > r[1] * 2


def test_remove_redistributes_proportionally():
    assert sh.after_remove([25, 25, 25, 25], 1) == [34, 33, 33]
    assert sh.after_remove([60, 20, 20], 0) == [50, 50]
    assert sh.after_remove([100], 0) == []


def test_zero_shares_fallback():
    assert sh.after_add([0, 0]) == [34, 33, 33]
    assert sum(sh.normalize([0, 0, 0])) == 100
