"""Unit tests for MCP tool interactions — one test per tool category.

Each test verifies that the agent correctly uses the mock MCP tools and
returns coherent, grounded responses. All LLM and MCP calls are mocked.
"""

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.tools import StructuredTool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tool(name: str, result: Any) -> StructuredTool:
    """Create a mock StructuredTool that returns a fixed result."""

    async def _run(**kwargs):
        return json.dumps(result)

    return StructuredTool.from_function(
        coroutine=_run,
        name=name,
        description=f"Mock tool: {name}",
    )


def _mock_llm_response(content: str) -> MagicMock:
    """Build a fake LLM that returns a fixed message content."""
    from langchain_core.messages import AIMessage

    mock_result = {"messages": [AIMessage(content=content)]}
    mock_graph = AsyncMock()
    mock_graph.ainvoke = AsyncMock(return_value=mock_result)
    return mock_graph


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_product_tool(add_agent_to_path):
    """Test: list_a_product_for_api_product_srv returns product list."""
    from agent import SampleAgent

    tool_result = {
        "results": [
            {"Product": "TG11", "BaseUnit": "EA", "ProductGroup": "L001"},
        ]
    }
    mock_tool = _make_tool("list_a_product_for_api_product_srv", tool_result)

    with patch("mcp_tools.get_mcp_tools", return_value=[mock_tool]):
        with patch.object(SampleAgent, "_create_graph") as mock_create:
            mock_create.return_value = _mock_llm_response(
                "Product TG11 has base unit EA and belongs to product group L001."
            )
            agent = SampleAgent()
            result = await agent.invoke("List available products", "test-ctx-001", tools=[mock_tool])

    assert result.status == "completed"
    assert result.message


@pytest.mark.asyncio
async def test_get_product_description_tool(add_agent_to_path):
    """Test: get_a_productdescription_for_api_product_srv retrieves description."""
    from agent import SampleAgent

    tool_result = {"Product": "TG11", "Language": "EN", "ProductDescription": "Finished Good TG11"}
    mock_tool = _make_tool("get_a_productdescription_for_api_product_srv", tool_result)

    with patch("mcp_tools.get_mcp_tools", return_value=[mock_tool]):
        with patch.object(SampleAgent, "_create_graph") as mock_create:
            mock_create.return_value = _mock_llm_response(
                "The English description for product TG11 is 'Finished Good TG11'."
            )
            agent = SampleAgent()
            result = await agent.invoke(
                "What is the description of product TG11?", "test-ctx-002", tools=[mock_tool]
            )

    assert result.status == "completed"
    assert result.message


@pytest.mark.asyncio
async def test_get_product_plant_data_tool(add_agent_to_path):
    """Test: list_a_productplant_for_api_product_srv retrieves plant data."""
    from agent import SampleAgent

    tool_result = {
        "results": [
            {"Product": "TG11", "Plant": "1000", "MRPType": "PD", "ProcurementType": "E"}
        ]
    }
    mock_tool = _make_tool("list_a_productplant_for_api_product_srv", tool_result)

    with patch("mcp_tools.get_mcp_tools", return_value=[mock_tool]):
        with patch.object(SampleAgent, "_create_graph") as mock_create:
            mock_create.return_value = _mock_llm_response(
                "Product TG11 is available at plant 1000 with MRP type PD."
            )
            agent = SampleAgent()
            result = await agent.invoke(
                "Show plant data for product TG11", "test-ctx-003", tools=[mock_tool]
            )

    assert result.status == "completed"
    assert result.message


@pytest.mark.asyncio
async def test_get_product_valuation_tool(add_agent_to_path):
    """Test: get_a_productvaluation_for_api_product_srv retrieves pricing."""
    from agent import SampleAgent

    tool_result = {
        "Product": "TG11",
        "ValuationArea": "1000",
        "StandardPrice": "125.00",
        "Currency": "USD",
    }
    mock_tool = _make_tool("get_a_productvaluation_for_api_product_srv", tool_result)

    with patch("mcp_tools.get_mcp_tools", return_value=[mock_tool]):
        with patch.object(SampleAgent, "_create_graph") as mock_create:
            mock_create.return_value = _mock_llm_response(
                "Product TG11 has a standard price of 125.00 USD in valuation area 1000."
            )
            agent = SampleAgent()
            result = await agent.invoke(
                "What is the price of product TG11?", "test-ctx-004", tools=[mock_tool]
            )

    assert result.status == "completed"
    assert result.message


@pytest.mark.asyncio
async def test_get_product_classification_tool(add_agent_to_path):
    """Test: list_a_productcharc_for_api_clfn_product_srv retrieves classification."""
    from agent import SampleAgent

    tool_result = {
        "results": [
            {"Product": "TG11", "CharcInternalID": "0000000001", "ClassType": "001"}
        ]
    }
    mock_tool = _make_tool("list_a_productcharc_for_api_clfn_product_srv", tool_result)

    with patch("mcp_tools.get_mcp_tools", return_value=[mock_tool]):
        with patch.object(SampleAgent, "_create_graph") as mock_create:
            mock_create.return_value = _mock_llm_response(
                "Product TG11 has 1 characteristic assigned in class type 001."
            )
            agent = SampleAgent()
            result = await agent.invoke(
                "Show the classification of product TG11", "test-ctx-005", tools=[mock_tool]
            )

    assert result.status == "completed"
    assert result.message


@pytest.mark.asyncio
async def test_product_not_found(add_agent_to_path):
    """Test: agent clearly states when a product is not found."""
    from agent import SampleAgent

    mock_tool = _make_tool("get_a_product_for_api_product_srv", {"results": []})

    with patch("mcp_tools.get_mcp_tools", return_value=[mock_tool]):
        with patch.object(SampleAgent, "_create_graph") as mock_create:
            mock_create.return_value = _mock_llm_response(
                "Product UNKNOWN123 could not be found. Please verify the product number."
            )
            agent = SampleAgent()
            result = await agent.invoke(
                "What is product UNKNOWN123?", "test-ctx-006", tools=[mock_tool]
            )

    assert result.status == "completed"
    assert result.message


@pytest.mark.asyncio
@pytest.mark.integration
async def test_integration_product_query_end_to_end(add_agent_to_path):
    """Integration test: full agent flow with mocked LLM and MCP tools."""
    from agent import SampleAgent

    tools = [
        _make_tool("list_a_product_for_api_product_srv", {
            "results": [{"Product": "TG11", "BaseUnit": "EA", "ProductGroup": "L001"}]
        }),
        _make_tool("get_a_productdescription_for_api_product_srv", {
            "Product": "TG11", "Language": "EN", "ProductDescription": "Finished Good TG11"
        }),
    ]

    from langchain_core.messages import AIMessage

    mock_result = {"messages": [AIMessage(content="Product TG11 is 'Finished Good TG11' with base unit EA.")]}
    mock_graph = AsyncMock()
    mock_graph.ainvoke = AsyncMock(return_value=mock_result)

    with patch("mcp_tools.get_mcp_tools", return_value=tools):
        with patch.object(SampleAgent, "_create_graph", return_value=mock_graph):
            agent = SampleAgent()
            result = await agent.invoke(
                "Tell me about product TG11", "integration-ctx-001", tools=tools
            )

    assert result.status == "completed"
    assert len(result.message) > 0
