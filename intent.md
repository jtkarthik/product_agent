# S/4HANA Product Query Agent

AI agent that answers natural language queries about Products in an SAP S/4HANA system.

## Business challenge

Users need a conversational AI agent that can answer questions about products stored in an SAP S/4HANA system — including product master data, material attributes, classification, and pricing — without needing to navigate complex SAP transactions.

## Key Milestones

1. **Query Received** — User submits a natural language question about a product or set of products.
2. **Intent Understood** — Agent identifies the relevant product data domain (master data, classification, valuation, etc.).
3. **Data Retrieved** — Agent calls the appropriate S/4HANA Product Master API tool to fetch the relevant data.
4. **Answer Formulated** — Agent synthesizes the retrieved data into a clear, human-readable response.
5. **Response Delivered** — User receives a complete, accurate answer to their product query.

## Business Architecture (RBA)

### End-to-End Process

Idea to Market (E2E)

### Process Hierarchy

```
Idea to Market (E2E)
└── Manage Products and Services (generic)
    └── Manage product, service lifecycle and compliance (BPS-323)
        └── Manage regulatory requirements
```

### Summary

Product queries in S/4HANA map to the "Idea to Market" E2E process under "Manage Products and Services", supported by S/4HANA Cloud's Product and Service Data Management capabilities.

## Fit Gap Analysis

| Requirement (business) | Standard asset(s) found | API ORD ID | MCP Server ORD ID | MCP Server Version | Gap? | Notes / assumptions |
| ---------------------- | ----------------------- | ---------- | ----------------- | ------------------ | ---- | ------------------- |
| Query product master data (descriptions, units, categories) | SAP S/4HANA Product Master API | `sap.s4:apiResource:API_PRODUCT_SRV:v1` | — | — | No | Agent will call this API directly via custom MCP translation |
| Query product classification data | SAP S/4HANA Product Master Data Including Classification | `sap.s4:apiResource:API_CLFN_PRODUCT_SRV:v1` | — | — | No | Supplementary API for classification attributes |
| Natural language understanding & response generation | SAP AI Core (LLM) | — | — | — | No | Standard AI Core capability |
| Conversational agent orchestration | Custom Python AI Agent | — | — | — | No | Pro-code agent with A2A protocol |

### Key findings
- No pre-built MCP server exists for the S/4HANA Product Master API; a custom MCP translation file must be generated from the EDMX spec.
- `API_PRODUCT_SRV:v1` is the primary OData API for product master data (Cloud Public Edition).
- `API_CLFN_PRODUCT_SRV:v1` adds classification and characteristic data for richer queries.
- SAP AI Core provides the LLM backbone for natural language understanding.
- The solution is a read-only query agent; no write operations are required.
- Fast-track: no additional clarifying questions needed given the clear scope.

## Recommendations

### S/4HANA Product Query AI Agent

#### Executive Summary

Python AI agent answering natural language product queries via S/4HANA APIs.

#### Recommended Solution

Build a pro-code Python AI agent (A2A protocol) that uses MCP tool calls to the SAP S/4HANA Product Master API. The agent receives natural language queries, determines which product data to fetch, calls the appropriate S/4HANA OData API endpoint via a generated MCP translation layer, and returns a human-readable answer. SAP AI Core provides the LLM for reasoning and response generation.

#### Recommended solution category

AI Agent

#### Intent fit
90%
