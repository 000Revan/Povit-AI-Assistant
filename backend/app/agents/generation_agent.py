import asyncio
from collections.abc import AsyncIterator

from app.services.llm_client import chat_completion, stream_chat_completion


def build_generation_messages(message: str, history: list[dict], contexts: list[str], tool_results: list[dict]) -> list[dict[str, str]]:
    context_text = _format_rag_contexts(contexts)
    tool_text = _format_tool_results(tool_results)
    return [
        {
            "role": "system",
            "content": (
                "你是灵枢智能助手。回答要简洁、可靠。"
                "如果提供了知识库片段，必须优先依据片段回答。"
                "如果同时提供了 Tavily 搜索结果，需要结合搜索结果中的 Title、URL、Content 补充最新或外部信息。"
                "如果提供了爬虫工具结果，需要优先基于工具结果回答，只展示用户关心的推荐内容，忽略内部记录字段。"
                "使用爬虫工具结果推荐内容时，回答必须分行展示，避免把多个条目连成一整段。"
                "推荐类回答优先使用：简短开场 + 编号列表 + 每条 2 到 4 个关键字段。"
                "回答中可以引用 URL，但不要编造未出现在知识库或搜索结果中的事实。"
                "如果私有知识库和搜索结果都无相关资料，应说明未找到相关信息。"
            ),
        },
        *[{"role": item["role"], "content": item["content"]} for item in history[-8:]],
        {
            "role": "user",
            "content": (
                f"用户输入：{message}\n\n"
                f"RAG 检索内容：\n{context_text}\n\n"
                f"搜索或工具返回内容：\n{tool_text}\n\n"
                "请基于以上内容回答用户。"
            ),
        },
    ]


async def generate_answer(message: str, history: list[dict], contexts: list[str], tool_results: list[dict]) -> str:
    crawler_answer = _direct_crawler_answer(tool_results)
    if crawler_answer:
        return crawler_answer

    try:
        return await chat_completion(build_generation_messages(message, history, contexts, tool_results))
    except Exception:
        return _local_rag_answer(message, contexts, tool_results)


async def generate_answer_stream(
    message: str,
    history: list[dict],
    contexts: list[str],
    tool_results: list[dict],
) -> AsyncIterator[str]:
    crawler_answer = _direct_crawler_answer(tool_results)
    if crawler_answer:
        for chunk in _split_for_stream(crawler_answer, size=12):
            yield chunk
            await asyncio.sleep(0.01)
        return

    try:
        async for chunk in stream_chat_completion(build_generation_messages(message, history, contexts, tool_results)):
            yield chunk
        return
    except Exception:
        fallback = _local_rag_answer(message, contexts, tool_results)
        for chunk in _split_for_stream(fallback):
            yield chunk
            await asyncio.sleep(0.015)


def _local_rag_answer(message: str, contexts: list[str], tool_results: list[dict]) -> str:
    search_text = _format_tool_results(tool_results)
    if contexts or tool_results:
        rag_text = "\n\n".join(context[:500] for context in contexts[:3]) if contexts else "无检索结果"
        return (
            f"我已整理与“{message}”相关的上下文：\n\n"
            f"RAG 检索内容：\n{rag_text}\n\n"
            f"搜索或工具返回内容：\n{search_text}\n\n"
            "以上为本地降级回答，后续接通大模型后会生成更自然的综合回答。"
        )
    return "当前未检索到相关知识库片段，也无法连接大模型生成回答。"


def _split_for_stream(text: str, size: int = 4) -> list[str]:
    return [text[index : index + size] for index in range(0, len(text), size)]


def _format_rag_contexts(contexts: list[str]) -> str:
    if not contexts:
        return "无检索结果"
    return "\n\n".join(f"[RAG-{index}]\n{context}" for index, context in enumerate(contexts[:5], start=1))


def _format_tool_results(tool_results: list[dict]) -> str:
    if not tool_results:
        return "无搜索或工具结果"

    blocks: list[str] = []
    for result in tool_results:
        if result.get("tool") == "tavily_search":
            blocks.append(result.get("formatted") or "Tavily 搜索结果：无内容")
        else:
            blocks.append(result.get("formatted") or str(result))
    return "\n\n".join(blocks)


def _direct_crawler_answer(tool_results: list[dict]) -> str | None:
    crawler_tools = {"netease_soaring_crawler", "bilibili_popular_crawler"}
    blocks = [
        result["formatted"]
        for result in tool_results
        if result.get("tool") in crawler_tools and result.get("implemented") and result.get("formatted")
    ]
    return "\n\n".join(blocks) if blocks else None
