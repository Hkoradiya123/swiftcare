import logging

from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

logger = logging.getLogger(__name__)

from app.ai.agent.clinical import make_clinical_tools
from app.ai.agent.scheduling import make_scheduling_tools
from app.ai.history import load_history, save_history, new_conversation_id
from app.core.config import get_settings
from app.db.engine import AsyncSessionLocal
from app.models.user import User

_RECURSION_LIMIT = {"recursion_limit": 15}


def _history_to_messages(history: list[dict]) -> list:
    result = []
    for m in history:
        if m["role"] == "user":
            result.append(HumanMessage(content=m["content"]))
        elif m["role"] == "assistant":
            result.append(AIMessage(content=m["content"]))
    return result


async def run_chat(
    message: str,
    current_user: User | None,
    conversation_id: str | None = None,
) -> tuple[str, str]:
    """
    Run the multi-agent supervisor.
    Returns (reply, conversation_id).
    """
    if not conversation_id:
        conversation_id = new_conversation_id()

    user_id = current_user.id if current_user else None
    history = await load_history(conversation_id, user_id)
    settings = get_settings()

    llm = ChatOpenAI(model=settings.openai_model, api_key=settings.openai_api_key, temperature=0)

    scheduling_tools = make_scheduling_tools(AsyncSessionLocal, current_user)
    clinical_tools = make_clinical_tools(AsyncSessionLocal, current_user)

    scheduling_agent = create_react_agent(
        llm,
        scheduling_tools,
        prompt="You are a scheduling assistant for a healthcare clinic. "
               "Help with finding providers, checking availability, and booking appointments. "
               "IMPORTANT: Before booking any appointment, always call confirm_appointment_details first "
               "and return the confirmation to the user. Only call book_appointment after the user "
               "explicitly replies yes or confirm.",
    )
    clinical_agent = create_react_agent(
        llm,
        clinical_tools,
        prompt="You are a clinical assistant for healthcare providers. "
               "Help with patient history, prescriptions, allergies, and medical record queries. "
               "Always respect patient privacy and only share information with authorised users. "
               "IMPORTANT: Before creating any prescription, always call confirm_prescription_details first "
               "and return the confirmation to the user. Only call create_prescription after the user "
               "explicitly replies yes or confirm.",
    )

    @tool
    async def ask_scheduling(query: str) -> str:
        """
        Handle anything related to scheduling: finding providers by specialization,
        checking slot availability, and booking appointments.
        """
        result = await scheduling_agent.ainvoke(
            {"messages": [HumanMessage(content=query)]},
            config=_RECURSION_LIMIT,
        )
        return result["messages"][-1].content

    @tool
    async def ask_clinical(query: str) -> str:
        """
        Handle clinical queries: patient visit history, prescriptions, allergies,
        and any medical record questions. Requires the caller to be authenticated.
        """
        result = await clinical_agent.ainvoke(
            {"messages": [HumanMessage(content=query)]},
            config=_RECURSION_LIMIT,
        )
        return result["messages"][-1].content

    role_context = "unauthenticated guest"
    if current_user:
        role_context = f"{current_user.role} (user_id={current_user.id})"

    supervisor = create_react_agent(
        llm,
        [ask_scheduling, ask_clinical],
        prompt=f"You are a helpful clinical assistant for SwiftCare. "
               f"The current user is a {role_context}. "
               f"Route scheduling requests to ask_scheduling and clinical/medical requests to ask_clinical. "
               f"Guests can only access public information (provider list, availability). "
               f"Be concise and professional.",
    )

    prior_messages = _history_to_messages(history)
    all_messages = prior_messages + [HumanMessage(content=message)]

    try:
        result = await supervisor.ainvoke(
            {"messages": all_messages},
            config=_RECURSION_LIMIT,
        )
        reply = result["messages"][-1].content
    except Exception:
        logger.exception(
            "agent_run_failed conversation_id=%s user_id=%s",
            conversation_id, user_id,
        )
        return "I encountered an error processing your request. Please try again.", conversation_id

    updated_history = history + [
        {"role": "user", "content": message},
        {"role": "assistant", "content": reply},
    ]
    await save_history(conversation_id, user_id, updated_history)

    return reply, conversation_id
