"""Zero-call benchmark floor. It is not a headline competitor."""
def alias_overlap(text, aliases):
    lowered = text.casefold()
    return sorted(alias for alias in aliases if alias.casefold() in lowered)
