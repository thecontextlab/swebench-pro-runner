# Architecture Decision Records

This directory tracks architectural decisions for the SWE-bench Pro Runner platform. Each ADR is filed as a GitHub issue and indexed here.

## ADR Index

| ADR | Title | Status | Issue | Priority |
|-----|-------|--------|-------|----------|
| ADR-001 | Create MCP server onboarding guide | **Accepted** | [#16](https://github.com/thecontextlab/swebench-pro-runner/issues/16) | Critical |
| ADR-002 | MCP server name hardcoded as "mcp-server" — make configurable | Proposed | [#17](https://github.com/thecontextlab/swebench-pro-runner/issues/17) | High |
| ADR-003 | `token_secret_name` in config.yaml is parsed but unused | Proposed | [#18](https://github.com/thecontextlab/swebench-pro-runner/issues/18) | Medium |
| ADR-004 | Add MCP health check to validate-infrastructure workflow | Proposed | [#19](https://github.com/thecontextlab/swebench-pro-runner/issues/19) | Medium |
| ADR-005 | Document the full configuration hierarchy | **Accepted** | [#20](https://github.com/thecontextlab/swebench-pro-runner/issues/20) | High |
| ADR-006 | `MAX_TURNS` workflow input is accepted but never used | Proposed | [#21](https://github.com/thecontextlab/swebench-pro-runner/issues/21) | High |
| ADR-007 | Deduplicate 33 agent wrappers to 3 shared files | Proposed | [#22](https://github.com/thecontextlab/swebench-pro-runner/issues/22) | Medium |
| ADR-008 | Create Docker image manifest with variant rationale | **Accepted** | [#23](https://github.com/thecontextlab/swebench-pro-runner/issues/23) | Medium |
| ADR-009 | Design per-task tool allowlisting for A/B testing | Proposed | [#24](https://github.com/thecontextlab/swebench-pro-runner/issues/24) | Low |
| ADR-010 | Document hybrid Docker build strategy | **Accepted** | [#25](https://github.com/thecontextlab/swebench-pro-runner/issues/25) | Low |
| ADR-011 | Add batch Docker rebuild with CLI version staleness tracking | Proposed | [#26](https://github.com/thecontextlab/swebench-pro-runner/issues/26) | Low |
| ADR-012 | Evaluate MCP support for Codex and Gemini agents | Proposed | [#27](https://github.com/thecontextlab/swebench-pro-runner/issues/27) | Low |
| ADR-013 | Evaluate sidecar pattern for agent CLI containers | Proposed | [#28](https://github.com/thecontextlab/swebench-pro-runner/issues/28) | Low |

## Status Definitions

- **Proposed** — Issue filed, awaiting implementation or further discussion
- **Accepted** — Decision made and documented; implementation complete or in progress
- **Superseded** — Replaced by a newer ADR (linked in the issue)

## Template

New ADRs should follow the [ADR template](TEMPLATE.md).
