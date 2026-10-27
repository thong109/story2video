"""Consistent child proportions and scene height for humanoid characters."""
HUMANOID = ('human', 'ghost', 'corpse')


def age_of(spec):
    try:
        return max(1, min(120, int(spec.get('age', 25))))
    except (TypeError, ValueError):
        return 25


def height_scale(spec):
    if spec.get('kind', 'human') not in HUMANOID:
        return 1.0
    age = age_of(spec)
    if age >= 12:
        return 1.0
    if age <= 3:
        return 0.50
    if age <= 6:
        return 0.60
    if age <= 9:
        return 0.68
    return 0.76
