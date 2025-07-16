#!/usr/bin/env python3
"""
MongoDB File Insertion Example - Ambivo Agents

This example demonstrates how to insert a JSON file into a local MongoDB database
using the Ambivo Agents DatabaseAgent with natural language commands.

Prerequisites:
1. MongoDB running locally on default port (27017)
2. Ambivo Agents installed with database support: pip install ambivo-agents[database]
3. Configuration set up with MongoDB credentials

Author: Hemant Gosain 'Sunny'
Company: Ambivo
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add the parent directory to the path to import ambivo_agents
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from ambivo_agents import DatabaseAgent
    print("✅ DatabaseAgent imported successfully")
except ImportError as e:
    print(f"❌ Failed to import DatabaseAgent: {e}")
    print("💡 Install with: pip install ambivo-agents[database]")
    sys.exit(1)


async def basic_file_insertion_example():
    """Basic example using DatabaseAgent directly"""
    print("\n" + "="*60)
    print("🗄️  BASIC FILE INSERTION EXAMPLE")
    print("="*60)
    
    # Create DatabaseAgent
    try:
        agent = DatabaseAgent.create_simple(user_id="mongodb_demo_user")
        print("✅ DatabaseAgent created successfully")
    except Exception as e:
        print(f"❌ Failed to create DatabaseAgent: {e}")
        return False
    
    try:
        # Step 1: Connect to local MongoDB
        print("\n📡 Step 1: Connecting to local MongoDB...")
        connection_response = await agent.chat(
            "connect to mongodb://localhost:27017 database company_db"
        )
        print(f"Connection Response: {connection_response}")
        
        # Step 2: Insert sample data file
        print("\n📄 Step 2: Inserting sample_data.json into employees collection...")
        
        # Get the path to sample_data.json
        sample_file_path = Path(__file__).parent / "sample_data.json"
        
        insertion_response = await agent.chat(
            f"insert file {sample_file_path} into employees collection"
        )
        print(f"Insertion Response: {insertion_response}")
        
        # Step 3: Verify the data was inserted
        print("\n🔍 Step 3: Verifying inserted data...")
        verify_response = await agent.chat("count documents in employees collection")
        print(f"Count Response: {verify_response}")
        
        # Step 4: Query some data
        print("\n📊 Step 4: Querying inserted data...")
        query_response = await agent.chat("find first 3 documents in employees collection")
        print(f"Query Response: {query_response}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during file insertion: {e}")
        return False
    finally:
        # Cleanup
        await agent.cleanup_session()
        print("🧹 Agent session cleaned up")


async def natural_language_insertion_example():
    """Example using natural language commands"""
    print("\n" + "="*60)
    print("💬 NATURAL LANGUAGE INSERTION EXAMPLE")
    print("="*60)
    
    agent = DatabaseAgent.create_simple(user_id="nlp_demo_user")
    
    try:
        # Single natural language command for everything
        sample_file_path = Path(__file__).parent / "sample_data.json"
        
        print("🗣️  Using single natural language command...")
        response = await agent.chat(
            f"connect to mongodb://localhost:27017/company_db and insert file {sample_file_path} into employees collection"
        )
        print(f"Response: {response}")
        
        # Query with natural language
        print("\n🗣️  Querying with natural language...")
        query_response = await agent.chat("show me all employees in the engineering department")
        print(f"Engineering Employees: {query_response}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        await agent.cleanup_session()


async def cli_command_examples():
    """Show CLI command examples"""
    print("\n" + "="*60)
    print("⌨️  CLI COMMAND EXAMPLES")
    print("="*60)
    
    sample_file_path = Path(__file__).parent / "sample_data.json"
    
    print("🔧 You can also use these CLI commands directly:")
    print()
    
    print("1️⃣  Basic file insertion:")
    print(f'   python -c "from ambivo_agents.cli import main; main()" -- chat \\')
    print(f'     "insert file {sample_file_path} into mongodb database mongodb://localhost:27017/company_db"')
    print()
    
    print("2️⃣  Interactive mode:")
    print('   python -c "from ambivo_agents.cli import main; main()" -- interactive')
    print('   Then type: insert file examples/sample_data.json into mongodb://localhost:27017/company_db')
    print()
    
    print("3️⃣  With collection specification:")
    print(f'   python -c "from ambivo_agents.cli import main; main()" -- chat \\')
    print(f'     "connect to mongodb://localhost:27017/company_db and insert {sample_file_path} into employees collection"')


def check_prerequisites():
    """Check if prerequisites are met"""
    print("🔍 Checking prerequisites...")
    
    # Check if sample data file exists
    sample_file = Path(__file__).parent / "sample_data.json"
    if not sample_file.exists():
        print(f"❌ Sample data file not found: {sample_file}")
        return False
    else:
        print(f"✅ Sample data file found: {sample_file}")
    
    # Check if file contains valid JSON
    try:
        with open(sample_file) as f:
            data = json.load(f)
        print(f"✅ Sample data is valid JSON with {len(data)} records")
    except Exception as e:
        print(f"❌ Invalid JSON in sample file: {e}")
        return False
    
    # Note about MongoDB
    print("⚠️  Note: This example assumes MongoDB is running on localhost:27017")
    print("   If MongoDB is not running, the connection will fail")
    
    return True


async def main():
    """Main function demonstrating MongoDB file insertion"""
    print("🗄️  AMBIVO AGENTS - MONGODB FILE INSERTION EXAMPLE")
    print("="*60)
    
    # Check prerequisites
    if not check_prerequisites():
        print("❌ Prerequisites not met. Exiting.")
        return
    
    print("\n📋 This example will:")
    print("1. Connect to local MongoDB (mongodb://localhost:27017)")
    print("2. Insert sample_data.json into a 'employees' collection")
    print("3. Verify the insertion with queries")
    print("4. Show CLI command alternatives")
    
    # Ask user if they want to proceed
    try:
        proceed = input("\n❓ Proceed with the example? (y/N): ").strip().lower()
        if proceed not in ['y', 'yes']:
            print("👋 Example cancelled by user")
            return
    except KeyboardInterrupt:
        print("\n👋 Example cancelled by user")
        return
    
    # Run examples
    success1 = await basic_file_insertion_example()
    
    if success1:
        # Ask if user wants to see natural language example
        try:
            proceed = input("\n❓ Run natural language example? (y/N): ").strip().lower()
            if proceed in ['y', 'yes']:
                await natural_language_insertion_example()
        except KeyboardInterrupt:
            print("\n👋 Skipping natural language example")
    
    # Show CLI examples
    await cli_command_examples()
    
    print("\n" + "="*60)
    print("✅ EXAMPLE COMPLETE")
    print("="*60)
    print("📚 Key takeaways:")
    print("  • DatabaseAgent can read and parse JSON files automatically")
    print("  • Natural language commands work for database operations")
    print("  • Both programmatic and CLI interfaces are available")
    print("  • MongoDB URIs are parsed and used for connections")
    print("  • File paths are resolved from multiple locations")
    print()
    print("🔗 Next steps:")
    print("  • Try with your own JSON/CSV files")
    print("  • Use different MongoDB databases and collections")
    print("  • Combine with AnalyticsAgent for data analysis")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Example interrupted by user")
    except Exception as e:
        print(f"\n❌ Example failed: {e}")
        import traceback
        traceback.print_exc()