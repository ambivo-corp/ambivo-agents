#!/usr/bin/env python3
"""
knowledge_base_operations.py -
Real-world example of text ingestion and querying using Ambivo Agents Knowledge Base
ALL CONFIGURATION FROM agent_config.yaml - NO HARDCODING

Author: Hemant Gosain 'Sunny'
Company: Ambivo
Email: sgosain@ambivo.com
License: MIT
"""

import asyncio
import os
import sys
import time
import json
import requests
from pathlib import Path
from datetime import datetime

# Add the ambivo_agents package to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from ambivo_agents.services import create_agent_service
from ambivo_agents.services.factory import AgentFactory
from ambivo_agents.core.memory import create_redis_memory_manager
from ambivo_agents.core.llm import create_multi_provider_llm_service


class KnowledgeBaseDemo:
    """Demonstrate real knowledge base operations with text ingestion and querying - CONFIG-DRIVEN"""

    def __init__(self):
        print("🧠 Initializing Knowledge Base Operations Demo...")

        # Load and validate configuration FIRST
        self.load_and_validate_config()

        # Create agent service
        self.agent_service = create_agent_service()

        # Create session
        self.session_id = self.agent_service.create_session()
        self.user_id = "kb_demo_user"

        # Knowledge base name from config or default
        self.kb_name = self.kb_config.get('default_kb_name', 'ambivo_demo_kb')

        # Setup directories
        self.setup_directories()


        self.kb_agent = None
        self.llm_service = None

    def load_and_validate_config(self):
        """Load configuration from agent_config.yaml and validate required sections"""
        try:
            from ambivo_agents.config.loader import load_config, get_config_section

            print("📋 Loading configuration from agent_config.yaml...")
            self.config = load_config()


            # Validate required sections exist
            required_sections = ['knowledge_base', 'redis', 'llm', 'agent_capabilities']
            for section in required_sections:
                if section not in self.config:
                    raise ValueError(f"Missing required section '{section}' in agent_config.yaml")

            # Load specific configurations
            self.kb_config = get_config_section('knowledge_base', self.config)
            self.redis_config = get_config_section('redis', self.config)
            self.llm_config = get_config_section('llm', self.config)

            # Validate required knowledge base settings
            required_kb_settings = ['qdrant_url']
            for setting in required_kb_settings:
                if setting not in self.kb_config:
                    raise ValueError(f"Missing required setting 'knowledge_base.{setting}' in agent_config.yaml")

            # Validate capabilities
            capabilities = self.config.get('agent_capabilities', {})

            if not capabilities.get('enable_knowledge_base', False):
                raise ValueError(
                    "knowledge_base capability is not enabled in agent_config.yaml. Set capabilities.knowledge_base: true")

            # Validate LLM configuration
            if not self.llm_config.get('openai_api_key') and not self.llm_config.get('anthropic_api_key'):
                raise ValueError(
                    "No LLM API keys found in agent_config.yaml. Please set either openai_api_key or anthropic_api_key")

            print("✅ Configuration validated successfully")
            print(f"🔧 Qdrant URL: {self.kb_config['qdrant_url']}")
            print(f"🔧 Redis: {self.redis_config['host']}:{self.redis_config['port']}")
            print(f"🔧 LLM Provider: {self.llm_config.get('preferred_provider', 'openai')}")

        except FileNotFoundError:
            raise FileNotFoundError(
                "agent_config.yaml not found. Please create the configuration file with required knowledge_base, redis, and llm settings."
            )
        except Exception as e:
            raise RuntimeError(f"Configuration error: {e}")

    def setup_directories(self):
        """Setup directories for documents"""
        # Use configured directory or default
        docs_dir_config = self.kb_config.get('documents_dir', './demo_documents')
        self.docs_dir = Path(docs_dir_config)
        self.docs_dir.mkdir(exist_ok=True)

        print(f"📁 Documents directory (from config): {self.docs_dir.absolute()}")

    async def initialize_direct_kb_agent(self):
        """Initialize Knowledge Base Agent directly using configuration"""
        try:
            from ambivo_agents.agents.knowledge_base import KnowledgeBaseAgent

            print("🔧 Initializing direct Knowledge Base Agent with configuration...")

            # Create memory manager for KB agent using config
            kb_memory = create_redis_memory_manager(f"kb_agent_{int(time.time())}", self.redis_config)

            # Create LLM service using config
            self.llm_service = create_multi_provider_llm_service(
                self.llm_config,
                self.llm_config.get('preferred_provider', 'openai')
            )

            # Create KB agent directly
            self.kb_agent = KnowledgeBaseAgent(
                agent_id=f"kb_direct_{int(time.time())}",
                memory_manager=kb_memory,
                llm_service=self.llm_service
            )

            print("✅ Direct Knowledge Base Agent initialized successfully!")
            return True

        except Exception as e:
            print(f"❌ Failed to initialize direct KB agent: {e}")
            raise RuntimeError(f"KB Agent initialization failed: {e}")

    async def check_knowledge_base_availability(self):
        """Check if knowledge base agent is available"""
        print("\n🔍 Checking Knowledge Base Agent Availability...")

        # Try to initialize direct KB agent
        if await self.initialize_direct_kb_agent():
            print("✅ Knowledge Base Agent is available (direct mode)")
            return True
        else:
            raise RuntimeError("Knowledge Base Agent initialization failed")

    async def test_qdrant_connection(self):
        """Test direct connection to Qdrant Cloud using get_collections()"""
        try:
            print(f"\n🔗 Testing Qdrant connection to: {self.kb_config['qdrant_url']}")

            import qdrant_client

            qdrant_url = self.kb_config['qdrant_url']
            qdrant_api_key = self.kb_config['qdrant_api_key']

            print(f"📡 Connecting to: {qdrant_url}")
            client = qdrant_client.QdrantClient(
                url=qdrant_url,
                api_key=qdrant_api_key,
                timeout=30,
                check_compatibility=False
            )

            # Test connection by getting collections
            collections = client.get_collections()
            print("✅ Qdrant is accessible")
            print(f"📊 Found {len(collections.collections)} existing collections")

            if collections.collections:
                for collection in collections.collections[:5]:  # Show max 5
                    print(f"  - {collection.name}")

            return True

        except ImportError:
            print("❌ qdrant-client not installed: pip install qdrant-client")
            raise RuntimeError("qdrant-client package required for Knowledge Base functionality")
        except Exception as e:
            print(f"❌ Qdrant connection failed: {e}")
            print(f"💡 URL: {qdrant_url}")
            print(f"💡 API Key: {'✅ Present' if qdrant_api_key else '❌ Missing'}")
            print("💡 Troubleshooting:")
            print("   1. Verify Qdrant Cloud instance is active")
            print("   2. Check API key is correct and has proper permissions")
            print("   3. Ensure URL is correct (should include :6333 port)")
            print("   4. Check your Qdrant Cloud dashboard for instance status")
            raise RuntimeError(f"Cannot connect to Qdrant at {qdrant_url}: {e}")

    async def direct_ingest_document(self, file_path: str):
        """Directly ingest a document using KB agent"""
        if not self.kb_agent:
            raise RuntimeError("No direct KB agent available - initialization failed")

        try:
            print(f"📄 [DIRECT] Ingesting document: {file_path}")

            if not Path(file_path).exists():
                raise FileNotFoundError(f"Document file not found: {file_path}")

            # Use the agent's tool directly with configured kb_name
            result = await self.kb_agent._ingest_document(
                kb_name=self.kb_name,
                doc_path=file_path,
                custom_meta={
                    "demo_source": "direct_ingestion",
                    "file_name": Path(file_path).name,
                    "ingestion_timestamp": datetime.now().isoformat()
                }
            )

            if result.get('success'):
                print(f"✅ [DIRECT] Document ingested: {result.get('message', 'Success')}")
                return True
            else:
                print(f"❌ [DIRECT] Ingestion failed: {result.get('error', 'Unknown error')}")
                return False

        except Exception as e:
            print(f"❌ [DIRECT] Exception during ingestion: {e}")
            raise

    async def direct_ingest_text(self, text_content: str, metadata: dict = None):
        """Directly ingest text using KB agent"""
        if not self.kb_agent:
            raise RuntimeError("No direct KB agent available - initialization failed")

        try:
            print(f"📝 [DIRECT] Ingesting text content ({len(text_content)} chars)")

            # Use the agent's tool directly with configured kb_name
            result = await self.kb_agent._ingest_text(
                kb_name=self.kb_name,
                input_text=text_content,
                custom_meta=metadata or {
                    "demo_source": "direct_text_ingestion",
                    "ingestion_timestamp": datetime.now().isoformat()
                }
            )

            if result.get('success'):
                print(f"✅ [DIRECT] Text ingested: {result.get('message', 'Success')}")
                return True
            else:
                print(f"❌ [DIRECT] Text ingestion failed: {result.get('error', 'Unknown error')}")
                return False

        except Exception as e:
            print(f"❌ [DIRECT] Exception during text ingestion: {e}")
            raise

    async def direct_query_knowledge_base(self, query: str):
        """Directly query KB using KB agent"""
        if not self.kb_agent:
            raise RuntimeError("No direct KB agent available - initialization failed")

        try:
            print(f"🔍 [DIRECT] Querying: {query}")

            # Use the agent's tool directly with configured kb_name
            result = await self.kb_agent._query_knowledge_base(
                kb_name=self.kb_name,
                query=query,
                question_type="free-text"
            )

            if result.get('success'):
                answer = result.get('answer', 'No answer provided')
                sources = result.get('source_details', [])

                print(f"✅ [DIRECT] Query successful!")
                print(f"📝 Answer: {answer}")

                if sources:
                    print(f"📚 Found {len(sources)} source(s)")
                    for i, source in enumerate(sources[:2], 1):  # Show first 2 sources
                        if isinstance(source, dict):
                            print(f"  Source {i}: {source.get('source', 'Unknown')}")

                return answer
            else:
                print(f"❌ [DIRECT] Query failed: {result.get('error', 'Unknown error')}")
                return None

        except Exception as e:
            print(f"❌ [DIRECT] Exception during query: {e}")
            raise

    def create_sample_documents(self):
        """Create sample text documents for ingestion in configured directory"""
        print(f"\n📝 Creating sample documents in: {self.docs_dir}")

        documents = {
            "company_overview.txt": """
Ambivo Company Overview

Ambivo is a leading technology company specializing in artificial intelligence and automation solutions. 
Founded in 2020, we have been at the forefront of developing innovative AI-powered systems that help 
businesses streamline their operations and improve efficiency.

Our Mission:
To democratize artificial intelligence and make advanced automation accessible to businesses of all sizes.

Our Vision:
A world where intelligent automation empowers every organization to achieve unprecedented efficiency and innovation.

Core Values:
- Innovation: We constantly push the boundaries of what's possible with AI
- Integrity: We build trustworthy and transparent AI systems
- Inclusivity: We make AI accessible to everyone
- Impact: We focus on creating meaningful solutions that solve real problems

Founded: 2020
Headquarters: San Francisco, California
Employees: 50+
Industry: Artificial Intelligence, Software Development
            """,

            "products_services.txt": """
Ambivo Products and Services

1. Ambivo Agents Platform
   - Multi-agent AI system for enterprise automation
   - Supports code execution, web scraping, media processing
   - Redis-based memory management
   - Docker-based secure execution
   - Multi-LLM provider support (OpenAI, Anthropic, AWS Bedrock)

2. Knowledge Base Solutions
   - Vector database integration with Qdrant
   - Document ingestion and semantic search
   - Support for PDF, DOCX, TXT, and web content
   - Custom metadata and chunking strategies

3. Pricing Plans
   - Starter Plan: $99/month - Basic features for small teams
   - Professional Plan: $299/month - Advanced features and integrations
   - Enterprise Plan: Custom pricing - Full platform access
   - Consulting Services: $200/hour - Custom development and training

4. Support Services
   - 24/7 technical support
   - Custom agent development
   - Training and onboarding
   - API integration assistance
            """,

            "best_practices.txt": """
Ambivo Agents Best Practices

Performance Optimization:
- Enable Redis compression for large datasets
- Use appropriate chunk sizes for document ingestion
- Configure connection pooling for high-throughput applications
- Monitor memory usage and scale Redis as needed

Security Guidelines:
- Always run code execution in isolated Docker containers
- Use environment variables for API keys and secrets
- Enable TLS/SSL for all network communications
- Implement proper input validation and sanitization
- Regular security audits and updates

Knowledge Base Management:
- Use descriptive collection names
- Add meaningful metadata to documents
- Regular backup of Qdrant data
- Monitor query performance and optimize as needed
- Implement proper document lifecycle management

Deployment Recommendations:
- Use Docker Compose for multi-service deployments
- Implement health checks for all services
- Set up monitoring and alerting
- Plan for disaster recovery
- Use load balancers for high availability
            """
        }

        created_files = []
        for filename, content in documents.items():
            file_path = self.docs_dir / filename
            file_path.write_text(content.strip())
            created_files.append(str(file_path))
            print(f"📄 Created: {filename}")

        return created_files

    async def run_comprehensive_demo(self):
        """Run the complete knowledge base demonstration - CONFIG-DRIVEN VERSION"""
        print("\n" + "=" * 80)
        print("🧠 COMPREHENSIVE KNOWLEDGE BASE OPERATIONS DEMO (CONFIG-DRIVEN)")
        print("=" * 80)

        try:
            # 1. Test Qdrant connection with configured URL
            await self.test_qdrant_connection()

            # 2. Check agent availability
            await self.check_knowledge_base_availability()

            if not self.kb_agent:
                raise RuntimeError("KB agent initialization failed")

            # 3. Show configuration being used
            print(f"\n📋 Configuration Summary:")
            print(f"  Qdrant URL: {self.kb_config['qdrant_url']}")
            print(f"  Knowledge Base Name: {self.kb_name}")
            print(f"  Documents Directory: {self.docs_dir}")
            print(f"  Chunk Size: {self.kb_config.get('chunk_size', 1024)}")
            print(f"  Similarity Top K: {self.kb_config.get('similarity_top_k', 5)}")
            print(f"  Collection Prefix: {self.kb_config.get('default_collection_prefix', 'kb')}")

            # 4. Create sample documents in configured directory
            print("\n--- Creating Sample Documents ---")
            document_files = self.create_sample_documents()

            # 5. Direct document ingestion
            print("\n--- Direct Document Ingestion ---")
            ingested_count = 0

            for doc_file in document_files:
                success = await self.direct_ingest_document(doc_file)
                if success:
                    ingested_count += 1
                await asyncio.sleep(1)  # Rate limiting

            print(f"📊 Successfully ingested {ingested_count}/{len(document_files)} documents")

            # 6. Direct text ingestion
            print("\n--- Direct Text Ingestion ---")

            sample_text = """
            Ambivo Agents Advanced Features

            Machine Learning Integration:
            - Support for custom ML models
            - Automated model training and deployment
            - Real-time inference capabilities
            - Model versioning and rollback

            Enterprise Features:
            - Single Sign-On (SSO) integration
            - Role-based access control
            - Audit logging and compliance
            - High availability deployment
            - Multi-tenancy support

            API Capabilities:
            - RESTful API for all operations
            - WebSocket support for real-time updates
            - GraphQL endpoint for flexible queries
            - Comprehensive API documentation
            - Rate limiting and throttling
            """

            text_success = await self.direct_ingest_text(
                sample_text,
                {"category": "advanced_features", "importance": "high"}
            )

            # 7. Verify collections were created in configured Qdrant
            print("\n--- Verifying Qdrant Collections ---")
            await self.test_qdrant_connection()

            # 8. Direct querying
            print("\n--- Direct Knowledge Base Queries ---")

            queries = [
                "What is Ambivo's mission and vision?",
                "What are the pricing plans for Ambivo services?",
                "What are the best practices for performance optimization?",
                "What advanced features does Ambivo Agents offer?",
                "How much does the Professional Plan cost?",
                "What security guidelines should I follow?",
                "What enterprise features are available?"
            ]

            successful_queries = 0
            for i, query in enumerate(queries, 1):
                print(f"\n--- Query {i}/{len(queries)}: {query[:50]}... ---")

                try:
                    answer = await self.direct_query_knowledge_base(query)
                    if answer and len(answer) > 50:  # Valid answer with substance
                        successful_queries += 1
                        print(f"✅ Query successful")
                    else:
                        print(f"⚠️  Query returned minimal response")
                except Exception as e:
                    print(f"❌ Query failed: {e}")

                await asyncio.sleep(1)

            # 9. Final verification
            print("\n--- Final Verification ---")
            await self.test_qdrant_connection()

            print(f"\n✅ Knowledge Base operations demo completed!")
            print(f"📊 Documents ingested: {ingested_count}")
            print(f"📝 Text content ingested: {'✅' if text_success else '❌'}")
            print(f"🔍 Successful queries: {successful_queries}/{len(queries)}")

            if successful_queries > 0:
                print("🎉 Knowledge Base is working correctly with your configuration!")
            else:
                raise RuntimeError("All queries failed - check Qdrant connection and agent configuration")

        except Exception as e:
            print(f"\n❌ Demo failed with error: {e}")
            print("💡 Check your agent_config.yaml file for proper configuration")
            raise

    async def cleanup(self):
        """Clean up demo resources"""
        print("\n🧹 Cleaning up demo resources...")

        # Delete the demo session
        if self.session_id:
            success = self.agent_service.delete_session(self.session_id)
            if success:
                print(f"✅ Deleted demo session: {self.session_id}")

        print("✅ Cleanup completed")
        print(f"💡 Note: Knowledge base data remains in Qdrant at {self.kb_config['qdrant_url']}")
        print("🗑️  To clear Qdrant data, please navigate to your Qdrant account")


async def main():
    """Main function to run the knowledge base operations demo"""
    import argparse

    parser = argparse.ArgumentParser(description="Knowledge Base Operations Demo (Config-Driven)")
    parser.add_argument("--kb-name", help="Override knowledge base name from config")
    parser.add_argument("--query-only", help="Perform only a specific query")
    parser.add_argument("--ingest-file", help="Ingest a specific file")
    parser.add_argument("--test-connection", action="store_true", help="Test Qdrant connection only")

    args = parser.parse_args()

    try:
        demo = KnowledgeBaseDemo()

        # Override kb_name if provided
        if args.kb_name:
            demo.kb_name = args.kb_name
            print(f"🔧 Using knowledge base name: {demo.kb_name}")

        if args.test_connection:
            # Test connection only
            await demo.test_qdrant_connection()

        elif args.query_only:
            # Perform specific query only
            print(f"🔍 Performing specific query: {args.query_only}")

            await demo.check_knowledge_base_availability()
            answer = await demo.direct_query_knowledge_base(args.query_only)
            if answer:
                print(f"\n📝 Full Answer:\n{answer}")

        elif args.ingest_file:
            # Ingest specific file only
            print(f"📄 Ingesting specific file: {args.ingest_file}")

            if not Path(args.ingest_file).exists():
                raise FileNotFoundError(f"File not found: {args.ingest_file}")

            await demo.check_knowledge_base_availability()
            success = await demo.direct_ingest_document(args.ingest_file)
            if success:
                print(f"✅ File ingested successfully: {args.ingest_file}")

                # Test query
                test_query = f"What information is contained in the document {Path(args.ingest_file).name}?"
                await demo.direct_query_knowledge_base(test_query)
        else:
            # Run full demo
            await demo.run_comprehensive_demo()

        await demo.cleanup()

    except KeyboardInterrupt:
        print("\n\n⚠️  Demo interrupted by user")
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        print(f"\n\n❌ Configuration/Runtime Error: {e}")
        print("💡 Please check your agent_config.yaml file")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())


    async def initialize_direct_kb_agent(self):
        """Initialize Knowledge Base Agent directly"""
        try:
            from ambivo_agents.config.loader import load_config, get_config_section
            from ambivo_agents.agents.knowledge_base import KnowledgeBaseAgent

            print("🔧 Initializing direct Knowledge Base Agent...")

            # Load configuration
            config = load_config()
            redis_config = get_config_section('redis', config)
            llm_config = get_config_section('llm', config)

            # Create memory manager for KB agent
            kb_memory = create_redis_memory_manager(f"kb_agent_{int(time.time())}", redis_config)

            # Create LLM service
            self.llm_service = create_multi_provider_llm_service(llm_config)

            # Create KB agent directly
            self.kb_agent = KnowledgeBaseAgent(
                agent_id=f"kb_direct_{int(time.time())}",
                memory_manager=kb_memory,
                llm_service=self.llm_service
            )

            print("✅ Direct Knowledge Base Agent initialized successfully!")
            return True

        except Exception as e:
            print(f"❌ Failed to initialize direct KB agent: {e}")
            return False


    async def check_knowledge_base_availability(self):
        """Check if knowledge base agent is available"""
        print("\n🔍 Checking Knowledge Base Agent Availability...")

        # Try to initialize direct KB agent
        if await self.initialize_direct_kb_agent():
            print("✅ Knowledge Base Agent is available (direct mode)")
            return True

        # Fallback to service health check
        health = self.agent_service.health_check()
        available_agents = health.get('available_agent_types', {})

        if available_agents.get('knowledge_base', False):
            print("✅ Knowledge Base Agent is available (via service)")
            return True
        else:
            print("❌ Knowledge Base Agent is not available")
            print("Please ensure knowledge_base is enabled in agent_config.yaml")
            print("Also ensure Qdrant is running and accessible")
            return False


    async def direct_ingest_document(self, file_path: str):
        """Directly ingest a document using KB agent"""
        if not self.kb_agent:
            print("❌ No direct KB agent available")
            return False

        try:
            print(f"📄 [DIRECT] Ingesting document: {file_path}")

            # Use the agent's tool directly
            result = await self.kb_agent._ingest_document(
                kb_name=self.kb_name,
                doc_path=file_path,
                custom_meta={
                    "demo_source": "direct_ingestion",
                    "file_name": Path(file_path).name
                }
            )

            if result.get('success'):
                print(f"✅ [DIRECT] Document ingested: {result.get('message', 'Success')}")
                return True
            else:
                print(f"❌ [DIRECT] Ingestion failed: {result.get('error', 'Unknown error')}")
                return False

        except Exception as e:
            print(f"❌ [DIRECT] Exception during ingestion: {e}")
            return False


    async def direct_ingest_text(self, text_content: str, metadata: dict = None):
        """Directly ingest text using KB agent"""
        if not self.kb_agent:
            print("❌ No direct KB agent available")
            return False

        try:
            print(f"📝 [DIRECT] Ingesting text content ({len(text_content)} chars)")

            # Use the agent's tool directly
            result = await self.kb_agent._ingest_text(
                kb_name=self.kb_name,
                input_text=text_content,
                custom_meta=metadata or {"demo_source": "direct_text_ingestion"}
            )

            if result.get('success'):
                print(f"✅ [DIRECT] Text ingested: {result.get('message', 'Success')}")
                return True
            else:
                print(f"❌ [DIRECT] Text ingestion failed: {result.get('error', 'Unknown error')}")
                return False

        except Exception as e:
            print(f"❌ [DIRECT] Exception during text ingestion: {e}")
            return False


    async def direct_query_knowledge_base(self, query: str):
        """Directly query KB using KB agent"""
        if not self.kb_agent:
            print("❌ No direct KB agent available")
            return None

        try:
            print(f"🔍 [DIRECT] Querying: {query}")

            # Use the agent's tool directly
            result = await self.kb_agent._query_knowledge_base(
                kb_name=self.kb_name,
                query=query,
                question_type="free-text"
            )

            if result.get('success'):
                answer = result.get('answer', 'No answer provided')
                sources = result.get('source_details', [])

                print(f"✅ [DIRECT] Query successful!")
                print(f"📝 Answer: {answer}")

                if sources:
                    print(f"📚 Found {len(sources)} source(s)")
                    for i, source in enumerate(sources[:2], 1):  # Show first 2 sources
                        if isinstance(source, dict):
                            print(f"  Source {i}: {source.get('source', 'Unknown')}")

                return answer
            else:
                print(f"❌ [DIRECT] Query failed: {result.get('error', 'Unknown error')}")
                return None

        except Exception as e:
            print(f"❌ [DIRECT] Exception during query: {e}")
            return None


    def create_sample_documents(self):
        """Create sample text documents for ingestion"""
        print("\n📝 Creating sample documents for knowledge base...")

        documents = {
            "company_overview.txt": """
Ambivo Company Overview

Ambivo is a leading technology company specializing in artificial intelligence and automation solutions. 
Founded in 2020, we have been at the forefront of developing innovative AI-powered systems that help 
businesses streamline their operations and improve efficiency.

Our Mission:
To democratize artificial intelligence and make advanced automation accessible to businesses of all sizes.

Our Vision:
A world where intelligent automation empowers every organization to achieve unprecedented efficiency and innovation.

Core Values:
- Innovation: We constantly push the boundaries of what's possible with AI
- Integrity: We build trustworthy and transparent AI systems
- Inclusivity: We make AI accessible to everyone
- Impact: We focus on creating meaningful solutions that solve real problems

Founded: 2020
Headquarters: San Francisco, California
Employees: 50+
Industry: Artificial Intelligence, Software Development
            """,

            "products_services.txt": """
Ambivo Products and Services

1. Ambivo Agents Platform
   - Multi-agent AI system for enterprise automation
   - Supports code execution, web scraping, media processing
   - Redis-based memory management
   - Docker-based secure execution
   - Multi-LLM provider support (OpenAI, Anthropic, AWS Bedrock)

2. Knowledge Base Solutions
   - Vector database integration with Qdrant
   - Document ingestion and semantic search
   - Support for PDF, DOCX, TXT, and web content
   - Custom metadata and chunking strategies

3. Pricing Plans
   - Starter Plan: $99/month - Basic features for small teams
   - Professional Plan: $299/month - Advanced features and integrations
   - Enterprise Plan: Custom pricing - Full platform access
   - Consulting Services: $200/hour - Custom development and training

4. Support Services
   - 24/7 technical support
   - Custom agent development
   - Training and onboarding
   - API integration assistance
            """,

            "best_practices.txt": """
Ambivo Agents Best Practices

Performance Optimization:
- Enable Redis compression for large datasets
- Use appropriate chunk sizes for document ingestion
- Configure connection pooling for high-throughput applications
- Monitor memory usage and scale Redis as needed

Security Guidelines:
- Always run code execution in isolated Docker containers
- Use environment variables for API keys and secrets
- Enable TLS/SSL for all network communications
- Implement proper input validation and sanitization
- Regular security audits and updates

Knowledge Base Management:
- Use descriptive collection names
- Add meaningful metadata to documents
- Regular backup of Qdrant data
- Monitor query performance and optimize as needed
- Implement proper document lifecycle management

Deployment Recommendations:
- Use Docker Compose for multi-service deployments
- Implement health checks for all services
- Set up monitoring and alerting
- Plan for disaster recovery
- Use load balancers for high availability
            """
        }

        created_files = []
        for filename, content in documents.items():
            file_path = self.docs_dir / filename
            file_path.write_text(content.strip())
            created_files.append(str(file_path))
            print(f"📄 Created: {filename}")

        return created_files


    async def test_qdrant_connection(self):
        """Test direct connection to Qdrant using config URL"""
        try:
            print("\n🔗 Testing Qdrant connection...")

            # Load Qdrant URL from configuration
            from ambivo_agents.config.loader import load_config, get_config_section
            config = load_config()
            print("!!!!!!!config {}".format(config))
            kb_config = get_config_section('knowledge_base', config)
            qdrant_url = kb_config.get('qdrant_url', None)
            if not qdrant_url:
                raise ValueError("Qdrant URL not found in knowledge_base section of agent_config.yaml")

            print(f"🔧 Using Qdrant URL from config: {qdrant_url}")

            # Test basic connection
            import requests
            health_url = f"{qdrant_url}/health"
            response = requests.get(health_url, timeout=5)

            if response.status_code == 200:
                print("✅ Qdrant is accessible")

                # Check collections
                collections_url = f"{qdrant_url}/collections"
                collections_response = requests.get(collections_url, timeout=5)

                if collections_response.status_code == 200:
                    collections = collections_response.json()
                    print(f"📊 Current collections: {len(collections.get('result', {}).get('collections', []))}")

                    for collection in collections.get('result', {}).get('collections', []):
                        print(f"  - {collection.get('name', 'Unknown')}")

                return True
            else:
                print(f"❌ Qdrant returned status: {response.status_code}")
                return False

        except Exception as e:
            print(f"❌ Qdrant connection failed: {e}")
            print(f"💡 Check qdrant_url in agent_config.yaml: {qdrant_url}")
            print("💡 Make sure Qdrant is running and accessible")
            return False


    async def run_comprehensive_demo(self):
        """Run the complete knowledge base demonstration """
        print("\n" + "=" * 80)
        print("🧠 COMPREHENSIVE KNOWLEDGE BASE OPERATIONS DEMO ")
        print("=" * 80)

        try:
            # 1. Test Qdrant connection first
            if not await self.test_qdrant_connection():
                print("❌ Cannot proceed without Qdrant connection")
                return

            # 2. Check agent availability
            if not await self.check_knowledge_base_availability():
                print("❌ Knowledge Base agent not available. Exiting demo.")
                return

            if not self.kb_agent:
                print("❌ No direct KB agent available. Cannot proceed with demo.")
                return

            # 3. Create sample documents
            print("\n--- Creating Sample Documents ---")
            document_files = self.create_sample_documents()

            # 4. Direct document ingestion
            print("\n--- Direct Document Ingestion ---")
            ingested_count = 0

            for doc_file in document_files:
                success = await self.direct_ingest_document(doc_file)
                if success:
                    ingested_count += 1
                await asyncio.sleep(1)  # Rate limiting

            print(f"📊 Successfully ingested {ingested_count}/{len(document_files)} documents")

            # 5. Direct text ingestion
            print("\n--- Direct Text Ingestion ---")

            sample_text = """
            Ambivo Agents Advanced Features

            Machine Learning Integration:
            - Support for custom ML models
            - Automated model training and deployment
            - Real-time inference capabilities
            - Model versioning and rollback

            Enterprise Features:
            - Single Sign-On (SSO) integration
            - Role-based access control
            - Audit logging and compliance
            - High availability deployment
            - Multi-tenancy support

            API Capabilities:
            - RESTful API for all operations
            - WebSocket support for real-time updates
            - GraphQL endpoint for flexible queries
            - Comprehensive API documentation
            - Rate limiting and throttling
            """

            text_success = await self.direct_ingest_text(
                sample_text,
                {"category": "advanced_features", "importance": "high"}
            )

            # 6. Verify collections were created
            print("\n--- Verifying Qdrant Collections ---")
            await self.test_qdrant_connection()

            # 7. Direct querying
            print("\n--- Direct Knowledge Base Queries ---")

            queries = [
                "What is Ambivo's mission and vision?",
                "What are the pricing plans for Ambivo services?",
                "What are the best practices for performance optimization?",
                "What advanced features does Ambivo Agents offer?",
                "How much does the Professional Plan cost?",
                "What security guidelines should I follow?",
                "What enterprise features are available?"
            ]

            successful_queries = 0
            for i, query in enumerate(queries, 1):
                print(f"\n--- Query {i}/{len(queries)}: {query[:50]}... ---")

                answer = await self.direct_query_knowledge_base(query)
                if answer and "No proxy scraping methods" not in answer:
                    successful_queries += 1
                    print(f"✅ Query successful")
                else:
                    print(f"❌ Query failed or returned invalid response")

                await asyncio.sleep(1)

            # 8. Final verification
            print("\n--- Final Verification ---")
            await self.test_qdrant_connection()

            print(f"\n✅ Knowledge Base operations demo completed!")
            print(f"📊 Documents ingested: {ingested_count}")
            print(f"📝 Text content ingested: {'✅' if text_success else '❌'}")
            print(f"🔍 Successful queries: {successful_queries}/{len(queries)}")

            if successful_queries > 0:
                print("🎉 Knowledge Base is working correctly!")
            else:
                print("⚠️  Knowledge Base queries failed - check Qdrant and agent configuration")

        except Exception as e:
            print(f"\n❌ Demo failed with error: {e}")
            import traceback
            traceback.print_exc()


    async def cleanup(self):
        """Clean up demo resources"""
        print("\n🧹 Cleaning up demo resources...")

        # Delete the demo session
        if self.session_id:
            success = self.agent_service.delete_session(self.session_id)
            if success:
                print(f"✅ Deleted demo session: {self.session_id}")

        print("✅ Cleanup completed")
        print("💡 Note: Knowledge base data remains in Qdrant for future use")
        print("🗑️  To clear Qdrant data: docker restart qdrant-container")


async def main():
    """Main function to run the knowledge base operations demo"""
    import argparse

    parser = argparse.ArgumentParser(description="Knowledge Base Operations Demo (Fixed)")
    parser.add_argument("--kb-name", default="ambivo_demo_kb",
                        help="Knowledge base name to use")
    parser.add_argument("--query-only", help="Perform only a specific query")
    parser.add_argument("--ingest-file", help="Ingest a specific file")
    parser.add_argument("--test-connection", action="store_true", help="Test Qdrant connection only")

    args = parser.parse_args()

    try:
        demo = KnowledgeBaseDemo()
        demo.kb_name = args.kb_name

        if args.test_connection:
            # Test connection only
            await demo.test_qdrant_connection()

        elif args.query_only:
            # Perform specific query only
            print(f"🔍 Performing specific query: {args.query_only}")

            if await demo.check_knowledge_base_availability():
                answer = await demo.direct_query_knowledge_base(args.query_only)
                if answer:
                    print(f"\n📝 Full Answer:\n{answer}")

        elif args.ingest_file:
            # Ingest specific file only
            print(f"📄 Ingesting specific file: {args.ingest_file}")

            if await demo.check_knowledge_base_availability():
                success = await demo.direct_ingest_document(args.ingest_file)
                if success:
                    print(f"✅ File ingested successfully: {args.ingest_file}")

                    # Test query
                    test_query = f"What information is contained in the document {Path(args.ingest_file).name}?"
                    await demo.direct_query_knowledge_base(test_query)
        else:
            # Run full demo
            await demo.run_comprehensive_demo()

        await demo.cleanup()

    except KeyboardInterrupt:
        print("\n\n⚠️  Demo interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())