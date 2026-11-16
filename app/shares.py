"""Распределение долей офферов в потоке.

Keitaro требует, чтобы доли (share) активных офферов потока были целыми и
в сумме давали 100. Логика:

* добавление оффера — новый получает 100/n, остальные пропорционально
  ужимаются (если доли были равными, получится снова равное деление);
* удаление — освободившаяся доля раздаётся оставшимся пропорционально;
* если доли были равными (34/33/33 и т.п.), после изменения они снова
  делятся поровну — без «хвостов» от округления вроде 51/49;
* округление — методом наибольшего остатка, сумма всегда ровно 100.
"""

TOTAL = 100


def largest_remainder(weights: list[float], total: int = TOTAL) -> list[int]:
    """Целочисленное распределение `total` пропорционально `weights`."""
    if not weights:
        return []
    s = sum(weights)
    if s <= 0:
        weights = [1.0] * len(weights)
        s = float(len(weights))
    raw = [w * total / s for w in weights]
    floors = [int(x + 1e-9) for x in raw]
    rest = total - sum(floors)
    # при равных остатках приоритет у более ранних офферов
    # округляем остатки, чтобы погрешность float не ломала порядок
    order = sorted(range(len(raw)), key=lambda i: (-round(raw[i] - floors[i], 9), i))
    for i in order[:rest]:
        floors[i] += 1
    return floors


def equal(n: int) -> list[int]:
    return largest_remainder([1.0] * n)


def is_equal(shares: list[int]) -> bool:
    """Доли равные с точностью до округления (напр. 34/33/33)."""
    return bool(shares) and sum(shares) == TOTAL and shares == equal(len(shares))


def after_add(shares: list[int]) -> list[int]:
    """Доли после добавления нового оффера в конец списка."""
    n = len(shares) + 1
    if not shares or sum(shares) <= 0 or is_equal(shares):
        return equal(n)
    scale = (n - 1) / n
    k = sum(shares)
    weights = [s / k * TOTAL * scale for s in shares] + [TOTAL / n]
    return largest_remainder(weights)


def after_remove(shares: list[int], index: int) -> list[int]:
    """Доли после удаления оффера с позицией `index`."""
    rest = shares[:index] + shares[index + 1 :]
    if not rest:
        return []
    if is_equal(shares):
        return equal(len(rest))
    return largest_remainder([float(s) for s in rest])


def normalize(shares: list[int]) -> list[int]:
    return largest_remainder([float(max(s, 0)) for s in shares])
