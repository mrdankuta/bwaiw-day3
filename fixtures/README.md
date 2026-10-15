# Engine conformance fixtures

Language-neutral vectors for the deterministic budget engine seam:
fixture months in, expected Plan plus Warnings JSON out. Every engine
port (Rust core, WASM binding, future ports) runs these same cases.

- `version`: fixture schema version, bumped on breaking shape changes.
- `cases[]`: success paths. `inputs` are fully explicit — no reliance on
  any implementation's defaults. `expected` holds the six Plan integers,
  the ordered `warning_rule_ids`, and the `suggestions` strings.
- `error_cases[]`: inputs that must fail, with a substring of the error.

Conformance contract across languages: the six Plan integers and the
ordered warning rule identifiers are normative and must match exactly.
Suggestion strings are informative: ports should convey the same
instruction (Wants cuts first, leftover to savings) but exact wording
may vary by port.
