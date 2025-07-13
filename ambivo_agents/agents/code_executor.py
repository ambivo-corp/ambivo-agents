# CodeExecutorAgent with BaseAgentHistoryMixin - COMPLETE FIXED VERSION
import asyncio
import json
import re
import uuid
from typing import Any, AsyncIterator, Dict

from ..config.loader import load_config

# FIXED IMPORTS - No circular dependency
from ..core.base import (
    AgentMessage,
    AgentRole,
    AgentTool,
    BaseAgent,
    ExecutionContext,
    MessageType,
    StreamChunk,
    StreamSubType,
)
from ..core.history import BaseAgentHistoryMixin, ContextType
from ..executors import DockerCodeExecutor


class CodeExecutorAgent(BaseAgent, BaseAgentHistoryMixin):
    """Agent specialized in code execution with execution history and code writing"""

    def __init__(
        self,
        agent_id: str = None,
        memory_manager=None,
        llm_service=None,
        system_message: str = None,
        **kwargs,
    ):
        if agent_id is None:
            agent_id = f"code_executor_{str(uuid.uuid4())[:8]}"

        default_system = """You are a code execution specialist with the following guidelines:
                - Write clean, well-commented code that follows best practices
                - Always explain what the code does before suggesting execution
                - Include error handling and input validation where appropriate
                - Prefer readable, maintainable code over clever one-liners
                - When writing code to accomplish a task, break it down into logical steps
                - If execution fails, analyze the error and suggest specific fixes
                - Use appropriate libraries and avoid deprecated functions
                - Consider security implications and avoid potentially harmful operations"""
        super().__init__(
            agent_id=agent_id,
            role=AgentRole.CODE_EXECUTOR,
            memory_manager=memory_manager,
            llm_service=llm_service,
            name="Code Executor Agent",
            description="Agent for secure code execution using Docker containers",
            system_message=system_message or default_system,
            **kwargs,
        )

        # Initialize history mixin
        self.setup_history_mixin()

        # Load Docker configuration from YAML
        try:
            config = load_config()
            docker_config = config.get("docker", {})
        except Exception as e:
            docker_config = {}

        self.docker_executor = DockerCodeExecutor(docker_config)
        self._add_code_tools()

        # Add code-specific context extractors
        self.register_context_extractor(
            ContextType.CODE_REFERENCE,
            lambda text: re.findall(
                r"```(?:python|bash|javascript)?\n?(.*?)\n?```", text, re.DOTALL
            ),
        )

    async def _analyze_intent(
        self, user_message: str, conversation_context: str = ""
    ) -> Dict[str, Any]:
        """Analyze code execution intent with previous execution context"""
        if not self.llm_service:
            return self._keyword_based_analysis(user_message)

        prompt = f"""
        Analyze this user message in the context of code execution:

        Previous Execution Context:
        {conversation_context}

        Current User Message: {user_message}

        Respond in JSON format:
        {{
            "primary_intent": "write_and_execute_code|execute_code|modify_code|debug_code|explain_code|continue_execution",
            "language": "python|bash|javascript",
            "references_previous": true/false,
            "code_blocks": ["extracted code"],
            "execution_type": "new|modification|continuation",
            "wants_code_written": true/false,
            "confidence": 0.0-1.0
        }}
        """

        try:
            response = await self.llm_service.generate_response(prompt)
            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                return self._extract_intent_from_llm_response(response, user_message)
        except Exception as e:
            return self._keyword_based_analysis(user_message)

    def _keyword_based_analysis(self, user_message: str) -> Dict[str, Any]:
        """Enhanced fallback keyword-based analysis for code execution"""
        content_lower = user_message.lower()

        # Detect code writing vs execution intent
        write_code_keywords = [
            "write code",
            "create code",
            "generate code",
            "make code",
            "code to",
            "write a function",
            "create a function",
            "write python",
            "can you write",
            "please write",
            "function to",
            "script to",
            "program to",
        ]

        wants_code_written = any(keyword in content_lower for keyword in write_code_keywords)

        if "```python" in user_message:
            intent = "execute_code"
            language = "python"
        elif "```bash" in user_message:
            intent = "execute_code"
            language = "bash"
        elif wants_code_written:
            intent = "write_and_execute_code"  # New intent type
            language = "python"  # Default to Python for code writing
        elif any(word in content_lower for word in ["run", "execute", "test"]):
            intent = "execute_code"
            language = "python"
        elif any(word in content_lower for word in ["modify", "change", "update"]):
            intent = "modify_code"
            language = "python"
        elif any(word in content_lower for word in ["debug", "fix", "error"]):
            intent = "debug_code"
            language = "python"
        else:
            # If no clear intent but mentions code-related terms, assume they want code written
            if any(
                word in content_lower
                for word in ["multiply", "add", "calculate", "function", "algorithm"]
            ):
                intent = "write_and_execute_code"
                language = "python"
            else:
                intent = "execute_code"
                language = "python"

        # Extract code blocks
        code_blocks = re.findall(r"```(?:python|bash)?\n?(.*?)\n?```", user_message, re.DOTALL)

        return {
            "primary_intent": intent,
            "language": language,
            "references_previous": any(
                word in content_lower for word in ["that", "previous", "last", "again"]
            ),
            "code_blocks": code_blocks,
            "execution_type": "new",
            "wants_code_written": wants_code_written,
            "confidence": 0.8,
        }

    def _get_conversation_context_summary(self) -> str:
        """Get code execution context summary"""
        try:
            recent_history = self.get_conversation_history_with_context(
                limit=3, context_types=[ContextType.CODE_REFERENCE]
            )

            context_summary = []
            for msg in recent_history:
                if msg.get("message_type") == "user_input":
                    extracted_context = msg.get("extracted_context", {})
                    code_refs = extracted_context.get("code_reference", [])

                    if code_refs:
                        context_summary.append(f"Previous code: {code_refs[0][:100]}...")
                elif msg.get("message_type") == "agent_response":
                    content = msg.get("content", "")
                    if "executed successfully" in content.lower():
                        context_summary.append("Previous execution: successful")
                    elif "failed" in content.lower():
                        context_summary.append("Previous execution: failed")

            return "\n".join(context_summary) if context_summary else "No previous code execution"
        except:
            return "No previous code execution"

    async def _route_request(
        self, intent_analysis: Dict[str, Any], user_message: str, context: ExecutionContext
    ) -> str:
        """Route code execution request based on intent analysis"""
        primary_intent = intent_analysis.get("primary_intent", "execute_code")
        language = intent_analysis.get("language", "python")
        code_blocks = intent_analysis.get("code_blocks", [])
        references_previous = intent_analysis.get("references_previous", False)
        wants_code_written = intent_analysis.get("wants_code_written", False)

        message_lower = user_message.lower()
        asking_for_previous_code = any(
            phrase in message_lower
            for phrase in [
                "show me that code",
                "show that code",
                "show the code",
                "that code again",
                "code again",
                "previous code",
                "show me the code",
                "display the code",
                "see the code",
                "show me that",
                "that again",
            ]
        )

        if asking_for_previous_code:
            return await self._show_previous_code_from_history()

        # Handle different intents
        if primary_intent == "write_and_execute_code" or (wants_code_written and not code_blocks):
            # User wants us to write code, not execute existing code
            return await self._handle_code_writing_request(user_message, language)

        elif primary_intent == "execute_code":
            if code_blocks:
                # Execute the provided code
                code = code_blocks[0]
                if language == "python":
                    result = await self._execute_python_code(code)
                elif language == "bash":
                    result = await self._execute_bash_code(code)
                else:
                    return f"Unsupported language: {language}"

                if result["success"]:
                    return f"Code executed successfully:\n\n```\n{result['output']}\n```\n\nExecution time: {result['execution_time']:.2f}s"
                else:
                    return f"Code execution failed:\n\n```\n{result['error']}\n```"
            else:
                return (
                    "Please provide code wrapped in ```python or ```bash code blocks for execution."
                )

        elif primary_intent == "modify_code":
            if references_previous:
                return "I can help modify code. Please provide the specific changes you want to make or show me the modified code."
            else:
                return "Please provide the code you want to modify."

        elif primary_intent == "debug_code":
            return "I can help debug code. Please provide the code that's having issues and describe the problem."

        else:
            return "Please provide code wrapped in ```python or ```bash code blocks for execution."

    async def _handle_code_writing_request(
        self, user_message: str, language: str = "python"
    ) -> str:
        """Handle requests to write code (not just execute)"""

        if not self.llm_service:
            return "I can execute code, but I need an LLM service to write code. Please provide the code you want to execute."

            # 🔥 FIX: Get conversation history for context
        conversation_history = []
        try:
            conversation_history = await self.get_conversation_history(
                limit=5, include_metadata=True
            )
        except:
            pass

        task_description = self._extract_task_from_message(user_message)

        code_prompt = f"""Write {language} code to {task_description}. 

        Requirements:
        - Write clean, well-commented code
        - Include error handling if appropriate
        - Make the code executable
        - If the task involves specific inputs (like numbers), use those values

        Respond with ONLY the code wrapped in ```{language} code blocks, followed by a brief explanation."""

        try:
            # 🔥 FIX: Pass conversation history through context
            llm_context = {
                "conversation_history": conversation_history,
                "task_type": "code_generation",
                "language": language,
            }

            llm_response = await self.llm_service.generate_response(
                prompt=code_prompt,
                context=llm_context,  # 🔥 FIX: Context preserves memory across provider switches
            )

            # Extract code from LLM response
            code_match = re.search(rf"```{language}\n?(.*?)\n?```", llm_response, re.DOTALL)

            if code_match:
                generated_code = code_match.group(1).strip()

                # Execute the generated code automatically
                if language == "python":
                    execution_result = await self._execute_python_code(generated_code)
                elif language == "bash":
                    execution_result = await self._execute_bash_code(generated_code)
                else:
                    return f"Generated code:\n\n```{language}\n{generated_code}\n```\n\n(Execution not supported for {language})"

                # Format response with both generated code and execution result
                response = f"Here's the {language} code I wrote for you:\n\n```{language}\n{generated_code}\n```\n\n"

                if execution_result["success"]:
                    response += f"**Code Executor agent Result:**\n```\n{execution_result['output']}\n```\n\n"
                    response += f"✅ Code executed successfully in {execution_result['execution_time']:.2f}s"
                else:
                    response += f"**Execution Error:**\n```\n{execution_result['error']}\n```"

                return response
            else:
                return f"I wrote some code for you:\n\n{llm_response}"

        except Exception as e:
            return f"I had trouble generating the code: {str(e)}\n\nPlease provide more specific details about what you want the code to do."

    def _extract_task_from_message(self, message: str) -> str:
        """Extract the task description from user message"""
        message_lower = message.lower()

        # Remove common prefixes
        prefixes = [
            "write code to",
            "create code to",
            "generate code to",
            "make code to",
            "code to",
            "write a function to",
            "create a function to",
            "write python to",
            "can you write",
            "please write",
        ]

        task = message
        for prefix in prefixes:
            if message_lower.startswith(prefix):
                task = message[len(prefix) :].strip()
                break

        # Clean up the task description
        task = task.replace("?", "").strip()

        return task if task else "accomplish the requested task"

    def _extract_intent_from_llm_response(
        self, llm_response: str, user_message: str
    ) -> Dict[str, Any]:
        """Extract intent from non-JSON LLM response"""
        content_lower = llm_response.lower()

        if "write" in content_lower and "code" in content_lower:
            intent = "write_and_execute_code"
        elif "execute" in content_lower:
            intent = "execute_code"
        elif "modify" in content_lower:
            intent = "modify_code"
        elif "debug" in content_lower:
            intent = "debug_code"
        else:
            intent = "execute_code"

        return {
            "primary_intent": intent,
            "language": "python",
            "references_previous": False,
            "code_blocks": [],
            "execution_type": "new",
            "wants_code_written": "write" in content_lower,
            "confidence": 0.6,
        }

    async def process_message(
        self, message: AgentMessage, context: ExecutionContext = None
    ) -> AgentMessage:
        """Process code execution requests with execution history"""
        self.memory.store_message(message)

        try:
            user_message = message.content

            # Update conversation state
            self.update_conversation_state(user_message)

            # Get conversation context for analysis
            conversation_context = self._get_conversation_context_summary()

            # Use LLM to analyze intent
            intent_analysis = await self._analyze_intent(user_message, conversation_context)

            # Route request based on analysis
            response_content = await self._route_request(intent_analysis, user_message, context)

            response = self.create_response(
                content=response_content,
                recipient_id=message.sender_id,
                session_id=message.session_id,
                conversation_id=message.conversation_id,
            )

            self.memory.store_message(response)
            return response

        except Exception as e:
            error_response = self.create_response(
                content=f"Error in code execution: {str(e)}",
                recipient_id=message.sender_id,
                message_type=MessageType.ERROR,
                session_id=message.session_id,
                conversation_id=message.conversation_id,
            )
            return error_response

    async def process_message_stream(
        self, message: AgentMessage, context: ExecutionContext = None
    ) -> AsyncIterator[StreamChunk]:
        """Stream processing for CodeExecutorAgent - FIXED: Context preserved across provider switches"""
        self.memory.store_message(message)

        try:
            user_message = message.content
            self.update_conversation_state(user_message)

            yield StreamChunk(
                text="**Code Executor Agent**\n\n",
                sub_type=StreamSubType.STATUS,
                metadata={"agent": "code_executor", "phase": "initialization"},
            )

            # 🔥 FIX: Get conversation context for streaming
            conversation_context = self._get_conversation_context_summary()
            conversation_history = await self.get_conversation_history(
                limit=5, include_metadata=True
            )

            yield StreamChunk(
                text="Analyzing code request...\n",
                sub_type=StreamSubType.STATUS,
                metadata={"phase": "analysis"},
            )

            # Use LLM to analyze intent with context
            intent_analysis = await self._analyze_intent(user_message, conversation_context)
            primary_intent = intent_analysis.get("primary_intent", "execute_code")

            # 🔥 FIX: Build LLM context for streaming
            llm_context = {
                "conversation_history": conversation_history,  # 🔥 KEY FIX
                "conversation_id": message.conversation_id,
                "intent_analysis": intent_analysis,
                "streaming": True,
            }

            if primary_intent == "write_and_execute_code":
                yield StreamChunk(
                    text="**Writing and Executing Code**\n\n",
                    sub_type=StreamSubType.STATUS,
                    metadata={"intent": "write_and_execute_code"},
                )

                language = intent_analysis.get("language", "python")
                yield StreamChunk(
                    text=f"**Language:** {language.upper()}\n",
                    sub_type=StreamSubType.STATUS,
                    metadata={"language": language},
                )

                task_description = self._extract_task_from_message(user_message)
                yield StreamChunk(
                    text=f"**Task:** {task_description}\n\n",
                    sub_type=StreamSubType.STATUS,
                    metadata={"task": task_description},
                )

                yield StreamChunk(
                    text="Generating code...\n",
                    sub_type=StreamSubType.STATUS,
                    metadata={"phase": "code_generation"},
                )

                # 🔥 FIX: Generate and execute code with context preservation
                response_content = await self._handle_code_writing_request_with_context(
                    user_message, language, llm_context
                )
                yield StreamChunk(
                    text=response_content,
                    sub_type=StreamSubType.RESULT,
                    metadata={"language": language, "content_type": "code_execution_result"},
                )

            elif "```python" in user_message or "```bash" in user_message:
                yield StreamChunk(
                    text="🐍 **Code Execution Detected**\n\n",
                    sub_type=StreamSubType.STATUS,
                    metadata={"intent": "execute_existing_code"},
                )
                # ... existing code execution logic ...

            else:
                yield StreamChunk(
                    text="⚠️ **No executable code detected**\n\n",
                    sub_type=StreamSubType.STATUS,
                    metadata={"intent": "no_code_detected"},
                )
                # ... existing help logic ...

        except Exception as e:
            yield StreamChunk(
                text=f"**Code Executor Error:** {str(e)}",
                sub_type=StreamSubType.ERROR,
                metadata={"error": str(e)},
            )

    async def _handle_code_writing_request_with_context(
        self, user_message: str, language: str, llm_context: Dict[str, Any]
    ) -> str:
        """Handle code writing with system message"""

        if not self.llm_service:
            return "I can execute code, but I need an LLM service to write code."

        task_description = self._extract_task_from_message(user_message)

        # 🆕 Code-specific prompt that works with system message
        code_prompt = f"""Task: {task_description}

    Requirements:
    - Write {language} code to accomplish this task
    - Follow the coding guidelines in your system instructions
    - Wrap the code in ```{language} code blocks
    - Provide a brief explanation after the code

    Please write the code now:"""

        try:
            # 🆕 Get enhanced system message for code generation
            enhanced_system_message = self.get_system_message_for_llm(llm_context)

            # Generate code with system message guidance
            llm_response = await self.llm_service.generate_response(
                prompt=code_prompt,
                context=llm_context,
                system_message=enhanced_system_message,  # 🆕 System message guides code style
            )

            # Extract and execute code (existing logic)
            code_match = re.search(rf"```{language}\n?(.*?)\n?```", llm_response, re.DOTALL)

            if code_match:
                generated_code = code_match.group(1).strip()

                # Execute the code
                if language == "python":
                    execution_result = await self._execute_python_code(generated_code)
                else:
                    return f"Generated code:\n\n```{language}\n{generated_code}\n```"

                # Format response
                response = f"Here's the {language} code following best practices:\n\n```{language}\n{generated_code}\n```\n\n"

                if execution_result["success"]:
                    response += f"**Execution Result:**\n```\n{execution_result['output']}\n```\n\n"
                    response += f"✅ Code executed successfully in {execution_result['execution_time']:.2f}s"
                else:
                    response += f"**Execution Error:**\n```\n{execution_result['error']}\n```"

                return response
            else:
                return f"Generated response:\n\n{llm_response}"

        except Exception as e:
            return f"I had trouble generating the code: {str(e)}"

    def _add_code_tools(self):
        """Add code execution tools"""
        self.add_tool(
            AgentTool(
                name="execute_python",
                description="Execute Python code in a secure Docker container",
                function=self._execute_python_code,
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "Python code to execute"},
                        "files": {"type": "object", "description": "Additional files needed"},
                    },
                    "required": ["code"],
                },
            )
        )

        self.add_tool(
            AgentTool(
                name="execute_bash",
                description="Execute bash commands in a secure Docker container",
                function=self._execute_bash_code,
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "Bash commands to execute"},
                        "files": {"type": "object", "description": "Additional files needed"},
                    },
                    "required": ["code"],
                },
            )
        )

    async def _execute_python_code(self, code: str, files: Dict[str, str] = None) -> Dict[str, Any]:
        """Execute Python code safely"""
        return self.docker_executor.execute_code(code, "python", files)

    async def _execute_bash_code(self, code: str, files: Dict[str, str] = None) -> Dict[str, Any]:
        """Execute bash commands safely"""
        return self.docker_executor.execute_code(code, "bash", files)

    async def _show_previous_code_from_history(self) -> str:
        """Use BaseAgentHistoryMixin to show previous code from conversation history"""
        try:
            # UTILIZE BaseAgentHistoryMixin - this is exactly what it's for!
            recent_history = self.get_conversation_history_with_context(
                limit=10, context_types=[ContextType.CODE_REFERENCE]
            )

            # Look for the most recent code in agent responses
            for msg in reversed(recent_history):
                if msg.get("message_type") == "agent_response":
                    content = msg.get("content", "")

                    # Extract code blocks from previous responses
                    import re

                    code_matches = re.findall(r"```python\n(.*?)\n```", content, re.DOTALL)

                    if code_matches:
                        latest_code = code_matches[-1].strip()

                        return f"""Here's the code from our previous conversation:

    ```python
    {latest_code}
    ```

    Would you like me to:
    - Execute this code again?
    - Modify it for a different purpose?
    - Explain how it works?"""

            # Fallback: Check extracted context from BaseAgentHistoryMixin
            for msg in reversed(recent_history):
                extracted_context = msg.get("extracted_context", {})
                code_refs = extracted_context.get("code_reference", [])

                if code_refs:
                    return f"""Here's the previous code I found in our conversation:

    ```python
    {code_refs[0]}
    ```

    This was automatically extracted from our conversation history using the BaseAgentHistoryMixin."""

            # No code found in this agent's memory
            return """I don't see any code in our conversation history for this session.

    This might happen if:
    - The code was handled by a different agent type
    - We haven't written any code yet in this conversation
    - The conversation history was cleared

    Would you like me to write some new code for you?"""

        except Exception as e:
            return f"I had trouble accessing our conversation history: {str(e)}\n\nThe BaseAgentHistoryMixin should be working. Could you specify what code you're looking for?"
