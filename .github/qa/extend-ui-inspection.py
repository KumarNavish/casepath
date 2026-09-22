from pathlib import Path
p=Path('.github/qa/release-browser.mjs');s=p.read_text()
s=s.replace("  await snapshot(page,'06-reviewed-mobile',390,844);await axe(page,'reviewed-mobile');", """  await page.locator('.cp-work-column').evaluate(el=>el.scrollTop=0);
  await snapshot(page,'06-reviewed-mobile',390,844);await axe(page,'reviewed-mobile');
  const action=await page.locator('#cwLoopCommit').boundingBox();
  observation.mobile_next_action=action;
  check('The current evidence action is visible without scrolling on mobile',Boolean(action)&&action.y>=0&&action.y+action.height<=844);
  check('The compact summary follows the next action',await page.evaluate(()=>Boolean(document.querySelector('#cwLoopWorkbench').compareDocumentPosition(document.querySelector('#awClaimWork'))&Node.DOCUMENT_POSITION_FOLLOWING)));
""")
s=s.replace("  await snapshot(page,'07-process-desktop');", "  await page.locator('#awProcessCanvas').scrollIntoViewIfNeeded();\n  await snapshot(page,'07-process-desktop');await axe(page,'process-desktop');")
s=s.replace("  await snapshot(page,'08-evidence-desktop');", "  await page.locator('#cpPanel-evidence').scrollIntoViewIfNeeded();\n  await snapshot(page,'08-evidence-desktop');await axe(page,'evidence-desktop');")
s=s.replace("  await snapshot(page,'10-agent-review-desktop');", "  await page.locator('#awTimeline').scrollIntoViewIfNeeded();\n  await snapshot(page,'10-agent-review-desktop');await axe(page,'agent-review-desktop');")
s=s.replace("  await snapshot(page,'11-agent-review-mobile',390,844);", "  await snapshot(page,'11-agent-review-mobile',390,844);await axe(page,'agent-review-mobile');")
s=s.replace("  observation.status='baseline_captured';", "  observation.status='ui_iteration_captured';")
p.write_text(s)
