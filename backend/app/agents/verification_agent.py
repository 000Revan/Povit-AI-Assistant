def verify_answer(answer: str, contexts: list[str], intent: str) -> str:
    if intent == "task" and not contexts and any(word in answer for word in ["根据资料", "文档中", "明确指出"]):
        return "未找到相关知识库信息，暂不能给出基于私有资料的确定回答。"
    return answer

