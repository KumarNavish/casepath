"""Reference aggregation for CasePath-Bench-v3."""
def macro(values):
    if not values: raise ValueError('empty metric cell')
    return sum(values) / len(values)

def failure_score(direction):
    return 0.0 if direction == 'higher' else 1.0
