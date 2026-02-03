"""
LangGraph Agent with Translation Sandwich
Qualification Flow State Machine with multi-language support.
"""

from typing import TypedDict, List
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, SystemMessage, AIMessage, HumanMessage
from langchain_openai import ChatOpenAI
from .tools import TOOLS, check_availability, generate_payment_link, qualify_lead
from ..services.translation import translation_service
import json


# Define the State (PRD v1.2 compliant)
class AgentState(TypedDict):
    messages: List[BaseMessage]
    lead_data: dict
    next_step: str
    language: str  # Detected language code (e.g., 'DE', 'ES')
    original_input: str  # Preserved original input for context
    channel: str  # PRD Zone 1: web, whatsapp, instagram, telegram
    handoff_flag: bool  # PRD Module C: Whether to escalate to human
    handoff_reason: (
        str  # PRD Module C: ambiguity, high_value, complaint, medical_risk, fallback
    )


# Node: Translation Input (Step 1 of Sandwich)
def translate_input_node(state: AgentState) -> dict:
    """
    Translate incoming user message to English.
    Preserves original language for response translation.
    """
    if not state["messages"]:
        return {}

    last_message = state["messages"][-1]

    # Only translate HumanMessages
    if not isinstance(last_message, HumanMessage):
        return {}

    original_text = last_message.content

    # Translate to English and detect language
    english_text, detected_lang = translation_service.translate_to_english(
        original_text
    )

    # Update the message with English text for LLM
    if detected_lang != "EN" and english_text != original_text:
        # Replace last message with translated version
        translated_message = HumanMessage(content=english_text)
        messages = state["messages"][:-1] + [translated_message]

        return {
            "messages": messages,
            "language": detected_lang,
            "original_input": original_text,
        }

    return {"language": "EN"}


# Node: AI Agent (The Brain) - Processes with RAG and optional multilingual output
def agent_node(state: AgentState) -> dict:
    from ..services.knowledge_base import knowledge_base

    llm = ChatOpenAI(model="gpt-4o", temperature=0.7)
    llm_with_tools = llm.bind_tools(TOOLS)

    # Get language for context
    lang_code = state.get("language", "EN")
    lang_name = translation_service.get_language_name(lang_code)

    # Check if translation service is available
    translation_available = translation_service.is_available

    # Get last user message for RAG context
    user_query = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            user_query = msg.content
            break

    # Retrieve relevant knowledge base context
    kb_context = ""
    if user_query:
        kb_context = knowledge_base.get_context_for_query(user_query)

    # Build language instruction based on translation availability
    if translation_available and lang_code != "EN":
        # DeepL will handle translation - respond in English
        language_instruction = f"The user speaks {lang_name}. Respond in English (translation handled separately)."
    elif lang_code == "EN":
        language_instruction = "Respond in English."
    else:
        # No DeepL - GPT-4 must respond directly in user's language
        language_instruction = f"""IMPORTANT: The user speaks {lang_name}. 
You MUST respond entirely in {lang_name}. Do NOT respond in English.
All your messages, questions, and suggestions must be in {lang_name}."""

    # System prompt with knowledge base context
    system_prompt = f"""You are the Aesthetic Concierge for Luxe MedSpa, a high-end medical aesthetics clinic.

{language_instruction}

{kb_context}

CORE BEHAVIORS:
1. **Empathy First**: If a user expresses fear (pain, needles), reassure them with our "Comfort Protocol".
2. **Medical Expertise**: Use the knowledge base information above to provide accurate, professional answers.
3. **Qualification Flow**: Service Interest → Timeline → Medical Safety Check
4. **Booking**: If qualified, use 'check_availability' and 'generate_payment_link' tools.

SAFETY:
- Do not give medical diagnoses.
- If pregnancy mentioned, politely decline treatment.
- For severe concerns (vision changes, severe pain), advise immediate medical attention.

Be warm, professional, and empathetic. Acknowledge aesthetic goals enthusiastically.
"""

    messages = [SystemMessage(content=system_prompt)] + state["messages"]
    response = llm_with_tools.invoke(messages)

    return {"messages": [response]}


# Node: Translation Output (Step 3 of Sandwich)
def translate_output_node(state: AgentState) -> dict:
    """
    Translate agent response back to user's language.
    """
    if not state["messages"]:
        return {}

    last_message = state["messages"][-1]
    target_lang = state.get("language", "EN")

    # Only translate AIMessages to non-English
    if isinstance(last_message, AIMessage) and target_lang != "EN":
        translated_content = translation_service.translate_from_english(
            last_message.content, target_lang
        )

        if translated_content != last_message.content:
            # Create new message with translated content
            translated_message = AIMessage(
                content=translated_content,
                tool_calls=last_message.tool_calls
                if hasattr(last_message, "tool_calls")
                else [],
            )
            messages = state["messages"][:-1] + [translated_message]
            return {"messages": messages}

    return {}


# Node: Tool Execution (PRD Module C: Handoff Detection)
def tool_execution_node(state: AgentState) -> dict:
    from langchain_core.messages import ToolMessage

    last_message = state["messages"][-1]
    tool_calls = last_message.tool_calls

    responses = []
    handoff_flag = False
    handoff_reason = None

    for tool_call in tool_calls:
        func_name = tool_call["name"]
        args = tool_call["args"]

        if func_name == "qualify_lead":
            result = qualify_lead(**args)
            # Check for handoff trigger from qualification
            if result.get("action") == "ESCALATE_TO_HUMAN":
                handoff_flag = True
                handoff_reason = "medical_risk"
        elif func_name == "check_availability":
            result = check_availability(**args)
        elif func_name == "generate_payment_link":
            result = generate_payment_link(**args)
        else:
            result = {"error": "Tool not found"}

        responses.append(
            ToolMessage(content=json.dumps(result), tool_call_id=tool_call["id"])
        )

    # Return with handoff flags if triggered
    return_data = {"messages": responses}
    if handoff_flag:
        return_data["handoff_flag"] = handoff_flag
        return_data["handoff_reason"] = handoff_reason

    return return_data


# Edge Logic
def should_continue(state: AgentState):
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return "translate_output"


def after_translate_output(state: AgentState):
    return END


# Build the Graph with Translation Sandwich
workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("translate_input", translate_input_node)
workflow.add_node("agent", agent_node)
workflow.add_node("tools", tool_execution_node)
workflow.add_node("translate_output", translate_output_node)

# Set entry point (translation first)
workflow.set_entry_point("translate_input")

# Define edges
workflow.add_edge("translate_input", "agent")
workflow.add_conditional_edges(
    "agent", should_continue, {"tools": "tools", "translate_output": "translate_output"}
)
workflow.add_edge("tools", "agent")
workflow.add_edge("translate_output", END)

# Compile
app = workflow.compile()
