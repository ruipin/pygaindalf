# pygaindalf AI contribution guide

## Architecture map
- `pygaindalf.py` boots the CLI: it calls `CFG.initialize()`, then resolves providers from `CFG.providers[...]` and runs component entrypoints. Treat this as the canonical runtime wiring when adding workflows.
- Configuration lives under `app/config/` (Pydantic models) and is consumed across the app via the `ConfigWrapper` in `app/config/__init__.py`. Most subsystems live in `app/util/**` and the domain model for tax portfolios sits in `app/portfolio/**`.
- Components are modular plugins. `app/components/component.py` defines the base class hierarchy and callguard runtime that enforce entrypoint discipline and decimal contexts.

## Configuration workflow
- CLI options are defined in `app/config/args.py` and extend `DefaultArgParser`. Flags like `--config.providers.oanda.decimal.precision` map onto nested config keys; environment overrides use the uppercase name prefixed with `PYGAINDALF_`.
- Config files support YAML `!include` via `IncludeLoader` (`app/util/config/yaml_loader.py`). Keep reusable snippets in `data/*.yaml` and prefer includes over copy/paste.
- `ConfigFileLoader` injects an `app` section with script metadata, seeds logging (`LoggingManager`) and installs the HTTP cache (`RequestsManager`). Don’t manually populate `app.*` keys—they’re reserved.
- `FieldInherit` makes decimal/logging defaults inheritable. When extending config models, prefer `FieldInherit` or `Field(default_factory=...)` so overrides merge cleanly.

## Component pattern
- Every concrete component module must set a top-level `COMPONENT` pointing to a subclass of `ComponentBase`; its config subclass extends `BaseComponentConfig` and sets `package` to the module name (`forex.oanda`, etc.).
- Public methods must be decorated with `@component_entrypoint`. The callguard layer blocks direct access to helpers and ensures `_before_entrypoint`, `_wrap_entrypoint`, and `_after_entrypoint` run with the shared `DecimalFactory` context.
- Use `self.decimal(value)` (from `DecimalFactory`) for all money math. Decimal context is configured per-component via the config tree (see `data/example.yaml`).

## Portfolio domain model
- Domain entities derive from `app/portfolio/models/entity/entity_base.py`. Constructors are guarded: `EntityBase.__new__` calculates UIDs, prevents duplicate records, and hydrates existing instances from the global `EntityStore`.
- Entities delegate persistence to matching `EntityRecord` subclasses and maintain `EntityDependents` + `EntityLog` objects to audit state. When adding fields, update `calculate_instance_name_from_dict` to keep deterministic `Uid` generation.
- Logging inside entities relies on the `t"..."` templated strings patched by `app/util/logging/tstring.py`; prefer that style for interpolated log messages.

## Integration infrastructure
- `app/util/logging/manager.py` configures both file and rich TTY handlers; log levels derive from config. Tests autoinitialize logging with minimal output.
- `RequestsManager.install()` monkeypatches `requests.Session`: once called (via config bootstrap) **every** `requests` client, including `requests.session()`, picks up caching, retries, and rate limiting. You don’t need to create a custom session; just import `requests` normally unless you intentionally want an isolated session (`RequestsManager().session()`).
- Cache backends default to filesystem (`cache/` / `test/cache/**`). Keys stay human-readable thanks to `RequestsManager.human_readable_key_fn`.
- The project targets Python ≥3.14 and expects `t-string` support (`string.templatelib`). Keep compatibility with that toolchain.

## Developer workflows
- Install deps with `uv sync`; run commands through `uv run ...` to reuse the managed environment.
- Core test command: `uv run pytest` (note `pytest.ini` adds `-x`, strict markers, and HTML coverage). When debugging multiple failures, append `-x=false` or run a focused subset via `-k`/`-m`.
- Lint with `uv run ruff check` and format via `uv run ruff format`. Type-check with `uv run pyright --project pyrightconfig.json`. These are also integrated into VSCode's python and ruff extensions, so you shouldn't need to run them manually.
- On the first run of a unit test the HTTP cache under `test/cache/**` is populated automatically by the installed `requests-cache` and used in future unit test runs to ensure determinism. Avoid editing `test/cache/**` manually unless you are deliberately refreshing or pruning stale fixtures.

## Conventions to follow
- Every source file starts with the GPL SPDX header and groups sections using `# MARK:` comments (Ruff is configured to ignore these tags).
- Prefer relative imports within the package (`ruff.toml` permits them).
- When writing tests, reuse the factories in `test/components/fixture.py` to build configs/components instead of instantiating directly, and rely on the `config` fixture rather than touching `app.config.CFG` (including `CFG.reset()`) directly.
- Avoid running commands; rely solely on VSCode's integrated linting/type-checking, ensuring it is clean; once you believe your task is complete (or you are not able to make any further progress) summarize your work and ask the user if they want to run tests or other relevant commands.

Let me know if any section needs clarifying or if you spot additional patterns worth documenting.
