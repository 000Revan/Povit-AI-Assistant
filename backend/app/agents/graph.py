from collections.abc import AsyncIterator
import re
from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents.generation_agent import generate_answer, generate_answer_stream
from app.agents.intent_agent import parse_intent
from app.agents.rag_agent import run_rag
from app.agents.tool_agent import decide_tools, run_tools
from app.agents.verification_agent import verify_answer_detail


class AgentState(TypedDict, total=False):
    message: str
    effective_message: str
    history: list[dict]
    intent: Literal["chitchat", "task"]
    needs_rag: bool
    selected_tools: list[str]
    contexts: list[str]
    tool_results: list[dict]
    answer: str
    verification_passed: bool
    verification_reason: str
    route_trace: list[str]


def _append_trace(state: AgentState, item: str) -> list[str]:
    return [*state.get("route_trace", []), item]


def _contextualize_node(state: AgentState) -> AgentState:
    effective_message = contextualize_message(state["message"], state.get("history", []))
    trace_item = "contextualize"
    if effective_message != state["message"]:
        trace_item = f"contextualize:{effective_message}"
    return {"effective_message": effective_message, "route_trace": _append_trace(state, trace_item)}


def _classify_intent_node(state: AgentState) -> AgentState:
    intent = parse_intent(state.get("effective_message") or state["message"])
    return {"intent": intent, "route_trace": _append_trace(state, f"intent:{intent}")}


def _plan_resources_node(state: AgentState) -> AgentState:
    message = state.get("effective_message") or state["message"]
    selected_tools = decide_tools(message)
    needs_rag = _should_use_rag(message, selected_tools)
    return {
        "needs_rag": needs_rag,
        "selected_tools": selected_tools,
        "route_trace": _append_trace(
            state,
            f"plan:rag={needs_rag},tools={','.join(selected_tools) or 'none'}",
        ),
    }


def _rag_node(state: AgentState) -> AgentState:
    contexts = run_rag(state.get("effective_message") or state["message"])
    return {"contexts": contexts, "route_trace": _append_trace(state, f"rag:{len(contexts)}")}


def _tools_node(state: AgentState) -> AgentState:
    selected_tools = state.get("selected_tools", [])
    tool_results = run_tools(state.get("effective_message") or state["message"], selected_tools)
    return {"tool_results": tool_results, "route_trace": _append_trace(state, f"tools:{len(tool_results)}")}


def _merge_context_node(state: AgentState) -> AgentState:
    return {
        "contexts": state.get("contexts", []),
        "tool_results": state.get("tool_results", []),
        "route_trace": _append_trace(state, "merge_context"),
    }


async def _generate_node(state: AgentState) -> AgentState:
    answer = await generate_answer(
        state.get("effective_message") or state["message"],
        state.get("history", []),
        state.get("contexts", []),
        state.get("tool_results", []),
    )
    return {"answer": answer, "route_trace": _append_trace(state, "generate")}


def _verify_node(state: AgentState) -> AgentState:
    result = verify_answer_detail(
        state.get("answer", ""),
        state.get("contexts", []),
        state.get("intent", "chitchat"),
    )
    return {
        "answer": result["answer"],
        "verification_passed": result["passed"],
        "verification_reason": result["reason"],
        "route_trace": _append_trace(state, f"verify:{result['reason']}"),
    }


def _route_after_intent(state: AgentState) -> str:
    return "plan_resources" if state.get("intent") == "task" else "generate"


def _route_after_plan(state: AgentState) -> str:
    if state.get("needs_rag"):
        return "rag"
    if state.get("selected_tools"):
        return "tools"
    return "merge_context"


def _route_after_rag(state: AgentState) -> str:
    return "tools" if state.get("selected_tools") else "merge_context"


def _should_use_rag(message: str, selected_tools: list[str]) -> bool:
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
    if any(keyword in message for keyword in rag_keywords):
        return True
    return not selected_tools


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
    if any(marker in message for marker in explicit_markers):
        return True
    if len(message) <= 8:
        return False
    return False


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


def _build_agent_graph():
    graph = StateGraph(AgentState)
    graph.add_node("contextualize", _contextualize_node)
    graph.add_node("classify_intent", _classify_intent_node)
    graph.add_node("plan_resources", _plan_resources_node)
    graph.add_node("rag", _rag_node)
    graph.add_node("tools", _tools_node)
    graph.add_node("merge_context", _merge_context_node)
    graph.add_node("generate", _generate_node)
    graph.add_node("verify", _verify_node)

    graph.add_edge(START, "contextualize")
    graph.add_edge("contextualize", "classify_intent")
    graph.add_conditional_edges(
        "classify_intent",
        _route_after_intent,
        {"plan_resources": "plan_resources", "generate": "generate"},
    )
    graph.add_conditional_edges(
        "plan_resources",
        _route_after_plan,
        {"rag": "rag", "tools": "tools", "merge_context": "merge_context"},
    )
    graph.add_conditional_edges(
        "rag",
        _route_after_rag,
        {"tools": "tools", "merge_context": "merge_context"},
    )
    graph.add_edge("tools", "merge_context")
    graph.add_edge("merge_context", "generate")
    graph.add_edge("generate", "verify")
    graph.add_edge("verify", END)
    return graph.compile()


agent_graph = _build_agent_graph()


async def run_agent_graph(message: str, history: list[dict]) -> dict:
    initial_state: AgentState = {"message": message, "history": history, "contexts": [], "tool_results": []}
    result = await agent_graph.ainvoke(initial_state)
    return {
        "intent": result.get("intent", "chitchat"),
        "contexts": result.get("contexts", []),
        "tool_results": result.get("tool_results", []),
        "answer": result.get("answer", ""),
        "effective_message": result.get("effective_message", message),
        "route_trace": result.get("route_trace", []),
        "verification_passed": result.get("verification_passed", True),
        "verification_reason": result.get("verification_reason", "ok"),
    }


async def run_agent_graph_stream(message: str, history: list[dict]) -> AsyncIterator[str]:
    pre_generation_state = await _prepare_generation_state(message, history)
    contexts = pre_generation_state.get("contexts", [])
    tool_results = pre_generation_state.get("tool_results", [])
    answer_parts: list[str] = []

    async for chunk in generate_answer_stream(message, history, contexts, tool_results):
        answer_parts.append(chunk)
        yield chunk

    answer = "".join(answer_parts)
    verified = verify_answer_detail(answer, contexts, pre_generation_state.get("intent", "chitchat"))
    if verified["answer"] != answer:
        correction = f"\n\n{verified['answer']}"
        yield correction


async def _prepare_generation_state(message: str, history: list[dict]) -> AgentState:
    state: AgentState = {"message": message, "history": history, "contexts": [], "tool_results": []}
    state.update(_contextualize_node(state))
    state.update(_classify_intent_node(state))
    if state.get("intent") != "task":
        return state
    state.update(_plan_resources_node(state))
    if state.get("needs_rag"):
        state.update(_rag_node(state))
    if state.get("selected_tools"):
        state.update(_tools_node(state))
    state.update(_merge_context_node(state))
    return state
