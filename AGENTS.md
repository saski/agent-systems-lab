# Agent Systems Lab

Build small, runnable experiments with explicit evidence and permission boundaries.

- Python backend, LangGraph workflow, LangChain specialists, deterministic gateway.
- Use `uv` and the committed lockfile. Run `make check` before commits.
- Run `make spec-check` when changing OpenSpec artifacts.
- Start behavior changes with a failing test when practical.
- Keep technical artifacts in English and explain results to the user in their language.
- Never treat fixture-model results as evidence of real-model quality or safety.
- Keep runtime secrets, checkpoints, and artifacts under ignored `.lab/`.
- Agent personas and skills cannot authorize actions. Only the gateway grants permissions.
- Keep model-provider credentials in the gateway; do not mount host credentials or Docker sockets into workers.
- Do not expand live model access, external writes, or experiment scope implicitly.
- Distinguish implemented controls, demonstrated tests, and future architecture in documentation.
- OpenSpec lives in `docs/openspec/`, exposed through the `openspec` symlink.
- New experiments need a hypothesis, system boundary, variables, observations, and limitations.
