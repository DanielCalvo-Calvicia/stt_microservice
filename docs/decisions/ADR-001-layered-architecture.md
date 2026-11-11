# ADR-001: The same layered layout as the other services

- **Status:** Accepted (in force since the first layout; checked by a test).
- **Date of this record:** 2026-11-05 (the decision predates it; see the history in the architecture document).

## Context

OBLIVION is a set of small HTTP microservices that Brain coordinates. They are edited by the same maintainer and by Claude, and they must be readable in the same way.

## Decision

STT follows the workspace layout: `main.py`, `main_flow/`, `composition_root/`, `application/`, `domain/`, `infrastructure/` (inbound and outbound adapters, config). Source dependencies point inward only: `composition_root -> infrastructure -> application -> domain`. The application owns two ports (`SttTranscriptionPort` driving, `TranscriptionPort` driven); adapters implement or call them; only the composition root chooses concrete classes. `tests/architecture/test_dependency_rules.py` parses every import and fails on a forbidden edge, on a `print()` outside `infrastructure`, on relative imports and on modules named `utils`, `common` or `helpers`.

## Consequences

- An engine can be replaced or faked without touching the service ([ADR-004](ADR-004-two-engines-behind-one-port.md)); the unit tests need no model and no network.
- `application` cannot import `contracts` or any framework: the wire types stay in `infrastructure/inbound`.
- A new feature has an obvious place; a new file must fit one of the layers.

> **Update 2026-11-11:** the application now owns three ports, not two: `SttServicePort` (the service's own, what `SttService` implements; it was called `SttTranscriptionPort` and sat in `ports/inbound/`), `SttInboundPort` (new: what every inbound adapter offers, implemented by the HTTP handler) and `SttOutboundPort` (what every engine offers; it was called `TranscriptionPort` and the file `transcription_port.py`, renamed the same day). A new inbound or outbound adapter implements its port, so the functions are the same; `tests/architecture/test_ports.py` checks it. The inbound adapter folder follows `dynamics_microservice` (`http_handler.py` wires, `routes/`, `response/`, `errors/`, `helpers/`); `helpers/` is the one place the `helpers` name is allowed.
