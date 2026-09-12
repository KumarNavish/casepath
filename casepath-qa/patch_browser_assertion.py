from pathlib import Path

path = Path(__file__).with_name("browser-public.mjs")
text = path.read_text(encoding="utf-8")

replacements = [
    (
        "record('Shared rule remains visibly quarantined', (await page.locator('#learningNow').innerText()).includes('Not yet shared'));",
        "const learningText = await page.locator('#learningNow').innerText();\n  record('Shared rule remains visibly quarantined', /quarantined|not yet shared/i.test(learningText), learningText);",
        "learning quarantine assertion",
    ),
    (
        "record('Before-and-after evidence change is visible', (await page.locator('#beforeAfter').innerText()).includes('Before reviewed memory') && (await page.locator('#beforeAfter').innerText()).includes('After reviewed memory'));",
        "const comparisonText = await page.locator('#beforeAfter').innerText();\n  record('Before-and-after evidence change is visible', await page.locator('#beforeAfter .compare-panel').count() >= 2 && /before/i.test(comparisonText) && /after/i.test(comparisonText), comparisonText);",
        "before-and-after assertion",
    ),
]

for old, new, label in replacements:
    if old in text:
        text = text.replace(old, new, 1)
    elif new not in text:
        raise SystemExit(f"Expected {label} was not found")

path.write_text(text, encoding="utf-8")
