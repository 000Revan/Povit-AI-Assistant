from collections.abc import AsyncIterator
import json
import re
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field, ValidationError

from app.agents.generation_agent import generate_answer, generate_answer_stream
from app.agents.intent_agent import parse_intent
from app.agents.rag_agent import run_rag
from app.agents.tool_agent import decide_tools, normalize_tool_names, run_tools
from app.agents.verification_agent import verify_answer_detail
from app.services.llm_client import chat_completion


class AgentPlan(BaseModel):
    intent: Literal["chitchat", "task"] = "chitchat"
    rewritten_query: str = ""
    sub_tasks: list[str] = Field(default_factory=list)
    need_rag: bool = False
    rag_search_query: str | None = None
    need_tool: bool = False
    selected_tools: list[str] = Field(default_factory=list)
    tool_input_params: dict[str, dict[str, Any]] = Field(default_factory=dict)


class AgentState(TypedDict, total=False):
    # 对话基础
    user_query: str
    effective_query: str
    chat_history: list[dict[str, str]]

    # 意图任务
    intent: Literal["chitchat", "task"]
    sub_tasks: list[str]

    # RAG 模块
    need_rag: bool
    rag_search_query: str | None
    rag_documents: list[Any]
    rag_context: str

    # 工具调度
    need_tool: bool
    selected_tools: list[str]
    tool_input_params: dict[str, dict[str, Any]]
    tool_outputs: dict[str, Any]
    tool_results: list[dict]

    # 信息融合
    fusion_context: str

    # 反思循环
    need_retry: bool
    retry_reason: str | None
    retry_count: int

    # 最终输出
    final_answer: str

    # 兼容旧调用与调试
    message: str
    history: list[dict]
    contexts: list[str]
    answer: str
    verification_passed: bool
    verification_reason: str
    route_trace: list[str]


TOOL_DESCRIPTIONS = {
    "time": "时间获取工具，适合查询当前时间、日期、星期、时区。",
    "ip_lookup": "IP地址查询工具，适合查询当前 IP 所在省市或指定 IP 地址归属。",
    "weather": "天气信息获取工具，适合查询城市实时天气或天气预报。",
    "bilibili_video": "B站视频获取工具，适合获取 B站视频/热门视频数据。",
    "web_search": "全网搜索工具，适合查询最新信息、新闻、网页资料、外部事实。",
    "netease_soaring": "爬虫工具：网易云飙升榜单爬虫。",
    "bilibili_popular": "爬虫工具：B站热门视频爬虫。",
}
MAX_RETRY_COUNT = 1


def _append_trace(state: AgentState, item: str) -> list[str]:
    return [*state.get("route_trace", []), item]


async def _plan_node(state: AgentState) -> AgentState:
    user_query = state["user_query"]
    chat_history = state.get("chat_history", [])
    rewritten_query = contextualize_message(user_query, chat_history)
    plan = await _build_agent_plan(user_query, rewritten_query, chat_history)
    effective_query = plan.rewritten_query or rewritten_query or user_query
    selected_tools = normalize_tool_names(plan.selected_tools)
    need_tool = plan.need_tool or bool(selected_tools)
    return {
        "effective_query": effective_query,
        "intent": plan.intent,
        "sub_tasks": plan.sub_tasks,
        "need_rag": plan.need_rag,
        "rag_search_query": plan.rag_search_query or effective_query,
        "need_tool": need_tool,
        "selected_tools": selected_tools,
        "tool_input_params": _normalize_tool_input_params(plan.tool_input_params, selected_tools),
        "route_trace": _append_trace(
            state,
            f"plan:intent={plan.intent},rag={plan.need_rag},tools={','.join(selected_tools) or 'none'}",
        ),
    }


def _rag_node(state: AgentState) -> AgentState:
    query = state.get("rag_search_query") or state.get("effective_query") or state["user_query"]
    documents = run_rag(query)
    rag_context = _format_rag_context(documents)
    return {
        "rag_documents": documents,
        "contexts": documents,
        "rag_context": rag_context,
        "route_trace": _append_trace(state, f"rag:{len(documents)}"),
    }


async def _tool_router_node(state: AgentState) -> AgentState:
    query = state.get("effective_query") or state["user_query"]
    selected_tools = normalize_tool_names(state.get("selected_tools", []))

    if state.get("retry_count", 0) and state.get("need_retry"):
        retry_plan = await _retry_tool_plan(state)
        selected_tools = normalize_tool_names(retry_plan.selected_tools) or selected_tools
        tool_input_params = _normalize_tool_input_params(retry_plan.tool_input_params, selected_tools)
        return {
            "need_tool": bool(selected_tools),
            "selected_tools": selected_tools,
            "tool_input_params": tool_input_params,
            "route_trace": _append_trace(state, f"retry_tool_router:{','.join(selected_tools) or 'none'}"),
        }

    if state.get("need_tool") and not selected_tools:
        selected_tools = decide_tools(query)

    return {
        "need_tool": bool(selected_tools),
        "selected_tools": selected_tools,
        "tool_input_params": _normalize_tool_input_params(state.get("tool_input_params", {}), selected_tools),
        "route_trace": _append_trace(state, f"tool_router:{','.join(selected_tools) or 'none'}"),
    }


def _tool_dispatch_node(state: AgentState) -> AgentState:
    query = state.get("effective_query") or state["user_query"]
    selected_tools = state.get("selected_tools", [])
    tool_results = run_tools(query, selected_tools, state.get("tool_input_params", {}))
    return {
        "tool_results": tool_results,
        "route_trace": _append_trace(state, f"tool_dispatch:{len(tool_results)}"),
    }


def _tool_aggregate_node(state: AgentState) -> AgentState:
    tool_outputs: dict[str, Any] = {}
    for result in state.get("tool_results", []):
        tool_name = str(result.get("tool") or "unknown")
        tool_outputs[tool_name] = result
    return {
        "tool_outputs": tool_outputs,
        "route_trace": _append_trace(state, f"tool_aggregate:{len(tool_outputs)}"),
    }


def _fusion_node(state: AgentState) -> AgentState:
    fusion_context = _build_fusion_context(state)
    return {
        "fusion_context": fusion_context,
        "route_trace": _append_trace(state, "fusion"),
    }


def _reflect_node(state: AgentState) -> AgentState:
    retry_count = state.get("retry_count", 0)
    if _is_chitchat(state):
        return {
            "need_retry": False,
            "retry_reason": None,
            "route_trace": _append_trace(state, "reflect:chitchat"),
        }

    reason = _reflection_retry_reason(state)
    if reason and retry_count < MAX_RETRY_COUNT:
        selected_tools = normalize_tool_names([*state.get("selected_tools", []), "web_search"])
        return {
            "need_retry": True,
            "retry_reason": reason,
            "retry_count": retry_count + 1,
            "need_tool": True,
            "selected_tools": selected_tools,
            "route_trace": _append_trace(state, f"reflect:retry:{reason}"),
        }

    return {
        "need_retry": False,
        "retry_reason": reason,
        "route_trace": _append_trace(state, f"reflect:enough:{reason or 'ok'}"),
    }


async def _final_answer_node(state: AgentState) -> AgentState:
    query = state.get("effective_query") or state["user_query"]
    contexts = state.get("rag_documents", [])
    tool_results = state.get("tool_results", [])
    answer = await generate_answer(query, state.get("chat_history", []), contexts, tool_results)
    verified = verify_answer_detail(answer, contexts, state.get("intent", "chitchat"))
    return {
        "final_answer": verified["answer"],
        "answer": verified["answer"],
        "verification_passed": verified["passed"],
        "verification_reason": verified["reason"],
        "route_trace": _append_trace(state, f"final_answer:{verified['reason']}"),
    }


def _route_after_plan(state: AgentState) -> str:
    return "rag" if state.get("need_rag") else "tool_router"


def _route_after_tool_router(state: AgentState) -> str:
    return "tool_dispatch" if state.get("need_tool") and state.get("selected_tools") else "fusion"


def _route_after_reflect(state: AgentState) -> str:
    return "tool_router" if state.get("need_retry") else "final_answer"


def _build_agent_graph():
    graph = StateGraph(AgentState)
    graph.add_node("plan", _plan_node)
    graph.add_node("rag", _rag_node)
    graph.add_node("tool_router", _tool_router_node)
    graph.add_node("tool_dispatch", _tool_dispatch_node)
    graph.add_node("tool_aggregate", _tool_aggregate_node)
    graph.add_node("fusion", _fusion_node)
    graph.add_node("reflect", _reflect_node)
    graph.add_node("generate_final", _final_answer_node)

    graph.add_edge(START, "plan")
    graph.add_conditional_edges("plan", _route_after_plan, {"rag": "rag", "tool_router": "tool_router"})
    graph.add_edge("rag", "tool_router")
    graph.add_conditional_edges(
        "tool_router",
        _route_after_tool_router,
        {"tool_dispatch": "tool_dispatch", "fusion": "fusion"},
    )
    graph.add_edge("tool_dispatch", "tool_aggregate")
    graph.add_edge("tool_aggregate", "fusion")
    graph.add_edge("fusion", "reflect")
    graph.add_conditional_edges(
        "reflect",
        _route_after_reflect,
        {"tool_router": "tool_router", "final_answer": "generate_final"},
    )
    graph.add_edge("generate_final", END)
    return graph.compile()


agent_graph = _build_agent_graph()


async def run_agent_graph(message: str, history: list[dict]) -> dict:
    initial_state: AgentState = _initial_state(message, history)
    result = await agent_graph.ainvoke(initial_state)
    return {
        "intent": result.get("intent", "chitchat"),
        "sub_tasks": result.get("sub_tasks", []),
        "need_rag": result.get("need_rag", False),
        "need_tool": result.get("need_tool", False),
        "selected_tools": result.get("selected_tools", []),
        "contexts": result.get("rag_documents", []),
        "tool_results": result.get("tool_results", []),
        "tool_outputs": result.get("tool_outputs", {}),
        "fusion_context": result.get("fusion_context", ""),
        "answer": result.get("final_answer", result.get("answer", "")),
        "effective_message": result.get("effective_query", message),
        "route_trace": result.get("route_trace", []),
        "verification_passed": result.get("verification_passed", True),
        "verification_reason": result.get("verification_reason", "ok"),
        "retry_reason": result.get("retry_reason"),
    }


async def run_agent_graph_stream(message: str, history: list[dict]) -> AsyncIterator[str]:
    pre_generation_state = await _prepare_generation_state(message, history)
    query = pre_generation_state.get("effective_query") or message
    contexts = pre_generation_state.get("rag_documents", [])
    tool_results = pre_generation_state.get("tool_results", [])
    answer_parts: list[str] = []

    async for chunk in generate_answer_stream(query, history, contexts, tool_results):
        answer_parts.append(chunk)
        yield chunk

    answer = "".join(answer_parts)
    verified = verify_answer_detail(answer, contexts, pre_generation_state.get("intent", "chitchat"))
    if verified["answer"] != answer:
        yield f"\n\n{verified['answer']}"


async def _prepare_generation_state(message: str, history: list[dict]) -> AgentState:
    state: AgentState = _initial_state(message, history)
    state.update(await _plan_node(state))
    if state.get("need_rag"):
        state.update(_rag_node(state))
    state.update(await _tool_router_node(state))
    if state.get("need_tool") and state.get("selected_tools"):
        state.update(_tool_dispatch_node(state))
        state.update(_tool_aggregate_node(state))
    state.update(_fusion_node(state))
    state.update(_reflect_node(state))
    if state.get("need_retry"):
        state.update(await _tool_router_node(state))
        if state.get("need_tool") and state.get("selected_tools"):
            state.update(_tool_dispatch_node(state))
            state.update(_tool_aggregate_node(state))
        state.update(_fusion_node(state))
        state.update(_reflect_node(state))
    return state


async def _build_agent_plan(user_query: str, rewritten_query: str, history: list[dict]) -> AgentPlan:
    try:
        raw = await chat_completion(_build_planner_messages(user_query, rewritten_query, history))
        return _parse_plan_json(raw, rewritten_query)
    except Exception:
        return _fallback_plan(rewritten_query)


def _build_planner_messages(user_query: str, rewritten_query: str, history: list[dict]) -> list[dict[str, str]]:
    tool_text = "\n".join(f"- {name}: {desc}" for name, desc in TOOL_DESCRIPTIONS.items())
    history_text = _format_history_for_planner(history)
    return [
        {
            "role": "system",
            "content": (
                "你是灵枢智能助手的自主规划 Agent，只输出 JSON，不要输出 Markdown。"
                "你需要完成意图分类、任务拆解、RAG 判断、工具选择和工具参数规划。"
                "可选 intent 只有 chitchat 或 task。"
                "可选工具枚举只有 time, ip_lookup, weather, bilibili_video, web_search, "
                "netease_soaring, bilibili_popular。"
                "当问题涉及私有文档、项目代码、知识库内容、上传资料、RAG、实现分析时 need_rag=true。"
                "当问题涉及实时信息、外部网页、时间、IP、天气、B站、网易云榜单时 need_tool=true。"
                "多工具任务可以选择多个工具。"
                "输出字段必须包含 intent, rewritten_query, sub_tasks, need_rag, rag_search_query, "
                "need_tool, selected_tools, tool_input_params。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"工具列表：\n{tool_text}\n\n"
                f"历史对话：\n{history_text}\n\n"
                f"用户原始输入：{user_query}\n"
                f"上下文改写输入：{rewritten_query}\n\n"
                "请输出严格 JSON。"
            ),
        },
    ]


async def _retry_tool_plan(state: AgentState) -> AgentPlan:
    try:
        raw = await chat_completion(
            [
                {
                    "role": "system",
                    "content": (
                        "你是工具重选 Agent，只输出 JSON。根据反思原因重新选择工具。"
                        "可选工具：time, ip_lookup, weather, bilibili_video, web_search, netease_soaring, bilibili_popular。"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"用户问题：{state.get('effective_query') or state['user_query']}\n"
                        f"已有RAG：{state.get('rag_context', '')}\n"
                        f"已有工具结果：{_format_tool_outputs(state.get('tool_results', []))}\n"
                        f"反思原因：{state.get('retry_reason')}\n"
                        "请输出同 AgentPlan 字段兼容的严格 JSON。"
                    ),
                },
            ]
        )
        return _parse_plan_json(raw, state.get("effective_query") or state["user_query"])
    except Exception:
        query = state.get("effective_query") or state["user_query"]
        selected = normalize_tool_names([*state.get("selected_tools", []), "web_search"])
        return AgentPlan(
            intent="task",
            rewritten_query=query,
            sub_tasks=state.get("sub_tasks", []),
            need_rag=state.get("need_rag", False),
            rag_search_query=state.get("rag_search_query") or query,
            need_tool=bool(selected),
            selected_tools=selected,
            tool_input_params={"web_search": {"query": query, "max_results": 3}},
        )


def _parse_plan_json(raw: str, fallback_query: str) -> AgentPlan:
    payload = _extract_json_object(raw)
    try:
        plan = AgentPlan.model_validate(payload)
    except ValidationError:
        plan = _fallback_plan(fallback_query)
    selected_tools = normalize_tool_names(plan.selected_tools)
    return plan.model_copy(
        update={
            "rewritten_query": plan.rewritten_query or fallback_query,
            "selected_tools": selected_tools,
            "need_tool": plan.need_tool or bool(selected_tools),
            "tool_input_params": _normalize_tool_input_params(plan.tool_input_params, selected_tools),
        }
    )


def _extract_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            raise
        return json.loads(match.group(0))


def _fallback_plan(query: str) -> AgentPlan:
    intent = parse_intent(query)
    selected_tools = decide_tools(query) if intent == "task" else []
    need_rag = _fallback_need_rag(query, selected_tools) if intent == "task" else False
    return AgentPlan(
        intent=intent,
        rewritten_query=query,
        sub_tasks=[query] if intent == "task" else [],
        need_rag=need_rag,
        rag_search_query=query if need_rag else None,
        need_tool=bool(selected_tools),
        selected_tools=selected_tools,
        tool_input_params=_default_tool_params(query, selected_tools),
    )


def _fallback_need_rag(query: str, selected_tools: list[str]) -> bool:
    rag_keywords = [
        "RAG",
        "rag",
        "知识库",
        "向量",
        "文档",
        "资料",
        "检索",
        "上传",
        "项目",
        "Agent",
        "agent",
        "LangGraph",
        "langgraph",
        "实现",
        "优化",
        "流程",
        "代码",
    ]
    return any(keyword in query for keyword in rag_keywords) or not selected_tools


def _default_tool_params(query: str, selected_tools: list[str]) -> dict[str, dict[str, Any]]:
    params: dict[str, dict[str, Any]] = {}
    for tool_name in selected_tools:
        if tool_name in {"weather", "web_search"}:
            params[tool_name] = {"query": query}
        if tool_name == "web_search":
            params[tool_name]["max_results"] = 3
        if tool_name in {"bilibili_video", "bilibili_popular"}:
            params[tool_name] = {"limit": 20}
        if tool_name == "netease_soaring":
            params[tool_name] = {"limit": 100}
    return params


def _normalize_tool_input_params(
    params: dict[str, dict[str, Any]],
    selected_tools: list[str],
) -> dict[str, dict[str, Any]]:
    normalized: dict[str, dict[str, Any]] = {}
    for raw_name, raw_params in (params or {}).items():
        names = normalize_tool_names([raw_name])
        if not names:
            continue
        normalized[names[0]] = dict(raw_params or {})
    for tool_name in selected_tools:
        normalized.setdefault(tool_name, {})
    return normalized


def _initial_state(message: str, history: list[dict]) -> AgentState:
    return {
        "user_query": message,
        "message": message,
        "chat_history": history,
        "history": history,
        "sub_tasks": [],
        "rag_documents": [],
        "contexts": [],
        "rag_context": "",
        "selected_tools": [],
        "tool_input_params": {},
        "tool_outputs": {},
        "tool_results": [],
        "fusion_context": "",
        "need_retry": False,
        "retry_reason": None,
        "retry_count": 0,
        "route_trace": [],
    }


def _format_history_for_planner(history: list[dict], limit: int = 8) -> str:
    if not history:
        return "无"
    lines: list[str] = []
    for item in history[-limit:]:
        role = item.get("role", "unknown")
        content = _summarize_context_text(str(item.get("content") or ""), 240)
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def _format_rag_context(documents: list[Any]) -> str:
    if not documents:
        return ""
    return "\n\n".join(str(document) for document in documents[:5])


def _build_fusion_context(state: AgentState) -> str:
    blocks: list[str] = []
    blocks.append(f"用户问题：{state.get('effective_query') or state['user_query']}")
    if state.get("sub_tasks"):
        blocks.append("任务拆解：\n" + "\n".join(f"- {task}" for task in state["sub_tasks"]))
    if state.get("rag_context"):
        blocks.append("RAG 私有知识库上下文：\n" + state["rag_context"])
    if state.get("tool_results"):
        blocks.append("工具结果：\n" + _format_tool_outputs(state["tool_results"]))
    history_text = _format_history_for_planner(state.get("chat_history", []), limit=6)
    if history_text != "无":
        blocks.append("历史对话：\n" + history_text)
    return "\n\n".join(blocks)


def _format_tool_outputs(tool_results: list[dict]) -> str:
    if not tool_results:
        return ""
    blocks: list[str] = []
    for index, result in enumerate(tool_results, start=1):
        tool_name = result.get("tool") or "unknown"
        formatted = result.get("formatted") or result.get("message") or str(result)
        blocks.append(f"[Tool-{index}:{tool_name}]\n{formatted}")
    return "\n\n".join(blocks)


def _is_chitchat(state: AgentState) -> bool:
    return state.get("intent") == "chitchat" and not state.get("need_rag") and not state.get("need_tool")


def _reflection_retry_reason(state: AgentState) -> str | None:
    if state.get("need_rag") and not state.get("rag_documents"):
        if not state.get("tool_results"):
            return "rag_empty_and_no_tool_evidence"
    if state.get("need_tool") and not state.get("tool_results"):
        return "tool_selected_but_no_output"
    if _all_tools_failed(state.get("tool_results", [])):
        return "all_tools_failed"
    return None


def _all_tools_failed(tool_results: list[dict]) -> bool:
    if not tool_results:
        return False
    return all(result.get("implemented") is False or result.get("error") for result in tool_results)


def contextualize_message(message: str, history: list[dict]) -> str:
    current = message.strip()
    if not current:
        return message
    if _is_standalone_message(current):
        return message

    if _is_weather_followup(current):
        weather_context = _last_weather_context(history, current)
        if weather_context:
            city = _extract_city_followup(current) or weather_context.get("city", "")
            day = _extract_day_word(current) or weather_context.get("day", "") or "今天"
            if city:
                return f"{city}{day}天气如何"
            return f"{weather_context.get('message', '')}。用户追问：{current}"

    if _is_contextual_followup(current):
        conversation_context = _last_conversation_context(history, current)
        if conversation_context:
            return _build_contextualized_followup(current, conversation_context)

    return message


def _is_standalone_message(message: str) -> bool:
    if _has_followup_marker(message):
        return False
    explicit_markers = [
        "天气",
        "时间",
        "地点",
        "位置",
        "搜索",
        "联网",
        "知识库",
        "RAG",
        "rag",
        "Agent",
        "agent",
        "LangGraph",
        "实现",
        "分析",
        "总结",
        "优化",
        "项目",
        "代码",
        "接口",
    ]
    return any(marker in message for marker in explicit_markers)


def _is_contextual_followup(message: str) -> bool:
    if len(message) <= 14:
        return True
    return _has_followup_marker(message)


def _has_followup_marker(message: str) -> bool:
    followup_markers = [
        "它",
        "这个",
        "那个",
        "上述",
        "上面",
        "前面",
        "刚才",
        "继续",
        "还有",
        "另外",
        "为什么",
        "怎么",
        "如何",
        "能不能",
        "可以吗",
        "换成",
        "改成",
        "对比",
        "详细",
        "展开",
        "补充",
        "再说",
        "呢",
    ]
    return any(marker in message for marker in followup_markers)


def _last_conversation_context(history: list[dict], current: str) -> dict[str, str]:
    skipped_current = False
    last_user = ""
    last_assistant = ""
    for item in reversed(history):
        role = item.get("role")
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        if role == "user" and not skipped_current and content == current:
            skipped_current = True
            continue
        if role == "assistant" and not last_assistant:
            last_assistant = _summarize_context_text(content)
            continue
        if role == "user" and not last_user:
            last_user = _summarize_context_text(content)
        if last_user and last_assistant:
            break
    if not last_user and not last_assistant:
        return {}
    return {"last_user": last_user, "last_assistant": last_assistant}


def _build_contextualized_followup(message: str, context: dict[str, str]) -> str:
    parts: list[str] = []
    if context.get("last_user"):
        parts.append(f"上一轮用户问题：{context['last_user']}")
    if context.get("last_assistant"):
        parts.append(f"上一轮助手回答摘要：{context['last_assistant']}")
    context_text = "；".join(parts)
    return f"基于上下文（{context_text}），回答用户追问：{message}"


def _summarize_context_text(text: str, limit: int = 160) -> str:
    compact = " ".join(text.split())
    return compact[:limit]


def _is_weather_followup(message: str) -> bool:
    short_followup = len(message) <= 8 and (
        any(word in message for word in ["今天", "明天", "后天", "现在", "呢"])
        or bool(_extract_city_followup(message))
    )
    return short_followup and "天气" not in message


def _last_weather_context(history: list[dict], current: str) -> dict[str, str]:
    skipped_current = False
    for item in reversed(history):
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        if item.get("role") == "user" and not skipped_current and content == current:
            skipped_current = True
            continue
        if not _looks_like_weather_context(content):
            continue
        return {
            "message": content,
            "city": _extract_weather_city(content),
            "day": _extract_day_word(content),
        }
    return {}


def _looks_like_weather_context(message: str) -> bool:
    return "天气" in message or "气温" in message or "温度" in message or "风力" in message or "湿度" in message


def _extract_day_word(message: str) -> str:
    for word in ["今天", "明天", "后天"]:
        if word in message:
            return word
    if "现在" in message:
        return "今天"
    return ""


def _extract_weather_city(message: str) -> str:
    compact = "".join(message.split())
    weather_index = compact.find("天气")
    if weather_index <= 0:
        return _extract_city_from_weather_answer(compact)
    prefix = compact[:weather_index]
    for word in ["今天", "明天", "后天", "未来", "这几天", "近期", "最近", "的"]:
        prefix = prefix.replace(word, "")
    prefix = re.sub(r"^(帮我|请问|查一下|查询|看一下|问一下)", "", prefix)
    prefix = re.sub(r"(市|县|区)$", "", prefix)
    match = re.search(r"([\u4e00-\u9fff]{2,8})$", prefix)
    return match.group(1) if match else ""


def _extract_city_followup(message: str) -> str:
    compact = "".join(message.split())
    compact = compact.replace("呢", "").replace("?", "").replace("？", "")
    compact = re.sub(r"(今天|明天|后天|现在|的|市|县|区)$", "", compact)
    if not 2 <= len(compact) <= 8:
        return ""
    if any(word in compact for word in ["今天", "明天", "后天", "现在", "天气"]):
        return ""
    return compact if re.fullmatch(r"[\u4e00-\u9fff]{2,8}", compact) else ""


def _extract_city_from_weather_answer(message: str) -> str:
    patterns = [
        r"([\u4e00-\u9fff]{2,8})市的天气",
        r"([\u4e00-\u9fff]{2,8})的天气",
        r"([\u4e00-\u9fff]{2,8})天气",
        r"([\u4e00-\u9fff]{2,8})市天气",
    ]
    for pattern in patterns:
        match = re.search(pattern, message)
        if match:
            return match.group(1)
    return ""
