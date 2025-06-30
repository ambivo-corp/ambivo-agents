# CodeExecutorAgent with BaseAgentHistoryMixin
import re
import uuid

import json
import uuid
from typing import Dict, Any

from ambivo_agents import BaseAgent, AgentRole, ExecutionContext, AgentMessage, MessageType, load_config
from ambivo_agents.core.history import BaseAgentHistoryMixin, ContextType
from ambivo_agents.executors import DockerCodeExecutor


class CodeExecutorAgent(BaseAgent, BaseAgentHistoryMixin):
    """Agent specialized in code execution with execution history"""

    def __init__(self, agent_id: str = None, memory_manager=None, llm_service=None, **kwargs):
        if agent_id is None:
            agent_id = f"code_executor_{str(uuid.uuid4())[:8]}"

        super().__init__(
            agent_id=agent_id,
            role=AgentRole.CODE_EXECUTOR,
            memory_manager=memory_manager,
            llm_service=llm_service,
            name="Code Executor Agent",
            description="Agent for secure code execution using Docker containers",
            **kwargs
        )

        # Initialize history mixin
        self.setup_history_mixin()

        # Load Docker configuration from YAML
        try:
            config = load_config()
            docker_config = config.get('docker', {})
        except Exception as e:
            docker_config = {}

        self.docker_executor = DockerCodeExecutor(docker_config)
        self._add_code_tools()

        # Add code-specific context extractors
        self.register_context_extractor(
            ContextType.CODE_REFERENCE,
            lambda text: re.findall(r'```(?:python|bash|javascript)?\n?(.*?)\n?```', text, re.DOTALL)
        )

    async def _analyze_intent(self, user_message: str, conversation_context: str = "") -> Dict[str, Any]:
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
            "primary_intent": "execute_code|modify_code|debug_code|explain_code|continue_execution",
            "language": "python|bash|javascript",
            "references_previous": true/false,
            "code_blocks": ["extracted code"],
            "execution_type": "new|modification|continuation",
            "confidence": 0.0-1.0
        }}
        """

        try:
            response = await self.llm_service.generate_response(prompt)
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                return self._extract_intent_from_llm_response(response, user_message)
        except Exception as e:
            return self._keyword_based_analysis(user_message)

    def _keyword_based_analysis(self, user_message: str) -> Dict[str, Any]:
        """Fallback keyword-based analysis for code execution"""
        content_lower = user_message.lower()

        if "```python" in user_message:
            intent = 'execute_code'
            language = 'python'
        elif "```bash" in user_message:
            intent = 'execute_code'
            language = 'bash'
        elif any(word in content_lower for word in ['run', 'execute', 'test']):
            intent = 'execute_code'
            language = 'python'
        elif any(word in content_lower for word in ['modify', 'change', 'update']):
            intent = 'modify_code'
            language = 'python'
        elif any(word in content_lower for word in ['debug', 'fix', 'error']):
            intent = 'debug_code'
            language = 'python'
        else:
            intent = 'execute_code'
            language = 'python'

        # Extract code blocks
        code_blocks = re.findall(r'```(?:python|bash)?\n?(.*?)\n?```', user_message, re.DOTALL)

        return {
            "primary_intent": intent,
            "language": language,
            "references_previous": any(word in content_lower for word in ['that', 'previous', 'last', 'again']),
            "code_blocks": code_blocks,
            "execution_type": "new",
            "confidence": 0.8
        }

    def _get_conversation_context_summary(self) -> str:
        """Get code execution context summary"""
        try:
            recent_history = self.get_conversation_history_with_context(
                limit=3,
                context_types=[ContextType.CODE_REFERENCE]
            )

            context_summary = []
            for msg in recent_history:
                if msg.get('message_type') == 'user_input':
                    extracted_context = msg.get('extracted_context', {})
                    code_refs = extracted_context.get('code_reference', [])

                    if code_refs:
                        context_summary.append(f"Previous code: {code_refs[0][:100]}...")
                elif msg.get('message_type') == 'agent_response':
                    content = msg.get('content', '')
                    if 'executed successfully' in content.lower():
                        context_summary.append("Previous execution: successful")
                    elif 'failed' in content.lower():
                        context_summary.append("Previous execution: failed")

            return "\n".join(context_summary) if context_summary else "No previous code execution"
        except:
            return "No previous code execution"

    async def _route_request(self, intent_analysis: Dict[str, Any], user_message: str,
                             context: ExecutionContext) -> str:
        """Route code execution request based on intent analysis"""
        primary_intent = intent_analysis.get("primary_intent", "execute_code")
        language = intent_analysis.get("language", "python")
        code_blocks = intent_analysis.get("code_blocks", [])
        references_previous = intent_analysis.get("references_previous", False)

        if primary_intent == "execute_code":
            if code_blocks:
                # Execute the provided code
                code = code_blocks[0]
                if language == "python":
                    result = await self._execute_python_code(code)
                elif language == "bash":
                    result = await self._execute_bash_code(code)
                else:
                    return f"Unsupported language: {language}"

                if result['success']:
                    return f"Code executed successfully:\n\n```\n{result['output']}\n```\n\nExecution time: {result['execution_time']:.2f}s"
                else:
                    return f"Code execution failed:\n\n```\n{result['error']}\n```"
            else:
                return "Please provide code wrapped in ```python or ```bash code blocks for execution."

        elif primary_intent == "modify_code":
            if references_previous:
                return "I can help modify code. Please provide the specific changes you want to make or show me the modified code."
            else:
                return "Please provide the code you want to modify."

        elif primary_intent == "debug_code":
            return "I can help debug code. Please provide the code that's having issues and describe the problem."

        else:
            return "Please provide code wrapped in ```python or ```bash code blocks for execution."

    async def process_message(self, message: AgentMessage, context: ExecutionContext = None) -> AgentMessage:
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
                conversation_id=message.conversation_id
            )

            self.memory.store_message(response)
            return response

        except Exception as e:
            error_response = self.create_response(
                content=f"Error in code execution: {str(e)}",
                recipient_id=message.sender_id,
                message_type=MessageType.ERROR,
                session_id=message.session_id,
                conversation_id=message.conversation_id
            )
            return error_response