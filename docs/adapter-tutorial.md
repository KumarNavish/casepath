# Local evidence-adapter tutorial

The minimal provider-neutral boundary is `source.register@1`. Start from
[`examples/local_source_adapter.py`](../examples/local_source_adapter.py), which
constructs the persistent local artifact registry adapter without network or
credential access.

Validate a candidate in an isolated temporary root:

```bash
./bin/casepath adapter-check examples/local_source_adapter.py
```

The module must be one regular Python file exporting `build_adapter(root)`.
The returned object must declare `capability_id == "source.register@1"`, a
stable implementation identity, and `stage`, `execute`, `status`, `reconcile`,
and `cancel` methods. The check rejects network/subprocess imports and never
opens the persistent product journal.

An adapter registers bytes; it does not decide a claim. Semantic capability,
implementation adapter identity, source observation, interpretation, decision,
and action receipt remain separate records. Never accept caller-authored fact
authority or use an adapter result without verifying its content, locator,
action, session, loop, and record-version bindings.
