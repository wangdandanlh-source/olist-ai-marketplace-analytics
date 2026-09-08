# Security and data boundary

Static Dashboard; no credentials required at runtime, no external tracker, no backend. Only reviewed aggregate JSON is loaded. Raw datasets, per-review text, databases and model weights are excluded.

If accidental exposure is discovered, stop distribution and remove the affected artifact from the public repository. After a repository exists, a project Issue may report the affected file and general problem; never post the exposed value, personal data or credential itself. No private email or nonexistent reporting URL is provided.

Before any later publication, repeat privacy, secret, relative-path, raw-data, reference-image and dependency checks on the exact final file set. .gitignore is a convenience, not a substitute for an allowlist review.
