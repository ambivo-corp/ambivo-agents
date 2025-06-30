# ambivo_agents/agents/code_executor.py
"""
Code Executor Agent for running code in secure Docker containers.
"""

import logging
import uuid
from typing import Dict, Any

from ..core.base import BaseAgent, AgentRole, AgentMessage, MessageType, ExecutionContext, AgentTool, DockerCodeExecutor
from ..config.loader import load_config, get_config_section


class CodeExecutorAgent(BaseAgent):
    """Agent specialized in code execution"""

    def __init__(self, agent_id: str=None, memory_manager=None, llm_service=None, **kwargs):
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

        # Load Docker configuration from YAML
        try:
            config = load_config()
            docker_config = config.get('docker', {})
        except Exception as e:
            logging.warning(f"Could not load Docker config from YAML: {e}")
            docker_config = {}

        self.docker_executor = DockerCodeExecutor(docker_config)
        self._add_code_tools()

    def _add_code_tools(self):
        """Add code execution tools"""
        self.add_tool(AgentTool(
            name="execute_python",
            description="Execute Python code in a secure Docker container",
            function=self._execute_python_code,
            parameters_schema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Python code to execute"},
                    "files": {"type": "object", "description": "Additional files needed"}
                },
                "required": ["code"]
            }
        ))

        self.add_tool(AgentTool(
            name="execute_bash",
            description="Execute bash commands in a secure Docker container",
            function=self._execute_bash_code,
            parameters_schema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Bash commands to execute"},
                    "files": {"type": "object", "description": "Additional files needed"}
                },
                "required": ["code"]
            }
        ))

    async def _execute_python_code(self, code: str, files: Dict[str, str] = None) -> Dict[str, Any]:
        """Execute Python code safely"""
        return self.docker_executor.execute_code(code, "python", files)

    async def _execute_bash_code(self, code: str, files: Dict[str, str] = None) -> Dict[str, Any]:
        """Execute bash commands safely"""
        return self.docker_executor.execute_code(code, "bash", files)

    async def process_message(self, message: AgentMessage, context: ExecutionContext=None) -> AgentMessage:
        """Process code execution requests"""
        self.memory.store_message(message)

        try:
            content = message.content

            if "```python" in content:
                code_start = content.find("```python") + 9
                code_end = content.find("```", code_start)
                code = content[code_start:code_end].strip()

                result = await self._execute_python_code(code)

                if result['success']:
                    response_content = f"Code executed successfully:\n\n```\n{result['output']}\n```\n\nExecution time: {result['execution_time']:.2f}s"
                else:
                    response_content = f"Code execution failed:\n\n```\n{result['error']}\n```"

            elif "```bash" in content:
                code_start = content.find("```bash") + 7
                code_end = content.find("```", code_start)
                code = content[code_start:code_end].strip()

                result = await self._execute_bash_code(code)

                if result['success']:
                    response_content = f"Commands executed successfully:\n\n```\n{result['output']}\n```\n\nExecution time: {result['execution_time']:.2f}s"
                else:
                    response_content = f"Command execution failed:\n\n```\n{result['error']}\n```"

            else:
                response_content = "Please provide code wrapped in ```python or ```bash code blocks for execution."

            response = self.create_response(
                content=response_content,
                recipient_id=message.sender_id,
                session_id=message.session_id,
                conversation_id=message.conversation_id
            )

            self.memory.store_message(response)
            return response

        except Exception as e:
            logging.error(f"Code executor error: {e}")
            error_response = self.create_response(
                content=f"Error in code execution: {str(e)}",
                recipient_id=message.sender_id,
                message_type=MessageType.ERROR,
                session_id=message.session_id,
                conversation_id=message.conversation_id
            )
            return error_response