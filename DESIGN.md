---
version: alpha
name: CasePath
description: Visual language for the synthetic claims workbench
colors:
  cp-ink: "#202125"
  cp-muted: "#65676f"
  cp-line: "#e7e7ec"
  cp-chrome: "#f5f5f7"
  cp-soft: "#fafafb"
  cp-accent: "#244e72"
  cp-green: "#32664a"
  cp-amber: "#866027"
---

## Overview

CasePath helps a claims handler answer why the current action follows from the claim record. The interface is precise, quiet, and editorial: original sources and the active decision receive attention before review machinery or technical receipts.

## Colors

Use white for reading surfaces and `cp-accent` for the active path, selected object, and primary action. Use `cp-amber` for unresolved attention and `cp-green` for recorded acceptance. Supporting chrome and rules stay quiet. Pair each color state with a text label or other visible cue.

## Typography

Use the workbench's plain system sans serif. Give the current claim question and action the strongest weight; keep labels, timestamps, and secondary explanations compact. Use sentence case and explain uncertainty in ordinary language. Put hashes and internal identifiers behind named disclosures.

## Layout

The desktop workbench keeps the original packet at left, the active handling path or reasoning lens in the center, and one next action at right. Opening **Why this?** reveals the chain from action through evidence, fact, obligation, and process to source support while the action remains visible. On narrow screens, put the action first, the path and explanation next, and the source packet in an accessible drawer.

Selecting a process node or evidence item explores the saved record. Keep the authoritative current step distinguishable from the selected step. After a saved action changes the path, return the explanation to the new current step. Evidence, the full process, and the work log remain secondary views of the same claim.

## Elevation & Depth

Use alignment, whitespace, light tonal shifts, and thin rules to separate functions. Keep source documents visually distinct as reading surfaces. Avoid nested cards and heavy shadows in the decision path.

## Components

Show one primary action at a time. Name what it will do before it runs, and distinguish source checking from customer communication or claim settlement. The reasoning lens uses an ordered chain with direct controls for linked evidence, process steps, and exact accepted passages.

An opened document is not accepted evidence. Show an accepted passage only when a saved observation links it to the original packet. Unknown, conditional, missing, insufficient, and uncertain states stay explicit. A completed agent review remains a review record; it does not turn the claim into a completed decision. Keep role handoffs, event history, rule details, and receipts inspectable on demand.

Use native buttons, tabs, and disclosures with visible keyboard focus. A saved state change can use a brief reveal, but the meaning must be clear without animation and reduced-motion preferences must be respected.

## Do's and Don'ts

- Do keep the original source and current action reachable from the explanation.
- Do use exact status language when a passage is recorded but a requirement remains unresolved.
- Don't invent a document request, source acceptance, process completion, or legal conclusion.
- Don't use gradients, glow, generic agent avatars, decorative motion, or a dashboard grid in the claim decision.
