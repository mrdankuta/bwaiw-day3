# Vendored wa-sqlite 1.0.0 (MIT)

WebAssembly SQLite with browser-storage virtual filesystems, from
https://github.com/rhashimoto/wa-sqlite (npm `wa-sqlite@1.0.0`).

Only the files the on-device store needs are vendored here so the app
runs fully offline once loaded:

- `dist/`: synchronous (`wa-sqlite.*`, used with OPFS) and asynchronous
  (`wa-sqlite-async.*`, used with IndexedDB) builds.
- `src/`: the JS API plus the two VFS implementations used
  (`examples/OriginPrivateFileSystemVFS.js` for OPFS where sync access
  handles exist, `examples/IDBBatchAtomicVFS.js` for IndexedDB
  everywhere else) and their shared helpers.

To upgrade: `npm pack wa-sqlite@<version>` and replace these files,
keeping the `dist/` + `src/` relative layout (the modules import each
other with relative paths).
