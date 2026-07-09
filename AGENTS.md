# Repository Guidelines

## Project Structure & Module Organization

This repository is a Python 3.12 package using a `src/` layout. Core bridge code lives in `src/kiwi_local_llm_bridge/`, with modules for protocol types, routing, registry management, tool execution, and bridge orchestration. Transport implementations are under `src/kiwi_local_llm_bridge/transports/`; mock client/server helpers are under `client/` and `server/`. Tests live in `tests/`, runnable examples in `examples/`, and protocol documentation in `docs/protocol.md`.

## Build, Test, and Development Commands

- `uv sync --extra dev`: install runtime and development dependencies from `pyproject.toml` and `uv.lock`.
- `uv run pytest`: run the full test suite configured by `pyproject.toml`.
- `uv run python examples/streaming_response.py`: run the minimal streaming bridge example.
- `uv run python examples/tool_call_roundtrip.py`: exercise local-model tool-call handling.
- `uv run python examples/routing_decision.py`: inspect local LLM routing behavior.

The package builds with Hatchling. Keep dependency changes in `pyproject.toml` and refresh `uv.lock` when needed.

## Coding Style & Naming Conventions

Use typed, explicit Python and keep async bridge behavior clear. Follow the existing style: 4-space indentation, descriptive dataclass/Pydantic model names, snake_case functions and variables, and PascalCase classes such as `LocalLLMBridge`. Prefer small modules with narrow responsibility. Keep protocol message names stable, for example `llm_infer_request`, `llm_infer_chunk`, and `llm_tool_result`. Invalid local-model config should fail clearly.

## Testing Guidelines

Tests use `pytest` and `pytest-asyncio`. Add tests under `tests/` with filenames matching `test_*.py`. For async behavior, model the client/server exchange with `InMemoryBridgeTransport` or existing mock runtimes instead of sleeping on timing assumptions. Cover protocol validation, routing decisions, timeout paths, unknown requests, and tool-call loops when changing those areas. Run `uv run pytest` before submitting changes.

## Commit & Pull Request Guidelines

Recent commits use short, imperative summaries, sometimes with a scope prefix, such as `docs: simplify README scope and architecture diagram`. Keep commits focused and explain behavior changes in the body when the summary is not enough.

Pull requests should include a concise description, the reason for the change, test results, and links to related issues or design notes. Include updated examples or docs when changing public protocol shape, routing behavior, or contributor-facing commands.

## Security & Configuration Tips

Treat server-side tool execution as privileged. Do not put secrets in examples, tests, or route configuration. Validate model registry and route updates with Pydantic-backed paths, and prefer explicit errors over permissive parsing.
