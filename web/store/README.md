# On-device month store (ticket #17)

Browser SQLite for the month grain, mirroring the server store:
`schema.sql` (months, expenses, suggestions log), `grain.js` (pure
row mapping plus the versioned export/import document), `store.js`
(the wa-sqlite wiring: OPFS where sync access handles exist,
IndexedDB everywhere else).

## Verify

- Logic and schema: `node --test web/store/test-store.mjs` (11 checks:
  schema shape, grain round-trip through real SQL, validation,
  export/import, no-drift between `store.js` and the schema).
- Binding in a real browser: serve the repo root
  (`npx serve .`), open `/web/store/harness.html`, run the
  acceptance checks, reload the page and re-run for the durability
  proof. The OPFS/IndexedDB VFS layer cannot be exercised in Node, so
  the harness is the verification for `store.js` itself.
