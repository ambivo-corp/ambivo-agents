#!/usr/bin/env python3
"""
Simple Database → Analytics Workflow Test
==========================================

Quick test script for both MySQL and MongoDB integrations.

Run with:
    python examples/test_database_analytics_simple.py

Prerequisites:
- pip install ambivo-agents[database]
- MySQL: localhost:3306, root/test_root, academicworld database
- MongoDB: mongodb://127.0.0.1:27017
"""

import asyncio
import sys
from pathlib import Path


async def test_mysql_workflow():
    """Simple MySQL workflow test"""
    
    print("🔍 Testing MySQL → Analytics Workflow")
    print("-" * 40)
    
    try:
        from ambivo_agents import ModeratorAgent
        
        # Create moderator with database capabilities
        moderator, context = ModeratorAgent.create(
            user_id="mysql_simple_test",
            enabled_agents=["database_agent", "analytics", "assistant"]
        )
        
        print("✅ ModeratorAgent created")
        
        # Test MySQL connection
        response = await moderator.chat(
            "Connect to MySQL database at localhost:3306, database: academicworld, username: root, password: test_root"
        )
        print(f"Connection: {response[:100]}...")
        
        # Test schema query
        response = await moderator.chat("Show me the database schema")
        print(f"Schema: {response[:100]}...")
        
        # Test analytics workflow
        response = await moderator.chat(
            "Query some data and create visualizations for analysis"
        )
        print(f"Analytics: {response[:150]}...")
        
        await moderator.cleanup_session()
        print("✅ MySQL test completed\n")
        
    except Exception as e:
        print(f"❌ MySQL test failed: {e}\n")


async def test_mongodb_workflow():
    """Simple MongoDB workflow test"""
    
    print("🔍 Testing MongoDB → Analytics Workflow")
    print("-" * 40)
    
    try:
        from ambivo_agents import ModeratorAgent
        
        # Create moderator with database capabilities
        moderator, context = ModeratorAgent.create(
            user_id="mongodb_simple_test",
            enabled_agents=["database_agent", "analytics", "assistant"]
        )
        
        print("✅ ModeratorAgent created")
        
        # Test MongoDB connection
        response = await moderator.chat(
            "Connect to MongoDB using URI mongodb://127.0.0.1:27017"
        )
        print(f"Connection: {response[:100]}...")
        
        # Test database exploration
        response = await moderator.chat("Show me available databases and collections")
        print(f"Collections: {response[:100]}...")
        
        # Test basic query
        response = await moderator.chat(
            "Explore the database structure for analytics"
        )
        print(f"Exploration: {response[:150]}...")
        
        await moderator.cleanup_session()
        print("✅ MongoDB test completed\n")
        
    except Exception as e:
        print(f"❌ MongoDB test failed: {e}\n")


async def test_direct_database_agents():
    """Test database agents directly"""
    
    print("🔧 Testing Direct Database Agent Usage")
    print("-" * 40)
    
    try:
        from ambivo_agents.agents.database_agent import DatabaseAgent
        
        # Test MySQL direct
        print("Testing MySQL direct connection...")
        mysql_agent = DatabaseAgent.create_simple(user_id="direct_mysql")
        
        response = await mysql_agent.chat(
            "Connect to MySQL localhost:3306 academicworld root test_root"
        )
        print(f"MySQL Direct: {response[:100]}...")
        
        await mysql_agent.cleanup_session()
        
        # Test MongoDB direct
        print("Testing MongoDB direct connection...")
        mongo_agent = DatabaseAgent.create_simple(user_id="direct_mongo")
        
        response = await mongo_agent.chat(
            "Connect to MongoDB mongodb://127.0.0.1:27017"
        )
        print(f"MongoDB Direct: {response[:100]}...")
        
        await mongo_agent.cleanup_session()
        print("✅ Direct tests completed\n")
        
    except Exception as e:
        print(f"❌ Direct tests failed: {e}\n")


def check_dependencies():
    """Check if required dependencies are available"""
    
    print("🔍 Checking Dependencies")
    print("-" * 25)
    
    issues = []
    
    try:
        import mysql.connector
        print("✅ mysql-connector-python available")
    except ImportError:
        issues.append("mysql-connector-python")
        print("❌ mysql-connector-python missing")
    
    try:
        import pymongo
        print("✅ pymongo available")
    except ImportError:
        issues.append("pymongo")
        print("❌ pymongo missing")
    
    try:
        import tabulate
        print("✅ tabulate available")
    except ImportError:
        issues.append("tabulate")
        print("❌ tabulate missing")
    
    try:
        from ambivo_agents.agents.database_agent import DatabaseAgent
        print("✅ DatabaseAgent available")
    except ImportError:
        issues.append("ambivo_agents[database]")
        print("❌ DatabaseAgent missing")
    
    if issues:
        print(f"\n⚠️ Missing dependencies: {', '.join(issues)}")
        print("Install with: pip install ambivo-agents[database]")
        return False
    
    print("\n✅ All dependencies available")
    return True


async def main():
    """Main test function"""
    
    print("🚀 Simple Database → Analytics Workflow Tests")
    print("=" * 50)
    
    # Check dependencies first
    if not check_dependencies():
        print("\n❌ Please install missing dependencies before testing")
        sys.exit(1)
    
    # Create output directories
    Path("./examples/mysql_exports").mkdir(parents=True, exist_ok=True)
    Path("./examples/mongodb_exports").mkdir(parents=True, exist_ok=True)
    
    print("\n🧪 Running Tests...")
    print("=" * 20)
    
    # Test direct agents first
    await test_direct_database_agents()
    
    # Test MySQL workflow
    await test_mysql_workflow()
    
    # Test MongoDB workflow
    await test_mongodb_workflow()
    
    print("🎉 All Tests Completed!")
    print("=" * 25)
    
    print("\n💡 Next Steps:")
    print("1. Check output directories for exported CSV files")
    print("2. Try more complex queries with analytics keywords")
    print("3. Experiment with different visualization requests")
    print("4. Check logs for detailed workflow information")
    
    print("\n🔧 Configuration Files:")
    print("- examples/mysql_test_config.yaml")
    print("- examples/mongodb_test_config.yaml")
    
    print("\n📚 Example Queries to Try:")
    print('- "Get top 10 records and create charts"')
    print('- "Analyze data trends with visualizations"')
    print('- "Export data and show statistical insights"')


if __name__ == "__main__":
    # Set up environment
    import os
    os.chdir(Path(__file__).parent.parent)  # Change to project root
    
    # Run tests
    asyncio.run(main())