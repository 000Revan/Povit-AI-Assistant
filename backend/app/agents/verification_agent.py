from typing import TypedDict


class VerificationResult(TypedDict):
    answer: str
    passed: bool
    reason: str


def verify_answer(answer: str, contexts: list[str], intent: str) -> str:
    return verify_answer_detail(answer, contexts, intent)["answer"]


def verify_answer_detail(answer: str, contexts: list[str], intent: str) -> VerificationResult:
    if intent == "task" and not contexts and any(word in answer for word in ["根据资料", "文档中", "明确指出"]):
        return {
            "answer": "未找到相关知识库信息，暂不能给出基于私有资料的确定回答。",
            "passed": False,
            "reason": "answer_claims_private_knowledge_without_context",
        }
    if not answer.strip():
        return {
            "answer": "暂时没有生成有效回答，请稍后重试。",
            "passed": False,
            "reason": "empty_answer",
        }
    return {"answer": answer, "passed": True, "reason": "ok"}
