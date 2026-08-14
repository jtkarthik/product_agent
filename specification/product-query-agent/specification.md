# Specification: product-query-agent

> **Guidelines**: Read [guidelines.md](../guidelines.md) and [guidelines-agent.md](../guidelines-agent.md) before executing ANY tasks below. Follow all constraints described there throughout execution.

## Basic Setup

- [x] Read the project input (`product-requirements-document.md`, `intent.md`)
- [ ] Bootstrap agent code in `assets/product-query-agent/` using skill `sap-agent-bootstrap` (invoke from inside `assets/product-query-agent/`, use copy commands — do NOT create files manually)
- [ ] Install dependencies, validate the agent starts and responds at `/.well-known/agent.json`

## MCP Translation & Integration

- [ ] Invoke `mcp-translation-file` skill for `specification/product-query-agent/api-specs/API_PRODUCT_SRV.edmx` (ORD ID: `sap.s4:apiResource:API_PRODUCT_SRV:v1`, type: `edmx`)
- [ ] Invoke `mcp-translation-file` skill for `specification/product-query-agent/api-specs/API_CLFN_PRODUCT_SRV.edmx` (ORD ID: `sap.s4:apiResource:API_CLFN_PRODUCT_SRV:v1`, type: `edmx`)
- [ ] Invoke `setup-solution` skill to create MCP server assets for both translation files generated above
- [ ] Read each generated MCP server asset's `asset.yaml` and extract the exact `ordId` field — use those values verbatim in the agent's `asset.yaml` `requires` entries (NEVER invent or guess ORD IDs)
- [ ] Wire both MCP servers in `assets/product-query-agent/asset.yaml` under `requires`

## Agent Implementation

- [ ] Implement `assets/product-query-agent/app/agent.py`:
  - Wire MCP tools dynamically using `get_mcp_tools()` from `mcp_tools.py` (canonical pattern — never hard-code tool names)
  - System prompt must instruct the agent to:
    - Answer product queries using only data returned by MCP tools — never hallucinate
    - Always set `$top` to a maximum of 100 on any tool call that accepts it, and inform the user when this limit is applied
    - Be concise, human-readable, and structured in responses
    - Explicitly state when a product is not found
  - The five bootstrap decorators must remain exactly as generated (`@agent_model` x2, `@agent_config` x2, `@prompt_section` x1)

- [ ] Implement business step instrumentation for all 5 milestones from the PRD:
  - M1: Query Received — `M1.achieved: user query received` / `M1.missed: no user query received`
  - M2: Intent Understood — `M2.achieved: query intent classified, tool selected` / `M2.missed: intent classification failed or no tool selected`
  - M3: Data Retrieved — `M3.achieved: product data retrieved from S/4HANA` / `M3.missed: API call returned no data or error`
  - M4: Answer Formulated — `M4.achieved: response formulated from retrieved data` / `M4.missed: response synthesis failed`
  - M5: Response Delivered — `M5.achieved: response delivered to user` / `M5.missed: response delivery failed`
  - Add OpenTelemetry spans — use decorator form on regular async methods; extract business logic from `stream()` into `_run_agent()` and instrument that helper; never use context manager form inside async generators

- [ ] Verify `auto_instrument()` is called at top of `main.py` before any AI framework imports

- [ ] Delete the template runtime skill: `rm -rf assets/product-query-agent/app/skills/template-skill/`

## Mock Configuration

- [ ] After `mcp-translation-file` and `setup-solution` complete, invoke `mcp-mock-config` skill to generate `mcp-mock.json` for testing

## Testing

- [ ] `conftest.py` only sets `IBD_TESTING=true`
- [ ] Write unit tests in `assets/product-query-agent/tests/` — exactly one per tool, run each immediately after writing
  - Test: list/query product master data tool
  - Test: get product description tool
  - Test: list product plant data tool
  - Test: query product valuation/pricing tool
  - Test: query product classification/characteristic tool
- [ ] Write one integration test executing end-to-end agent flow with real LLM call mocked (mock `ChatLiteLLM` to return canned responses)
- [ ] Run `pytest` from `assets/product-query-agent/` (no args) — if coverage < 70%, add tests until threshold met
- [ ] Verify `assets/product-query-agent/app/agent.py` has exactly 5 decorated functions — run `grep -c "^@agent_model\|^@agent_config\|^@prompt_section" assets/product-query-agent/app/agent.py` and confirm it returns 5
- [ ] Run `pytest` again from `assets/product-query-agent/` (no args) to generate final `test_report.json`
- [ ] Verify `test_report.json` exists in `assets/product-query-agent/`
