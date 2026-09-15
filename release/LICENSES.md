# Licences

## This package

Benchmark data, generator, evaluator, analysis and the method implementation are released under the licence
in the repository root `LICENSE`. The CasePath product code included in `product_adapter/` is covered by
that same repository licence.

## Generated content

Every episode in `benchmark/data/` is synthetic text produced by a model from a machine-generated brief. It
depicts no real person, organisation, claim or document. Names, addresses, amounts and dates are invented.

## Model providers

Episodes and arm executions were produced through OpenRouter against models from OpenAI and Anthropic.
Provider terms govern the use of those services; nothing in this package redistributes provider weights or
outputs beyond the generated episode text and the recorded plans, which are included so the results can be
audited.

## Third-party dependencies

Pinned in `environment.lock`, each under its own licence.
