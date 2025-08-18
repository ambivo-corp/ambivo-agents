# Skill Assignment System - Developer Summary

## Overview
The **Skill Assignment System** allows AssistantAgent and ModeratorAgent to be "assigned" external capabilities (APIs, databases, knowledge bases) and intelligently use them based on user intent.

## Key Concept
Instead of manually routing to specialized agents, you **assign skills** to general agents. They automatically detect when to use these skills and handle the technical details internally.

## Quick Example
```python
from ambivo_agents import AssistantAgent

# Create agent and assign API skill
assistant = AssistantAgent.create_simple(user_id="user123")
await assistant.assign_api_skill(
    api_spec_path="/path/to/openapi.yaml",
    base_url="https://api.example.com/v1",
    api_token="your-token"
)

# Natural language requests now work automatically!
response = await assistant.chat("create a lead for John Doe")
# Agent internally: detects intent → spawns APIAgent → makes API call → returns natural response
```

## Available Skill Types

### 1. API Skills
```python
await agent.assign_api_skill(
    api_spec_path="path/to/openapi.yaml",  # OpenAPI/Swagger spec
    base_url="https://api.example.com",    # API base URL
    api_token="your-token",                # Auth token
    skill_name="my_api"                    # Optional name
)
```
**Triggers:** "create lead", "send email", "list contacts", "call api", etc.

### 2. Database Skills  
```python
await agent.assign_database_skill(
    connection_string="postgresql://user:pass@host:5432/db",
    skill_name="main_db",
    description="Customer database"
)
```
**Triggers:** "query database", "show data", "recent sales", "count records", etc.

### 3. Knowledge Base Skills
```python
await agent.assign_kb_skill(
    documents_path="/path/to/docs/",
    collection_name="company_docs",
    skill_name="knowledge"
)
```
**Triggers:** "what do docs say", "search documentation", "company policy", etc.

## How It Works

1. **Intent Detection**: Agent analyzes user message for skill-related keywords
2. **Skill Routing**: If match found, agent internally spawns appropriate specialized agent
3. **Execution**: Specialized agent (APIAgent, DatabaseAgent, etc.) handles the request
4. **Translation**: Technical response is converted to natural language
5. **Fallback**: If no skills match, normal agent behavior continues

## Agent Priority

### AssistantAgent
Skills are checked **before** normal conversation processing:
```
User Message → Check Skills → Use Skill OR → Normal Conversation
```

### ModeratorAgent  
Skills take **priority over agent routing**:
```
User Message → Check Skills → Use Skill OR → Normal Agent Routing
```

## Skill Management
```python
# List assigned skills
skills = agent.list_assigned_skills()
# Returns: {'api_skills': ['api1'], 'database_skills': ['db1'], 'kb_skills': [], 'total_skills': 2}

# Check agent capabilities
status = agent.get_agent_status()
print(status['capabilities'])  # Includes skill assignment features
print(status['assigned_skills'])  # Details of assigned skills
```

## Use Cases

**✅ Perfect For:**
- Custom API integrations with conversational interface
- Database access through natural language
- Document search with chat interface
- Adding external capabilities to existing agents

**❌ Not Ideal For:**
- Simple one-off API calls (use APIAgent directly)
- Complex multi-step workflows (use ModeratorAgent routing)
- When you need full control over agent selection

## Implementation Details

- **Dynamic Agent Creation**: Specialized agents are created on-demand and cached
- **Session Context Sharing**: All skill agents share the same session context
- **Error Handling**: Skill failures fall back to normal agent behavior
- **Memory Efficiency**: Skill agents are cleaned up with the main agent
- **Natural Language Processing**: Responses are automatically made conversational

## Migration Path

**From Direct Agent Usage:**
```python
# Old way
api_agent = APIAgent.create_simple(user_id="user")
response = await api_agent.chat("create lead...")

# New way  
assistant = AssistantAgent.create_simple(user_id="user")
await assistant.assign_api_skill(api_spec_path, base_url, token)
response = await assistant.chat("create lead...")  # Same result, more natural
```

**From ModeratorAgent Routing:**
```python
# Old way - relies on ModeratorAgent's built-in routing
moderator = ModeratorAgent.create_simple(user_id="user")
response = await moderator.chat("call the API")  # May or may not route to APIAgent

# New way - explicit skill assignment takes priority
moderator = ModeratorAgent.create_simple(user_id="user") 
await moderator.assign_api_skill(api_spec_path, base_url, token)
response = await moderator.chat("call the API")  # Guaranteed to use assigned API skill
```

The skill assignment system provides a **middle ground** between direct agent usage (too technical) and generic routing (too unpredictable), giving you **controlled, predictable access** to specialized capabilities through **natural language interfaces**.