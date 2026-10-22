# Web API v1 compatibility contract

`openapi-v1.json` freezes the public FastAPI surface currently served under `/api/v1/`. It is
generated from the application with optional preview, network, and local-model features disabled,
so generation does not read user data, access the network, or load model weights.

Run the following command after an intentional API change:

```bash
make api-contract
```

Review the JSON diff and then run:

```bash
make api-contract-check
cd frontend && npm run api:generate && npm run api:check
```

The generated `frontend/src/api/generated.ts` file is the Vue client's source of API response types;
do not edit it directly. Continuous integration checks both generated artifacts. A change to paths,
operations, parameters, request bodies, response schemas, validation constraints, or component
schemas therefore requires an explicit update to the contract and generated TypeScript diff.

## Compatibility policy

Within API v1, additions are normally compatible when existing clients can ignore them. Examples
include a new endpoint, a new optional request property, or a new optional response property.

The following changes are breaking and must not be published silently within v1:

- removing or renaming a path, operation, parameter, property, status code, or enum value;
- making an optional input required or narrowing an accepted input constraint;
- changing a property type or the meaning of an existing success response;
- adding a required response property when strict clients may reject it;
- changing authentication, privacy, network-access, or confirmation requirements.

A required breaking change needs a new versioned route and a documented migration path. The old v1
route remains available for the support period described in `MAINTENANCE.md`.

## Scope

The contract covers the Web product API only. It excludes frontend routes, local timing-study tools,
benchmark commands, release tooling, and the separately frozen CLI/JSON contract. Presence of the
optional VLM endpoint in the schema does not enable that feature: its runtime configuration, model
verification, photo-scene gate, editable preview, risk review, and user confirmation remain required.
