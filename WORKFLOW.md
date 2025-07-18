# Workflow Development Guide

## 🏗️ Complete Workflow Architecture & Development Guide

This guide provides comprehensive documentation for building robust, stateful workflows using the ambivo_agents library.

## 📋 Table of Contents

1. [Core Workflow Components](#core-workflow-components)
2. [Agent Creation Patterns](#agent-creation-patterns)
3. [Orchestrator Setup](#orchestrator-setup)
4. [Workflow Building](#workflow-building)
5. [State Persistence & SQLite Configuration](#state-persistence--sqlite-configuration)
6. [Complete Examples](#complete-examples)
7. [Best Practices](#best-practices)

## Core Workflow Components

### 🏗️ System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    SYSTEM DOMAIN CLASS                         │
│  (RealtorSystem, ECommerceSystem, CustomerServiceSystem)       │
│                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   AGENTS        │  │  ORCHESTRATOR   │  │ STATE & PERSIST │ │
│  │                 │  │                 │  │                 │ │
│  │ • DatabaseAgent │  │ • Conversation  │  │ • SQLite DB     │ │
│  │ • AssistantAgent│  │   Orchestrator  │  │ • Redis Cache   │ │
│  │ • CustomAgents  │  │ • Memory Mgmt   │  │ • File Storage  │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
│                                │                                │
│  ┌─────────────────────────────▼──────────────────────────────┐ │
│  │                  WORKFLOW CREATION                         │ │
│  │                                                            │ │
│  │  self.workflow = self._create_workflow()                  │ │
│  │                                                            │ │
│  │  ┌─────────────────────────────────────────────────────┐  │ │
│  │  │              ConversationFlow                       │  │ │
│  │  │  ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐     │  │ │
│  │  │  │Step1│─▶│Step2│─▶│Step3│─▶│Step4│─▶│Step5│ ... │  │ │
│  │  │  └─────┘  └─────┘  └─────┘  └─────┘  └─────┘     │  │ │
│  │  │                                                 │  │ │
│  │  │  Pattern: STEP_BY_STEP_PROCESS                  │  │ │
│  │  │  Persistence: SQLite/Redis/File                 │  │ │
│  │  └─────────────────────────────────────────────────────┘  │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Agent Creation Patterns

### 1. `self.agents = self._create_agents()`

The agent creation pattern is the foundation of your workflow system. It defines all the AI agents that will participate in your workflow.

#### 🎯 Purpose
- **Specialization**: Each agent has a specific role and expertise
- **Modularity**: Agents can be reused across different workflows
- **Scalability**: Easy to add new agents or modify existing ones

#### 📝 Detailed Pattern

```python
def _create_agents(self) -> Dict[str, BaseAgent]:
    """
    Create all agents needed for your workflow domain.
    
    Best Practices:
    - Use descriptive agent names that reflect their role
    - Give each agent a specific system message that defines their behavior
    - Consider agent interactions and data flow
    - Use appropriate agent types for different tasks
    """
    
    agents = {}
    
    # 1. PRIMARY AGENT - Main conversation handler
    agents['primary'] = AssistantAgent.create_simple(
        user_id="primary_agent",
        system_message="""You are the primary customer service representative.
        
        Your responsibilities:
        - Welcome users and understand their needs
        - Guide them through the process step by step
        - Provide clear explanations and ask clarifying questions
        - Maintain a friendly, professional tone
        - Escalate complex issues to specialist agents when needed
        
        Communication style: Conversational, helpful, patient"""
    )
    
    # 2. DATABASE AGENT - Data operations
    agents['database'] = DatabaseAgent.create_simple(
        user_id="database_agent"
        # DatabaseAgent automatically handles:
        # - MongoDB connections
        # - Data querying and insertion
        # - Schema validation
        # - Error handling for database operations
    )
    
    # 3. SPECIALIST AGENT - Domain expertise
    agents['specialist'] = AssistantAgent.create_simple(
        user_id="specialist_agent",
        system_message="""You are a domain specialist with deep expertise.
        
        Your role:
        - Analyze complex requests that require expert knowledge
        - Provide detailed technical explanations
        - Recommend best solutions based on user requirements
        - Work with the primary agent to deliver comprehensive answers
        
        Expertise areas: [Customize based on your domain]"""
    )
    
    # 4. VALIDATION AGENT - Quality assurance
    agents['validator'] = AssistantAgent.create_simple(
        user_id="validation_agent",
        system_message="""You are a quality assurance specialist.
        
        Your responsibilities:
        - Review responses before they're sent to users
        - Ensure accuracy and completeness
        - Flag potential issues or inconsistencies
        - Suggest improvements to responses
        
        Focus: Accuracy, clarity, user satisfaction"""
    )
    
    return agents
```

#### 🏢 Real-World Example: E-Commerce System

```python
def _create_agents(self) -> Dict[str, BaseAgent]:
    """E-Commerce workflow agents"""
    
    return {
        # Customer service representative
        'customer_service': AssistantAgent.create_simple(
            user_id="cs_agent",
            system_message="""You are a friendly e-commerce customer service rep.
            Help customers with orders, returns, product questions, and general inquiries.
            Always be helpful and solution-oriented."""
        ),
        
        # Product catalog specialist
        'product_specialist': AssistantAgent.create_simple(
            user_id="product_agent", 
            system_message="""You are a product specialist with deep knowledge of our catalog.
            Help customers find products, compare features, check availability,
            and provide detailed product information."""
        ),
        
        # Order management system
        'order_manager': DatabaseAgent.create_simple(
            user_id="order_db_agent"
        ),
        
        # Inventory specialist
        'inventory': AssistantAgent.create_simple(
            user_id="inventory_agent",
            system_message="""You manage inventory and shipping information.
            Provide real-time stock levels, shipping estimates, and delivery tracking."""
        ),
        
        # Payment processor (if needed)
        'payment': AssistantAgent.create_simple(
            user_id="payment_agent",
            system_message="""You handle payment-related inquiries.
            Help with billing questions, refunds, payment methods, and transaction issues."""
        )
    }
```

#### 🏥 Real-World Example: Healthcare System

```python
def _create_agents(self) -> Dict[str, BaseAgent]:
    """Healthcare workflow agents"""
    
    return {
        # Patient intake coordinator
        'intake': AssistantAgent.create_simple(
            user_id="intake_agent",
            system_message="""You are a patient intake coordinator.
            Collect patient information, schedule appointments, verify insurance,
            and guide patients through registration processes."""
        ),
        
        # Medical records manager
        'records': DatabaseAgent.create_simple(
            user_id="records_agent"
        ),
        
        # Appointment scheduler
        'scheduler': AssistantAgent.create_simple(
            user_id="scheduler_agent",
            system_message="""You manage appointment scheduling and calendar coordination.
            Find available slots, handle rescheduling, send reminders,
            and coordinate with multiple departments."""
        ),
        
        # Insurance specialist
        'insurance': AssistantAgent.create_simple(
            user_id="insurance_agent",
            system_message="""You are an insurance and billing specialist.
            Verify coverage, explain benefits, handle prior authorizations,
            and assist with billing questions."""
        ),
        
        # Clinical support
        'clinical': AssistantAgent.create_simple(
            user_id="clinical_agent",
            system_message="""You provide clinical support and triage.
            Assess symptom urgency, direct patients to appropriate care levels,
            and provide general health information."""
        )
    }
```

## Orchestrator Setup

### 2. `self.orchestrator = ConversationOrchestrator()`

The orchestrator is the "brain" that manages workflow execution, state persistence, and agent coordination.

#### 🎯 Purpose
- **Workflow Management**: Controls the flow between conversation steps
- **State Persistence**: Saves and restores conversation state
- **Session Management**: Handles multiple concurrent user sessions
- **Error Recovery**: Provides rollback and retry capabilities

#### 📝 Detailed Setup Patterns

```python
def _create_orchestrator(self) -> ConversationOrchestrator:
    """
    Create the conversation orchestrator with appropriate configuration.
    
    Configuration Options:
    - Memory management strategy
    - Persistence backend (SQLite, Redis, File)
    - Session timeout settings
    - Error recovery options
    """
    
    # OPTION 1: Shared Memory with Database Agent
    # Use this when you want all agents to share conversation history
    if hasattr(self, 'agents') and 'database' in self.agents:
        return ConversationOrchestrator(
            memory_manager=self.agents['database'].memory,
            persistence_config={
                'backend': 'sqlite',
                'database_path': './workflow_state.db',
                'auto_checkpoint': True,
                'checkpoint_interval': 30  # seconds
            }
        )
    
    # OPTION 2: Independent Memory Management
    # Use this when you want the orchestrator to manage its own memory
    return ConversationOrchestrator(
        memory_manager=None,  # Creates its own memory manager
        persistence_config={
            'backend': 'file',
            'state_directory': './workflow_states/',
            'auto_save': True
        }
    )
    
    # OPTION 3: Redis-based High-Performance Setup
    # Use this for production systems with high concurrency
    return ConversationOrchestrator(
        memory_manager=None,
        persistence_config={
            'backend': 'redis',
            'redis_host': 'localhost',
            'redis_port': 6379,
            'redis_db': 2,
            'session_ttl': 3600  # 1 hour
        }
    )
```

#### 🔧 Advanced Orchestrator Configuration

```python
def _create_orchestrator(self) -> ConversationOrchestrator:
    """Advanced orchestrator with full configuration"""
    
    config = {
        # Memory Management
        'memory_manager': self.agents['database'].memory,
        
        # Persistence Configuration
        'persistence_config': {
            'backend': 'sqlite',
            'database_path': './data/workflow_state.db',
            'auto_checkpoint': True,
            'checkpoint_interval': 30,
            'max_checkpoints': 100,
            'compression': True
        },
        
        # Session Management
        'session_config': {
            'default_timeout': 1800,  # 30 minutes
            'max_concurrent_sessions': 1000,
            'session_cleanup_interval': 300,  # 5 minutes
            'idle_session_timeout': 3600  # 1 hour
        },
        
        # Error Handling
        'error_config': {
            'max_retries': 3,
            'retry_delay': 1.0,
            'auto_recovery': True,
            'fallback_responses': {
                'agent_timeout': "I'm sorry, there was a delay. Let me try again.",
                'agent_error': "I encountered an issue. Let me handle this differently.",
                'network_error': "Connection issue detected. Retrying..."
            }
        },
        
        # Performance Settings
        'performance_config': {
            'parallel_execution': False,  # Set True for concurrent step execution
            'step_timeout': 60,  # seconds
            'max_workflow_duration': 3600,  # 1 hour
            'resource_monitoring': True
        }
    }
    
    return ConversationOrchestrator(**config)
```

#### 🌐 Multi-Tenant Setup Example

```python
def _create_orchestrator(self) -> ConversationOrchestrator:
    """Multi-tenant orchestrator for SaaS applications"""
    
    return ConversationOrchestrator(
        memory_manager=self.agents['database'].memory,
        persistence_config={
            'backend': 'sqlite',
            'database_path': f'./tenant_data/{self.tenant_id}/workflow_state.db',
            'tenant_isolation': True,
            'encryption': True,
            'encryption_key': self.tenant_encryption_key
        },
        session_config={
            'tenant_id': self.tenant_id,
            'session_prefix': f'tenant_{self.tenant_id}_',
            'quota_limits': {
                'max_sessions_per_tenant': 100,
                'max_steps_per_session': 1000,
                'rate_limit_per_minute': 60
            }
        }
    )
```

## Workflow Building

### 3. `self.workflow = self._create_workflow()`

The workflow creation is where you define the conversation flow as a series of interconnected steps.

#### 🎯 Purpose
- **Conversation Logic**: Define the step-by-step interaction flow
- **User Experience**: Control how users navigate through the process
- **Business Rules**: Implement domain-specific logic and validation
- **State Management**: Define what data is collected and how it flows

#### 📝 Detailed Workflow Creation

```python
def _create_workflow(self) -> ConversationFlow:
    """
    Create the main conversation workflow.
    
    Workflow Design Principles:
    - Each step should have a single, clear purpose
    - User input should be validated and structured
    - Agent responses should be contextual and helpful
    - Flow should handle both happy path and edge cases
    - State should be preserved at each step
    """
    
    # STEP ARRAY: Define each conversation step
    steps = [
        # === WELCOME & INTRODUCTION ===
        ConversationStep(
            step_id="welcome",
            step_type="agent_response",
            agent=self.agents['primary'],
            prompt="""Welcome the user warmly and professionally.
            
            Your tasks:
            1. Introduce yourself and your role
            2. Briefly explain what you can help with
            3. Ask how you can assist them today
            4. Set expectations for the conversation process
            
            Keep it friendly but concise.""",
            next_steps=["identify_need"],
            metadata={
                'step_category': 'introduction',
                'required_context': [],
                'expected_duration': 30  # seconds
            }
        ),
        
        # === NEED IDENTIFICATION ===
        ConversationStep(
            step_id="identify_need",
            step_type="user_input",
            prompt="How can I help you today? Please describe what you're looking for or what you need assistance with.",
            input_schema={
                'type': 'text',
                'required': True,
                'min_length': 10,
                'max_length': 500,
                'validation_hints': [
                    "Please provide at least a brief description",
                    "You can describe your situation in your own words"
                ]
            },
            next_steps=["analyze_request"],
            metadata={
                'step_category': 'information_gathering',
                'data_collection': ['user_request', 'initial_intent'],
                'timeout': 300  # 5 minutes
            }
        ),
        
        # === REQUEST ANALYSIS ===
        ConversationStep(
            step_id="analyze_request",
            step_type="agent_response",
            agent=self.agents['primary'],
            prompt="""Analyze the user's request and determine the best approach.
            
            Your tasks:
            1. Acknowledge their request to show you understand
            2. Identify the type of assistance needed
            3. Determine if you need additional information
            4. Explain the next steps in the process
            
            If the request is complex, mention that you may involve specialists.
            If you need more information, ask specific, helpful questions.""",
            next_steps=["collect_details", "provide_solution"],
            conditional_logic={
                'condition': 'request_complexity',
                'simple_request': 'provide_solution',
                'complex_request': 'collect_details'
            },
            metadata={
                'step_category': 'analysis',
                'decision_point': True
            }
        ),
        
        # === DETAIL COLLECTION (for complex requests) ===
        ConversationStep(
            step_id="collect_details",
            step_type="user_input",
            prompt="To provide the best assistance, I need a few more details. {dynamic_questions}",
            input_schema={
                'type': 'structured',
                'fields': {
                    'specific_requirements': {
                        'type': 'text',
                        'required': True,
                        'prompt': 'What are your specific requirements?'
                    },
                    'timeline': {
                        'type': 'choice',
                        'options': ['Urgent (today)', 'Soon (this week)', 'Flexible (this month)', 'Planning ahead'],
                        'required': True,
                        'prompt': 'What is your timeline?'
                    },
                    'budget_considerations': {
                        'type': 'text',
                        'required': False,
                        'prompt': 'Are there any budget considerations? (optional)'
                    }
                }
            },
            next_steps=["process_details"],
            metadata={
                'step_category': 'detailed_information_gathering',
                'data_collection': ['requirements', 'timeline', 'budget'],
                'allows_partial_completion': True
            }
        ),
        
        # === DETAIL PROCESSING ===
        ConversationStep(
            step_id="process_details",
            step_type="agent_response",
            agent=self.agents['specialist'],
            prompt="""Process the detailed information provided by the user.
            
            Your tasks:
            1. Analyze all collected information comprehensively
            2. Identify potential solutions or next steps
            3. Consider any constraints or special requirements
            4. Prepare recommendations based on their needs
            
            Use your specialist knowledge to provide the most helpful approach.""",
            next_steps=["present_solution"],
            metadata={
                'step_category': 'processing',
                'requires_specialist': True,
                'processing_time': 60  # seconds
            }
        ),
        
        # === SOLUTION PRESENTATION ===
        ConversationStep(
            step_id="provide_solution",
            step_type="agent_response",
            agent=self.agents['primary'],
            prompt="""Provide a solution or next steps for the user's request.
            
            Your approach:
            1. Present your recommendations clearly
            2. Explain the reasoning behind your suggestions
            3. Provide actionable next steps
            4. Ask if they need clarification or have questions
            
            Be thorough but easy to understand.""",
            next_steps=["get_feedback"],
            metadata={
                'step_category': 'solution_delivery',
                'solution_type': 'direct'
            }
        ),
        
        ConversationStep(
            step_id="present_solution",
            step_type="agent_response",
            agent=self.agents['specialist'],
            prompt="""Present comprehensive solutions based on detailed analysis.
            
            Your approach:
            1. Present multiple options if appropriate
            2. Explain pros and cons of each approach
            3. Recommend the best option based on their requirements
            4. Provide detailed implementation steps
            5. Address potential challenges or considerations
            
            Use your expertise to give them confidence in the solution.""",
            next_steps=["get_feedback"],
            metadata={
                'step_category': 'solution_delivery',
                'solution_type': 'comprehensive'
            }
        ),
        
        # === FEEDBACK COLLECTION ===
        ConversationStep(
            step_id="get_feedback",
            step_type="user_input",
            prompt="How does this solution work for you? Do you have any questions or would you like me to adjust anything?",
            input_schema={
                'type': 'choice',
                'options': [
                    'Perfect, this is exactly what I needed',
                    'Good, but I have some questions',
                    'Helpful, but I need some adjustments',
                    'Not quite right, let me provide more details',
                    'I need to think about this'
                ],
                'required': True,
                'allow_custom_response': True
            },
            next_steps=["handle_feedback"],
            metadata={
                'step_category': 'feedback_collection',
                'satisfaction_check': True
            }
        ),
        
        # === FEEDBACK HANDLING ===
        ConversationStep(
            step_id="handle_feedback",
            step_type="agent_response",
            agent=self.agents['primary'],
            prompt="""Respond to the user's feedback appropriately.
            
            Based on their feedback:
            - If satisfied: Summarize next steps and offer additional help
            - If questions: Answer thoroughly and check for more questions
            - If adjustments needed: Work with them to refine the solution
            - If not right: Gather more information and try a different approach
            - If thinking: Offer to follow up and provide contact information
            
            Always end by asking if there's anything else you can help with.""",
            next_steps=["followup_questions", "completion"],
            conditional_logic={
                'condition': 'satisfaction_level',
                'satisfied': 'completion',
                'needs_more_help': 'followup_questions'
            },
            metadata={
                'step_category': 'feedback_handling',
                'potential_loop_back': True
            }
        ),
        
        # === FOLLOW-UP QUESTIONS ===
        ConversationStep(
            step_id="followup_questions",
            step_type="user_input",
            prompt="What additional questions do you have? I'm here to help clarify anything.",
            input_schema={
                'type': 'text',
                'required': True,
                'placeholder': 'Please ask your question...'
            },
            next_steps=["answer_questions"],
            metadata={
                'step_category': 'follow_up',
                'allows_multiple_iterations': True
            }
        ),
        
        # === QUESTION ANSWERING ===
        ConversationStep(
            step_id="answer_questions",
            step_type="agent_response",
            agent=self.agents['primary'],
            prompt="""Answer the user's follow-up questions thoroughly.
            
            Your approach:
            1. Address each question directly and completely
            2. Provide examples or clarification where helpful
            3. Connect answers back to their original request
            4. Check if they have more questions
            
            Be patient and thorough.""",
            next_steps=["check_satisfaction"],
            metadata={
                'step_category': 'question_answering'
            }
        ),
        
        # === SATISFACTION CHECK ===
        ConversationStep(
            step_id="check_satisfaction",
            step_type="user_input",
            prompt="Does that answer your questions? Is there anything else I can help you with?",
            input_schema={
                'type': 'choice',
                'options': [
                    'Yes, that covers everything',
                    'I have one more question',
                    'I need help with something else',
                    'No, I\'m all set'
                ],
                'required': True
            },
            next_steps=["followup_questions", "completion"],
            conditional_logic={
                'condition': 'user_choice',
                'more_questions': 'followup_questions',
                'something_else': 'identify_need',
                'satisfied': 'completion'
            },
            metadata={
                'step_category': 'satisfaction_verification'
            }
        ),
        
        # === COMPLETION ===
        ConversationStep(
            step_id="completion",
            step_type="agent_response",
            agent=self.agents['primary'],
            prompt="""Wrap up the conversation professionally.
            
            Your closing tasks:
            1. Summarize what was accomplished
            2. Confirm next steps if any
            3. Provide contact information for future needs
            4. Thank them for their time
            5. Offer assistance in the future
            
            Leave them with a positive impression.""",
            next_steps=["end"],
            metadata={
                'step_category': 'completion',
                'conversation_summary': True,
                'satisfaction_survey': True
            }
        )
    ]
    
    # CREATE THE CONVERSATION FLOW
    return ConversationFlow(
        flow_id="comprehensive_workflow",
        name="Comprehensive Customer Service Workflow",
        description="A full-featured workflow for handling various customer service scenarios",
        pattern=ConversationPattern.STEP_BY_STEP_PROCESS,
        steps=steps,
        start_step="welcome",
        end_steps=["completion"],
        settings={
            # State Management
            'enable_rollback': True,
            'auto_checkpoint': True,
            'checkpoint_interval': 30,  # seconds
            'max_rollback_steps': 5,
            
            # Interaction Management
            'interaction_timeout': 600,  # 10 minutes
            'max_retries': 3,
            'retry_delay': 2.0,
            
            # Flow Control
            'allow_step_skipping': False,
            'allow_early_termination': True,
            'resume_on_failure': True,
            
            # Data Management
            'persist_state': True,
            'compress_state': True,
            'encrypt_sensitive_data': True,
            
            # Performance
            'lazy_load_agents': True,
            'parallel_validation': True,
            'cache_agent_responses': False
        }
    )
```

## State Persistence & SQLite Configuration

### 🗄️ SQLite Persistence Setup

To enable SQLite persistence for workflow state and step preservation, you need to configure the system properly.

#### 1. Add SQLite Dependency

First, update your `requirements.txt`:

```text
# Add to requirements.txt
aiosqlite>=0.19.0
```

#### 2. Configuration in `agent_config.yaml`

```yaml
# agent_config.yaml

# Workflow Persistence Configuration
workflow_persistence:
  # Backend options: 'sqlite', 'redis', 'file', 'memory'
  backend: 'sqlite'
  
  # SQLite specific settings
  sqlite:
    database_path: './data/workflow_state.db'
    enable_wal: true  # Write-Ahead Logging for better performance
    timeout: 30.0     # Connection timeout in seconds
    auto_vacuum: true # Automatic database cleanup
    journal_mode: 'WAL'  # Journal mode for concurrent access
    
    # Table configuration
    tables:
      conversations: 'workflow_conversations'
      steps: 'workflow_steps' 
      checkpoints: 'workflow_checkpoints'
      sessions: 'workflow_sessions'
    
    # Retention policies
    retention:
      conversation_ttl: 2592000  # 30 days in seconds
      checkpoint_ttl: 604800     # 7 days in seconds
      session_ttl: 86400         # 24 hours in seconds
      cleanup_interval: 3600     # 1 hour cleanup cycle
  
  # Redis settings (alternative)
  redis:
    host: 'localhost'
    port: 6379
    db: 2
    password: null
    ssl: false
    session_ttl: 3600
  
  # File storage settings (alternative)
  file:
    storage_directory: './data/workflow_states'
    compression: true
    encryption: false
    max_file_size: 10485760  # 10MB
  
  # General persistence settings
  general:
    auto_checkpoint: true
    checkpoint_interval: 30    # seconds
    max_checkpoints_per_session: 100
    enable_compression: true
    enable_encryption: false
    encryption_key: null       # Set this for encryption

# Memory configuration for workflow orchestrator
memory:
  # Use shared memory between orchestrator and agents
  shared_memory: true
  
  # Memory backend for conversation history
  backend: 'redis'  # 'redis' or 'in_memory'
  
  # Redis settings for memory (if using Redis)
  redis:
    host: ${AMBIVO_AGENTS_REDIS_HOST:localhost}
    port: ${AMBIVO_AGENTS_REDIS_PORT:6379}
    db: ${AMBIVO_AGENTS_REDIS_DB:0}
    password: ${AMBIVO_AGENTS_REDIS_PASSWORD:}
```

#### 3. Environment Variables

Add these environment variables for configuration override:

```bash
# .env file or environment
AMBIVO_AGENTS_WORKFLOW_PERSISTENCE_BACKEND=sqlite
AMBIVO_AGENTS_WORKFLOW_PERSISTENCE_SQLITE_DATABASE_PATH=./data/workflow_state.db
AMBIVO_AGENTS_WORKFLOW_PERSISTENCE_SQLITE_ENABLE_WAL=true
AMBIVO_AGENTS_WORKFLOW_PERSISTENCE_GENERAL_AUTO_CHECKPOINT=true
AMBIVO_AGENTS_WORKFLOW_PERSISTENCE_GENERAL_CHECKPOINT_INTERVAL=30
```

#### 4. Update `config/loader.py`

```python
# In config/loader.py - add workflow persistence configuration

def load_workflow_persistence_config(config_data: Dict[str, Any]) -> Dict[str, Any]:
    """Load workflow persistence configuration"""
    persistence_config = config_data.get('workflow_persistence', {})
    
    # Apply environment variable overrides
    env_mappings = {
        'AMBIVO_AGENTS_WORKFLOW_PERSISTENCE_BACKEND': 
            ('backend',),
        'AMBIVO_AGENTS_WORKFLOW_PERSISTENCE_SQLITE_DATABASE_PATH': 
            ('sqlite', 'database_path'),
        'AMBIVO_AGENTS_WORKFLOW_PERSISTENCE_SQLITE_ENABLE_WAL': 
            ('sqlite', 'enable_wal'),
        'AMBIVO_AGENTS_WORKFLOW_PERSISTENCE_GENERAL_AUTO_CHECKPOINT': 
            ('general', 'auto_checkpoint'),
        'AMBIVO_AGENTS_WORKFLOW_PERSISTENCE_GENERAL_CHECKPOINT_INTERVAL': 
            ('general', 'checkpoint_interval'),
    }
    
    for env_var, config_path in env_mappings.items():
        env_value = os.getenv(env_var)
        if env_value is not None:
            # Navigate to nested config and set value
            current = persistence_config
            for key in config_path[:-1]:
                current = current.setdefault(key, {})
            
            # Convert value to appropriate type
            final_key = config_path[-1]
            if env_value.lower() in ('true', 'false'):
                current[final_key] = env_value.lower() == 'true'
            elif env_value.isdigit():
                current[final_key] = int(env_value)
            else:
                current[final_key] = env_value
    
    return persistence_config

# Update the main load_config function
def load_config() -> Dict[str, Any]:
    """Load complete configuration including workflow persistence"""
    config_data = _load_yaml_config()
    
    config = {
        'redis': load_redis_config(config_data),
        'llm': load_llm_config(config_data),
        'agent_capabilities': load_agent_capabilities_config(config_data),
        'knowledge_base': load_knowledge_base_config(config_data),
        'web_search': load_web_search_config(config_data),
        'docker': load_docker_config(config_data),
        'analytics': load_analytics_config(config_data),
        'api_agent': load_api_agent_config(config_data),
        'workflow_persistence': load_workflow_persistence_config(config_data),  # NEW
    }
    
    return config
```

#### 5. SQLite Persistence Implementation

Create the SQLite persistence backend:

```python
# ambivo_agents/core/persistence/sqlite_backend.py

import aiosqlite
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import asdict

class SQLiteWorkflowPersistence:
    """SQLite-based workflow state persistence"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.db_path = config.get('database_path', './workflow_state.db')
        self.enable_wal = config.get('enable_wal', True)
        self.timeout = config.get('timeout', 30.0)
        
        # Table names
        tables = config.get('tables', {})
        self.conversations_table = tables.get('conversations', 'workflow_conversations')
        self.steps_table = tables.get('steps', 'workflow_steps')
        self.checkpoints_table = tables.get('checkpoints', 'workflow_checkpoints')
        self.sessions_table = tables.get('sessions', 'workflow_sessions')
        
        # Retention settings
        retention = config.get('retention', {})
        self.conversation_ttl = retention.get('conversation_ttl', 2592000)  # 30 days
        self.checkpoint_ttl = retention.get('checkpoint_ttl', 604800)       # 7 days
        self.session_ttl = retention.get('session_ttl', 86400)             # 24 hours
        
        self._initialized = False
    
    async def initialize(self):
        """Initialize the SQLite database and tables"""
        if self._initialized:
            return
            
        async with aiosqlite.connect(self.db_path, timeout=self.timeout) as db:
            # Enable WAL mode for better concurrency
            if self.enable_wal:
                await db.execute("PRAGMA journal_mode=WAL")
            
            # Create tables
            await self._create_tables(db)
            await db.commit()
            
        self._initialized = True
    
    async def _create_tables(self, db: aiosqlite.Connection):
        """Create necessary tables for workflow persistence"""
        
        # Conversations table
        await db.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.conversations_table} (
                conversation_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                flow_id TEXT NOT NULL,
                status TEXT NOT NULL,
                current_step TEXT,
                state_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX(session_id),
                INDEX(flow_id),
                INDEX(status)
            )
        """)
        
        # Steps table
        await db.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.steps_table} (
                step_id TEXT,
                conversation_id TEXT,
                step_type TEXT NOT NULL,
                agent_id TEXT,
                input_data TEXT,
                output_data TEXT,
                execution_start TIMESTAMP,
                execution_end TIMESTAMP,
                status TEXT NOT NULL,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (step_id, conversation_id),
                FOREIGN KEY (conversation_id) REFERENCES {self.conversations_table}(conversation_id),
                INDEX(conversation_id),
                INDEX(status)
            )
        """)
        
        # Checkpoints table
        await db.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.checkpoints_table} (
                checkpoint_id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                step_id TEXT NOT NULL,
                state_snapshot TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES {self.conversations_table}(conversation_id),
                INDEX(conversation_id),
                INDEX(created_at)
            )
        """)
        
        # Sessions table
        await db.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.sessions_table} (
                session_id TEXT PRIMARY KEY,
                user_id TEXT,
                metadata TEXT,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX(user_id),
                INDEX(last_activity)
            )
        """)
    
    async def save_conversation_state(self, conversation_id: str, state: Dict[str, Any]):
        """Save conversation state to SQLite"""
        await self.initialize()
        
        async with aiosqlite.connect(self.db_path, timeout=self.timeout) as db:
            await db.execute(f"""
                INSERT OR REPLACE INTO {self.conversations_table}
                (conversation_id, session_id, flow_id, status, current_step, state_data, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                conversation_id,
                state.get('session_id'),
                state.get('flow_id'),
                state.get('status'),
                state.get('current_step'),
                json.dumps(state)
            ))
            await db.commit()
    
    async def load_conversation_state(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Load conversation state from SQLite"""
        await self.initialize()
        
        async with aiosqlite.connect(self.db_path, timeout=self.timeout) as db:
            async with db.execute(f"""
                SELECT state_data FROM {self.conversations_table}
                WHERE conversation_id = ?
            """, (conversation_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return json.loads(row[0])
                return None
    
    async def save_step_execution(self, conversation_id: str, step_data: Dict[str, Any]):
        """Save step execution details"""
        await self.initialize()
        
        async with aiosqlite.connect(self.db_path, timeout=self.timeout) as db:
            await db.execute(f"""
                INSERT OR REPLACE INTO {self.steps_table}
                (step_id, conversation_id, step_type, agent_id, input_data, 
                 output_data, execution_start, execution_end, status, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                step_data.get('step_id'),
                conversation_id,
                step_data.get('step_type'),
                step_data.get('agent_id'),
                json.dumps(step_data.get('input_data')),
                json.dumps(step_data.get('output_data')),
                step_data.get('execution_start'),
                step_data.get('execution_end'),
                step_data.get('status'),
                step_data.get('error_message')
            ))
            await db.commit()
    
    async def create_checkpoint(self, conversation_id: str, step_id: str, state_snapshot: Dict[str, Any]) -> str:
        """Create a checkpoint for rollback capability"""
        await self.initialize()
        
        checkpoint_id = f"{conversation_id}_{step_id}_{int(datetime.now().timestamp())}"
        
        async with aiosqlite.connect(self.db_path, timeout=self.timeout) as db:
            await db.execute(f"""
                INSERT INTO {self.checkpoints_table}
                (checkpoint_id, conversation_id, step_id, state_snapshot)
                VALUES (?, ?, ?, ?)
            """, (
                checkpoint_id,
                conversation_id,
                step_id,
                json.dumps(state_snapshot)
            ))
            await db.commit()
            
        return checkpoint_id
    
    async def rollback_to_checkpoint(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """Rollback to a specific checkpoint"""
        await self.initialize()
        
        async with aiosqlite.connect(self.db_path, timeout=self.timeout) as db:
            async with db.execute(f"""
                SELECT state_snapshot FROM {self.checkpoints_table}
                WHERE checkpoint_id = ?
            """, (checkpoint_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return json.loads(row[0])
                return None
    
    async def cleanup_expired_data(self):
        """Clean up expired conversations, steps, and checkpoints"""
        await self.initialize()
        
        now = datetime.now()
        conversation_cutoff = now - timedelta(seconds=self.conversation_ttl)
        checkpoint_cutoff = now - timedelta(seconds=self.checkpoint_ttl)
        session_cutoff = now - timedelta(seconds=self.session_ttl)
        
        async with aiosqlite.connect(self.db_path, timeout=self.timeout) as db:
            # Clean up old conversations
            await db.execute(f"""
                DELETE FROM {self.conversations_table}
                WHERE updated_at < ?
            """, (conversation_cutoff,))
            
            # Clean up old checkpoints
            await db.execute(f"""
                DELETE FROM {self.checkpoints_table}
                WHERE created_at < ?
            """, (checkpoint_cutoff,))
            
            # Clean up old sessions
            await db.execute(f"""
                DELETE FROM {self.sessions_table}
                WHERE last_activity < ?
            """, (session_cutoff,))
            
            await db.commit()
```

#### 6. Integration with ConversationOrchestrator

Update the orchestrator to use SQLite persistence:

```python
# In workflow_orchestrator.py

from .persistence.sqlite_backend import SQLiteWorkflowPersistence

class ConversationOrchestrator:
    def __init__(self, memory_manager=None, persistence_config=None):
        self.memory_manager = memory_manager
        
        # Initialize persistence backend based on configuration
        if persistence_config:
            backend = persistence_config.get('backend', 'memory')
            
            if backend == 'sqlite':
                sqlite_config = persistence_config.get('sqlite', {})
                self.persistence = SQLiteWorkflowPersistence(sqlite_config)
            elif backend == 'redis':
                # Initialize Redis persistence
                pass
            elif backend == 'file':
                # Initialize file persistence
                pass
            else:
                self.persistence = None
        else:
            self.persistence = None
    
    async def start_conversation(self, flow_id: str, session_id: str, initial_message: str):
        """Start conversation with persistence"""
        # Create conversation state
        conversation_state = {
            'conversation_id': f"{session_id}_{flow_id}_{int(time.time())}",
            'session_id': session_id,
            'flow_id': flow_id,
            'status': 'active',
            'current_step': self.registered_flows[flow_id].start_step,
            'step_history': [],
            'user_data': {},
            'created_at': datetime.now().isoformat()
        }
        
        # Save initial state
        if self.persistence:
            await self.persistence.save_conversation_state(
                conversation_state['conversation_id'], 
                conversation_state
            )
        
        return conversation_state['conversation_id'], {'success': True, 'state': conversation_state}
```

## Complete Examples

### 🏢 E-Commerce Workflow Example

```python
#!/usr/bin/env python3
"""
Complete E-Commerce Workflow System with SQLite Persistence
"""

import asyncio
from typing import Dict
from ambivo_agents import AssistantAgent, DatabaseAgent
from ambivo_agents.core.workflow_orchestrator import (
    ConversationOrchestrator,
    ConversationStep,
    ConversationFlow,
    ConversationPattern
)
from ambivo_agents.config.loader import load_config

class ECommerceWorkflowSystem:
    """Complete e-commerce customer service workflow"""
    
    def __init__(self):
        # Load configuration including persistence settings
        self.config = load_config()
        
        # 1. Create specialized agents
        self.agents = self._create_agents()
        
        # 2. Create orchestrator with SQLite persistence
        self.orchestrator = self._create_orchestrator()
        
        # 3. Build comprehensive workflows
        self.workflows = self._create_workflows()
        
        # 4. Register all workflows
        self._register_workflows()
        
        # 5. Session management
        self.active_sessions: Dict[str, str] = {}
    
    def _create_agents(self) -> Dict[str, Any]:
        """Create e-commerce specialized agents"""
        return {
            'customer_service': AssistantAgent.create_simple(
                user_id="cs_representative",
                system_message="""You are a professional e-commerce customer service representative.
                
                Your expertise:
                - Order management and tracking
                - Product information and recommendations
                - Returns and refunds processing
                - Account and billing support
                - Shipping and delivery assistance
                
                Communication style: Friendly, efficient, solution-oriented.
                Always prioritize customer satisfaction."""
            ),
            
            'product_specialist': AssistantAgent.create_simple(
                user_id="product_expert",
                system_message="""You are a product specialist with deep knowledge of our catalog.
                
                Your role:
                - Detailed product information and specifications
                - Product comparisons and recommendations
                - Inventory and availability checking
                - Technical support for products
                - Upselling and cross-selling when appropriate
                
                Focus: Helping customers find exactly what they need."""
            ),
            
            'order_system': DatabaseAgent.create_simple(
                user_id="order_database"
            ),
            
            'inventory_manager': AssistantAgent.create_simple(
                user_id="inventory_specialist",
                system_message="""You manage inventory, shipping, and logistics.
                
                Your responsibilities:
                - Real-time inventory levels
                - Shipping options and costs
                - Delivery time estimates
                - Tracking information
                - Warehouse and fulfillment coordination
                
                Priority: Accurate, up-to-date logistics information."""
            )
        }
    
    def _create_orchestrator(self) -> ConversationOrchestrator:
        """Create orchestrator with SQLite persistence"""
        persistence_config = self.config.get('workflow_persistence', {})
        
        return ConversationOrchestrator(
            memory_manager=self.agents['order_system'].memory,
            persistence_config=persistence_config
        )
    
    def _create_workflows(self) -> Dict[str, ConversationFlow]:
        """Create all e-commerce workflows"""
        return {
            'customer_support': self._create_customer_support_workflow(),
            'product_inquiry': self._create_product_inquiry_workflow(),
            'order_tracking': self._create_order_tracking_workflow(),
            'returns_refunds': self._create_returns_workflow()
        }
    
    def _create_customer_support_workflow(self) -> ConversationFlow:
        """Main customer support workflow"""
        steps = [
            ConversationStep(
                step_id="welcome",
                step_type="agent_response",
                agent=self.agents['customer_service'],
                prompt="Welcome the customer and ask how you can help them today.",
                next_steps=["identify_issue"]
            ),
            
            ConversationStep(
                step_id="identify_issue",
                step_type="user_input",
                prompt="What can I help you with today?",
                input_schema={
                    'type': 'choice',
                    'options': [
                        'Order status or tracking',
                        'Product questions',
                        'Returns or refunds',
                        'Account or billing',
                        'Technical support',
                        'Other inquiry'
                    ],
                    'required': True
                },
                next_steps=["route_to_specialist"]
            ),
            
            ConversationStep(
                step_id="route_to_specialist",
                step_type="agent_response",
                agent=self.agents['customer_service'],
                prompt="Based on the customer's selection, route them to appropriate specialist workflow.",
                next_steps=["handle_inquiry"],
                conditional_logic={
                    'condition': 'issue_type',
                    'order_tracking': 'order_tracking_flow',
                    'product_questions': 'product_inquiry_flow',
                    'returns_refunds': 'returns_flow',
                    'default': 'handle_inquiry'
                }
            ),
            
            ConversationStep(
                step_id="handle_inquiry",
                step_type="agent_response",
                agent=self.agents['customer_service'],
                prompt="Handle the customer's inquiry comprehensively and ask if they need additional help.",
                next_steps=["satisfaction_check"]
            ),
            
            ConversationStep(
                step_id="satisfaction_check",
                step_type="user_input",
                prompt="Is there anything else I can help you with today?",
                input_schema={
                    'type': 'choice',
                    'options': ['No, that\'s everything', 'Yes, I have another question'],
                    'required': True
                },
                next_steps=["completion", "identify_issue"],
                conditional_logic={
                    'condition': 'user_choice',
                    'another_question': 'identify_issue',
                    'default': 'completion'
                }
            ),
            
            ConversationStep(
                step_id="completion",
                step_type="agent_response",
                agent=self.agents['customer_service'],
                prompt="Thank the customer and provide follow-up information.",
                next_steps=["end"]
            )
        ]
        
        return ConversationFlow(
            flow_id="customer_support",
            name="Customer Support Workflow",
            description="Main customer service workflow with specialist routing",
            pattern=ConversationPattern.STEP_BY_STEP_PROCESS,
            steps=steps,
            start_step="welcome",
            end_steps=["completion"],
            settings={
                'enable_rollback': True,
                'auto_checkpoint': True,
                'checkpoint_interval': 60,
                'interaction_timeout': 900,  # 15 minutes
                'persist_state': True
            }
        )
    
    # Additional workflow creation methods...
    
    def _register_workflows(self):
        """Register all workflows with the orchestrator"""
        for workflow_id, workflow in self.workflows.items():
            self.orchestrator.registered_flows[workflow_id] = workflow
    
    async def start_customer_session(self, session_id: str = None, issue_type: str = "customer_support"):
        """Start a customer service session"""
        if not session_id:
            session_id = f"ecommerce_session_{int(time.time())}"
        
        execution_id, result = await self.orchestrator.start_conversation(
            flow_id=issue_type,
            session_id=session_id,
            initial_message="Customer service session started"
        )
        
        self.active_sessions[session_id] = execution_id
        return session_id, execution_id, result
    
    async def cleanup(self):
        """Cleanup all system resources"""
        for agent in self.agents.values():
            await agent.cleanup_session()

# Usage example
async def main():
    ecommerce_system = ECommerceWorkflowSystem()
    
    try:
        session_id, execution_id, result = await ecommerce_system.start_customer_session()
        print(f"Started e-commerce session: {session_id}")
        print(f"Execution ID: {execution_id}")
        print(f"Result: {result}")
        
        # The workflow will now persist state to SQLite automatically
        # Users can resume sessions, rollback to checkpoints, etc.
        
    finally:
        await ecommerce_system.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
```

## Best Practices

### 🎯 Agent Design Best Practices

1. **Single Responsibility**: Each agent should have one clear role
2. **Clear System Messages**: Define agent behavior explicitly
3. **Appropriate Agent Types**: Use DatabaseAgent for data operations, AssistantAgent for conversations
4. **Naming Conventions**: Use descriptive names that reflect the agent's purpose

### 🎛️ Orchestrator Best Practices

1. **Shared Memory**: Use shared memory when agents need to collaborate
2. **Persistence Configuration**: Always configure persistence for production systems
3. **Error Handling**: Implement comprehensive error recovery
4. **Resource Management**: Set appropriate timeouts and limits

### 🔄 Workflow Design Best Practices

1. **Step Granularity**: Each step should accomplish one clear objective
2. **User Experience**: Design for intuitive user interaction
3. **Error Recovery**: Include rollback and retry capabilities
4. **State Management**: Preserve important data at each step
5. **Performance**: Use lazy loading and caching where appropriate

### 📊 State Persistence Best Practices

1. **Backend Selection**: Choose the right persistence backend for your scale
2. **Retention Policies**: Set appropriate data retention periods
3. **Security**: Encrypt sensitive data and use proper access controls
4. **Monitoring**: Implement logging and monitoring for persistence operations
5. **Backup Strategy**: Regular backups of workflow state data

This comprehensive guide provides everything needed to build robust, production-ready workflows with the ambivo_agents library!