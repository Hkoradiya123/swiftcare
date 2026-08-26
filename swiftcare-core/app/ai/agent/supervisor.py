import logging
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

logger = logging.getLogger(__name__)

from app.ai.agent.clinical import make_clinical_tools
from app.ai.agent.scheduling import make_scheduling_tools
from app.ai.history import (
    load_history, save_history, new_conversation_id,
    load_sub_messages, save_sub_messages, clear_sub_messages,
    load_pending_action, clear_pending_action,
)
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

    norm_msg = message.strip().lower().rstrip(".!")

    # ── Fast-path 1: Deterministic cancellation of pending action ─────────────
    if norm_msg in {"cancel", "no", "n", "dont book", "don't book", "stop"}:
        pending = await load_pending_action(conversation_id, user_id)
        if pending:
            await clear_pending_action(conversation_id, user_id)
            reply = "Appointment booking has been cancelled."
            updated_history = history + [
                {"role": "user", "content": message},
                {"role": "assistant", "content": reply},
            ]
            await save_history(conversation_id, user_id, updated_history)
            return reply, conversation_id

    # ── Fast-path 2: Deterministic execution of pending booking ────────────────
    if norm_msg in {"yes", "y", "confirm", "confirmed", "proceed", "please book", "book it", "sure", "ok", "confirm and book"}:
        pending = await load_pending_action(conversation_id, user_id)
        if pending and pending.get("action_type") == "book_appointment":
            from app.schemas.appointment import AppointmentCreate
            from app.services.appointment import AppointmentService
            from app.models.enums import AppointmentType

            async with AsyncSessionLocal() as db:
                if current_user and current_user.role == "patient":
                    from app.repositories.patient import PatientRepository
                    patient = await PatientRepository(db).get_by_user_id(current_user.id)
                    if not patient or patient.id != pending["patient_id"]:
                        reply = "Patients can only book appointments for themselves."
                        await clear_pending_action(conversation_id, user_id)
                        return reply, conversation_id

                appt_type = AppointmentType.IN_PERSON if pending["appointment_type"] == "in_person" else AppointmentType.TELEHEALTH
                data = AppointmentCreate(
                    patient_id=pending["patient_id"],
                    provider_id=pending["provider_id"],
                    appointment_type=appt_type,
                    scheduled_start=datetime.fromisoformat(pending["start_datetime"]),
                    scheduled_end=datetime.fromisoformat(pending["end_datetime"]),
                    reason=pending["reason"],
                )
                try:
                    appt = await AppointmentService(db).create(data)
                    await clear_pending_action(conversation_id, user_id)
                    await clear_sub_messages(conversation_id, user_id, "scheduling")
                    reply = (
                        f"Appointment successfully booked! Appointment ID: {appt.id}, "
                        f"Status: {appt.status}. A confirmation email and notification have been sent."
                    )
                except Exception as e:
                    detail = getattr(e, "detail", str(e))
                    reply = f"Failed to book appointment: {detail}"

            updated_history = history + [
                {"role": "user", "content": message},
                {"role": "assistant", "content": reply},
            ]
            await save_history(conversation_id, user_id, updated_history)
            return reply, conversation_id

    # ── Conversational Orchestration with LLM ──────────────────────────────────
    llm = ChatOpenAI(model=settings.openai_model, api_key=settings.openai_api_key, temperature=0)

    if current_user:
        user_context = f"The user is authenticated as {current_user.full_name}, a {current_user.role} (user_id={current_user.id}). They are logged in and authorized to book appointments."
        guest_restriction = ""
    else:
        user_context = "The user is an unauthenticated guest."
        guest_restriction = (
            "Guests can browse providers and availability but CANNOT book appointments — if a guest tries to book, "
            "tell them they must log in first and do not call book_appointment. "
        )

    scheduling_tools = make_scheduling_tools(AsyncSessionLocal, current_user, conversation_id)
    clinical_tools = make_clinical_tools(AsyncSessionLocal, current_user)

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    scheduling_agent = create_react_agent(
        llm,
        scheduling_tools,
        prompt=f"You are a scheduling assistant for a healthcare clinic. "
               f"{user_context} "
               f"Current date and time: {now_utc}. "
               f"{guest_restriction}"
               f"To find a provider by name use search_provider_by_name or find_providers_by_specialization or list_all_providers. "
               f"IMPORTANT: Before booking any appointment, always call confirm_appointment_details first "
               f"and return the confirmation to the user. "
               f"If a tool returns an error, surface that error to the user directly — do not retry. "
               f"Never use markdown formatting — plain text only.",
    )
    clinical_agent = create_react_agent(
        llm,
        clinical_tools,
        prompt=f"You are a clinical assistant for healthcare providers. "
               f"{user_context} "
               f"Help with patient history, prescriptions, allergies, and medical record queries. "
               f"Always respect patient privacy and only share information with authorised users. "
               f"PRESCRIPTION RULES: "
               f"(1) When asked to add or prescribe a drug without explicit confirmation, call confirm_prescription_details first and return the output to the caller — do not call create_prescription yet. "
               f"(2) When the query says 'confirmed', 'user confirmed', 'create prescription', 'proceed to create', or 'yes' in the context of a previously shown prescription — call create_prescription directly WITHOUT calling confirm_prescription_details again. "
               f"(3) Never ask for patient_id — it is resolved automatically from appointment_id. "
               f"(4) If a tool returns an error, surface that error directly — do not retry. "
               f"Never use markdown formatting — plain text only.",
    )

    recent_context = _history_to_messages(history[-6:])

    @tool
    async def ask_scheduling(query: str) -> str:
        """
        Handle anything related to scheduling: finding providers by specialization or name,
        checking slot availability, and booking appointments.
        """
        prior = await load_sub_messages(conversation_id, user_id, "scheduling")
        input_messages = (prior or recent_context) + [HumanMessage(content=query)]
        result = await scheduling_agent.ainvoke(
            {"messages": input_messages},
            config=_RECURSION_LIMIT,
        )
        reply = result["messages"][-1].content
        if '"appointment_id"' in reply:
            await clear_sub_messages(conversation_id, user_id, "scheduling")
        else:
            await save_sub_messages(conversation_id, user_id, "scheduling", result["messages"])
        return reply

    @tool
    async def ask_clinical(query: str) -> str:
        """
        Handle clinical queries: patient visit history, prescriptions, allergies,
        and any medical record questions. Requires the caller to be authenticated.
        """
        result = await clinical_agent.ainvoke(
            {"messages": recent_context + [HumanMessage(content=query)]},
            config=_RECURSION_LIMIT,
        )
        return result["messages"][-1].content

    supervisor = create_react_agent(
        llm,
        [ask_scheduling, ask_clinical],
        prompt=f"You are a helpful clinical assistant for SwiftCare. "
               f"{user_context} "
               f"Route scheduling requests (booking, providers, availability) to ask_scheduling and clinical/medical requests to ask_clinical. "
               f"Guests can only access public information (provider list, availability). "
               f"Be concise and professional. "
               f"Never use markdown formatting — no bold, no headers, no bullet symbols, plain text only.",
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
