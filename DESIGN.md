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

CasePath helps a claims handler read a claim, see its path, understand what is needed, and draft the request. The interface is precise, quiet, and editorial: original sources, the current step, and the next question receive attention before technical receipts.

## Colors

Use white for reading surfaces and `cp-accent` for the active path, selected object, and primary action. Use `cp-amber` for unresolved attention and `cp-green` for recorded acceptance. Supporting chrome and rules stay quiet. Pair each color state with a text label or other visible cue.

## Typography

Use the workbench's plain system sans serif. Give the current claim question and action the strongest weight; keep labels, timestamps, and secondary explanations compact. Use sentence case and explain uncertainty in ordinary language. Put hashes and internal identifiers behind named disclosures.

## Layout

The desktop workbench keeps the original packet at left, the handling path in the center, and needs with the next action at right. **Why this step** connects the action, need, condition quote, step, and article. At 900 px and below, stack path, needs, and sources; keep the next action in a bottom bar.

Selecting a step or document explores the saved record. Keep the authoritative current step distinguishable from the selected step. After a saved action changes the path, return the explanation to the new current step. The Timeline holds recorded review lines and handler actions.

## Elevation & Depth

Use alignment, whitespace, light tonal shifts, and thin rules to separate functions. Keep source documents visually distinct as reading surfaces. Avoid nested cards and heavy shadows in the decision path.

## Components

Show one primary action at a time. Name what it will do before it runs, and distinguish source checking from customer communication or claim settlement. The reasoning canvas uses an ordered path, grouped needs, and direct controls for linked sources and exact accepted passages.

An opened document is not accepted evidence. Show an accepted passage only when a saved observation links it to the original packet. Unknown, conditional, missing, insufficient, and uncertain states stay explicit. A completed agent review remains a review record; it does not turn the claim into a completed decision. Keep role handoffs, event history, rule details, and receipts inspectable on demand.

Use native buttons and disclosures with visible keyboard focus. The first-run walk follows source, review, needs, What if, and draft. Reviewer mode labels provenance on displayed objects and keeps study measurements separate from product behavior.

## Do's and Don'ts

- Do keep the original source and current action reachable from the explanation.
- Do use exact status language when a passage is recorded but a requirement remains unresolved.
- Don't invent a document request, source acceptance, process completion, or legal conclusion.
- Don't use gradients, glow, generic agent avatars, decorative motion, or a dashboard grid in the claim decision.
