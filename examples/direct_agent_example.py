#!/usr/bin/env python3
"""
Direct Agent Usage Example - Bypass Moderator Routing
Shows how to use specific agents directly for their intended roles
"""

import asyncio
import sys
from pathlib import Path
from ambivo_agents.agents.analytics import AnalyticsAgent
from ambivo_agents.agents.knowledge_base import KnowledgeBaseAgent
from ambivo_agents.agents.database_agent import DatabaseAgent
from ambivo_agents.config.loader import get_config_section


async def create_sample_data():
    """Create sample CSV file for testing"""
    docker_config = get_config_section("docker") or {}
    shared_base_dir = docker_config.get("shared_base_dir", "./docker_shared")
    
    analytics_input_dir = Path(shared_base_dir) / "input" / "analytics"
    analytics_input_dir.mkdir(parents=True, exist_ok=True)
    
    csv_content = """date,product,category,quantity,price,revenue
2024-01-01,Laptop,Electronics,5,1200,6000
2024-01-01,Mouse,Accessories,20,25,500
2024-01-02,Keyboard,Accessories,15,75,1125
2024-01-02,Monitor,Electronics,8,350,2800
2024-01-03,Laptop,Electronics,3,1200,3600
2024-01-03,Webcam,Accessories,12,80,960
2024-01-04,Tablet,Electronics,7,600,4200
2024-01-05,Headphones,Accessories,25,150,3750"""
    
    file_path = analytics_input_dir / "sample_sales.csv"
    with open(file_path, 'w') as f:
        f.write(csv_content)
    
    print(f"✅ Created sample file: {file_path}")
    return str(file_path)


async def demo_analytics_agent():
    """Demonstrate direct Analytics Agent usage"""
    print("\n" + "="*60)
    print("📊 ANALYTICS AGENT - Data Analysis & Visualization")
    print("="*60)
    
    await create_sample_data()
    
    analytics = AnalyticsAgent.create_simple(user_id="demo_user")
    
    try:
        print("\n1. Loading and analyzing data...")
        response = await analytics.process_message("load data from sample_sales.csv and analyze it")
        if hasattr(response, 'content'):
            print(response.content)
        else:
            print(response)
        
        print("\n" + "-"*50)
        print("\n2. Natural language query...")
        response = await analytics.process_message("what are the top 3 products by revenue?")
        if hasattr(response, 'content'):
            print(response.content)
        else:
            print(response)
            
    finally:
        await analytics.cleanup_session()


async def demo_knowledge_base_agent():
    """Demonstrate direct Knowledge Base Agent usage"""
    print("\n" + "="*60)
    print("🧠 KNOWLEDGE BASE AGENT - Document Ingestion & Semantic Search")
    print("="*60)
    
    kb = KnowledgeBaseAgent.create_simple(user_id="demo_user")
    
    try:
        # Note: This will show what the KB agent response looks like
        # even if vector database isn't configured
        print("\n1. Attempting knowledge base ingestion...")
        response = await kb.process_message("ingest sample_sales.csv into knowledge base called 'sales_data'")
        if hasattr(response, 'content'):
            print(response.content)
        else:
            print(response)
        
        print("\n" + "-"*50)
        print("\n2. Attempting semantic search...")
        response = await kb.process_message("search for information about laptops in sales_data knowledge base")
        if hasattr(response, 'content'):
            print(response.content)
        else:
            print(response)
            
    finally:
        await kb.cleanup_session()


async def demo_database_agent():
    """Demonstrate direct Database Agent usage"""
    print("\n" + "="*60)
    print("💾 DATABASE AGENT - Database Operations & SQL Queries")
    print("="*60)
    
    db = DatabaseAgent.create_simple(user_id="demo_user")
    
    try:
        print("\n1. Checking database connection status...")
        response = await db.process_message("show database status")
        if hasattr(response, 'content'):
            print(response.content)
        else:
            print(response)
        
        print("\n" + "-"*50)
        print("\n2. Attempting database ingestion...")
        response = await db.process_message("ingest sample_sales.csv into database")
        if hasattr(response, 'content'):
            print(response.content)
        else:
            print(response)
            
    finally:
        await db.cleanup_session()


async def demo_targeted_commands():
    """Show how to target specific functionality with precise commands"""
    print("\n" + "="*60)
    print("🎯 TARGETED COMMANDS - Avoiding Routing Ambiguity")
    print("="*60)
    
    await create_sample_data()
    
    print("\n📊 Analytics Agent - Data Analysis:")
    print("   Command: 'load data from sample_sales.csv and analyze it'")
    analytics = AnalyticsAgent.create_simple(user_id="analytics_demo")
    response = await analytics.process_message("load data from sample_sales.csv and analyze it")
    print(f"   Response: {(response.content if hasattr(response, 'content') else response)[:100]}...")
    await analytics.cleanup_session()
    
    print("\n🧠 Knowledge Base Agent - Document Ingestion:")
    print("   Command: 'create knowledge base called sales_analysis'")
    kb = KnowledgeBaseAgent.create_simple(user_id="kb_demo")
    response = await kb.process_message("create knowledge base called sales_analysis")
    print(f"   Response: {(response.content if hasattr(response, 'content') else response)[:100]}...")
    await kb.cleanup_session()
    
    print("\n💾 Database Agent - Connection Check:")
    print("   Command: 'check database connection status'")
    db = DatabaseAgent.create_simple(user_id="db_demo")
    response = await db.process_message("check database connection status")
    print(f"   Response: {(response.content if hasattr(response, 'content') else response)[:100]}...")
    await db.cleanup_session()


async def interactive_direct_mode():
    """Interactive mode using direct agent selection"""
    print("\n" + "="*60)
    print("🎮 INTERACTIVE DIRECT MODE")
    print("="*60)
    print("Choose your agent directly - no routing ambiguity!")
    print("\nAvailable agents:")
    print("  1. Analytics Agent (data analysis, CSV processing)")
    print("  2. Knowledge Base Agent (document ingestion, semantic search)")
    print("  3. Database Agent (SQL queries, database operations)")
    print("  4. Exit")
    
    await create_sample_data()
    
    # Keep agents initialized for session continuity
    agents = {
        'analytics': AnalyticsAgent.create_simple(user_id="interactive_analytics"),
        'knowledge_base': KnowledgeBaseAgent.create_simple(user_id="interactive_kb"),
        'database': DatabaseAgent.create_simple(user_id="interactive_db")
    }
    
    try:
        while True:
            print("\n" + "-"*50)
            choice = input("\nSelect agent (1-4): ").strip()
            
            if choice == "4":
                break
            elif choice in ["1", "2", "3"]:
                agent_map = {
                    "1": ("analytics", "📊 Analytics Agent"),
                    "2": ("knowledge_base", "🧠 Knowledge Base Agent"),
                    "3": ("database", "💾 Database Agent")
                }
                
                agent_key, agent_name = agent_map[choice]
                agent = agents[agent_key]
                
                print(f"\n{agent_name} selected.")
                query = input("Your command: ").strip()
                
                if query:
                    try:
                        print("\nProcessing...")
                        response = await agent.process_message(query)
                        print(f"\n{agent_name} Response:")
                        if hasattr(response, 'content'):
                            print(response.content)
                        else:
                            print(response)
                    except Exception as e:
                        print(f"\n❌ Error: {e}")
            else:
                print("Invalid choice. Please select 1-4.")
                
    finally:
        # Cleanup all agents
        for agent in agents.values():
            await agent.cleanup_session()
        print("\n✅ All sessions cleaned up")


def show_usage_guide():
    """Show usage guide for direct agent approach"""
    print("""
🎯 DIRECT AGENT USAGE GUIDE
==========================

Instead of relying on moderator routing, use agents directly for their specialized roles:

📊 ANALYTICS AGENT - Best for:
   • CSV/Excel data analysis
   • Statistical queries  
   • Data visualization recommendations
   • Schema exploration
   
   Example commands:
   • "load data from sales.csv and analyze it"
   • "what are the top 10 products by revenue?"
   • "show me summary statistics"

🧠 KNOWLEDGE BASE AGENT - Best for:
   • Document ingestion for semantic search
   • Text-based queries
   • Information retrieval
   • Document storage
   
   Example commands:
   • "create knowledge base called 'my_docs'"
   • "ingest document.pdf into my_docs"
   • "search for information about X in my_docs"

💾 DATABASE AGENT - Best for:
   • Database connections (MongoDB, MySQL, PostgreSQL)
   • SQL queries
   • Database schema operations
   • Structured data ingestion
   
   Example commands:
   • "connect to mongodb://localhost:27017"
   • "show tables in database"
   • "ingest data.json into mongodb collection"

🎮 INTERACTIVE MODE:
   python direct_agent_example.py interactive

📋 DEMO ALL AGENTS:
   python direct_agent_example.py demo
   
🎯 TARGETED COMMANDS:
   python direct_agent_example.py targeted
""")


async def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        show_usage_guide()
        return
    
    mode = sys.argv[1].lower()
    
    if mode == "demo":
        await demo_analytics_agent()
        await demo_knowledge_base_agent() 
        await demo_database_agent()
    elif mode == "targeted":
        await demo_targeted_commands()
    elif mode == "interactive":
        await interactive_direct_mode()
    elif mode == "analytics":
        await demo_analytics_agent()
    elif mode == "knowledge":
        await demo_knowledge_base_agent()
    elif mode == "database":
        await demo_database_agent()
    else:
        print(f"Unknown mode: {mode}")
        show_usage_guide()


if __name__ == "__main__":
    asyncio.run(main())