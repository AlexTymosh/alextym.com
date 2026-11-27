# Tests

Backend pytest discovers this directory via host configuration. The freeze and static boundary tests run from the repository hygiene task using Node built-ins; localization tests run after the host npm install. Use synthetic fixtures only. The legacy freeze manifest is generated once from the pinned commit at installation, checked against the pinned Git tree on every CI run. See `../docs/TEST_STRATEGY.md` for commands and limitations.

SP02 adds room invariant, transaction-port, HTTP, identity, host mounting and opt-in Emulator tests. Run the full repository checks; see `../docs/TEST_STRATEGY.md`.
