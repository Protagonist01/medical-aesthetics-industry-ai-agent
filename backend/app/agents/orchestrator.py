"""
Unified Orchestrator using LangGraph
Handles all channels: Web, WhatsApp, Instagram
"""

import time
from typing import List
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from .graph import app as langgraph_app
from .memory import memory
from .empathy import empathy_guardrail
from ..services.cost import cost_service


async def run_agent(
    messages: List[dict],
    source: str,
    session_id: str = "default",
    language: str = "English",
):
    """
    Unified entry point for all channels.
    Routes through LangGraph with translation sandwich.
    """
    start_time = time.time()

    # Add new user message to memory
    last_user_msg = messages[-1]
    memory.add_message(session_id, last_user_msg)

    # Check empathy guardrail for immediate responses
    empathy_res = empathy_guardrail(last_user_msg["content"])
    if empathy_res:
        response_text = empathy_res
    else:
        # Convert message history to LangChain format
        langchain_messages = []
        for msg in memory.get_history(session_id):
            if msg["role"] == "user":
                langchain_messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                langchain_messages.append(AIMessage(content=msg["content"]))
            elif msg["role"] == "system":
                langchain_messages.append(SystemMessage(content=msg["content"]))

        # Map language name to code for translation service
        lang_code_map = {
            "English": "EN",
            "German": "DE",
            "Spanish": "ES",
            "French": "FR",
            "Italian": "IT",
            "Portuguese": "PT",
            "Dutch": "NL",
            "Polish": "PL",
            "Russian": "RU",
            "Japanese": "JA",
            "Chinese": "ZH",
            "Arabic": "AR",
            "Turkish": "TR",
        }

        lang_code = lang_code_map.get(language, "EN")

        # Prepare initial state for LangGraph
        initial_state = {
            "messages": langchain_messages,
            "lead_data": {},
            "next_step": "greeting",
            "language": lang_code,
            "original_input": last_user_msg["content"],
        }

        try:
            # Invoke LangGraph (handles translation sandwich + RAG)
            result = langgraph_app.invoke(initial_state)

            # Extract final response
            final_messages = result.get("messages", [])
            if final_messages:
                last_response = final_messages[-1]
                if isinstance(last_response, AIMessage):
                    response_text = last_response.content
                else:
                    response_text = str(last_response.content)
            else:
                response_text = "I'm here to help with your aesthetic journey. What would you like to know?"

        except Exception as e:
            print(f"LangGraph error: {e}")
            response_text = "I apologize, but I'm having trouble connecting right now. Could you try again in a moment?"

    # Save assistant response to memory
    assistant_msg = {
        "role": "assistant",
        "content": response_text,
        "source": source,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    memory.add_message(session_id, assistant_msg)

    # Cost tracking
    input_tokens = len(last_user_msg["content"]) // 4
    output_tokens = len(response_text) // 4
    duration = int((time.time() - start_time) * 1000)

    cost_data = cost_service.calculate_cost(
        input_tokens, output_tokens, duration, session_id
    )

    return {**assistant_msg, "cost": cost_data}
