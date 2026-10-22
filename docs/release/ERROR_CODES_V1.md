# Public error-code contract v1

`error-codes-v1.json` is the machine-readable inventory of symbolic errors exposed by the v1 Web
API and CLI. It is generated from the actual exception sites rather than maintained as a separate
handwritten list.

Generate and review the contract after an intentional change:

```bash
make error-contract
make error-contract-check
```

The API section records whether an error is returned immediately in the standard HTTP error envelope
or later through task status/report data. Immediate errors list every HTTP status currently associated
with that symbolic code. A code can have more than one status when its meaning is shared across
different resource contexts.

The CLI section records every supported process exit code for each symbolic error. It includes codes
raised directly by the command layer, plan validation errors propagated by the image/document plan
loaders, and input-inspection errors propagated while those plans are built.

Within v1, removing or renaming a code, changing its delivery surface, or changing its HTTP/CLI status
is a compatibility change that requires review. Adding a code is additive only when existing clients
can continue treating unknown codes by their HTTP status or CLI exit code. User-facing messages may be
improved without changing the symbolic code and must not be parsed as stable identifiers.

Warning and acknowledgement codes are outside this file because they are successful plan metadata,
not errors. Their current schemas remain covered by the OpenAPI and CLI plan contracts.
