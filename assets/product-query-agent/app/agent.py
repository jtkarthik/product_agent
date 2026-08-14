import logging
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Literal, Sequence

from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool
from langchain_litellm import ChatLiteLLM
from langgraph.graph.state import CompiledStateGraph
from litellm.exceptions import APIConnectionError, APIError, Timeout
from opentelemetry import trace
from sap_cloud_sdk.agent_decorators import agent_config, agent_model, prompt_section

try:
    from sap_cloud_sdk.agent_memory.factory.langgraph_checkpoint import create_checkpointer
except ImportError:
    def create_checkpointer(ttl_seconds=None):
        return None

from mcp_tools import get_user_sub

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


@agent_model(
    key="config.model",
    label="LLM Model",
    description="The language model powering this agent",
)
def get_model_name() -> str:
    return "sap/anthropic--claude-4.5-sonnet"


@agent_model(
    key="config.fallback_model",
    label="Fallback LLM Model",
    description="Fallback model used when the primary model is unavailable. Leave empty to disable fallback.",
)
def get_fallback_model_name() -> str:
    return ""


@agent_config(
    key="config.temperature",
    label="LLM Temperature",
    description="Controls randomness of responses (0.0 = deterministic, 1.0 = creative)",
)
def get_temperature() -> float:
    return 0.0


@agent_config(
    key="config.checkpointer.ttl_seconds",
    label="Thread TTL (seconds)",
    description="Evict inactive conversation threads after this period of inactivity. Set to 0 to disable eviction.",
)
def thread_ttl_seconds() -> int:
    return 3600  # 1 hour


@prompt_section(
    key="prompts.system",
    label="System Prompt",
    description="The full system prompt defining the agent's role and behavior",
    validation={"format": "markdown", "max_length": 5000},
)
def get_system_prompt() -> str:
    return (
        "You are an AI agent that answers natural language queries about Products in an SAP S/4HANA system. "
        "Help users retrieve product information including descriptions, units of measure, classifications, "
        "plant data, and valuation details.\n\n"
        "IMPORTANT:\n"
        "- You MUST use tools to retrieve live data from S/4HANA. Never fabricate, guess, or invent product data.\n"
        "- On every tool call that accepts a $top or equivalent page-size parameter, always set it to a maximum "
        "of 100 to prevent context overflow. Inform the user when this limit is applied.\n"
        "- If a product is not found, clearly state that it could not be found and suggest the user verify "
        "the product number.\n"
        "- Relay tool errors verbatim without adding suggestions."
    )


@dataclass
class AgentResponse:
    status: Literal["input_required", "completed", "error"]
    message: str


class SampleAgent:
    SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]

    def __init__(self):
        ttl = thread_ttl_seconds()
        self._primary_model = get_model_name()
        self._fallback_model = get_fallback_model_name().strip()
        self._temperature = get_temperature()

        self.llm = ChatLiteLLM(model=self._primary_model, temperature=self._temperature)
        self._fallback_llm = (
            ChatLiteLLM(model=self._fallback_model, temperature=self._temperature)
            if self._fallback_model
            else None
        )

        self._checkpointer = create_checkpointer(ttl_seconds=ttl or None)
        self._summarization_middleware = SummarizationMiddleware(
            model=self.llm,
            trigger=("tokens", 100_000),
            keep=("messages", 4),
        )

    def _create_graph(
        self,
        llm: ChatLiteLLM,
        tools: Sequence[BaseTool],
        system_prompt: str,
    ) -> CompiledStateGraph:
        return create_agent(
            llm,
            tools=list(tools),
            system_prompt=system_prompt,
            checkpointer=self._checkpointer,
            middleware=[self._summarization_middleware],
        )

    async def _invoke_with_fallback(
        self,
        tools: Sequence[BaseTool],
        system_prompt: str,
        query: str,
        context_id: str,
    ) -> dict[str, Any]:
        config = {"configurable": {"thread_id": f"{get_user_sub()}:{context_id}"}}
        messages = {"messages": [HumanMessage(content=query)]}

        try:
            graph = self._create_graph(self.llm, tools, system_prompt)
            return await graph.ainvoke(messages, config)
        except (APIConnectionError, APIError, Timeout) as primary_error:
            if not self._fallback_llm:
                raise

            logger.warning(
                "Primary model '%s' failed. Retrying with fallback model '%s'. Error: %s",
                self._primary_model,
                self._fallback_model,
                primary_error,
            )

        graph = self._create_graph(self._fallback_llm, tools, system_prompt)
        result = await graph.ainvoke(messages, config)
        logger.info(
            "Request completed with fallback model '%s' after primary model '%s' failed.",
            self._fallback_model,
            self._primary_model,
        )
        return result

    @tracer.start_as_current_span("product_query_agent._run_agent")
    async def _run_agent(
        self,
        query: str,
        context_id: str,
        tools: Sequence[BaseTool] | None = None,
    ) -> str:
        """Core business logic: M2 intent → M3 data retrieval → M4 answer formulation."""
        # M2: Intent Understood — tool selection occurs implicitly in the LLM call
        system_prompt = get_system_prompt()
        if not tools:
            system_prompt += (
                "\n\nIMPORTANT: No tools are currently available. Do not attempt to call any tools. "
                "Respond to the user explaining that tools are temporarily unavailable."
            )

        tool_names = [tool.name for tool in tools] if tools else []
        if tool_names:
            logger.info("M2.achieved: query intent classified, tool selected — tools: %s", tool_names)
        else:
            logger.warning("M2.missed: intent classification failed or no tool selected")

        # M3: Data Retrieved — handled inside LangGraph; log on completion
        result = await self._invoke_with_fallback(
            tools=tools or [],
            system_prompt=system_prompt,
            query=query,
            context_id=context_id,
        )

        messages = result.get("messages", [])
        response = messages[-1].content if messages else ""

        if response:
            logger.info("M3.achieved: product data retrieved from S/4HANA")
        else:
            logger.warning("M3.missed: API call returned no data or error")

        # M4: Answer Formulated
        if response:
            logger.info("M4.achieved: response formulated from retrieved data")
        else:
            logger.warning("M4.missed: response synthesis failed")
            response = "I was unable to retrieve product information. Please check the product number and try again."

        return response

    async def stream(
        self,
        query: str,
        context_id: str,
        tools: Sequence[BaseTool] | None = None,
    ) -> AsyncGenerator[dict, None]:
        # M1: Query Received
        if query:
            logger.info("M1.achieved: user query received")
        else:
            logger.warning("M1.missed: no user query received")

        yield {
            "is_task_complete": False,
            "require_user_input": False,
            "content": "Processing...",
        }

        try:
            response = await self._run_agent(query, context_id, tools=tools)

            # M5: Response Delivered
            logger.info("M5.achieved: response delivered to user")
            yield {
                "is_task_complete": True,
                "require_user_input": False,
                "content": response,
            }

        except Exception:
            logger.exception("Agent stream() failed")
            logger.warning("M5.missed: response delivery failed")
            yield {
                "is_task_complete": True,
                "require_user_input": False,
                "content": "I encountered an error while processing your request. Please try again.",
            }

    async def invoke(
        self,
        query: str,
        context_id: str,
        tools: Sequence[BaseTool] | None = None,
    ) -> AgentResponse:
        last: dict = {}
        async for chunk in self.stream(query, context_id, tools=tools):
            last = chunk
        if last.get("is_task_complete"):
            return AgentResponse(status="completed", message=last["content"])
        if last.get("require_user_input"):
            return AgentResponse(status="input_required", message=last["content"])
        return AgentResponse(
            status="error", message=last.get("content", "Unknown error")
        )
