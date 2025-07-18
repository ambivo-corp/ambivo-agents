from ambivo_agents import DatabaseAgent


async def test_direct_database_agent():
    """Test file ingestion using DatabaseAgent directly"""
    print("\n🔍 Testing Direct DatabaseAgent File Ingestion")
    print("=" * 60)

    # Create agent
    agent = DatabaseAgent.create_simple(user_id="test_user")

    try:
        # Connect to MongoDB (adjust URI as needed)
        print("\n1. Connecting to MongoDB...")
        response = await agent.chat("connect to mongodb://localhost:27017/test_ingestion")
        print(f"Response: {response[:200]}...")

        # Test JSON ingestion
        print("\n2. Ingesting ...")
        response = await agent.chat("ingest sample_sales.json into sample_sales collection")
        print(f"Response: {response}")

        # Test CSV ingestion
        print("\n3. Ingesting sales_data.csv...")
        response = await agent.chat("load sample_sales.csv")
        print(f"Response: {response}")

        # Query the ingested data
        print("\n4. Querying ingested data...")
        response = await agent.chat("db.sample_sales.find().limit(5)")
        print(f"Response: {response[:3000]}...")

        response = await agent.chat("db.sample_sales.count()")
        print(f"Response: {response}")

    finally:
        await agent.cleanup_session()


async def main():
    """Main function to run the database agent test"""
    await test_direct_database_agent()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())