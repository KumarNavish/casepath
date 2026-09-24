# Hidden-test policy

One submission per team per 24 hours. Submissions return aggregate and domain scores, never item-level test labels. Evaluator code runs in a network-disabled container. Duplicate or near-duplicate submissions are cached. Test contracts remain private and hash-committed. Final paper comparisons use a frozen submission hash and image digest.

The evaluator accepts the same strict JSONL envelope used by the public dev scorer. It validates the complete 90-case test roster before scoring. Invalid, missing, duplicate, extra, or system-failed rows receive the frozen worst score; they are never silently dropped. The network-disabled evaluator resolves the submitted CandidateArtifact against the hash-committed test contract and returns only aggregate, domain, failure, and cost summaries. It never returns item-level labels, alignments, or contracts. `verify-hidden-interface` checks this public contract without opening the evaluator vault.
