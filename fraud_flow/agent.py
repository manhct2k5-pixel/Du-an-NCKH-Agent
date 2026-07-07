from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from langchain_classic.agents import AgentExecutor, create_react_agent
from langchain_classic.output_parsers import RetryOutputParser
from langchain_core.exceptions import OutputParserException
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.tools import StructuredTool

from .feature_store import RedisFeatureStore
from .llm_provider import build_decision_llm, build_react_llm, build_retry_llm
from .narratives import build_transaction_narrative
from .schema import (
    AgentDecision,
    AgentDecisionModel,
    FeatureLookup,
    InvestigationResult,
    ModelPrediction,
    TransactionEvent,
)


REACT_PROMPT = PromptTemplate.from_template(
    """You are a fraud investigation ReAct agent.
You must reason step by step and call tools when needed.

Available tools:
{tools}

Use this exact format:
Question: the investigation context
Thought: think about what evidence is needed next
Action: one of [{tool_names}]
Action Input: the input string for the tool
Observation: the tool result
... (repeat Thought/Action/Action Input/Observation as needed)
Thought: I now know the final answer
Final Answer: concise investigation summary

Question: INVESTIGATION_CONTEXT_JSON_START
{input}
INVESTIGATION_CONTEXT_JSON_END
Thought:{agent_scratchpad}"""
)


DECISION_PROMPT = PromptTemplate.from_template(
    """You convert a fraud investigation into strict JSON.
Return only JSON that matches the schema below.

{format_instructions}

DECISION_CONTEXT_JSON_START
{context}
DECISION_CONTEXT_JSON_END"""
)


RETRY_PROMPT = PromptTemplate.from_template(
    """Repair the broken completion into valid JSON.
ORIGINAL_PROMPT_START
{prompt}
ORIGINAL_PROMPT_END
BROKEN_COMPLETION_START
{completion}
BROKEN_COMPLETION_END
Return only valid JSON."""
)


class InvestigationTools:
    def __init__(self, feature_store: RedisFeatureStore, current_step: int) -> None:
        self.feature_store = feature_store
        self.current_step = current_step

    def check_ip_blacklist(self, ip_address: str) -> dict[str, Any]:
        result = self.feature_store.ip_summary(ip_address)
        result["tool"] = "check_ip_blacklist"
        return result

    def get_card_history(self, card_id: str) -> dict[str, Any]:
        result = self.feature_store.card_summary(card_id, self.current_step)
        result["tool"] = "get_card_history"
        return result

    def verify_device_id(self, device_id: str) -> dict[str, Any]:
        result = self.feature_store.device_summary(device_id, self.current_step)
        result["tool"] = "verify_device_id"
        return result

    def query_merchant_risk(self, merchant_id: str) -> dict[str, Any]:
        result = self.feature_store.merchant_summary(merchant_id, self.current_step)
        result["tool"] = "query_merchant_risk"
        return result

    def as_langchain_tools(self) -> list[StructuredTool]:
        def check_ip_blacklist(ip_address: str) -> str:
            """Check whether an IP address is historically fraudulent or blacklisted."""
            return json.dumps(self.check_ip_blacklist(ip_address), ensure_ascii=False)

        def get_card_history(card_id: str) -> str:
            """Get the recent 24h velocity and 7d spend profile for a card."""
            return json.dumps(self.get_card_history(card_id), ensure_ascii=False)

        def verify_device_id(device_id: str) -> str:
            """Check whether a device looks new or requires step-up verification."""
            return json.dumps(self.verify_device_id(device_id), ensure_ascii=False)

        def query_merchant_risk(merchant_id: str) -> str:
            """Get merchant risk statistics and recent transaction count."""
            return json.dumps(self.query_merchant_risk(merchant_id), ensure_ascii=False)

        return [
            StructuredTool.from_function(check_ip_blacklist, name="check_ip_blacklist"),
            StructuredTool.from_function(get_card_history, name="get_card_history"),
            StructuredTool.from_function(verify_device_id, name="verify_device_id"),
            StructuredTool.from_function(query_merchant_risk, name="query_merchant_risk"),
        ]


class ReActInvestigator:
    """Medium-path investigator implemented with LangChain ReAct + Pydantic parsing."""

    def __init__(self, feature_store: RedisFeatureStore) -> None:
        self.feature_store = feature_store
        self.react_llm = build_react_llm()
        self.decision_llm = build_decision_llm()
        self.retry_llm = build_retry_llm()

    def investigate(
        self,
        event: TransactionEvent,
        lookup: FeatureLookup,
        prediction: ModelPrediction,
    ) -> InvestigationResult:
        toolset = InvestigationTools(self.feature_store, event.step)
        tools = toolset.as_langchain_tools()
        agent = create_react_agent(self.react_llm, tools, REACT_PROMPT)
        executor = AgentExecutor(
            agent=agent,
            tools=tools,
            return_intermediate_steps=True,
            max_iterations=5,
            handle_parsing_errors=True,
        )

        investigation_context = {
            "event": event.to_dict(),
            "lookup": lookup.to_dict(),
            "prediction": prediction.to_dict(),
        }
        agent_result = executor.invoke({"input": json.dumps(investigation_context, ensure_ascii=False)})
        tool_results, trace = self._collect_tool_results(agent_result.get("intermediate_steps", []))

        structured_output, attempts, fallback_used = self._structure_output(
            investigation_context=investigation_context,
            agent_summary=str(agent_result.get("output", "")),
            tool_results=tool_results,
        )

        validated = AgentDecision(**structured_output)
        final_action, reviewer_note = self._review_and_finalize(validated, tool_results, prediction)

        return InvestigationResult(
            action=final_action,
            reviewer_note=reviewer_note,
            tool_results=tool_results,
            agent_output={
                "structured_output": structured_output,
                "agent_summary": agent_result.get("output", ""),
                "intermediate_steps": trace,
            },
            validation_attempts=attempts,
            fallback_used=fallback_used,
            human_readable_explanation=validated.human_readable_explanation,
            analyst_report=validated.analyst_report,
            dashboard_summary=validated.dashboard_summary,
        )

    def _structure_output(
        self,
        investigation_context: dict[str, Any],
        agent_summary: str,
        tool_results: dict[str, Any],
    ) -> tuple[dict[str, Any], int, bool]:
        parser = PydanticOutputParser(pydantic_object=AgentDecisionModel)
        prompt_value = DECISION_PROMPT.format_prompt(
            format_instructions=parser.get_format_instructions(),
            context=json.dumps(
                {
                    **investigation_context,
                    "agent_summary": agent_summary,
                    "tool_results": tool_results,
                },
                ensure_ascii=False,
            ),
        )

        completion = self.decision_llm.invoke(prompt_value.to_string())
        attempts = 1

        try:
            parsed = parser.parse(completion)
            return parsed.model_dump(), attempts, False
        except OutputParserException:
            retry_parser = RetryOutputParser.from_llm(
                llm=self.retry_llm,
                parser=parser,
                prompt=RETRY_PROMPT,
                max_retries=3,
            )
            try:
                parsed_retry = retry_parser.parse_with_prompt(completion, prompt_value)
                return parsed_retry.model_dump(), 2, False
            except OutputParserException:
                fallback = {
                    "recommended_action": "review",
                    "confidence": max(0.5, min(0.95, investigation_context["prediction"]["score"])),
                    "summary": "Parser fallback: routing this case to manual review with raw investigation attached.",
                    "reason_codes": ["parser_fallback"],
                    "evidence": [
                        agent_summary or "Agent summary unavailable.",
                        json.dumps(tool_results, ensure_ascii=False),
                    ],
                }
                fallback.update(
                    build_transaction_narrative(
                        event=investigation_context["event"],
                        lookup=investigation_context["lookup"],
                        prediction=investigation_context["prediction"],
                        final_action="review",
                        final_note="Parser fallback: transaction được giữ lại để analyst xác minh an toàn.",
                        agent={"agent_output": {"structured_output": fallback}},
                    )
                )
                return fallback, 4, True

    @staticmethod
    def _collect_tool_results(intermediate_steps: list[tuple[Any, str]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        tool_results: dict[str, Any] = {}
        trace: list[dict[str, Any]] = []

        for action, observation in intermediate_steps:
            try:
                parsed_observation = json.loads(observation)
            except (TypeError, json.JSONDecodeError):
                parsed_observation = observation

            tool_results[action.tool] = parsed_observation
            trace.append(
                {
                    "tool": action.tool,
                    "tool_input": action.tool_input,
                    "observation": parsed_observation,
                }
            )

        return tool_results, trace

    def _review_and_finalize(
        self,
        validated: AgentDecision,
        tool_results: dict[str, Any],
        prediction: ModelPrediction,
    ) -> tuple[str, str]:
        ip_result = tool_results.get("check_ip_blacklist", {})
        device_result = tool_results.get("verify_device_id", {})
        merchant_result = tool_results.get("query_merchant_risk", {})

        if ip_result.get("blacklisted") and prediction.score >= 0.55:
            return "block", "Tác tử điều tra xác nhận chặn giao dịch vì IP nằm trong blacklist và điểm rủi ro vẫn ở mức cao."

        if merchant_result.get("merchant_fraud_rate", 0.0) >= 0.1 and device_result.get("needs_step_up"):
            return "block", "Tác tử điều tra xác nhận chặn giao dịch vì merchant có lịch sử rủi ro cao và thiết bị cần xác minh tăng cường."

        if validated.recommended_action == "approve" and (
            device_result.get("needs_step_up") or ip_result.get("ip_fraud_rate", 0.0) >= 0.05
        ):
            return "review", "Tác tử điều tra nâng giao dịch lên mức review vì kiểm tra bổ sung vẫn cho thấy rủi ro trung bình."

        if validated.recommended_action == "block" and prediction.score < 0.55:
            return "review", "Tác tử điều tra hạ quyết định block xuống review vì giao dịch vẫn nằm trong dải medium và cần thêm xác minh."

        reviewer_note = {
            "approve": "Tác tử điều tra xác nhận có thể thông qua giao dịch sau khi rà soát các bằng chứng từ tool.",
            "review": "Tác tử điều tra tạm giữ giao dịch để analyst xác minh thêm.",
            "block": "Tác tử điều tra xác nhận cần chặn giao dịch ngay sau khi đối chiếu bằng chứng từ tool.",
        }[validated.recommended_action]
        return validated.recommended_action, reviewer_note
