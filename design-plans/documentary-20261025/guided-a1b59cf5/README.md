# CasePath — guided documentary

**A 4:58.4 standalone film that establishes understanding before demonstrating behavior.** All necessary explanation, attention guidance and pacing are baked into the image. Music is optional.

## Watch

- [Guided documentary with music](CasePath_Guided_Documentary_Music.mp4)
- [Identical picture, silent edition](CasePath_Guided_Documentary_Silent.mp4)

Both exports are 1920 × 1080, 30 fps, H.264, 8,952 frames. The music edition adds a freshly composed 48 kHz stereo score aligned with this edit's chapter clock.

## What this edition changes

The film now begins with the real-world question: **is this rent increase notice valid?** It then builds one mental model: documents → checks → proposed answer → human review.

Each substantial new context receives a short introduction. Selective dimming, a single clear spotlight, restrained camera movement and concise explanations establish what the viewer is seeing and why it matters. Relationships are drawn before the associated action proceeds. Outcomes hold long enough to connect the action to its consequence.

Within an understood view, recorded interactions continue without a new tutorial for every click. The viewer follows a marked passage into a proposed finding, a finding into a requirement, and the requirements into a scoped assessment and an unsent draft.

The later case is explicitly introduced as **Drew Shaw's**. A separate chronology graphic shows Drew's original notice on 22 November 2025 and the later email on 25 November. The checklist is reused; the dates and facts come from Drew's records. The film explicitly explains why this different case reaches the same proposed result.

## Chapters

| Starts | Visual lesson |
|---|---|
| 0:00.0 | The question |
| 0:22.5 | Read the evidence |
| 1:14.1 | Connect the checks |
| 1:35.1 | Check the source |
| 1:50.2 | Apply the rule |
| 2:11.5 | Inspect the supporting files |
| 2:23.3 | Understand the assessment |
| 3:08.6 | Prepare the next step |
| 3:30.5 | Reuse the questions |
| 4:36.1 | Keep the reasoning visible |

## Project state recovered for this edition

- Published product: https://casepath-autonomous.kumarnavish.chatgpt.site
- Recorded presentation: https://casepath-autonomous.kumarnavish.chatgpt.site/?present=1#autonomous/demonstration
- Bound product source: `a1b59cf5d78662b35790a11cfd2d46851310482d`.
- Evidence branch base before this edition: `8e0509f84b1ef21262230243f9aa9ebaeb675d25`.
- Canonical integration branch: `codex/casepath-causal-experience-integration-20261009`.
- The clean capture checked the public frontend's deployment identity and four assets against the sealed source, and checked that the API reported the same source with read-only operation.
- This release changes the film and its evidence package. It does not change or redeploy the product application.
- Earlier release tests are retained in their original release package. They are not relabelled as tests run for this film edit.

## Source and editorial integrity

The clean 4K recording contains 2,957 frames at 30 fps. The edit maps that source clock once, in order, and adds explanation and reading time. Editorial title cards, camera reframing, dissolves, focus cues and source-bound orientation plates are intentional parts of the film.

This is **not** a claim that every original pixel appears unchanged on screen or that the edited runtime measures processing speed. The legal-test emphasis is editorial guidance over a recorded completed view. No new inference is performed, and no invented product state is shown.

Product quotations remain in their original wording. The authored date graphic is visibly separate from the product interface. Its two dates are verified against exact, hash-checked source artifacts in the sealed recorded-operation fixture. The independent public date-fetch attempt did not complete; that limitation is recorded in [later-case-date-proof.json](later-case-date-proof.json). The public UI capture and its deployment identity checks did complete.

The earlier checklist is described as coming from an earlier recorded case. The film does not assert that its origin is the first showcased case. Proposed findings, unresolved questions, the unsent draft and responsible human review remain explicit throughout.

## Review and verification

[editorial-review.md](editorial-review.md) records the independent first-time editorial reading, the concrete defects it found and their corrections.

[film-qa.json](film-qa.json) records the encoded-frame checks and temporal sequence inspections. The compositor also checks source hashes, orientation-plate provenance, frame coverage, camera bounds, title length, export dimensions, frame count and a complete video decode.

The mastering receipt checks the final music edition's complete audio/video decode, frame count, audio duration, measured loudness and true peak. It verifies that muxing preserves the silent edition's encoded video packets.

The review establishes an editorial quality assessment. It is not a human comprehension study, a claim of universal comprehension, a new legal assessment or proof of measured business results. No subjective listening claim is made by the automated media checks.

## Reproduce the picture

The edit plan, compositor, source recording, selected source plates and receipts are included. The existing repository provides `casepath/assets/fonts/Mulish.ttf`. The compositor uses Python, Pillow and ffmpeg/ffprobe; it calls no model or paid service.

From the repository root, choose a **new, empty output directory**:

```bash
CASEPATH_PRODUCT_ROOT="$PWD" \
CASEPATH_FILM_WORK="$PWD/design-plans/documentary-20261025/guided-a1b59cf5" \
CASEPATH_FFMPEG=ffmpeg CASEPATH_FFPROBE=ffprobe \
python3 design-plans/documentary-20261025/guided-a1b59cf5/compose_guided_film.py \
  --plan design-plans/documentary-20261025/guided-a1b59cf5/edit-plan-v7.json \
  --out /tmp/casepath-guided-reproduction
```

The original clean-capture helper is retained as production evidence; it records the exact workstation paths used for this capture. Reproducing the editorial render does not require a new network capture.

## Reproduce the score and music edition

`score.py` synthesizes the original score locally with Python's standard library. Run these audio commands from this package's directory. It uses `score-timeline-final.json`; do not reuse the earlier 98-second or 279-second clocks. Use a fresh output path.

```bash
python3 score.py --timeline score-timeline-final.json \
  --out /tmp/casepath-guided-score.wav \
  --sample-rate 48000 --duration 298.4 --peak-dbfs -7

python3 master_and_mux.py \
  --silent /tmp/casepath-guided-reproduction/CasePath_Guided_Documentary_Silent.mp4 \
  --score /tmp/casepath-guided-score.wav \
  --out /tmp/CasePath_Guided_Documentary_Music.mp4 \
  --expected-frames 8952 --ffmpeg ffmpeg --ffprobe ffprobe
```

The large intermediate PCM master and redundant preview renders are intentionally omitted. Their deterministic recipes and receipts are retained. `package-manifest.json` lists the delivered files, sizes and SHA-256 hashes.

Raw ffmpeg diagnostic text is archived losslessly as gzip in media-evidence. Its archive manifest retains the original names, byte counts and hashes; this preserves terminal progress whitespace without treating it as authored source code.
