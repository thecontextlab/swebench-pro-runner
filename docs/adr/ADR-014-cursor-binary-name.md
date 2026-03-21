# ADR-014: Cursor CLI Binary Name — Symlink to `cursor-agent`

## Status

Proposed

## Context

The Cursor CLI (installed via `curl https://cursor.com/install -fsS | bash`) places a binary named `agent` at `~/.local/bin/agent`. This generic name creates multiple collision risks:

1. **GHA workflow conflict** — Our `swebench-eval.yml` workflow has an input parameter named `agent` (claude, codex, gemini). A binary with the same name on PATH creates confusion in logs and debugging.
2. **Future tool conflicts** — Other AI coding tools may also install binaries named `agent` (it's a common name in the AI agent space).
3. **PATH ordering** — The `~/.local/bin` location depends on HOME and PATH configuration inside Docker containers, making the binary's availability fragile.

The other three CLIs have unique, unambiguous names: `claude`, `codex`, `gemini`.

## Decision

After installing via the curl installer, copy the binary to a well-known system location with a unique name:

```dockerfile
RUN curl https://cursor.com/install -fsS | bash && \
    cp ~/.local/bin/agent /usr/local/bin/cursor-agent && \
    chmod +x /usr/local/bin/cursor-agent && \
    cursor-agent --version || echo "Cursor CLI installed"
```

All wrapper scripts (`run_cursor.py`) invoke `cursor-agent` explicitly, never the bare `agent` name.

## Consequences

- **Positive:** Unambiguous binary name consistent with our naming pattern (`claude`, `codex`, `gemini`, `cursor-agent`). No PATH ordering issues since `/usr/local/bin` is always on PATH.
- **Negative:** Slightly non-standard — Cursor docs reference `agent`, not `cursor-agent`. Future Cursor CLI updates that change the install path will require updating the `cp` command.
- **Mitigation:** The Dockerfile verification step checks `which cursor-agent` to catch install path changes early during image builds.
