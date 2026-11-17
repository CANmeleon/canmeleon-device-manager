# CDM OEM contributor rules

- This public repository owns the OEM UI, public CLI adapter, documentation and build scripts. Never add private CDM/QA source, internal repository history, device protocol implementations, firmware layout algorithms or credentials.
- Use the complete pinned CDM runtime through its public CLI. Keep schema compatibility and UID/plan checks. Do not inspect internal state files or call internal workers.
- Keep UI and error guidance bilingual. Busy write operations cannot be cancelled by killing their process. Unknown outcomes require a device refresh, never automatic retry.
- Before editing, inspect Git status and preserve unrelated changes. Do not commit downloaded binaries, caches, environments, test logs or build output.
- Run the relevant pytest tests and PowerShell parsing checks. Installer/real-device checks must use the final candidate. Record simulated and hardware evidence separately.
- Maintain clone and Source ZIP setup support. Pin downloads by exact release tag and SHA-256; never use latest for runtime setup.
- Follow CONTRIBUTING.md for development and release. Only explicitly requested releases may update remote branches, tags or Release assets.
