# ambivo_agents/agents/analytics.py
"""
Analytics Agent with DuckDB integration for data analysis and visualization recommendations.
This agent ingests CSV/XLS files, analyzes data, and provides text-based chart recommendations.
"""

import asyncio
import json
import logging
import os
import re
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple, Union

from ..core.base import (
    AgentMessage,
    AgentRole,
    BaseAgent,
    ExecutionContext,
    MessageType,
    StreamChunk,
    StreamSubType,
)
from ..core.history import BaseAgentHistoryMixin
from ..config.loader import get_config_section


class AnalyticsAgent(BaseAgent, BaseAgentHistoryMixin):
    """
    Analytics Agent that processes CSV/XLS files using DuckDB in Docker environment.
    Provides data analysis, schema exploration, and text-based chart recommendations.
    """

    def __init__(
        self,
        agent_id: str = None,
        memory_manager=None,
        llm_service=None,
        system_message: str = None,
        auto_configure: bool = True,
        **kwargs,
    ):
        if agent_id is None:
            agent_id = f"analytics_{str(uuid.uuid4())[:8]}"

        # Default system message for Analytics Agent
        if system_message is None:
            system_message = self._get_default_system_message()

        super().__init__(
            agent_id=agent_id,
            role=AgentRole.ANALYST,
            memory_manager=memory_manager,
            llm_service=llm_service,
            name="Analytics Agent",
            description="Data analysis agent with DuckDB integration and visualization recommendations",
            system_message=system_message,
            auto_configure=auto_configure,
            **kwargs,
        )

        # Initialize history mixin
        self.setup_history_mixin()
        
        # Load configuration
        self.config = self._load_analytics_config() if auto_configure else {}
        
        # Analytics agent specific settings
        self.docker_image = self.config.get("docker_image", "sgosain/amb-ubuntu-python-public-pod")
        self.input_dir = self.config.get("input_dir", "./examples")
        self.output_dir = self.config.get("output_dir", "./examples/analytics_output")
        self.current_dataset = None
        self.current_schema = None
        
        # Logging
        self.logger = logging.getLogger(f"AnalyticsAgent-{agent_id[:8]}")
        self.logger.info(f"Analytics Agent initialized with input_dir: {self.input_dir}")

    def _load_analytics_config(self) -> dict:
        """Load analytics configuration from agent_config.yaml"""
        try:
            return get_config_section("analytics") or {}
        except Exception as e:
            self.logger.warning(f"Failed to load analytics config: {e}")
            return {}

    def _get_default_system_message(self) -> str:
        """Get the default system message for the Analytics agent"""
        return """You are an intelligent Analytics Agent specialized in data analysis and visualization recommendations. Your capabilities include:

**Core Features:**
1. **Data Ingestion**: Load CSV and XLS files from local paths or URLs into in-memory DuckDB
2. **Schema Analysis**: Examine data structure, types, and relationships
3. **SQL Querying**: Execute SQL queries against loaded datasets (DuckDB SQL dialect)
4. **Natural Language Processing**: Convert English questions to SQL queries
5. **Visualization Recommendations**: Suggest appropriate charts with SQL and text-based rendering
6. **Data Insights**: Identify patterns, correlations, and anomalies in datasets

**Docker Execution:**
- ALL operations run in isolated Docker containers for security
- DuckDB is pre-installed in the container environment
- No additional dependencies required in requirements.txt
- Supports pandas, numpy, and common data analysis libraries

**Data Analysis Workflow:**
1. Ingest data from file path or URL
2. Analyze schema and data characteristics
3. Provide summary statistics and data quality insights
4. Recommend appropriate visualizations with SQL queries
5. Answer analytical questions using SQL or natural language

**Visualization Capabilities:**
- Generate text-based charts (ASCII art, simple tables)
- Provide SQL queries for chart data preparation
- Recommend chart types based on data characteristics:
  * Bar charts for categorical data
  * Line charts for time series
  * Scatter plots for correlations
  * Heatmaps for patterns
  * Distribution charts for statistical analysis

**SQL Query Support:**
- Full DuckDB SQL dialect support
- Aggregations, window functions, CTEs
- Data type conversions and cleaning
- Statistical functions and analysis
- Export results in various formats

**Text-Based Rendering:**
- Simple ASCII charts for quick visualization
- Formatted tables with alignment
- Statistical summaries and insights
- Pattern descriptions in plain text
- Markdown-compatible output for chat interfaces

**Usage Examples:**
- "Load data from /path/to/sales.csv and analyze it"
- "Show me the schema of the current dataset"
- "What are the top 10 products by revenue?"
- "Create a bar chart showing sales by region"
- "Find correlations between price and quantity"
- "Show monthly trends in the data"

**Security & Safety:**
- All code execution happens in Docker containers
- File access limited to provided paths
- No network access from container unless explicitly needed for URL loading
- Automatic cleanup of temporary files and containers

Always provide clear, actionable insights and explain your analysis process. Use text-based visualizations that work well in chat interfaces."""

    async def process_message(self, message: Union[str, AgentMessage], context: ExecutionContext = None, **kwargs) -> AgentMessage:
        """Process analytics requests and return response"""
        try:
            # Handle both string and AgentMessage inputs
            if hasattr(message, 'content'):
                message_text = message.content
                original_message = message
            else:
                message_text = str(message)
                original_message = AgentMessage(
                    id=str(uuid.uuid4()),
                    sender_id=context.user_id if context else self.context.user_id,
                    recipient_id=self.agent_id,
                    content=message_text,
                    message_type=MessageType.USER_INPUT,
                    session_id=context.session_id if context else self.context.session_id,
                    conversation_id=context.conversation_id if context else self.context.conversation_id
                )
            
            # Detect request type
            request_info = self._detect_request_type(message_text)
            
            # Route to appropriate handler
            response_content = ""
            if request_info["type"] == "data_loading":
                response_content = await self._handle_data_loading(request_info, message_text)
            elif request_info["type"] == "schema_exploration":
                response_content = await self._handle_schema_exploration(message)
            elif request_info["type"] == "sql_query":
                response_content = await self._handle_sql_query(request_info["query"])
            elif request_info["type"] == "visualization":
                response_content = await self._handle_visualization(message, request_info["chart_type"])
            elif request_info["type"] == "natural_language_query":
                response_content = await self._handle_natural_language_query(request_info["query"])
            else:
                response_content = "Please specify what you'd like to analyze. I can load data files, explore schemas, run SQL queries, or create visualizations."
            
            # Return AgentMessage object
            return AgentMessage(
                id=str(uuid.uuid4()),
                sender_id=self.agent_id,
                recipient_id=original_message.sender_id,
                content=response_content,
                message_type=MessageType.AGENT_RESPONSE,
                session_id=original_message.session_id,
                conversation_id=original_message.conversation_id,
                metadata={
                    "agent_type": "analytics",
                    "request_type": request_info["type"],
                    "processing_time": time.time()
                }
            )
                
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")
            error_content = f"❌ Analytics error: {str(e)}"
            
            # Return error as AgentMessage
            return AgentMessage(
                id=str(uuid.uuid4()),
                sender_id=self.agent_id,
                recipient_id=context.user_id if context else self.context.user_id,
                content=error_content,
                message_type=MessageType.ERROR,
                session_id=context.session_id if context else self.context.session_id,
                conversation_id=context.conversation_id if context else self.context.conversation_id,
                metadata={
                    "agent_type": "analytics",
                    "error": True,
                    "error_message": str(e)
                }
            )

    async def process_message_stream(self, message: str, context: ExecutionContext = None, **kwargs) -> AsyncIterator[StreamChunk]:
        """Process analytics requests with streaming response"""
        try:
            # Handle both string and AgentMessage inputs
            if hasattr(message, 'content'):
                message_text = message.content
            else:
                message_text = str(message)
            
            # Detect request type
            request_info = self._detect_request_type(message_text)
            
            yield StreamChunk(
                text=f"🔍 **Analyzing request**: {request_info['type'].replace('_', ' ').title()}",
                sub_type=StreamSubType.STATUS
            )
            
            # Route to appropriate handler
            if request_info["type"] == "data_loading":
                async for chunk in self._handle_data_loading_stream(request_info, message):
                    yield chunk
            elif request_info["type"] == "schema_exploration":
                async for chunk in self._handle_schema_exploration_stream(message):
                    yield chunk
            elif request_info["type"] == "sql_query":
                async for chunk in self._handle_sql_query_stream(request_info["query"]):
                    yield chunk
            elif request_info["type"] == "visualization":
                async for chunk in self._handle_visualization_stream(message, request_info["chart_type"]):
                    yield chunk
            elif request_info["type"] == "natural_language_query":
                async for chunk in self._handle_natural_language_query_stream(request_info["query"]):
                    yield chunk
            else:
                yield StreamChunk(
                    text="Please specify what you'd like to analyze. I can load data files, explore schemas, run SQL queries, or create visualizations.",
                    sub_type=StreamSubType.CONTENT
                )
                
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")
            yield StreamChunk(
                text=f"❌ Analytics error: {str(e)}",
                sub_type=StreamSubType.ERROR
            )

    def _detect_request_type(self, message: str) -> dict:
        """Detect the type of analytics request"""
        message_lower = message.lower().strip()
        
        # Schema exploration requests
        if any(pattern in message_lower for pattern in [
            "schema", "structure", "columns", "show schema", "data types", "describe"
        ]):
            return {
                "type": "schema_exploration",
                "confidence": 0.9
            }
        
        # SQL or analytical queries
        if any(pattern in message_lower for pattern in [
            "top", "sales", "records", "query", "select", "where", "group by", 
            "count", "sum", "average", "maximum", "minimum", "what are"
        ]):
            return {
                "type": "natural_language_query", 
                "query": message,
                "confidence": 0.8
            }
        
        # Data loading requests
        if any(pattern in message_lower for pattern in [
            "load", "import", "read", "ingest", "upload", "analyze file", "process file"
        ]):
            # Extract file path
            file_path = self._extract_file_path(message)
            return {
                "type": "data_loading",
                "file_path": file_path,
                "confidence": 0.9 if file_path else 0.7
            }
        
        # Default to data loading for now
        return {
            "type": "data_loading",
            "file_path": None,
            "confidence": 0.5
        }
    
    def _extract_file_path(self, message: str) -> str:
        """Extract file path from message"""
        import re
        import os
        
        patterns = [
            r'([^\s]+\.csv)',
            r'([^\s]+\.xlsx?)',
            r'from\s+([^\s]+)',
            r'load\s+([^\s]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                file_path = match.group(1)
                
                # If it's not an absolute path, try to resolve it relative to input_dir
                if not os.path.isabs(file_path):
                    resolved_path = os.path.join(self.input_dir, file_path)
                    if os.path.exists(resolved_path):
                        return resolved_path
                    
                    # Also try the original path in case it's relative to current dir
                    if os.path.exists(file_path):
                        return file_path
                else:
                    # Absolute path - check if it exists
                    if os.path.exists(file_path):
                        return file_path
                
                # Return the path even if it doesn't exist (let the error handling deal with it)
                return file_path
        
        return ""
    
    async def _handle_data_loading(self, request_info: dict, message: str) -> str:
        """Handle data loading requests with actual data analysis"""
        import os
        
        file_path = request_info.get("file_path")
        
        if not file_path:
            # List available files in input directory to help user
            try:
                available_files = [f for f in os.listdir(self.input_dir) 
                                 if f.endswith(('.csv', '.xlsx', '.xls'))]
                if available_files:
                    files_list = '\n'.join([f"  - {f}" for f in available_files])
                    return f"❌ No file path found. Available files in `{self.input_dir}`:\n{files_list}\n\nPlease specify: `load data from filename.csv`"
                else:
                    return f"❌ No file path found and no data files in `{self.input_dir}`. Please specify a CSV or XLS file path."
            except Exception:
                return "❌ No file path found. Please specify a CSV or XLS file path."

        # Check if file exists
        if not os.path.exists(file_path):
            return f"❌ File not found: `{file_path}`\n\nPlease check the file path and try again."
        
        try:
            # Load and analyze the data
            analysis_result = await self._load_and_analyze_data(file_path)
            
            if analysis_result['success']:
                self.current_dataset = analysis_result['data']
                self.current_schema = analysis_result['schema']
                
                # Generate widget recommendations
                recommendations = self._generate_widget_recommendations(
                    analysis_result['field_info'], 
                    analysis_result['data']
                )
                
                return f"""✅ **Data Loaded and Analyzed Successfully**

**File**: `{file_path}`
**Rows**: {analysis_result['row_count']:,}
**Columns**: {analysis_result['column_count']}
**Size**: {analysis_result['file_size_mb']:.2f} MB

📊 **Data Overview**:
{analysis_result['summary']}

🎯 **Recommended Visualizations**:
{self._format_recommendations(recommendations[:5])}

Ask me to:
- `show schema` - View detailed column information
- `show sample data` - Display first few rows
- `what are the top sales?` - Run natural language queries
- `create bar chart of sales by region` - Generate specific visualizations

Ready for analysis! 🚀"""
                
            else:
                return f"❌ Error loading data: {analysis_result['error']}"
                
        except Exception as e:
            self.logger.error(f"Error in data loading: {e}")
            return f"❌ Error analyzing data: {str(e)}"

    async def _handle_schema_exploration(self, message) -> str:
        """Handle schema exploration requests"""
        if not self.current_schema:
            return """📋 **Schema Analysis**

❌ No dataset loaded. Please load data first using:
`load data from filename.csv`

Then I can show you detailed schema information."""

        schema_lines = ["📋 **Dataset Schema Analysis**\n"]
        
        for col_name, col_info in self.current_schema.items():
            field_type = col_info.get('type', 'unknown')
            semantic_type = col_info.get('semantic_type', 'general')
            unique_ratio = col_info.get('unique_ratio', 0)
            non_null_count = col_info.get('non_null_count', 0) 
            total_count = col_info.get('total_count', 0)
            
            # Add type emojis
            type_emoji = {
                'integer': '🔢', 'float': '📊', 'string': '📝', 
                'boolean': '✅', 'datetime': '📅'
            }.get(field_type, '❓')
            
            # Data quality indicator
            completeness = (non_null_count / total_count * 100) if total_count > 0 else 0
            quality_emoji = "🟢" if completeness >= 90 else "🟡" if completeness >= 70 else "🔴"
            
            # Semantic type indicator
            semantic_emoji = {
                'price': '💰', 'datetime': '🕐', 'identifier': '🆔', 
                'latitude': '🌍', 'longitude': '🌍', 'address': '📍'
            }.get(semantic_type, '')
            
            schema_lines.append(
                f"**{col_name}** {type_emoji} {semantic_emoji}"
            )
            schema_lines.append(
                f"  Type: {field_type} | Completeness: {completeness:.1f}% {quality_emoji}"
            )
            schema_lines.append(
                f"  Unique Values: {col_info.get('unique_count', 0)} ({unique_ratio:.1%})"
            )
            
            if semantic_type != 'general':
                schema_lines.append(f"  Semantic: {semantic_type}")
            
            schema_lines.append("")  # Blank line between columns
        
        # Add summary insights
        schema_lines.append("🎯 **Key Insights**:")
        
        # Count meaningful metrics
        meaningful_metrics = [col for col in self.current_schema.keys() 
                            if self._is_meaningful_metric(col, self.current_schema)]
        if meaningful_metrics:
            schema_lines.append(f"• **Measurable Fields**: {', '.join(meaningful_metrics)}")
        
        # Count good categoricals
        good_categoricals = [col for col, info in self.current_schema.items() 
                           if info.get('type') in ['string', 'boolean'] 
                           and info.get('unique_ratio', 1.0) < 0.5]
        if good_categoricals:
            schema_lines.append(f"• **Grouping Fields**: {', '.join(good_categoricals)}")
        
        # Date fields
        date_fields = [col for col, info in self.current_schema.items() 
                      if info.get('semantic_type') == 'datetime' or 'date' in col.lower()]
        if date_fields:
            schema_lines.append(f"• **Time Fields**: {', '.join(date_fields)}")
        
        return '\n'.join(schema_lines)

    async def _handle_natural_language_query(self, query: str) -> str:
        """Handle natural language analytical queries"""
        if not self.current_dataset or not self.current_schema:
            return f"""📊 **Query Analysis**

❌ No dataset loaded. Please load data first using:
`load data from filename.csv`

Then I can process your query: "{query}" """

        try:
            # Simple query processing for common patterns
            query_lower = query.lower()
            
            # Handle "top N" queries
            if 'top' in query_lower and any(field in query_lower for field in ['sales', 'revenue', 'salary', 'price', 'cost']):
                return self._handle_top_query(query)
            
            # Handle count queries
            elif 'count' in query_lower or 'how many' in query_lower:
                return self._handle_count_query(query)
            
            # Handle average queries
            elif 'average' in query_lower or 'mean' in query_lower:
                return self._handle_average_query(query)
            
            # Handle summary statistics
            elif 'summary' in query_lower or 'statistics' in query_lower:
                return self._handle_summary_query(query)
            
            else:
                # Generic response with helpful suggestions
                meaningful_metrics = [col for col in self.current_schema.keys() 
                                    if self._is_meaningful_metric(col, self.current_schema)]
                
                suggestions = []
                if meaningful_metrics:
                    suggestions.append(f"• `top 10 {meaningful_metrics[0]}` - Find highest values")
                    suggestions.append(f"• `average {meaningful_metrics[0]}` - Calculate mean")
                
                categorical_fields = [col for col, info in self.current_schema.items() 
                                    if info.get('type') in ['string', 'boolean'] 
                                    and info.get('unique_ratio', 1.0) < 0.5]
                
                if categorical_fields:
                    suggestions.append(f"• `count by {categorical_fields[0]}` - Group counts")
                
                return f"""📊 **Query Processing**

**Your query**: "{query}"

I understand you want to analyze the data, but I need a more specific query pattern.

**Try these examples**:
{chr(10).join(suggestions) if suggestions else "• Load data first to see available query examples"}

**Available columns**: {', '.join(list(self.current_schema.keys())[:6])}{"..." if len(self.current_schema) > 6 else ""}"""
        
        except Exception as e:
            return f"""📊 **Query Error**

❌ Error processing query: {str(e)}

Please try a simpler query pattern or load data first."""

    async def _execute_query_in_docker(self, query_type: str, query: str, params: dict = None) -> str:
        """Execute analytical queries in Docker container"""
        try:
            # Generate query code based on type
            if query_type == "top":
                code = self._generate_top_query_code(query, params)
            elif query_type == "count":
                code = self._generate_count_query_code(query, params)
            elif query_type == "average":
                code = self._generate_average_query_code(query, params)
            elif query_type == "summary":
                code = self._generate_summary_query_code(query, params)
            else:
                return "❌ Unknown query type"
            
            # Execute in Docker
            from ..executors.docker_executor import DockerCodeExecutor
            executor = DockerCodeExecutor()
            
            # Prepare data for Docker
            data_json = json.dumps({
                "data": self.current_dataset,
                "schema": self.current_schema
            })
            
            files = {"data.json": data_json}
            result = executor.execute_code(code, language="python", files=files)
            
            if result.get("success"):
                # Extract JSON from output
                output = result["output"]
                json_start = output.find('{')
                if json_start != -1:
                    json_output = output[json_start:]
                    query_result = json.loads(json_output)
                    return query_result.get("result", "No result returned")
                else:
                    # If no JSON, return raw output
                    return output.strip()
            else:
                return f"❌ Docker execution error: {result.get('error', 'Unknown error')}"
                
        except Exception as e:
            return f"❌ Error executing query in Docker: {str(e)}"

    def _execute_query_sync(self, query_type: str, query: str, params: dict = None) -> str:
        """Execute analytical queries in Docker container synchronously"""
        try:
            # Generate query code based on type
            if query_type == "top":
                code = self._generate_top_query_code(query, params)
            elif query_type == "count":
                code = self._generate_count_query_code(query, params)
            elif query_type == "average":
                code = self._generate_average_query_code(query, params)
            elif query_type == "summary":
                code = self._generate_summary_query_code(query, params)
            else:
                return "❌ Unknown query type"
            
            # Execute in Docker
            from ..executors.docker_executor import DockerCodeExecutor
            executor = DockerCodeExecutor()
            
            # Prepare data for Docker
            data_json = json.dumps({
                "data": self.current_dataset,
                "schema": self.current_schema
            })
            
            files = {"data.json": data_json}
            result = executor.execute_code(code, language="python", files=files)
            
            if result.get("success"):
                # Extract JSON from output
                output = result["output"]
                json_start = output.find('{')
                if json_start != -1:
                    json_output = output[json_start:]
                    query_result = json.loads(json_output)
                    return query_result.get("result", "No result returned")
                else:
                    # If no JSON, return raw output
                    return output.strip()
            else:
                return f"❌ Docker execution error: {result.get('error', 'Unknown error')}"
                
        except Exception as e:
            return f"❌ Error executing query in Docker: {str(e)}"

    def _handle_top_query(self, query: str) -> str:
        """Handle top N queries using Docker execution"""
        try:
            # Find numeric fields that could be sorted
            meaningful_metrics = [col for col in self.current_schema.keys() 
                                if self._is_meaningful_metric(col, self.current_schema)]
            
            if not meaningful_metrics:
                return "❌ No sortable numeric fields found in the dataset."
            
            # Use the first meaningful metric
            sort_field = meaningful_metrics[0]
            
            # Extract top N (default to 5)
            import re
            match = re.search(r'top\s+(\d+)', query.lower())
            n = int(match.group(1)) if match else 5
            
            # Execute synchronously for now to avoid async issues
            result = self._execute_query_sync("top", query, {
                "sort_field": sort_field,
                "n": n
            })
            
            return result
            
        except Exception as e:
            return f"❌ Error processing top query: {str(e)}"

    def _handle_count_query(self, query: str) -> str:
        """Handle count queries using Docker execution"""
        try:
            result = self._execute_query_sync("count", query, {})
            return result
            
        except Exception as e:
            return f"❌ Error processing count query: {str(e)}"

    def _handle_average_query(self, query: str) -> str:
        """Handle average/mean queries using Docker execution"""
        try:
            result = self._execute_query_sync("average", query, {})
            return result
            
        except Exception as e:
            return f"❌ Error processing average query: {str(e)}"

    def _handle_summary_query(self, query: str) -> str:
        """Handle summary statistics queries using Docker execution"""
        try:
            result = self._execute_query_sync("summary", query, {})
            return result
            
        except Exception as e:
            return f"❌ Error processing summary query: {str(e)}"

    async def _handle_sql_query(self, query: str) -> str:
        """Handle direct SQL queries"""
        return f"""🔍 **SQL Query Execution**

**Query**: `{query}`

*This would execute the SQL query against the loaded dataset and return formatted results.*

*Note: Full implementation requires loading a dataset first.*"""

    async def _handle_visualization(self, message, chart_type: str) -> str:
        """Handle visualization requests"""
        return f"""📈 **Visualization Generation**

**Chart Type**: {chart_type}
**Request**: "{message}"

*This would generate:*
- Appropriate SQL query for chart data
- Text-based visualization (ASCII art)
- Chart recommendations
- Data insights

*Note: Full implementation requires loading a dataset first.*"""

    async def _load_and_analyze_data(self, file_path: str) -> dict:
        """Load and analyze data file using Docker execution"""
        try:
            # Read the file into memory and pass as file content
            import os
            
            # Read file as binary for XLS/XLSX files
            if file_path.endswith(('.xlsx', '.xls')):
                # For Excel files, we need to copy them to Docker workspace
                filename = os.path.basename(file_path)
                analysis_code = self._generate_analysis_code_for_binary_file(filename)
                
                # Read the file as binary content
                with open(file_path, 'rb') as f:
                    file_content = f.read()
                
                # Use DockerCodeExecutor with binary file support
                from ..executors.docker_executor import DockerCodeExecutor
                import tempfile
                import shutil
                
                # Create temp directory and copy file
                with tempfile.TemporaryDirectory() as temp_dir:
                    # Copy the Excel file to temp directory
                    temp_file_path = os.path.join(temp_dir, filename)
                    shutil.copy2(file_path, temp_file_path)
                    
                    # Write analysis code to temp directory
                    code_path = os.path.join(temp_dir, "analysis.py")
                    with open(code_path, 'w') as f:
                        f.write(analysis_code)
                    
                    # Execute using Docker with volume mounting
                    executor = DockerCodeExecutor()
                    
                    try:
                        import docker
                        client = executor.docker_client
                        
                        # Mount the temp directory containing both code and data file
                        volumes = {temp_dir: {"bind": "/workspace", "mode": "rw"}}
                        
                        container = client.containers.run(
                            image=executor.default_image,
                            command=["python", "/workspace/analysis.py"],
                            volumes=volumes,
                            working_dir="/workspace",
                            mem_limit=executor.memory_limit,
                            network_disabled=True,
                            remove=True,
                            stdout=True,
                            stderr=True,
                        )
                        
                        output = container.decode("utf-8") if isinstance(container, bytes) else str(container)
                        result = {"success": True, "output": output}
                        
                    except Exception as e:
                        self.logger.error(f"Docker execution error: {e}")
                        result = {"success": False, "error": str(e)}
                        
            else:
                # For CSV files, use the existing text-based approach
                analysis_code = self._generate_analysis_code_for_text_file(file_path)
                
                from ..executors.docker_executor import DockerCodeExecutor
                executor = DockerCodeExecutor()
                
                # Read file content as text
                with open(file_path, 'r') as f:
                    file_content = f.read()
                
                filename = os.path.basename(file_path)
                files = {filename: file_content}
                
                result = executor.execute_code(analysis_code, language="python", files=files)
            
            if result.get("success"):
                try:
                    # Extract JSON from Docker output (may have jemalloc warnings)
                    output = result["output"]
                    
                    # Find the JSON part (starts with '{')
                    json_start = output.find('{')
                    if json_start != -1:
                        json_output = output[json_start:]
                        analysis_result = json.loads(json_output)
                        # Don't override the success flag from the analysis result
                        # The Docker execution succeeded, but the analysis inside might have failed
                        return analysis_result
                    else:
                        return {"success": False, "error": f"No JSON found in Docker output: {output[:500]}"}
                        
                except json.JSONDecodeError as e:
                    return {"success": False, "error": f"Failed to parse Docker output as JSON: {e}. Output was: {result['output'][:500]}"}
            else:
                return {"success": False, "error": result.get("error", "Docker execution failed")}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _generate_analysis_code_for_binary_file(self, filename: str) -> str:
        """Generate Python code for Excel file analysis with mounted volume"""
        return f'''
import pandas as pd
import json
import os
import warnings
warnings.filterwarnings('ignore')

try:
    # Read the Excel file from mounted volume
    file_path = "/workspace/{filename}"
    
    # Load data based on file extension
    if file_path.endswith('.xlsx'):
        df = pd.read_excel(file_path, engine='openpyxl')
    elif file_path.endswith('.xls'):
        # Try openpyxl first (works for some .xls files), then fall back to default
        try:
            df = pd.read_excel(file_path, engine='openpyxl')
        except Exception:
            try:
                # Try without specifying engine (pandas will choose)
                df = pd.read_excel(file_path)
            except Exception as e:
                raise ValueError(f"Cannot read XLS file (old Excel format): {{str(e)}}. Please convert your XLS file to XLSX format for compatibility. You can do this in Excel by opening the file and saving as 'Excel Workbook (.xlsx)'.")
    else:
        raise ValueError("Unsupported Excel format")
        
    # Basic statistics
    row_count = len(df)
    column_count = len(df.columns)
    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    
    # Analyze columns
    field_info = {{}}
    for col in df.columns:
        dtype = str(df[col].dtype)
        non_null_count = int(df[col].count())
        total_count = len(df)
        unique_count = int(df[col].nunique())
        
        # Map pandas dtypes to our field types
        if dtype.startswith('int'):
            field_type = 'integer'
        elif dtype.startswith('float'):
            field_type = 'float'
        elif dtype.startswith('bool'):
            field_type = 'boolean'
        elif dtype.startswith('datetime'):
            field_type = 'datetime'
        else:
            field_type = 'string'
        
        # Calculate unique ratio
        unique_ratio = unique_count / total_count if total_count > 0 else 0
        
        # Simple semantic type detection
        col_lower = col.lower()
        semantic_type = 'general'
        
        if any(pattern in col_lower for pattern in ['price', 'cost', 'amount', 'revenue', 'salary']):
            semantic_type = 'price'
        elif any(pattern in col_lower for pattern in ['date', 'time', 'created', 'updated']):
            semantic_type = 'datetime'
        elif any(pattern in col_lower for pattern in ['id', 'uuid', 'key']) or col_lower.endswith('_id'):
            semantic_type = 'identifier'
        
        field_info[col] = {{
            "type": field_type,
            "semantic_type": semantic_type,
            "unique_ratio": unique_ratio,
            "non_null_count": non_null_count,
            "total_count": total_count,
            "unique_count": unique_count
        }}
    
    # Generate summary
    type_counts = {{}}
    for col_info in field_info.values():
        col_type = col_info['type']
        type_counts[col_type] = type_counts.get(col_type, 0) + 1
    
    type_summary = ', '.join([f"{{count}} {{type_name}}" for type_name, count in type_counts.items()])
    
    # Find key columns
    numeric_cols = [col for col, info in field_info.items() 
                   if info['type'] in ['integer', 'float']]
    categorical_cols = [col for col, info in field_info.items() 
                      if info['type'] in ['string', 'boolean'] and info['unique_ratio'] < 0.5]
    
    summary_parts = [f"**Column Types**: {{type_summary}}"]
    if numeric_cols:
        summary_parts.append(f"**Numeric Fields**: {{', '.join(numeric_cols[:3])}}")
    if categorical_cols:
        summary_parts.append(f"**Categories**: {{', '.join(categorical_cols[:3])}}")
    
    summary = '\\n'.join(summary_parts)
    
    # Convert first 100 rows to list of dicts for recommendations
    sample_data = df.head(100).to_dict('records')
    
    # Output results
    result = {{
        "row_count": row_count,
        "column_count": column_count,
        "file_size_mb": file_size_mb,
        "schema": field_info,
        "field_info": field_info,
        "data": sample_data,
        "summary": summary,
        "success": True
    }}
    
    print(json.dumps(result, indent=2, default=str))
    
except Exception as e:
    print(json.dumps({{"error": str(e), "success": False}}, indent=2))
'''

    def _generate_analysis_code_for_text_file(self, file_path: str) -> str:
        """Generate Python code for CSV file analysis"""
        filename = os.path.basename(file_path)
        return f'''
import pandas as pd
import json
import warnings
warnings.filterwarnings('ignore')

try:
    # Read the CSV file
    df = pd.read_csv("{filename}")
        
    # Basic statistics
    row_count = len(df)
    column_count = len(df.columns)
    
    # Analyze columns
    field_info = {{}}
    for col in df.columns:
        dtype = str(df[col].dtype)
        non_null_count = int(df[col].count())
        total_count = len(df)
        unique_count = int(df[col].nunique())
        
        # Map pandas dtypes to our field types
        if dtype.startswith('int'):
            field_type = 'integer'
        elif dtype.startswith('float'):
            field_type = 'float'
        elif dtype.startswith('bool'):
            field_type = 'boolean'
        elif dtype.startswith('datetime'):
            field_type = 'datetime'
        else:
            field_type = 'string'
        
        # Calculate unique ratio
        unique_ratio = unique_count / total_count if total_count > 0 else 0
        
        # Simple semantic type detection
        col_lower = col.lower()
        semantic_type = 'general'
        
        if any(pattern in col_lower for pattern in ['price', 'cost', 'amount', 'revenue', 'salary']):
            semantic_type = 'price'
        elif any(pattern in col_lower for pattern in ['date', 'time', 'created', 'updated']):
            semantic_type = 'datetime'
        elif any(pattern in col_lower for pattern in ['id', 'uuid', 'key']) or col_lower.endswith('_id'):
            semantic_type = 'identifier'
        
        field_info[col] = {{
            "type": field_type,
            "semantic_type": semantic_type,
            "unique_ratio": unique_ratio,
            "non_null_count": non_null_count,
            "total_count": total_count,
            "unique_count": unique_count
        }}
    
    # Generate summary
    type_counts = {{}}
    for col_info in field_info.values():
        col_type = col_info['type']
        type_counts[col_type] = type_counts.get(col_type, 0) + 1
    
    type_summary = ', '.join([f"{{count}} {{type_name}}" for type_name, count in type_counts.items()])
    
    # Find key columns
    numeric_cols = [col for col, info in field_info.items() 
                   if info['type'] in ['integer', 'float']]
    categorical_cols = [col for col, info in field_info.items() 
                      if info['type'] in ['string', 'boolean'] and info['unique_ratio'] < 0.5]
    
    summary_parts = [f"**Column Types**: {{type_summary}}"]
    if numeric_cols:
        summary_parts.append(f"**Numeric Fields**: {{', '.join(numeric_cols[:3])}}")
    if categorical_cols:
        summary_parts.append(f"**Categories**: {{', '.join(categorical_cols[:3])}}")
    
    summary = '\\n'.join(summary_parts)
    
    # Convert first 100 rows to list of dicts for recommendations
    sample_data = df.head(100).to_dict('records')
    
    # Output results
    result = {{
        "row_count": row_count,
        "column_count": column_count,
        "file_size_mb": 0.1,  # Approximate for CSV
        "schema": field_info,
        "field_info": field_info,
        "data": sample_data,
        "summary": summary,
        "success": True
    }}
    
    print(json.dumps(result, indent=2, default=str))
    
except Exception as e:
    print(json.dumps({{"error": str(e), "success": False}}, indent=2))
'''

    def _generate_analysis_code_with_mount(self, file_path: str) -> str:
        """Generate Python code for data analysis with mounted volume (deprecated)"""
        filename = os.path.basename(file_path)
        
        return f'''
import pandas as pd
import json
import os
import warnings
warnings.filterwarnings('ignore')

try:
    # Read the data file from mounted volume
    file_path = "/workspace/{filename}"
    
    # Load data based on file extension
    if file_path.endswith('.csv'):
        df = pd.read_csv(file_path)
    elif file_path.endswith('.xlsx'):
        df = pd.read_excel(file_path, engine='openpyxl')
    elif file_path.endswith('.xls'):
        df = pd.read_excel(file_path, engine='xlrd')
    else:
        raise ValueError("Unsupported file format")
        
    # Basic statistics
    row_count = len(df)
    column_count = len(df.columns)
    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    
    # Analyze columns
    field_info = {{}}
    for col in df.columns:
        dtype = str(df[col].dtype)
        non_null_count = int(df[col].count())
        total_count = len(df)
        unique_count = int(df[col].nunique())
        
        # Map pandas dtypes to our field types
        if dtype.startswith('int'):
            field_type = 'integer'
        elif dtype.startswith('float'):
            field_type = 'float'
        elif dtype.startswith('bool'):
            field_type = 'boolean'
        elif dtype.startswith('datetime'):
            field_type = 'datetime'
        else:
            field_type = 'string'
        
        # Calculate unique ratio
        unique_ratio = unique_count / total_count if total_count > 0 else 0
        
        # Simple semantic type detection
        col_lower = col.lower()
        semantic_type = 'general'
        
        if any(pattern in col_lower for pattern in ['price', 'cost', 'amount', 'revenue', 'salary']):
            semantic_type = 'price'
        elif any(pattern in col_lower for pattern in ['date', 'time', 'created', 'updated']):
            semantic_type = 'datetime'
        elif any(pattern in col_lower for pattern in ['id', 'uuid', 'key']) or col_lower.endswith('_id'):
            semantic_type = 'identifier'
        
        field_info[col] = {{
            "type": field_type,
            "semantic_type": semantic_type,
            "unique_ratio": unique_ratio,
            "non_null_count": non_null_count,
            "total_count": total_count,
            "unique_count": unique_count
        }}
    
    # Generate summary
    type_counts = {{}}
    for col_info in field_info.values():
        col_type = col_info['type']
        type_counts[col_type] = type_counts.get(col_type, 0) + 1
    
    type_summary = ', '.join([f"{{count}} {{type_name}}" for type_name, count in type_counts.items()])
    
    # Find key columns
    numeric_cols = [col for col, info in field_info.items() 
                   if info['type'] in ['integer', 'float']]
    categorical_cols = [col for col, info in field_info.items() 
                      if info['type'] in ['string', 'boolean'] and info['unique_ratio'] < 0.5]
    
    summary_parts = [f"**Column Types**: {{type_summary}}"]
    if numeric_cols:
        summary_parts.append(f"**Numeric Fields**: {{', '.join(numeric_cols[:3])}}")
    if categorical_cols:
        summary_parts.append(f"**Categories**: {{', '.join(categorical_cols[:3])}}")
    
    summary = '\\n'.join(summary_parts)
    
    # Convert first 100 rows to list of dicts for recommendations
    sample_data = df.head(100).to_dict('records')
    
    # Output results
    result = {{
        "row_count": row_count,
        "column_count": column_count,
        "file_size_mb": file_size_mb,
        "field_info": field_info,
        "schema": field_info,
        "summary": summary,
        "data": sample_data
    }}
    
    print(json.dumps(result))
    
except Exception as e:
    error_result = {{"error": str(e)}}
    print(json.dumps(error_result))
'''

    def _generate_top_query_code(self, query: str, params: dict) -> str:
        """Generate code for top N queries"""
        sort_field = params.get('sort_field', 'value')
        n = params.get('n', 5)
        
        return f'''
import pandas as pd
import json

# Load data
with open('/workspace/data.json', 'r') as f:
    data_info = json.load(f)
    
df = pd.DataFrame(data_info['data'])

# Get top {n} by {sort_field}
if '{sort_field}' in df.columns:
    top_records = df.nlargest({n}, '{sort_field}')
    
    result_lines = ["📊 **Top {n} Records by {sort_field}**\\n"]
    
    for i, (_, row) in enumerate(top_records.iterrows(), 1):
        value = row['{sort_field}']
        # Include other fields
        other_fields = [col for col in df.columns if col != '{sort_field}'][:2]
        other_info = ' | '.join([f"{{col}}: {{row[col]}}" for col in other_fields])
        
        result_lines.append(f"{{i}}. **{sort_field}**: {{value:,}} | {{other_info}}")
    
    result = '\\n'.join(result_lines)
else:
    result = "❌ Field '{sort_field}' not found in data"

print(json.dumps({{"result": result}}))
'''

    def _generate_count_query_code(self, query: str, params: dict) -> str:
        """Generate code for count queries"""
        return '''
import pandas as pd
import json

# Load data
with open('/workspace/data.json', 'r') as f:
    data_info = json.load(f)
    
df = pd.DataFrame(data_info['data'])
schema = data_info['schema']

# Find categorical fields
categorical_fields = [col for col, info in schema.items() 
                     if info.get('type') in ['string', 'boolean'] 
                     and info.get('unique_ratio', 1.0) < 0.5]

if not categorical_fields:
    result = f"📊 **Count Analysis**\\n\\nTotal records in dataset: **{len(df):,}**"
else:
    # Use the first categorical field
    group_field = categorical_fields[0]
    counts = df[group_field].value_counts()
    
    result_lines = [f"📊 **Count by {group_field}**\\n"]
    
    for value, count in counts.head(10).items():
        result_lines.append(f"• **{value}**: {count:,} records")
    
    if len(counts) > 10:
        result_lines.append(f"... and {len(counts) - 10} more categories")
    
    result = '\\n'.join(result_lines)

print(json.dumps({"result": result}))
'''

    def _generate_average_query_code(self, query: str, params: dict) -> str:
        """Generate code for average queries"""
        return '''
import pandas as pd
import json

# Load data
with open('/workspace/data.json', 'r') as f:
    data_info = json.load(f)
    
df = pd.DataFrame(data_info['data'])
schema = data_info['schema']

# Find meaningful numeric fields  
meaningful_metrics = []
for col, info in schema.items():
    if info.get('type') in ['integer', 'float']:
        col_lower = col.lower()
        # Check for meaningful patterns OR reasonable uniqueness
        if (any(pattern in col_lower for pattern in ['price', 'cost', 'amount', 'revenue', 'salary', 'total', 'quantity', 'age']) or 
            info.get('unique_ratio', 1.0) < 0.8):
            meaningful_metrics.append(col)

if not meaningful_metrics:
    result = "❌ No numeric fields suitable for averaging found."
else:
    result_lines = ["📊 **Average Values**\\n"]
    
    for field in meaningful_metrics[:5]:
        if field in df.columns:
            avg_value = df[field].mean()
            result_lines.append(f"• **{field}**: {avg_value:.2f}")
    
    result = '\\n'.join(result_lines)

print(json.dumps({"result": result}))
'''

    def _generate_summary_query_code(self, query: str, params: dict) -> str:
        """Generate code for summary statistics"""
        return '''
import pandas as pd
import json

# Load data
with open('/workspace/data.json', 'r') as f:
    data_info = json.load(f)
    
df = pd.DataFrame(data_info['data'])
schema = data_info['schema']

# Find meaningful numeric fields  
meaningful_metrics = []
for col, info in schema.items():
    if info.get('type') in ['integer', 'float']:
        col_lower = col.lower()
        # Check for meaningful patterns OR reasonable uniqueness
        if (any(pattern in col_lower for pattern in ['price', 'cost', 'amount', 'revenue', 'salary', 'total', 'quantity', 'age']) or 
            info.get('unique_ratio', 1.0) < 0.8):
            meaningful_metrics.append(col)

if not meaningful_metrics:
    result = "❌ No numeric fields found for summary statistics."
else:
    result_lines = ["📊 **Summary Statistics**\\n"]
    
    for field in meaningful_metrics[:3]:
        if field in df.columns:
            stats = df[field].describe()
            result_lines.append(f"**{field}**:")
            result_lines.append(f"  • Min: {stats['min']:.2f}")
            result_lines.append(f"  • Max: {stats['max']:.2f}")
            result_lines.append(f"  • Mean: {stats['mean']:.2f}")
            result_lines.append(f"  • Median: {stats['50%']:.2f}")
            result_lines.append("")
    
    result = '\\n'.join(result_lines)

print(json.dumps({"result": result}))
'''


    def _is_meaningful_metric(self, column_name: str, field_info: dict) -> bool:
        """Simplified version of the meaningful metric detection"""
        if column_name not in field_info:
            return False
            
        field_type = field_info[column_name].get("type", "").lower()
        if field_type not in ("integer", "float", "double", "decimal", "numeric"):
            return False
        
        column_lower = column_name.lower()
        
        # Check for meaningful patterns
        meaningful_patterns = [
            r".*price.*", r".*cost.*", r".*amount.*", r".*revenue.*", r".*sales.*", 
            r".*total.*", r".*quantity.*", r".*score.*", r".*rating.*", r".*salary.*"
        ]
        
        for pattern in meaningful_patterns:
            if re.search(pattern, column_lower):
                return True
        
        # Check uniqueness - high uniqueness might indicate identifier
        unique_ratio = field_info[column_name].get("unique_ratio", 0)
        return unique_ratio < 0.8

    def _generate_widget_recommendations(self, field_info: dict, data: list) -> list:
        """Generate widget recommendations based on data analysis"""
        recommendations = []
        
        # Get meaningful columns
        numeric_fields = [col for col in field_info.keys() 
                         if self._is_meaningful_metric(col, field_info)]
        
        categorical_fields = [col for col, info in field_info.items() 
                            if info.get('type') in ['string', 'boolean'] 
                            and info.get('unique_ratio', 1.0) < 0.5]
        
        date_fields = [col for col, info in field_info.items() 
                      if info.get('semantic_type') == 'datetime' or 'date' in col.lower()]
        
        # 1. Table view (always first)
        recommendations.append({
            "type": "table",
            "title": "📋 Data Table View",
            "description": "View raw data in tabular format",
            "confidence": 1.0
        })
        
        # 2. Time series charts
        if date_fields and numeric_fields:
            for date_field in date_fields[:1]:
                for metric in numeric_fields[:2]:
                    recommendations.append({
                        "type": "line_chart",
                        "title": f"📈 {metric} over {date_field}",
                        "description": f"Track {metric} trends over time",
                        "confidence": 0.9
                    })
        
        # 3. Bar charts for categorical analysis
        if categorical_fields and numeric_fields:
            for category in categorical_fields[:2]:
                for metric in numeric_fields[:2]:
                    # Check if reasonable number of categories
                    unique_count = field_info[category].get('unique_count', 0)
                    if unique_count <= 20:
                        recommendations.append({
                            "type": "bar_chart", 
                            "title": f"📊 {metric} by {category}",
                            "description": f"Compare {metric} across {category} categories",
                            "confidence": 0.85
                        })
        
        # 4. Pie charts for low-cardinality categoricals
        if categorical_fields:
            for category in categorical_fields[:2]:
                unique_count = field_info[category].get('unique_count', 0)
                if 2 <= unique_count <= 8:
                    recommendations.append({
                        "type": "pie_chart",
                        "title": f"🥧 Distribution by {category}",
                        "description": f"See percentage breakdown of {category}",
                        "confidence": 0.8
                    })
        
        # 5. Scatter plots for numeric relationships
        if len(numeric_fields) >= 2:
            recommendations.append({
                "type": "scatter_plot",
                "title": f"🔗 {numeric_fields[0]} vs {numeric_fields[1]}",
                "description": f"Explore relationship between {numeric_fields[0]} and {numeric_fields[1]}",
                "confidence": 0.75
            })
        
        # 6. Correlation analysis
        if len(numeric_fields) >= 3:
            recommendations.append({
                "type": "correlation_matrix",
                "title": "🔍 Correlation Analysis",
                "description": "Discover relationships between numeric variables",
                "confidence": 0.7
            })
        
        return sorted(recommendations, key=lambda x: x['confidence'], reverse=True)

    def _format_recommendations(self, recommendations: list) -> str:
        """Format recommendations for display"""
        if not recommendations:
            return "No specific recommendations available."
        
        formatted = []
        for i, rec in enumerate(recommendations, 1):
            confidence_emoji = "🟢" if rec['confidence'] >= 0.8 else "🟡" if rec['confidence'] >= 0.6 else "🔴"
            formatted.append(f"{i}. {rec['title']} {confidence_emoji}")
            formatted.append(f"   {rec['description']}")
            
        return '\n'.join(formatted)

    def _generate_data_loading_code(self, file_path: str) -> str:
        """Generate Python code to load data in Docker"""
        return f'''
import duckdb
import pandas as pd
import json

try:
    file_path = "{file_path}"
    
    # Load data based on file extension
    if file_path.endswith('.csv'):
        df = pd.read_csv(file_path)
    elif file_path.endswith(('.xlsx', '.xls')):
        df = pd.read_excel(file_path)
    else:
        raise ValueError("Unsupported file format. Use CSV or Excel files.")
    
    # Create DuckDB connection and load data
    conn = duckdb.connect(':memory:')
    conn.register('data', df)
    
    # Basic analysis
    result = {{
        "row_count": len(df),
        "column_count": len(df.columns),
        "schema": {{col: {{"type": str(df[col].dtype)}} for col in df.columns}},
        "data_quality": "Analysis completed",
        "recommendations": []
    }}
    
    print(json.dumps(result, indent=2))
    
except Exception as e:
    print(f"Error: {{str(e)}}")
'''

    async def cleanup_session(self):
        """Clean up Analytics Agent resources"""
        self.current_dataset = None
        self.current_schema = None
        await super().cleanup_session()