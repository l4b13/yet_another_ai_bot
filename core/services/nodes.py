from typing import TypedDict
from langgraph.graph import StateGraph
from langchain.messages import AnyMessage, HumanMessage, AIMessage


class SimpleGraphState(TypedDict):
    messages: list[AnyMessage]
    
    result: AIMessage


async def generate(state: SimpleGraphState):
    return {
        "result": result
    }