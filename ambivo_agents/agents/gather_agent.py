# ambivo_agents/agents/gather_agent.py
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from ..core.base import (
    AgentMessage,
    AgentRole,
    BaseAgent,
    ExecutionContext,
    MessageType,
    StreamChunk,
    StreamSubType,
)

try:
    import aiohttp

    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class GatherAgent(BaseAgent):
    """
    GatherAgent: A conversational form-filling agent that asks a sequence of questions,
    validates answers according to configured types, handles conditional questions, and
    submits the collected data to a configured API endpoint.

    Question types supported:
      - free-text
      - yes-no
      - single-select (requires choices)
      - multi-select (requires choices)

    Conditional questions:
      - is_conditional: bool
      - parent_question_id: str
      - Conditional Dependent Question Logic:
        • Free-Text parent: ask when parent answer is non-empty. If triggers include yes/no, interpret affirmative/negative accordingly.
        • Yes–No parent: ask when parent answer is affirmative (Yes/Y/True). If triggers provided, match against them.
        • Single-Select parent: ask when selected value is in the dependent question’s trigger list; default is any value except explicit "No" if no triggers.
        • Multi-Select parent: ask when at least one selected value is in the dependent question’s trigger list; default is non-empty selection if no triggers.

    Configuration (agent_config.yaml -> gather):
      gather:
        submission_endpoint: "https://api.example.com/submit"
        submission_method: "POST"
        submission_headers: {"Authorization": "Bearer ..."}
        memory_ttl_seconds: 3600

    State is stored in memory per session and reset after memory_ttl_seconds (default 1h).

    How to provide the questionnaire:
      - Paste JSON or YAML in the chat
      - Or send a file path/URL; the agent will read and parse it using BaseAgent utilities.

    Expected questionnaire schema (minimal):
      {
        "questions": [
          {
            "question_id": "10000100",
            "text": "Are network perimeter defense tools used?",
            "type": "single-select",  # free-text | yes-no | single-select | multi-select
            "is_conditional": false,
            "parent_question_id": null,
            "required": true,
            "answer_option_dict_list": [
              {"value": "Yes", "label": "Yes"},
              {"value": "No", "label": "No"}
            ]
          }
        ]
      }
    """

    DEFAULT_SYSTEM_MESSAGE = (
        "You are GatherAgent, a conversational form assistant. "
        "Your job is to ask the user the next question from a provided questionnaire, "
        "one at a time, in a friendly and natural manner. "
        "Respect the question type and choices. "
        "For yes-no questions, only accept Yes/No (case-insensitive). "
        "For single-select, present the available choices succinctly. "
        "For multi-select, allow multiple choices separated by commas and confirm. "
        "Ask clarifying questions if the user's answer does not match the required type. "
        "Do not skip questions unless they are conditional and the condition is not met. "
        "Keep responses concise. "
        "When all relevant questions are answered or user requests to finish, say you will submit."
    )

    def __init__(
        self,
        agent_id: str = None,
        memory_manager=None,
        llm_service=None,
        system_message: str = None,
        **kwargs,
    ):
        super().__init__(
            agent_id=agent_id,
            role=AgentRole.ASSISTANT,
            memory_manager=memory_manager,
            llm_service=llm_service,
            system_message=system_message or GatherAgent.DEFAULT_SYSTEM_MESSAGE,
            **kwargs,
        )
        self.logger = logging.getLogger(__name__)

        # Load config chunk for gather
        cfg = (self.config or {}).get("gather", {})
        self.submission_endpoint: Optional[str] = cfg.get("submission_endpoint")
        self.submission_method: str = (cfg.get("submission_method") or "POST").upper()
        self.submission_headers: Dict[str, str] = cfg.get("submission_headers") or {}
        self.memory_ttl_seconds: int = int(cfg.get("memory_ttl_seconds") or 3600)
        # LLM-based answer validation settings
        self.enable_llm_answer_validation: bool = bool(
            cfg.get("enable_llm_answer_validation", False)
        )
        self.answer_validation_cfg: Dict[str, Any] = cfg.get("answer_validation") or {}
        self.default_min_answer_length: int = int(
            self.answer_validation_cfg.get("default_min_length", 1)
        )
        # Control whether to use LLM to rephrase question prompts (disabled by default for predictability)
        self.enable_llm_prompt_rewrite: bool = bool(cfg.get("enable_llm_prompt_rewrite", False))
        # NEW: Enable natural language parsing for conversational responses
        self.enable_natural_language_parsing: bool = bool(
            cfg.get("enable_natural_language_parsing", False)
        )

    # -------- State Management --------
    def _state_key(self, session_id: str) -> str:
        return f"gather_state:{session_id}"

    async def _load_state(self) -> Dict[str, Any]:
        session_id = self.context.session_id
        state = {}
        try:
            if self.memory:
                raw = await self.memory.get_context(self._state_key(session_id))
                if raw:
                    state = raw
        except Exception as e:
            self.logger.warning(f"Failed to load state: {e}")

        # Reset if expired
        started_at = state.get("started_at")
        if started_at:
            try:
                started = datetime.fromisoformat(started_at)
                if datetime.utcnow() - started > timedelta(seconds=self.memory_ttl_seconds):
                    state = {}
            except Exception:
                pass
        return state or {}

    async def _save_state(self, state: Dict[str, Any]):
        session_id = self.context.session_id
        state = dict(state)
        if "started_at" not in state:
            state["started_at"] = datetime.utcnow().isoformat()
        try:
            if self.memory:
                await self.memory.store_context(self._state_key(session_id), state)
        except Exception as e:
            self.logger.warning(f"Failed to save state: {e}")

    async def _clear_state(self):
        session_id = self.context.session_id
        try:
            if self.memory:
                await self.memory.store_context(self._state_key(session_id), {})
        except Exception:
            pass

    # -------- Questionnaire Handling --------
    @staticmethod
    def _normalize_question(q: Dict[str, Any]) -> Dict[str, Any]:
        qn = {
            "question_id": str(q.get("question_id") or q.get("id") or str(uuid.uuid4())),
            "text": q.get("text") or q.get("question") or "",
            "type": (q.get("type") or "free-text").lower(),
            "is_conditional": bool(q.get("is_conditional") or False),
            "parent_question_id": q.get("parent_question_id"),
            "required": bool(q.get("required", True)),
            "answer_option_dict_list": q.get("answer_option_dict_list") or q.get("choices") or [],
            # New: optional trigger list for conditional logic on dependent questions
            "condition_trigger_values": q.get("condition_trigger_values")
            or q.get("trigger_values")
            or q.get("condition_values")
            or q.get("condition_triggers")
            or [],
            # New: optional per-question answer quality hints/constraints
            "answer_requirements": q.get("answer_requirements") or q.get("requirements") or "",
            "min_answer_length": q.get("min_answer_length"),
        }
        return qn

    @staticmethod
    def _normalize_questionnaire(obj: Any) -> Dict[str, Any]:
        if isinstance(obj, dict) and "questions" in obj:
            questions = obj["questions"]
        elif isinstance(obj, list):
            questions = obj
        else:
            raise ValueError("Questionnaire must be a dict with 'questions' or a list of questions")
        norm = [GatherAgent._normalize_question(q) for q in questions]
        return {"questions": norm}

    async def _try_parse_questionnaire_from_message(
        self, user_text: str
    ) -> Optional[Dict[str, Any]]:
        # Try JSON in message
        try:
            maybe_json = user_text.strip()
            if maybe_json.startswith("{") or maybe_json.startswith("["):
                obj = json.loads(maybe_json)
                return self._normalize_questionnaire(obj)
        except Exception:
            pass
        # Try reading file/URL
        try:
            file_result = await self.read_and_parse_file(user_text, auto_parse=True)
            if file_result and file_result.get("success"):
                # Prefer parsed result when available (supports YAML/JSON)
                parse_result = file_result.get("parse_result") or {}
                if parse_result.get("success"):
                    data = parse_result.get("data")
                    if isinstance(data, (dict, list)):
                        return self._normalize_questionnaire(data)
                # Fallback to raw content
                content = file_result.get("content")
                if isinstance(content, (dict, list)):
                    return self._normalize_questionnaire(content)
                # if text, try to json-load
                if isinstance(content, str):
                    obj = json.loads(content)
                    return self._normalize_questionnaire(obj)
        except Exception:
            pass
        return None

    # -------- Question Progression --------
    def _is_condition_met(
        self, parent_answer: Any, parent_type: str, child_q: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Evaluate whether a conditional (dependent) question should be asked based on
        the parent answer/type and optional child-level trigger values.

        Rules:
          - Yes–No: default affirmative (Yes/Y/True). If child triggers provided, match against them.
          - Single-Select: default any value except explicit "No". If triggers provided, require membership.
          - Multi-Select: default non-empty selection. If triggers provided, require overlap.
          - Free-Text: default non-empty. If triggers provided and include yes/no, interpret affirmative/negative;
                       otherwise do simple case-insensitive equality check.
        """
        if parent_answer is None:
            return False

        def _norm_text(v: Any) -> str:
            return str(v).strip().lower()

        def _is_affirmative(v: Any) -> bool:
            return _norm_text(v) in {"yes", "y", "true"}

        def _is_negative(v: Any) -> bool:
            return _norm_text(v) in {"no", "n", "false"}

        triggers: List[str] = []
        if child_q:
            raw_triggers = child_q.get("condition_trigger_values") or []
            # Normalize triggers to lower-case strings
            for tv in raw_triggers:
                if isinstance(tv, dict):
                    tv = tv.get("value") or tv.get("label") or ""
                triggers.append(_norm_text(tv))

        t = (parent_type or "free-text").lower()

        # If triggers are provided, they override defaults (except we keep simple bool-ish mapping where relevant)
        if triggers:
            if t == "yes-no":
                return _norm_text(parent_answer) in triggers or (
                    ("yes" in triggers and _is_affirmative(parent_answer))
                    or ("no" in triggers and _is_negative(parent_answer))
                )
            if t == "single-select":
                return _norm_text(parent_answer) in triggers
            if t == "multi-select":
                try:
                    pvals = [_norm_text(x) for x in (parent_answer or [])]
                    return any(p in triggers for p in pvals)
                except Exception:
                    return False
            # free-text with triggers
            pav = _norm_text(parent_answer)
            if "yes" in triggers and _is_affirmative(parent_answer):
                return True
            if "no" in triggers and _is_negative(parent_answer):
                return True
            # Otherwise simple equality match
            return pav in triggers

        # Defaults (no triggers provided)
        if t == "yes-no":
            return _is_affirmative(parent_answer)
        if t == "single-select":
            return _norm_text(parent_answer) not in ("no", "none", "n/a", "na")
        if t == "multi-select":
            try:
                return bool(parent_answer) and len(parent_answer) > 0
            except Exception:
                return False
        # free-text
        return _norm_text(parent_answer) != ""

    def _get_next_question(
        self, questionnaire: Dict[str, Any], answers: Dict[str, Any], asked: set
    ) -> Optional[Dict[str, Any]]:
        for q in questionnaire.get("questions", []):
            qid = q.get("question_id")
            if qid in asked:
                continue
            if q.get("is_conditional"):
                parent_id = q.get("parent_question_id")
                if not parent_id:
                    continue  # skip malformed
                # need parent asked and condition met
                if parent_id not in answers:
                    continue
                # Find parent type
                parent = next(
                    (
                        x
                        for x in questionnaire["questions"]
                        if str(x.get("question_id")) == str(parent_id)
                    ),
                    None,
                )
                parent_type = parent.get("type") if parent else "free-text"
                if not self._is_condition_met(answers.get(parent_id), parent_type, q):
                    asked.add(qid)  # considered not applicable
                    continue
            return q
        return None

    def _format_question_prompt(self, q: Dict[str, Any]) -> str:
        qtext = q.get("text", "")
        qtype = (q.get("type") or "free-text").lower()
        choices = q.get("answer_option_dict_list") or []
        if qtype in ("single-select", "multi-select") and choices:
            opt_str = ", ".join([str(c.get("label") or c.get("value")) for c in choices])
            if qtype == "single-select":
                return f"{qtext}\nPlease pick one: {opt_str}"
            else:
                return f"{qtext}\nYou may select multiple (comma-separated): {opt_str}"
        elif qtype == "yes-no":
            return f"{qtext} (Yes/No)"
        else:
            return qtext

    async def _extract_answer_with_llm(
        self, q: Dict[str, Any], user_text: str
    ) -> Tuple[bool, Any, str]:
        """Use LLM to extract structured answer from natural language response"""
        if not self.llm_service:
            return False, None, "LLM service not available for natural language parsing"

        qtype = (q.get("type") or "free-text").lower()
        qtext = q.get("text", "")
        choices = q.get("answer_option_dict_list") or []

        # Build prompt based on question type
        if qtype == "yes-no":
            prompt = f"""Extract a yes/no answer from the user's response.
Question asked: "{qtext}"
User response: "{user_text}"

Analyze the user's intent and respond with ONLY: {{"answer": "Yes"}} or {{"answer": "No"}}

Examples:
- "Absolutely!" -> {{"answer": "Yes"}}
- "I don't think so" -> {{"answer": "No"}}
- "Yeah, we use that" -> {{"answer": "Yes"}}"""

        elif qtype == "single-select":
            choices_str = "\n".join(
                [f"- {c.get('label', c.get('value'))}: {c.get('value')}" for c in choices]
            )
            prompt = f"""Extract the selected option from the user's natural language response.
Question asked: "{qtext}"
Available options:
{choices_str}

User response: "{user_text}"

Match the user's intent to ONE option and respond with ONLY: {{"answer": "exact_value_here"}}

Examples:
- "I'd prefer the first one" -> match to first option's value
- "The blue option sounds good" -> match to the option mentioning blue"""

        elif qtype == "multi-select":
            choices_str = "\n".join(
                [f"- {c.get('label', c.get('value'))}: {c.get('value')}" for c in choices]
            )
            prompt = f"""Extract multiple selected options from the user's natural language response.
Question asked: "{qtext}"
Available options:
{choices_str}

User response: "{user_text}"

Match the user's intent to one or more options and respond with ONLY: {{"answer": ["value1", "value2"]}}

Examples:
- "Both the first and third options" -> match to first and third option values
- "I'll take email and SMS" -> match options mentioning email and SMS"""

        else:  # free-text
            return True, user_text, ""

        try:
            response = await self.llm_service.generate_response(
                prompt,
                context={"conversation_history": []},
                system_message="You are a precise data extraction assistant. Extract structured answers from natural language. Respond only with JSON.",
            )

            # Parse LLM response
            if response:
                import json as _json

                response_str = str(response)
                # Try to find JSON in response
                start = response_str.find("{")
                end = response_str.rfind("}")
                if start != -1 and end != -1:
                    try:
                        parsed = _json.loads(response_str[start : end + 1])
                        answer = parsed.get("answer")
                        if answer is not None:
                            # Validate the answer matches expected format
                            if qtype == "yes-no" and answer in ["Yes", "No"]:
                                return True, answer, ""
                            elif qtype == "single-select":
                                # Check if answer is valid choice
                                valid_values = [c.get("value") for c in choices]
                                if answer in valid_values:
                                    return True, answer, ""
                            elif qtype == "multi-select" and isinstance(answer, list):
                                # Check if all answers are valid choices
                                valid_values = [c.get("value") for c in choices]
                                if all(a in valid_values for a in answer):
                                    return True, answer, ""
                    except Exception:
                        pass

            # If LLM parsing failed, return false to fall back to strict parsing
            return False, None, None

        except Exception as e:
            self.logger.warning(f"LLM answer extraction failed: {e}")
            return False, None, None

    def _validate_and_parse_answer(
        self, q: Dict[str, Any], user_text: str
    ) -> Tuple[bool, Any, str]:
        qtype = (q.get("type") or "free-text").lower()
        user_text = (user_text or "").strip()
        if qtype == "free-text":
            return True, user_text, ""
        if qtype == "yes-no":
            val = user_text.lower()
            if val in ["yes", "y", "true"]:
                return True, "Yes", ""
            if val in ["no", "n", "false"]:
                return True, "No", ""
            return False, None, "Please answer Yes or No."
        choices = q.get("answer_option_dict_list") or []
        valid_values = {str(c.get("value")).lower(): c.get("value") for c in choices}
        valid_labels = {str(c.get("label")).lower(): c.get("value") for c in choices}
        if qtype == "single-select":
            key = user_text.lower()
            if key in valid_values:
                return True, valid_values[key], ""
            if key in valid_labels:
                return True, valid_labels[key], ""
            return False, None, f"Please select one of the available choices."
        if qtype == "multi-select":
            parts = [p.strip().lower() for p in user_text.split(",") if p.strip()]
            if not parts:
                return False, None, "Please provide one or more choices, comma-separated."
            mapped = []
            for p in parts:
                if p in valid_values:
                    mapped.append(valid_values[p])
                elif p in valid_labels:
                    mapped.append(valid_labels[p])
                else:
                    return False, None, f"'{p}' is not a valid option."
            return True, mapped, ""
        # fallback
        return True, user_text, ""

    async def _evaluate_answer_sufficiency(
        self, q: Dict[str, Any], answer: Any
    ) -> Tuple[bool, str]:
        """
        Evaluate if a parsed answer satisfies the question requirements using LLM (if enabled),
        with heuristics fallback. Returns (sufficient, feedback).
        Only applies to free-text questions. Other types return (True, "").
        """
        qtype = (q.get("type") or "free-text").lower()
        if qtype != "free-text":
            return True, ""

        text_answer = str(answer or "").strip()
        # Heuristic: minimum length
        min_len = int(q.get("min_answer_length") or self.default_min_answer_length or 1)
        if len(text_answer) < max(0, min_len):
            return False, f"Answer is too short. Please provide at least {min_len} characters."

        # If no LLM enabled or unavailable, accept after length check
        if not (self.enable_llm_answer_validation and self.llm_service):
            return True, ""

        # Build a strict validation prompt
        req = q.get("answer_requirements") or "Provide a complete and specific answer."
        qtext = q.get("text") or ""
        instruction = (
            "You are a strict validator for a form-filling assistant. Determine if the user's answer fully satisfies the"
            " question and its requirements. Respond ONLY in JSON with keys: sufficient (boolean) and feedback (string)."
            " If insufficient, feedback must clearly state what is missing in 1-2 short sentences."
        )
        user_prompt = (
            f"Question: {qtext}\n"
            f"Requirements: {req}\n"
            f"Answer: {text_answer}\n\n"
            'Return JSON like: {"sufficient": true/false, "feedback": "..."}.'
        )

        try:
            llm_out = await self.llm_service.generate_response(
                user_prompt,
                context={"conversation_history": []},
                system_message=instruction,
            )
            parsed = None
            if llm_out:
                # Try to find a JSON object in the output
                llm_str = str(llm_out)
                start = llm_str.find("{")
                end = llm_str.rfind("}")
                if start != -1 and end != -1 and end > start:
                    import json as _json

                    try:
                        parsed = _json.loads(llm_str[start : end + 1])
                    except Exception:
                        parsed = None
            if isinstance(parsed, dict):
                sufficient = bool(parsed.get("sufficient", False))
                feedback = str(parsed.get("feedback") or "")
                if sufficient:
                    return True, ""
                # still apply length heuristic to avoid over-blocking
                if len(text_answer) >= min_len:
                    return False, feedback or "Please provide more details to fully answer."
            # Fallback: accept if passes heuristic
            return True, ""
        except Exception as e:
            self.logger.warning(f"LLM answer validation failed: {e}")
            return True, ""

    # -------- Submission --------
    async def _submit(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.submission_endpoint:
            return {"success": False, "error": "No submission endpoint configured"}
        try:
            if AIOHTTP_AVAILABLE:
                async with aiohttp.ClientSession() as session:
                    method = self.submission_method
                    if method == "POST":
                        async with session.post(
                            self.submission_endpoint, json=payload, headers=self.submission_headers
                        ) as resp:
                            data = await resp.text()
                            ok = 200 <= resp.status < 300
                            return {"success": ok, "status": resp.status, "response": data}
                    else:
                        async with session.get(
                            self.submission_endpoint,
                            params=payload,
                            headers=self.submission_headers,
                        ) as resp:
                            data = await resp.text()
                            ok = 200 <= resp.status < 300
                            return {"success": ok, "status": resp.status, "response": data}
            elif REQUESTS_AVAILABLE:
                if self.submission_method == "POST":
                    r = requests.post(
                        self.submission_endpoint,
                        json=payload,
                        headers=self.submission_headers,
                        timeout=15,
                    )
                else:
                    r = requests.get(
                        self.submission_endpoint,
                        params=payload,
                        headers=self.submission_headers,
                        timeout=15,
                    )
                return {"success": r.ok, "status": r.status_code, "response": r.text}
            else:
                return {
                    "success": False,
                    "error": "No HTTP client available (install aiohttp or requests)",
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # -------- Main message processing --------
    async def process_message(
        self, message: AgentMessage, context: ExecutionContext = None
    ) -> AgentMessage:
        if context is None:
            context = self.get_execution_context()

        user_text = message.content or ""
        state = await self._load_state()
        questionnaire = state.get("questionnaire")
        answers: Dict[str, Any] = state.get("answers") or {}
        asked: set = set(state.get("asked") or [])
        status: str = state.get("status") or "in_progress"

        # If conversation too old, state already reset by _load_state()

        # Check for user commands
        lower = user_text.strip().lower()
        if lower in ("finish", "submit", "done"):
            # Decide result status
            required_ids = (
                [
                    q.get("question_id")
                    for q in (questionnaire or {}).get("questions", [])
                    if q.get("required", True)
                ]
                if questionnaire
                else []
            )
            all_required_answered = all(qid in answers for qid in required_ids)
            result_status = (
                "successfully_collected" if all_required_answered else "partially_collected"
            )
            payload = {
                "session_id": self.context.session_id,
                "conversation_id": self.context.conversation_id,
                "result_status": result_status,
                "answers": answers,
                "timestamp": datetime.utcnow().isoformat(),
            }
            submit_result = await self._submit(payload)
            await self._clear_state()
            content = (
                f"Submitting your responses now. Status: {result_status}. "
                f"Submission: {submit_result.get('status') or submit_result.get('error')}"
            )
            return self.create_response(
                content=content,
                recipient_id=message.sender_id,
                message_type=MessageType.AGENT_RESPONSE,
                session_id=message.session_id,
                conversation_id=message.conversation_id,
            )

        if lower in ("cancel", "abort", "stop"):
            payload = {
                "session_id": self.context.session_id,
                "conversation_id": self.context.conversation_id,
                "result_status": "conversation_aborted",
                "answers": answers,
                "timestamp": datetime.utcnow().isoformat(),
            }
            submit_result = await self._submit(payload)
            await self._clear_state()
            content = f"Okay, aborting the gathering. Submission status: {submit_result.get('status') or submit_result.get('error')}"
            return self.create_response(
                content=content,
                recipient_id=message.sender_id,
                message_type=MessageType.AGENT_RESPONSE,
                session_id=message.session_id,
                conversation_id=message.conversation_id,
            )

        # If questionnaire not loaded, try to parse from message
        if not questionnaire:
            parsed = await self._try_parse_questionnaire_from_message(user_text)
            if parsed:
                questionnaire = parsed
                state["questionnaire"] = questionnaire
                state["answers"] = answers
                state["asked"] = list(asked)
                await self._save_state(state)
                # fall-through to ask the first question
            else:
                # Ask user to upload/paste questionnaire
                prompt = (
                    "I can help gather information by asking a set of questions. "
                    "Please upload or paste your questionnaire as JSON/YAML, or provide a file path/URL to it. "
                    'For example, you can paste: {"questions":[{"question_id":"10000100","text":"Are network perimeter defense tools used?","type":"single-select","answer_option_dict_list":[{"value":"Yes"},{"value":"No"}]}]}'
                )
                return self.create_response(
                    content=prompt,
                    recipient_id=message.sender_id,
                    message_type=MessageType.AGENT_RESPONSE,
                    session_id=message.session_id,
                    conversation_id=message.conversation_id,
                )

        # If we have a questionnaire but no current question tracked, pick next
        current_qid = state.get("current_qid")
        current_q: Optional[Dict[str, Any]] = None
        if current_qid:
            current_q = next(
                (
                    q
                    for q in questionnaire.get("questions", [])
                    if str(q.get("question_id")) == str(current_qid)
                ),
                None,
            )

        if current_q is None:
            next_q = self._get_next_question(questionnaire, answers, asked)
            if next_q is None:
                # No more questions needed; auto-submit
                result_status = "successfully_collected"
                # If some required missing, mark partial
                required_ids = [
                    q.get("question_id")
                    for q in questionnaire.get("questions", [])
                    if q.get("required", True)
                ]
                if not all(qid in answers for qid in required_ids):
                    result_status = "partially_collected"
                payload = {
                    "session_id": self.context.session_id,
                    "conversation_id": self.context.conversation_id,
                    "result_status": result_status,
                    "answers": answers,
                    "timestamp": datetime.utcnow().isoformat(),
                }
                submit_result = await self._submit(payload)
                await self._clear_state()
                content = (
                    f"We have reached the end of the questionnaire. Status: {result_status}. "
                    f"Submission: {submit_result.get('status') or submit_result.get('error')}"
                )
                return self.create_response(
                    content=content,
                    recipient_id=message.sender_id,
                    message_type=MessageType.AGENT_RESPONSE,
                    session_id=message.session_id,
                    conversation_id=message.conversation_id,
                )
            # Ask next question
            state["current_qid"] = next_q.get("question_id")
            await self._save_state(state)
            q_prompt = self._format_question_prompt(next_q)
            # Optionally use LLM to phrase better (gated by config)
            if self.llm_service and self.enable_llm_prompt_rewrite:
                llm_out = await self.llm_service.generate_response(
                    q_prompt,
                    context={"conversation_history": []},
                    system_message=self.get_system_message_for_llm(context={}),
                )
                q_prompt = llm_out or q_prompt
            return self.create_response(
                content=q_prompt,
                recipient_id=message.sender_id,
                message_type=MessageType.AGENT_RESPONSE,
                session_id=message.session_id,
                conversation_id=message.conversation_id,
            )

        # We have a current question and a user answer
        # First try standard parsing
        ok, parsed_answer, error_msg = self._validate_and_parse_answer(current_q, user_text)

        # If standard parsing failed and natural language parsing is enabled, try LLM extraction
        if not ok and self.enable_natural_language_parsing and self.llm_service:
            llm_ok, llm_answer, llm_error = await self._extract_answer_with_llm(
                current_q, user_text
            )
            if llm_ok:
                ok, parsed_answer, error_msg = True, llm_answer, ""

        if not ok:
            # Re-ask with guidance
            guidance = error_msg or "Please provide a valid answer."
            q_prompt = self._format_question_prompt(current_q)
            return self.create_response(
                content=f"{guidance}\n{q_prompt}",
                recipient_id=message.sender_id,
                message_type=MessageType.AGENT_RESPONSE,
                session_id=message.session_id,
                conversation_id=message.conversation_id,
            )

        # Optional LLM sufficiency check for free-text answers
        try:
            sufficient, feedback = await self._evaluate_answer_sufficiency(current_q, parsed_answer)
        except Exception as _e:
            self.logger.warning(f"Answer sufficiency check error: {_e}")
            sufficient, feedback = True, ""
        if not sufficient:
            q_prompt = self._format_question_prompt(current_q)
            guidance = feedback or "Please provide more details."
            return self.create_response(
                content=f"{guidance}\n{q_prompt}",
                recipient_id=message.sender_id,
                message_type=MessageType.AGENT_RESPONSE,
                session_id=message.session_id,
                conversation_id=message.conversation_id,
            )

        # Save answer
        qid = current_q.get("question_id")
        answers[str(qid)] = parsed_answer
        asked.add(str(qid))
        state["answers"] = answers
        state["asked"] = list(asked)
        state["current_qid"] = None
        await self._save_state(state)

        # Ask next question or finish
        next_q = self._get_next_question(questionnaire, answers, asked)
        if next_q is None:
            # End
            result_status = "successfully_collected"
            required_ids = [
                q.get("question_id")
                for q in questionnaire.get("questions", [])
                if q.get("required", True)
            ]
            if not all(qid in answers for qid in required_ids):
                result_status = "partially_collected"
            payload = {
                "session_id": self.context.session_id,
                "conversation_id": self.context.conversation_id,
                "result_status": result_status,
                "answers": answers,
                "timestamp": datetime.utcnow().isoformat(),
            }
            submit_result = await self._submit(payload)
            await self._clear_state()
            content = (
                f"Thanks, that's all I needed. Status: {result_status}. "
                f"Submission: {submit_result.get('status') or submit_result.get('error')}"
            )
            return self.create_response(
                content=content,
                recipient_id=message.sender_id,
                message_type=MessageType.AGENT_RESPONSE,
                session_id=message.session_id,
                conversation_id=message.conversation_id,
            )
        else:
            # Ask the next question
            state["current_qid"] = next_q.get("question_id")
            await self._save_state(state)
            q_prompt = self._format_question_prompt(next_q)
            if self.llm_service and self.enable_llm_prompt_rewrite:
                llm_out = await self.llm_service.generate_response(
                    q_prompt,
                    context={"conversation_history": []},
                    system_message=self.get_system_message_for_llm(context={}),
                )
                q_prompt = llm_out or q_prompt
            return self.create_response(
                content=q_prompt,
                recipient_id=message.sender_id,
                message_type=MessageType.AGENT_RESPONSE,
                session_id=message.session_id,
                conversation_id=message.conversation_id,
            )

    async def process_message_stream(self, message: AgentMessage, context: ExecutionContext = None):
        """Simple streaming wrapper: processes message and yields one chunk."""
        if context is None:
            context = self.get_execution_context()
        try:
            resp = await self.process_message(message, context)
            yield StreamChunk(
                text=resp.content or "",
                sub_type=StreamSubType.CONTENT,
                metadata={"agent_id": self.agent_id, **(resp.metadata or {})},
            )
        except Exception as e:
            yield StreamChunk(
                text=f"Error: {e}",
                sub_type=StreamSubType.ERROR,
                metadata={"agent_id": self.agent_id, "error": True},
            )
