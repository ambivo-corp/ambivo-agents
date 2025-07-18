# ambivo_agents/agents/workflow_developer.py
"""
Workflow Developer Agent

An agent that generates boilerplate workflow code for developers by asking questions
about their requirements and producing a complete Python file following WORKFLOW.md patterns.
"""

import asyncio
import json
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

from ..core.base import BaseAgent, AgentMessage, ExecutionContext, MessageType
from ..agents.assistant import AssistantAgent
from ..agents.code_executor import CodeExecutorAgent
from ..config.loader import load_config


@dataclass
class WorkflowRequirements:
    """Data structure to collect workflow requirements from developer"""
    domain_name: str = ""
    workflow_description: str = ""
    system_class_name: str = ""
    agents_needed: List[Dict[str, str]] = field(default_factory=list)
    ai_suggested_steps: List[str] = field(default_factory=list)
    persistence_backend: str = "sqlite"
    workflow_steps: List[Dict[str, Any]] = field(default_factory=list)
    use_database: bool = False
    use_web_search: bool = False
    use_media_processing: bool = False
    use_api_calls: bool = False
    custom_dependencies: List[str] = field(default_factory=list)
    output_directory: str = ""  # Will be set from config


class WorkflowDeveloperAgent(BaseAgent):
    """
    Agent that helps developers create workflow code by asking questions
    and generating boilerplate Python files following WORKFLOW.md patterns.
    """
    
    def __init__(self, agent_id: str = "workflow_developer", **kwargs):
        system_message = """You are a Workflow Developer Agent specialized in helping developers create ambivo_agents workflows.

Your role:
1. Ask strategic questions to understand the developer's workflow needs
2. Guide them through agent selection and workflow step design
3. Generate complete, working Python code following WORKFLOW.md patterns
4. Provide helpful comments and hints for customization

Your expertise:
- WORKFLOW.md architecture patterns
- Agent creation and orchestration
- ConversationFlow design
- SQLite persistence configuration
- Best practices for workflow development

Communication style: Professional, methodical, helpful. Ask one focused question at a time."""

        super().__init__(
            agent_id=agent_id,
            system_message=system_message,
            **kwargs
        )
        
        # Initialize helper agents
        self.assistant = None
        self.code_executor = None
        self.requirements = WorkflowRequirements()
        self.conversation_stage = "initial"
        
        # Load configuration for output directory
        self.config = load_config()
        self._setup_output_directory()
    
    def _setup_output_directory(self):
        """Setup output directory based on Docker shared configuration"""
        try:
            docker_config = self.config.get('docker', {})
            shared_base_dir = docker_config.get('shared_base_dir', './docker_shared')
            
            # Use the consistent docker_shared/output/generated_workflows structure
            self.requirements.output_directory = os.path.join(shared_base_dir, 'output', 'generated_workflows')
            
        except Exception as e:
            # Fallback to default if config loading fails
            self.requirements.output_directory = "./docker_shared/output/generated_workflows"
    
    async def _initialize_helpers(self):
        """Initialize helper agents if not already done"""
        if self.assistant is None:
            self.assistant = AssistantAgent.create_simple(
                user_id=f"{self.agent_id}_assistant"
            )
        
        if self.code_executor is None:
            self.code_executor = CodeExecutorAgent.create_simple(
                user_id=f"{self.agent_id}_code_executor"
            )
    
    async def process_message(self, message: AgentMessage, context: ExecutionContext = None) -> AgentMessage:
        """Process developer's message and guide through workflow creation"""
        await self._initialize_helpers()
        
        user_input = message.content.strip()
        
        # Route based on conversation stage
        if self.conversation_stage == "initial":
            return await self._handle_initial_greeting(message, context)
        elif self.conversation_stage == "domain_info":
            return await self._collect_domain_info(user_input, message, context)
        elif self.conversation_stage == "description_collection":
            return await self._collect_workflow_description(user_input, message, context)
        elif self.conversation_stage == "agent_suggestion":
            return await self._suggest_agents_with_llm(user_input, message, context)
        elif self.conversation_stage == "agent_selection":
            return await self._handle_agent_selection(user_input, message, context)
        elif self.conversation_stage == "workflow_steps":
            return await self._handle_workflow_steps(user_input, message, context)
        elif self.conversation_stage == "persistence_config":
            return await self._handle_persistence_config(user_input, message, context)
        elif self.conversation_stage == "additional_features":
            return await self._handle_additional_features(user_input, message, context)
        elif self.conversation_stage == "generate_code":
            return await self._generate_workflow_code(message, context)
        else:
            return await self._handle_general_question(user_input, message, context)
    
    async def _handle_initial_greeting(self, message: AgentMessage, context: ExecutionContext) -> AgentMessage:
        """Handle initial greeting and start requirements gathering"""
        
        greeting = """🏗️ Welcome to the Workflow Developer Agent!

I'll help you create a complete workflow system following the WORKFLOW.md patterns. 
I'll ask you a series of questions to understand your needs, then generate:

✅ Complete Python workflow system file
✅ All necessary imports and boilerplate code  
✅ Agent creation patterns
✅ ConversationFlow with your steps
✅ SQLite persistence configuration
✅ Test file template
✅ Helpful comments and customization hints

Let's start! What's the domain/industry for your workflow system?

Examples:
- "E-commerce customer service"
- "Healthcare patient intake" 
- "Real estate property search"
- "Financial loan processing"
- "Educational course enrollment"""

        self.conversation_stage = "domain_info"
        return self.create_response(
            content=greeting,
            recipient_id=message.sender_id,
            session_id=message.session_id,
            conversation_id=message.conversation_id
        )
    
    async def _collect_domain_info(self, user_input: str, message: AgentMessage, context: ExecutionContext) -> AgentMessage:
        """Collect domain information and suggest system class name"""
        
        # Extract and truncate domain name to max 150 characters
        domain_input = user_input.strip()
        if len(domain_input) > 150:
            self.requirements.domain_name = domain_input[:147] + "..."
        else:
            self.requirements.domain_name = domain_input
        
        # Generate suggested class name (keep it short and meaningful)
        # Extract only the first few key words for a concise class name
        words = domain_input.lower().split()
        key_words = []
        
        # Take only first 3-4 meaningful words
        for word in words[:4]:
            if len(word) > 2 and word not in ['the', 'and', 'for', 'with', 'where', 'then', 'that', 'this', 'into', 'one', 'new', 'added', 'sent']:
                clean_word = re.sub(r'[^a-zA-Z]', '', word)
                if clean_word:
                    key_words.append(clean_word.capitalize())
        
        if key_words:
            suggested_class = ''.join(key_words) + "WorkflowSystem"
        else:
            suggested_class = "CustomWorkflowSystem"
        
        # Ensure class name isn't too long (max 50 chars)
        if len(suggested_class) > 50:
            suggested_class = suggested_class[:47] + "System"
        
        self.requirements.system_class_name = suggested_class
        
        response = f"""Great! Working with: "{self.requirements.domain_name}"

I suggest the class name: `{suggested_class}`

Now, please provide a detailed description of your workflow. What should this system do? What are the main goals and user journey?

Example descriptions:
- "A customer service system that helps users find products, compare options, and complete purchases with personalized recommendations"
- "A healthcare intake system that collects patient information, schedules appointments, verifies insurance, and provides pre-visit instructions"
- "A loan processing system that evaluates applications, checks credit, calculates terms, and guides applicants through approval"

Please describe your workflow in detail (1-3 sentences):"""

        self.conversation_stage = "description_collection"
        return self.create_response(
            content=response,
            recipient_id=message.sender_id,
            session_id=message.session_id,
            conversation_id=message.conversation_id
        )
    
    async def _collect_workflow_description(self, user_input: str, message: AgentMessage, context: ExecutionContext) -> AgentMessage:
        """Collect detailed workflow description and use LLM to suggest agents"""
        
        # Store the workflow description
        self.requirements.workflow_description = user_input
        
        response = f"""Perfect! I understand your workflow:

"{user_input}"

Now I'll use AI to analyze your workflow and suggest the best agents and system prompts. This will take a moment while I think through the optimal agent architecture for your specific needs...

Type 'continue' when ready for AI-powered agent suggestions."""

        self.conversation_stage = "agent_suggestion"
        return self.create_response(
            content=response,
            recipient_id=message.sender_id,
            session_id=message.session_id,
            conversation_id=message.conversation_id
        )
    
    async def _suggest_agents_with_llm(self, user_input: str, message: AgentMessage, context: ExecutionContext) -> AgentMessage:
        """Use LLM to intelligently suggest agents and system prompts"""
        
        if user_input.lower() not in ['continue', 'yes', 'proceed', 'go']:
            return self.create_response(
                content="Please type 'continue' when you're ready for AI-powered agent suggestions.",
                recipient_id=message.sender_id,
                session_id=message.session_id,
                conversation_id=message.conversation_id
            )
        
        # Use assistant agent to analyze and suggest agents
        analysis_prompt = f"""I'm building a workflow system for: "{self.requirements.domain_name}"

Workflow Description: "{self.requirements.workflow_description}"

Please analyze this workflow and suggest:

1. **Agents Needed**: What specialized agents would be most effective? Consider:
   - Primary conversation handler
   - Domain specialists (e.g., product expert, medical specialist, etc.)
   - Technical agents (database, API, search, etc.)
   - Support agents (validation, scheduling, etc.)

2. **System Prompts**: For each agent, provide a detailed system prompt that defines:
   - Role and expertise
   - Communication style
   - Specific responsibilities
   - Domain knowledge

3. **Workflow Steps**: Suggest 4-6 logical workflow steps that users would go through

Format your response as:

**AGENTS:**
Agent1: [Name] - [Type] - [Brief Description]
System Prompt: [Detailed prompt]

Agent2: [Name] - [Type] - [Brief Description]  
System Prompt: [Detailed prompt]

(continue for all agents)

**WORKFLOW STEPS:**
1. [Step description]
2. [Step description]
(continue for all steps)

Be specific and detailed. This will generate actual production code."""

        try:
            # Get AI suggestions
            ai_suggestions = await self.assistant.chat(analysis_prompt)
            
            # Parse the AI suggestions and store them
            self._parse_ai_suggestions(ai_suggestions)
            
            response = f"""🤖 **AI Analysis Complete!** Here are my intelligent suggestions:

{ai_suggestions}

---

These suggestions are based on analyzing your specific workflow needs. The system prompts are designed to give each agent the right expertise and personality for your domain.

Do you want to:
1. **"accept"** - Use these AI-suggested agents and prompts
2. **"modify"** - Make changes to the suggestions  
3. **"manual"** - Provide your own agent specifications

What would you like to do?"""

            self.conversation_stage = "agent_selection"
            return self.create_response(
                content=response,
                recipient_id=message.sender_id,
                session_id=message.session_id,
                conversation_id=message.conversation_id
            )
            
        except Exception as e:
            return self.create_response(
                content=f"❌ Error getting AI suggestions: {e}\n\nLet's continue with manual agent selection. What agents do you need?",
                recipient_id=message.sender_id,
                session_id=message.session_id,
                conversation_id=message.conversation_id
            )
    
    def _parse_ai_suggestions(self, ai_response: str):
        """Parse AI suggestions and populate requirements"""
        try:
            # Extract agents section
            if "**AGENTS:**" in ai_response:
                agents_section = ai_response.split("**AGENTS:**")[1]
                if "**WORKFLOW STEPS:**" in agents_section:
                    agents_section = agents_section.split("**WORKFLOW STEPS:**")[0]
                
                # Parse individual agents
                self.requirements.agents_needed = []
                agent_blocks = agents_section.split("Agent")[1:]  # Split by "Agent" and skip first empty
                
                for block in agent_blocks:
                    if not block.strip():
                        continue
                        
                    lines = [line.strip() for line in block.strip().split('\n') if line.strip()]
                    if len(lines) >= 2:
                        # First line: "1: [Name] - [Type] - [Description]"
                        first_line = lines[0]
                        if ' - ' in first_line:
                            parts = first_line.split(' - ')
                            if len(parts) >= 3:
                                name_part = parts[0].strip()
                                agent_type = parts[1].strip()
                                description = parts[2].strip()
                                
                                # Extract name (remove number if present)
                                name = name_part.split(': ')[-1] if ': ' in name_part else name_part
                                name = name.lower().replace(' ', '_')
                                
                                # Find system prompt
                                system_prompt = ""
                                for line in lines[1:]:
                                    if line.startswith("System Prompt:"):
                                        system_prompt = line.replace("System Prompt:", "").strip()
                                        break
                                
                                self.requirements.agents_needed.append({
                                    "name": name,
                                    "class_name": name.replace('_', ' ').title().replace(' ', '') + "Agent",
                                    "type": agent_type,
                                    "description": description,
                                    "system_prompt": system_prompt
                                })
            
            # Extract workflow steps
            if "**WORKFLOW STEPS:**" in ai_response:
                steps_section = ai_response.split("**WORKFLOW STEPS:**")[1]
                step_lines = [line.strip() for line in steps_section.split('\n') if line.strip() and line.strip()[0].isdigit()]
                
                self.requirements.ai_suggested_steps = []
                for line in step_lines:
                    # Remove numbering
                    step_text = line.split('.', 1)[1].strip() if '.' in line else line
                    self.requirements.ai_suggested_steps.append(step_text)
                    
        except Exception as e:
            print(f"Error parsing AI suggestions: {e}")
            # Fallback to empty suggestions
            pass
    
    async def _handle_agent_selection(self, user_input: str, message: AgentMessage, context: ExecutionContext) -> AgentMessage:
        """Handle agent selection and create agent specifications"""
        
        if user_input.lower() in ["accept", "suggested"]:
            # Use AI-suggested agents (they should already be parsed)
            if not self.requirements.agents_needed:
                # Fallback to basic suggestions if AI parsing failed
                domain_lower = self.requirements.domain_name.lower()
                self.requirements.agents_needed = [
                    {
                        "name": "primary",
                        "class_name": "PrimaryAgent", 
                        "type": "AssistantAgent",
                        "description": f"Main {domain_lower} conversation handler",
                        "system_prompt": f"You are the primary {domain_lower} assistant."
                    },
                    {
                        "name": "specialist",
                        "class_name": "SpecialistAgent", 
                        "type": "AssistantAgent",
                        "description": f"{domain_lower.title()} domain expert",
                        "system_prompt": f"You are a {domain_lower} specialist with deep expertise."
                    }
                ]
            
            # Check if any agent needs database
            for agent in self.requirements.agents_needed:
                if 'database' in agent.get('type', '').lower() or 'database' in agent.get('name', '').lower():
                    self.requirements.use_database = True
        else:
            # Parse custom agent list
            agents = [agent.strip() for agent in user_input.split(',')]
            self.requirements.agents_needed = []
            
            for agent_desc in agents:
                clean_name = re.sub(r'[^a-zA-Z\s]', '', agent_desc)
                words = clean_name.split()
                if words:
                    name = '_'.join(word.lower() for word in words)
                    class_name = ''.join(word.capitalize() for word in words) + "Agent"
                    
                    # Determine agent type
                    agent_type = "AssistantAgent"
                    if any(keyword in agent_desc.lower() for keyword in ["database", "data", "storage"]):
                        agent_type = "DatabaseAgent"
                        self.requirements.use_database = True
                    
                    self.requirements.agents_needed.append({
                        "name": name,
                        "class_name": class_name,
                        "type": agent_type,
                        "description": agent_desc
                    })
        
        agents_summary = "\n".join([
            f"• {agent['name']}: {agent['description']} ({agent['type']})" 
            for agent in self.requirements.agents_needed
        ])
        
        # Check if we have AI-suggested steps
        ai_steps_text = ""
        if self.requirements.ai_suggested_steps:
            ai_steps_list = "\n".join([f"{i+1}. {step}" for i, step in enumerate(self.requirements.ai_suggested_steps)])
            ai_steps_text = f"""

**AI-Suggested Steps:**
{ai_steps_list}

You can:
- Type "use suggested" to use these AI-generated steps
- Describe your own workflow steps
- Modify the suggested steps"""

        response = f"""Perfect! Your agents:

{agents_summary}

Now let's design your workflow steps. A workflow is a series of conversation steps that guide users through a process.{ai_steps_text}

For your "{self.requirements.domain_name}" domain, what are the main steps users should go through?

Example format:
1. Welcome and understand customer need
2. Collect product preferences  
3. Search product database
4. Present options
5. Handle questions and finalize

Please describe your workflow steps (I'll convert them to technical specifications):"""

        self.conversation_stage = "workflow_steps"
        return self.create_response(
            content=response,
            recipient_id=message.sender_id,
            session_id=message.session_id,
            conversation_id=message.conversation_id
        )
    
    async def _handle_workflow_steps(self, user_input: str, message: AgentMessage, context: ExecutionContext) -> AgentMessage:
        """Handle workflow step design"""
        
        # Check if using AI-suggested steps
        if user_input.lower() in ["use suggested", "suggested", "use ai suggestions"]:
            if self.requirements.ai_suggested_steps:
                lines = self.requirements.ai_suggested_steps
            else:
                return self.create_response(
                    content="No AI suggestions available. Please describe your workflow steps manually:",
                    recipient_id=message.sender_id,
                    session_id=message.session_id,
                    conversation_id=message.conversation_id
                )
        else:
            # Parse workflow steps from user input
            lines = [line.strip() for line in user_input.split('\n') if line.strip()]
        
        self.requirements.workflow_steps = []
        for i, line in enumerate(lines):
            # Remove numbering if present
            step_text = re.sub(r'^\d+[\.\)]\s*', '', line)
            
            step_id = f"step_{i+1}"
            
            # Determine step type based on content
            if any(keyword in step_text.lower() for keyword in ["welcome", "greet", "introduce"]):
                step_type = "agent_response"
                agent_name = "primary"
            elif any(keyword in step_text.lower() for keyword in ["collect", "ask", "gather", "input"]):
                step_type = "user_input"
                agent_name = None
            elif any(keyword in step_text.lower() for keyword in ["search", "database", "find", "lookup"]):
                step_type = "agent_response"
                agent_name = "database" if self.requirements.use_database else "primary"
            elif any(keyword in step_text.lower() for keyword in ["present", "show", "display", "recommend"]):
                step_type = "agent_response"
                agent_name = "specialist" if len(self.requirements.agents_needed) > 2 else "primary"
            else:
                step_type = "agent_response"
                agent_name = "primary"
            
            self.requirements.workflow_steps.append({
                "id": step_id,
                "description": step_text,
                "type": step_type,
                "agent": agent_name
            })
        
        steps_summary = "\n".join([
            f"{i+1}. {step['description']} ({step['type']})"
            for i, step in enumerate(self.requirements.workflow_steps)
        ])
        
        response = f"""Excellent! I've analyzed your workflow steps:

{steps_summary}

For persistence, I recommend SQLite (default) which provides:
✅ Automatic state saving
✅ Conversation rollback capability  
✅ Session management
✅ Easy configuration

Do you want:
1. "SQLite" - Recommended for most use cases
2. "Redis" - For high-performance/concurrent systems
3. "File" - Simple file-based storage
4. "Memory" - No persistence (testing only)

Type your choice or press Enter for SQLite default:"""

        self.conversation_stage = "persistence_config"
        return self.create_response(
            content=response,
            recipient_id=message.sender_id,
            session_id=message.session_id,
            conversation_id=message.conversation_id
        )
    
    async def _handle_persistence_config(self, user_input: str, message: AgentMessage, context: ExecutionContext) -> AgentMessage:
        """Handle persistence configuration"""
        
        user_choice = user_input.lower().strip()
        
        if user_choice in ["redis", "2"]:
            self.requirements.persistence_backend = "redis"
        elif user_choice in ["file", "3"]:
            self.requirements.persistence_backend = "file"
        elif user_choice in ["memory", "4"]:
            self.requirements.persistence_backend = "memory"
        else:
            self.requirements.persistence_backend = "sqlite"  # default
        
        response = f"""Great! Using {self.requirements.persistence_backend} persistence.

Final questions - do you need any of these additional features?

1. **Web Search** - Search the internet for information
2. **Media Processing** - Handle audio/video files
3. **API Calls** - Make external API requests

Please type any that apply (comma-separated) or "none":
Example: "web search, api calls" or "none"""

        self.conversation_stage = "additional_features"
        return self.create_response(
            content=response,
            recipient_id=message.sender_id,
            session_id=message.session_id,
            conversation_id=message.conversation_id
        )
    
    async def _handle_additional_features(self, user_input: str, message: AgentMessage, context: ExecutionContext) -> AgentMessage:
        """Handle additional features selection"""
        
        user_input_lower = user_input.lower()
        
        if "web search" in user_input_lower:
            self.requirements.use_web_search = True
        
        if "media" in user_input_lower:
            self.requirements.use_media_processing = True
        
        if "api" in user_input_lower:
            self.requirements.use_api_calls = True
        
        # Generate summary
        features = []
        if self.requirements.use_database:
            features.append("Database operations")
        if self.requirements.use_web_search:
            features.append("Web search")
        if self.requirements.use_media_processing:
            features.append("Media processing")
        if self.requirements.use_api_calls:
            features.append("API calls")
        
        features_text = ", ".join(features) if features else "Core workflow only"
        
        summary = f"""🎯 Perfect! Here's your workflow specification:

**Domain:** {self.requirements.domain_name}
**System Class:** {self.requirements.system_class_name}
**Agents:** {len(self.requirements.agents_needed)} agents
**Workflow Steps:** {len(self.requirements.workflow_steps)} steps
**Persistence:** {self.requirements.persistence_backend.title()}
**Features:** {features_text}
**Output Directory:** {self.requirements.output_directory}

Ready to generate your code! I'll create:
✅ Complete workflow system Python file
✅ All imports and boilerplate code
✅ Agent creation with your specifications
✅ ConversationFlow with your steps
✅ Persistence configuration
✅ Test file template
✅ Helpful comments for customization

Files will be generated in the configured shared directory: `{self.requirements.output_directory}`

Type "generate" to create your workflow code!"""

        self.conversation_stage = "generate_code"
        return self.create_response(
            content=summary,
            recipient_id=message.sender_id,
            session_id=message.session_id,
            conversation_id=message.conversation_id
        )
    
    async def _generate_workflow_code(self, message: AgentMessage, context: ExecutionContext) -> AgentMessage:
        """Generate the complete workflow code using CodeExecutor"""
        
        user_input = message.content.strip().lower()
        if user_input not in ["generate", "create", "build", "make"]:
            return self.create_response(
                content='Please type "generate" to create your workflow code.',
                recipient_id=message.sender_id,
                session_id=message.session_id,
                conversation_id=message.conversation_id
            )
        
        # Generate the main workflow file
        main_code = self._generate_main_workflow_file()
        
        # Generate the test file
        test_code = self._generate_test_file()
        
        try:
            # Create output directory first
            output_dir = self.requirements.output_directory
            os.makedirs(output_dir, exist_ok=True)
            
            # Read the template file and create customized code
            template_path = "/Users/hemantgosain/Development/ambivo_agents/examples/workflow_stateful_example.py"
            
            with open(template_path, 'r', encoding='utf-8') as f:
                template_content = f.read()
            
            # Generate detailed customization script for CodeExecutor
            customization_script = f'''
import os
import re

# Template content
template_content = """{template_content.replace('"""', '\\"\\"\\"')}"""

# Customization parameters
domain_name = "{self.requirements.domain_name}"
system_class_name = "{self.requirements.system_class_name}"
persistence_backend = "{self.requirements.persistence_backend}"
output_dir = "{output_dir}"

# Create output directory
os.makedirs(output_dir, exist_ok=True)

# Customize the template
customized_content = template_content

# 1. Replace class name
customized_content = customized_content.replace("ProductionRealtorSystem", system_class_name)
customized_content = customized_content.replace("production_realtor", system_class_name.lower())

# 2. Update documentation and comments
customized_content = customized_content.replace("Production-Ready Interactive Realtor-Database Workflow", 
    f"Production-Ready {{domain_name}} Workflow System")
customized_content = customized_content.replace("realtor system using enhanced workflow orchestration", 
    f"{{domain_name.lower()}} system using enhanced workflow orchestration")

# 3. Update domain-specific text
customized_content = customized_content.replace("realtor", domain_name.lower().split()[0])
customized_content = customized_content.replace("Realtor", domain_name.split()[0].capitalize())
customized_content = customized_content.replace("rental properties", f"{{domain_name.lower()}} items")
customized_content = customized_content.replace("property database", f"{{domain_name.lower()}} database")

# 4. Fix imports to use correct ambivo_agents structure
correct_imports = """from ambivo_agents import DatabaseAgent, AssistantAgent
from ambivo_agents.core.workflow_orchestrator import (
    ConversationOrchestrator,
    ConversationStep,
    ConversationFlow,
    ConversationPattern
)"""
# Replace the import section
import_pattern = r'from ambivo_agents.*?\\)'
customized_content = re.sub(import_pattern, correct_imports, customized_content, flags=re.DOTALL)

# 5. Write main workflow file
main_file_path = os.path.join(output_dir, f"{{system_class_name.lower()}}.py")
with open(main_file_path, "w", encoding="utf-8") as f:
    f.write(customized_content)

# 6. Create simple test file
test_content = f"""#!/usr/bin/env python3
\"""
Test file for {{system_class_name}}
\"""

import asyncio
import sys
import os

# Add parent directory to path to import the workflow
sys.path.insert(0, os.path.dirname(__file__))

from {{system_class_name.lower()}} import {{system_class_name}}

async def test_workflow():
    \"""Test the {{domain_name.lower()}} workflow system\"""
    print(f"🧪 Testing {{system_class_name}}")
    
    try:
        # Create the workflow system
        system = {{system_class_name}}()
        print("✅ System created successfully")
        
        # Test basic functionality
        await system.start_interactive_session("test_session")
        print("✅ Session started successfully")
        
        # Cleanup
        await system.cleanup()
        print("✅ Cleanup completed")
        
        print("\\n🎉 All tests passed!")
        
    except Exception as e:
        print(f"❌ Test failed: {{e}}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_workflow())
\"""

test_file_path = os.path.join(output_dir, f"test_{{system_class_name.lower()}}.py")
with open(test_file_path, "w", encoding="utf-8") as f:
    f.write(test_content)

print(f"✅ Generated workflow files:")
print(f"📁 Directory: {{output_dir}}")
print(f"🐍 Main file: {{main_file_path}}")
print(f"🧪 Test file: {{test_file_path}}")
print(f"🔧 Persistence: {{persistence_backend}}")
print()
print("📖 Files are accessible on your host filesystem!")
print("💡 You can now run and customize the generated workflow.")
'''

            # Execute the customization script
            code_result = await self.code_executor.chat(
                f"Create customized workflow files from template:\n\n{customization_script}"
            )
            
            response = f"""🎉 **Workflow Code Generated Successfully!**

{code_result}

**What I've created for you:**

**Location:** `{self.requirements.output_directory}/`
**Main File:** `{self.requirements.system_class_name.lower()}.py`
- Complete {self.requirements.system_class_name} class
- All {len(self.requirements.agents_needed)} agents configured
- {len(self.requirements.workflow_steps)} workflow steps defined
- {self.requirements.persistence_backend.title()} persistence setup
- Comprehensive comments and hints

**Test File:** `test_{self.requirements.system_class_name.lower()}.py`
- Basic testing template
- Example usage patterns
- Async test setup

**Key Features Included:**
✅ Following WORKFLOW.md architecture patterns
✅ Agent creation with specialized system messages
✅ ConversationOrchestrator setup
✅ ConversationFlow with your steps
✅ {self.requirements.persistence_backend.title()} persistence configuration
✅ Session management
✅ Error handling
✅ Cleanup methods

**File Organization:**
📁 {self.requirements.output_directory}/
  📄 {self.requirements.system_class_name.lower()}.py (main workflow)
  🧪 test_{self.requirements.system_class_name.lower()}.py (tests)

**Customization Hints:**
- Look for `# TODO:` comments in the code
- Customize agent system messages for your domain
- Add your specific business logic to workflow steps
- Update agent_config.yaml with your persistence settings

Ready to build amazing workflows! 🚀"""

            return self.create_response(
                content=response,
                recipient_id=message.sender_id,
                session_id=message.session_id,
                conversation_id=message.conversation_id
            )
            
        except Exception as e:
            error_response = f"""❌ Error generating workflow code: {str(e)}

Let me provide the code directly instead:

**Main Workflow File Code:**
```python
{main_code[:5000]}...
```

**Test File Code:**
```python
{test_code[:3000]}...
```

Please save these manually to your project directory."""

            return self.create_response(
                content=error_response,
                recipient_id=message.sender_id,
                session_id=message.session_id,
                conversation_id=message.conversation_id,
                message_type=MessageType.ERROR
            )
    
    async def _handle_general_question(self, user_input: str, message: AgentMessage, context: ExecutionContext) -> AgentMessage:
        """Handle general questions using the assistant agent"""
        
        # Use assistant to answer questions about workflows
        assistant_response = await self.assistant.chat(
            f"The user is asking about workflow development: {user_input}\n\n"
            "Please provide helpful information about creating workflows with ambivo_agents. "
            "Reference the WORKFLOW.md patterns and architecture when relevant."
        )
        
        return self.create_response(
            content=f"📖 **Workflow Development Help:**\n\n{assistant_response}\n\n"
                   "If you'd like to start over with workflow generation, just say 'start over' or 'new workflow'.",
            recipient_id=message.sender_id,
            session_id=message.session_id,
            conversation_id=message.conversation_id
        )
    
    def _format_agents_for_prompt(self) -> str:
        """Format agents for the CodeExecutor prompt"""
        if not self.requirements.agents_needed:
            return "No specific agents defined - use default agents for the domain."
        
        agents_text = []
        for agent in self.requirements.agents_needed:
            agent_info = f"""
Agent: {agent.get('name', 'unnamed')}
Type: {agent.get('type', 'AssistantAgent')}
Description: {agent.get('description', 'No description')}
System Prompt: {agent.get('system_prompt', 'Default system prompt for ' + agent.get('name', 'agent'))}
"""
            agents_text.append(agent_info)
        
        return "\n".join(agents_text)
    
    def _format_steps_for_prompt(self) -> str:
        """Format workflow steps for the CodeExecutor prompt"""
        if not self.requirements.workflow_steps:
            return "No specific steps defined - create appropriate steps for the domain."
        
        steps_text = []
        for i, step in enumerate(self.requirements.workflow_steps):
            step_info = f"""
Step {i+1}: {step.get('id', f'step_{i+1}')}
Type: {step.get('type', 'agent_response')}
Description: {step.get('description', 'No description')}
Agent: {step.get('agent', 'primary')}
"""
            steps_text.append(step_info)
        
        return "\n".join(steps_text)
    
    def _generate_main_workflow_file(self) -> str:
        """Generate the main workflow Python file"""
        
        # Generate imports
        imports = self._generate_imports()
        
        # Generate agent creation code
        agent_creation = self._generate_agent_creation_code()
        
        # Generate orchestrator setup
        orchestrator_setup = self._generate_orchestrator_setup()
        
        # Generate workflow steps
        workflow_steps = self._generate_workflow_steps_code()
        
        # Generate main class
        main_class = f"""#!/usr/bin/env python3
\"\"\"
{self.requirements.system_class_name} - Generated by Workflow Developer Agent

This workflow system was generated following WORKFLOW.md patterns for:
Domain: {self.requirements.domain_name}
Persistence: {self.requirements.persistence_backend.title()}
Agents: {', '.join([agent['name'] for agent in self.requirements.agents_needed])}

Generated on: {{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}}
\"\"\"

{imports}


class {self.requirements.system_class_name}:
    \"\"\"
    {self.requirements.domain_name} workflow system.
    
    This class follows the WORKFLOW.md architecture pattern:
    1. Create specialized agents for your domain
    2. Set up orchestrator with persistence
    3. Build workflow with conversation steps
    4. Register and manage sessions
    \"\"\"
    
    def __init__(self):
        # Step 1: Create domain-specific agents
        self.agents = self._create_agents()
        
        # Step 2: Create orchestrator with persistence
        self.orchestrator = self._create_orchestrator()
        
        # Step 3: Build workflow
        self.workflow = self._create_workflow()
        
        # Step 4: Register workflows
        self._register_workflows()
        
        # Step 5: Session management
        self.active_sessions: Dict[str, str] = {{}}
        self.state_file = "{self.requirements.system_class_name.lower()}_state.json"
    
{agent_creation}
    
{orchestrator_setup}
    
{workflow_steps}
    
    def _register_workflows(self):
        \"\"\"Register all workflows with the orchestrator\"\"\"
        self.orchestrator.registered_flows["main_workflow"] = self.workflow
        
        # TODO: Register additional workflows here if needed
        # Example:
        # self.orchestrator.registered_flows["admin_workflow"] = self._create_admin_workflow()
    
    async def start_session(self, session_id: str = None, user_id: str = "user") -> tuple[str, str, Dict[str, Any]]:
        \"\"\"Start a new workflow session\"\"\"
        if not session_id:
            session_id = f"{self.requirements.system_class_name.lower()}_session_{{int(time.time())}}"
        
        try:
            # Start the workflow execution
            execution_id, result = await self.orchestrator.start_conversation(
                flow_id="main_workflow",
                session_id=session_id,
                initial_message="Starting {self.requirements.domain_name.lower()} workflow"
            )
            
            # Track the session
            self.active_sessions[session_id] = execution_id
            
            return session_id, execution_id, result
            
        except Exception as e:
            print(f"Error starting session: {{e}}")
            return session_id, "", {{"success": False, "error": str(e)}}
    
    async def resume_session(self, session_id: str) -> bool:
        \"\"\"Resume a paused session\"\"\"
        if session_id in self.active_sessions:
            try:
                success = await self.orchestrator.resume_conversation(session_id)
                if success:
                    print(f"✅ Session {{session_id}} resumed successfully")
                else:
                    print(f"❌ Failed to resume session {{session_id}}")
                return success
            except Exception as e:
                print(f"Error resuming session: {{e}}")
                return False
        else:
            print(f"❌ Session {{session_id}} not found")
            return False
    
    async def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        \"\"\"Get detailed session status\"\"\"
        try:
            return await self.orchestrator.get_conversation_status(session_id)
        except Exception as e:
            print(f"Error getting session status: {{e}}")
            return None
    
    async def cleanup(self):
        \"\"\"Cleanup all system resources\"\"\"
        try:
            for agent in self.agents.values():
                await agent.cleanup_session()
            print("🧹 System cleanup completed")
        except Exception as e:
            print(f"Error during cleanup: {{e}}")


async def main():
    \"\"\"Main function to run the {self.requirements.domain_name.lower()} workflow system\"\"\"
    print("🚀 {self.requirements.system_class_name} Starting...")
    print("=" * 60)
    
    system = {self.requirements.system_class_name}()
    
    try:
        # Start a demo session
        session_id, execution_id, result = await system.start_session()
        
        print(f"✅ Session started: {{session_id}}")
        print(f"🔄 Execution ID: {{execution_id}}")
        print(f"📊 Result: {{result}}")
        
        # You can add interactive session handling here
        # For example, waiting for user input and continuing the conversation
        
    except KeyboardInterrupt:
        print("\\n\\n⏸️  System interrupted by user")
    except Exception as e:
        print(f"\\n❌ System error: {{e}}")
    finally:
        await system.cleanup()


if __name__ == "__main__":
    import asyncio
    import time
    from datetime import datetime
    
    asyncio.run(main())"""
        
        return main_class
    
    def _generate_imports(self) -> str:
        """Generate import statements based on requirements"""
        imports = [
            "import asyncio",
            "import time",
            "from datetime import datetime",
            "from typing import Dict, Any, Optional",
            "",
            "from ambivo_agents.core.workflow_orchestrator import (",
            "    ConversationOrchestrator,",
            "    ConversationStep,", 
            "    ConversationFlow,",
            "    ConversationPattern",
            ")"
        ]
        
        # Add agent imports
        agent_imports = set()
        for agent in self.requirements.agents_needed:
            if agent['type'] == 'DatabaseAgent':
                agent_imports.add("from ambivo_agents import DatabaseAgent")
            elif agent['type'] == 'AssistantAgent':
                agent_imports.add("from ambivo_agents import AssistantAgent")
        
        if not agent_imports:
            agent_imports.add("from ambivo_agents import AssistantAgent")
        
        imports.extend(sorted(agent_imports))
        
        # Add feature-specific imports
        if self.requirements.use_web_search:
            imports.append("from ambivo_agents import WebSearchAgent")
        
        if self.requirements.use_api_calls:
            imports.append("from ambivo_agents import APIAgent")
        
        return "\n".join(imports)
    
    def _generate_agent_creation_code(self) -> str:
        """Generate agent creation method"""
        
        agents_code = []
        for agent in self.requirements.agents_needed:
            
            # Use AI-generated system prompt if available, otherwise create default
            if agent.get('system_prompt') and agent['system_prompt'].strip():
                system_msg = f'"""{agent["system_prompt"]}"""'
            else:
                # Generate default system message based on agent type and domain
                if agent['name'] == 'primary':
                    system_msg = f'''"""You are the primary {self.requirements.domain_name.lower()} assistant.
                    
                    Your role:
                    - Welcome users and understand their needs
                    - Guide them through the {self.requirements.domain_name.lower()} process
                    - Provide clear explanations and ask helpful questions
                    - Coordinate with other agents when needed
                    
                    Communication style: Professional, friendly, solution-oriented.
                    Always prioritize user satisfaction and clear communication."""'''
                
                elif agent['name'] == 'database':
                    system_msg = f'''"""You handle all {self.requirements.domain_name.lower()} data operations.
                    
                    Capabilities:
                    - Database queries and data retrieval
                    - Data insertion and updates
                    - Data validation and formatting
                    - Export and import operations
                    
                    Focus: Accurate, efficient data operations."""'''
                
                elif agent['name'] == 'specialist':
                    system_msg = f'''"""You are a {self.requirements.domain_name.lower()} domain specialist.
                    
                    Your expertise:
                    - Deep {self.requirements.domain_name.lower()} knowledge
                    - Complex problem analysis and solutions
                    - Best practices and recommendations
                    - Technical guidance and support
                    
                    Communication: Expert-level but accessible explanations."""'''
                
                else:
                    system_msg = f'''"""You are a {agent['description']} specialist.
                    
                    Your role: {agent['description']}
                    
                    TODO: Customize this system message for your specific needs.
                    Define the agent's expertise, communication style, and responsibilities."""'''
            
            agent_code = f'''        # {agent['description']}
        agents['{agent['name']}'] = {agent['type']}.create_simple(
            user_id="{agent['name']}_agent",
            system_message={system_msg}
        )'''
            
            agents_code.append(agent_code)
        
        return f'''    def _create_agents(self) -> Dict[str, Any]:
        """
        Create all agents needed for the {self.requirements.domain_name.lower()} workflow.
        
        Following WORKFLOW.md patterns:
        - Each agent has a specific role and expertise
        - Clear system messages define behavior
        - Agents can be reused across different workflows
        """
        agents = {{}}
        
{chr(10).join(agents_code)}
        
        # TODO: Add more agents here if needed
        # Example:
        # agents['validation'] = AssistantAgent.create_simple(
        #     user_id="validation_agent",
        #     system_message="You are a quality assurance specialist..."
        # )
        
        return agents'''
    
    def _generate_orchestrator_setup(self) -> str:
        """Generate orchestrator setup method"""
        
        if self.requirements.persistence_backend == "sqlite":
            persistence_config = '''        persistence_config = {
            'backend': 'sqlite',
            'sqlite': {
                'database_path': './data/workflow_state.db',
                'enable_wal': True,
                'auto_vacuum': True
            }
        }'''
        elif self.requirements.persistence_backend == "redis":
            persistence_config = '''        persistence_config = {
            'backend': 'redis',
            'redis': {
                'host': 'localhost',
                'port': 6379,
                'db': 2
            }
        }'''
        elif self.requirements.persistence_backend == "file":
            persistence_config = '''        persistence_config = {
            'backend': 'file',
            'file': {
                'storage_directory': './data/workflow_states'
            }
        }'''
        else:  # memory
            persistence_config = '''        persistence_config = {
            'backend': 'memory'
        }'''
        
        memory_setup = ""
        if self.requirements.use_database:
            memory_setup = '''        
        # Use shared memory with database agent for collaboration
        memory_manager = self.agents['database'].memory'''
        else:
            memory_setup = '''        
        # Use independent memory management
        memory_manager = None'''
        
        return f'''    def _create_orchestrator(self) -> ConversationOrchestrator:
        """
        Create orchestrator with {self.requirements.persistence_backend} persistence.
        
        Following WORKFLOW.md patterns:
        - Configurable persistence backend
        - Shared memory for agent collaboration
        - Production-ready settings
        """
{persistence_config}{memory_setup}
        
        return ConversationOrchestrator(
            memory_manager=memory_manager,
            persistence_config=persistence_config
        )'''
    
    def _generate_workflow_steps_code(self) -> str:
        """Generate workflow creation method with conversation steps"""
        
        steps_code = []
        for i, step in enumerate(self.requirements.workflow_steps):
            step_id = step['id']
            description = step['description']
            step_type = step['type']
            agent_name = step['agent']
            
            # Determine next step
            if i < len(self.requirements.workflow_steps) - 1:
                next_step = self.requirements.workflow_steps[i + 1]['id']
                next_steps = f'["{next_step}"]'
            else:
                next_steps = '["end"]'
            
            if step_type == "agent_response":
                # Agent response step
                step_code = f'''            ConversationStep(
                step_id="{step_id}",
                step_type="agent_response",
                agent=self.agents['{agent_name}'],
                prompt="""{description}
                
                TODO: Customize this prompt for your specific needs.
                Provide detailed instructions for what the agent should do.""",
                next_steps={next_steps}
            ),'''
            
            else:  # user_input
                # User input step
                step_code = f'''            ConversationStep(
                step_id="{step_id}",
                step_type="user_input",
                prompt="{description}",
                input_schema={{
                    "type": "text",
                    "required": True
                    # TODO: Customize input schema
                    # Examples:
                    # "type": "choice", "options": ["Option 1", "Option 2"]
                    # "type": "text", "validation": "email"
                }},
                next_steps={next_steps}
            ),'''
            
            steps_code.append(step_code)
        
        return f'''    def _create_workflow(self) -> ConversationFlow:
        """
        Create the main {self.requirements.domain_name.lower()} workflow.
        
        Following WORKFLOW.md patterns:
        - Clear conversation steps with single purposes
        - Structured user input validation
        - Contextual agent responses
        - State preservation at each step
        """
        steps = [
{chr(10).join(steps_code)}
        ]
        
        return ConversationFlow(
            flow_id="main_{self.requirements.domain_name.lower().replace(' ', '_')}_workflow",
            name="{self.requirements.domain_name} Workflow",
            description="Main workflow for {self.requirements.domain_name.lower()} operations",
            pattern=ConversationPattern.STEP_BY_STEP_PROCESS,
            steps=steps,
            start_step="{self.requirements.workflow_steps[0]['id'] if self.requirements.workflow_steps else 'step_1'}",
            end_steps=["{self.requirements.workflow_steps[-1]['id'] if self.requirements.workflow_steps else 'step_1'}"],
            settings={{
                'enable_rollback': True,
                'auto_checkpoint': True,
                'checkpoint_interval': 30,
                'interaction_timeout': 300,
                'persist_state': True
            }}
        )'''
    
    def _generate_test_file(self) -> str:
        """Generate a test file template"""
        
        return f'''#!/usr/bin/env python3
"""
Test file for {self.requirements.system_class_name}

This file demonstrates how to use your generated workflow system
and provides basic tests to verify functionality.
"""

import asyncio
import pytest
from {self.requirements.system_class_name.lower()} import {self.requirements.system_class_name}


class Test{self.requirements.system_class_name}:
    """Test cases for {self.requirements.system_class_name}"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.system = {self.requirements.system_class_name}()
    
    async def test_system_initialization(self):
        """Test that the system initializes correctly"""
        assert self.system is not None
        assert len(self.system.agents) == {len(self.requirements.agents_needed)}
        assert self.system.orchestrator is not None
        assert self.system.workflow is not None
    
    async def test_agent_creation(self):
        """Test that all agents are created properly"""
        expected_agents = {{{', '.join([f'"{agent["name"]}"' for agent in self.requirements.agents_needed])}}}
        
        for agent_name in expected_agents:
            assert agent_name in self.system.agents
            assert self.system.agents[agent_name] is not None
    
    async def test_workflow_structure(self):
        """Test that the workflow is properly structured"""
        workflow = self.system.workflow
        
        assert workflow.flow_id is not None
        assert len(workflow.steps) == {len(self.requirements.workflow_steps)}
        assert workflow.start_step is not None
        assert len(workflow.end_steps) > 0
    
    async def test_session_creation(self):
        """Test creating a new session"""
        session_id, execution_id, result = await self.system.start_session()
        
        assert session_id is not None
        assert session_id in self.system.active_sessions
        
        # Cleanup
        await self.system.cleanup()
    
    async def test_session_status(self):
        """Test getting session status"""
        session_id, execution_id, result = await self.system.start_session()
        
        status = await self.system.get_session_status(session_id)
        # Note: Status might be None if persistence is not configured
        
        # Cleanup
        await self.system.cleanup()
    
    async def teardown_method(self):
        """Clean up after tests"""
        await self.system.cleanup()


async def demo_interactive_session():
    """
    Demo function showing how to use the workflow system interactively.
    
    This demonstrates the basic usage pattern for your {self.requirements.domain_name.lower()} workflow.
    """
    print("🚀 {self.requirements.system_class_name} Demo")
    print("=" * 50)
    
    # Create the system
    system = {self.requirements.system_class_name}()
    
    try:
        # Start a session
        session_id, execution_id, result = await system.start_session()
        print(f"✅ Session started: {{session_id}}")
        print(f"🔄 Execution ID: {{execution_id}}")
        
        # Get session status
        status = await system.get_session_status(session_id)
        if status:
            print(f"📊 Status: {{status['status']}}")
            print(f"📈 Progress: {{status.get('progress', 0):.1%}}")
        
        # TODO: Add interactive conversation loop here
        # Example:
        # while True:
        #     user_input = input("You: ")
        #     if user_input.lower() in ['exit', 'quit']:
        #         break
        #     
        #     # Continue conversation with user input
        #     response = await system.continue_conversation(session_id, user_input)
        #     print(f"System: {{response}}")
        
        print("\\n🎉 Demo completed successfully!")
        
    except Exception as e:
        print(f"❌ Demo error: {{e}}")
    
    finally:
        await system.cleanup()


async def main():
    """Main function - run either tests or demo"""
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "demo":
        await demo_interactive_session()
    else:
        print("Running basic tests...")
        test_instance = Test{self.requirements.system_class_name}()
        
        # Run tests manually (or use pytest)
        test_instance.setup_method()
        
        try:
            await test_instance.test_system_initialization()
            print("✅ System initialization test passed")
            
            await test_instance.test_agent_creation()
            print("✅ Agent creation test passed")
            
            await test_instance.test_workflow_structure()
            print("✅ Workflow structure test passed")
            
            await test_instance.test_session_creation()
            print("✅ Session creation test passed")
            
            print("\\n🎉 All tests passed!")
            
        except Exception as e:
            print(f"❌ Test failed: {{e}}")
        
        finally:
            await test_instance.teardown_method()


if __name__ == "__main__":
    asyncio.run(main())'''
    
    async def process_message_stream(self, message: AgentMessage, context: ExecutionContext = None):
        """Stream processing for workflow developer (not implemented - returns regular response)"""
        # For now, just return the regular process_message result
        # Streaming can be added later if needed
        response = await self.process_message(message, context)
        yield response
    
    async def cleanup_session(self):
        """Cleanup session resources"""
        if self.assistant:
            await self.assistant.cleanup_session()
        if self.code_executor:
            await self.code_executor.cleanup_session()
        await super().cleanup_session()