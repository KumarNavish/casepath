# Original 150-claim intake workspace

The main application now uses `synthetic-150`. It contains all 150 original
intake packets, not copied or newly generated filler claims. Each packet opens
in the same source-grounded workbench. The separate `synthetic-dev-60` package
and its 60 claim bindings remain byte-identical for legacy regression tests.

## Source identity and boundaries

Source manifest SHA-256:
`638630886a1d291dfe9009839eb0519130e56700bb4d454277ce2e45c6044f4c`.

Operational corpus manifest SHA-256:
`921e7ce79ecb3ee7811b6ee2530b4f6dc5c302da3ade6afbdae0b92fd822790e`.

The operational bundle has 150 claims and 660 bound files, excluding its own
manifest. Its original visible packet materials are 150 customer communications
and 57 attachments: 47 PDFs and 10 JPEG images. Message-only claims say so;
no additional attachment is invented. The bundle also retains the exact source
registries and static policy documents needed by the existing workflow.

Only intake inputs, source registries, original documents, static rules and the
license were copied. No benchmark gold, sealed answers, expected outputs,
selected paths or research result records were imported. The 150 inputs have
been inspected in product work and must not be called untouched evaluation
inputs. Local use does not imply permission to publish the full source package.
