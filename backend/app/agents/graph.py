from collections.abc import AsyncIterator

from app.agents.generation_agent import generate_answer, generate_answer_stream
from app.agents.intent_agent import parse_intent
from app.agents.rag_agent import run_rag
from app.agents.tool_agent import run_tools
from app.agents.verification_agent import verify_answer


async def run_agent_graph(message: str, history: list[dict]) -> dict:
    intent = parse_intent(message)
    contexts = run_rag(message) if intent == "task" else []
    tool_results = run_tools(message) if intent == "task" else []
    answer = await generate_answer(message, history, contexts, tool_results)
    verified = verify_answer(answer, contexts, intent)
    return {"intent": intent, "contexts": contexts, "tool_results": tool_results, "answer": verified}


async def run_agent_graph_stream(message: str, history: list[dict]) -> AsyncIterator[str]:
    intent = parse_intent(message)
    contexts = run_rag(message) if intent == "task" else []
    tool_results = run_tools(message) if intent == "task" else []
    answer_parts: list[str] = []

    async for chunk in generate_answer_stream(message, history, contexts, tool_results):
        answer_parts.append(chunk)
        yield chunk

    answer = "".join(answer_parts)
    verified = verify_answer(answer, contexts, intent)
    if verified != answer:
        correction = f"\n\n{verified}"
        yield correction
