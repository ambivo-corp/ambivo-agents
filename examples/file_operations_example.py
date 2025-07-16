#!/usr/bin/env python3
"""
Example demonstrating file operations capabilities inherited by all agents
"""

import asyncio
from ambivo_agents.agents.assistant import AssistantAgent
from ambivo_agents.agents.moderator import ModeratorAgent


async def basic_file_operations():
    """Demonstrate basic file operations available to all agents"""
    print("📁 Basic File Operations Example")
    print("=" * 50)
    
    # Any agent can use file operations
    agent = AssistantAgent.create_simple(user_id="demo_user")
    
    try:
        # 1. Read a local file
        print("\n1. Reading local file...")
        result = await agent.read_file("examples/sample.csv")
        if result['success']:
            print(f"✅ File read: {result['size']} bytes")
            print(f"Content preview: {result['content'][:100]}...")
        else:
            print(f"File not found, creating sample file...")
            # Create a sample file for demo
            with open("examples/sample.csv", "w") as f:
                f.write("name,age,city\nAlice,30,New York\nBob,25,San Francisco\nCharlie,35,Chicago")
            
            # Try reading again
            result = await agent.read_file("examples/sample.csv")
            if result['success']:
                print(f"✅ Sample file read: {result['size']} bytes")
        
        # 2. Parse the content
        print("\n2. Parsing CSV content...")
        if result['success']:
            parse_result = await agent.parse_file_content(result['content'], 'csv')
            if parse_result['success']:
                print(f"✅ Parsed CSV: {parse_result['row_count']} rows")
                print(f"Columns: {parse_result['columns']}")
                print(f"Data: {parse_result['data']}")
        
        # 3. Convert CSV to JSON
        print("\n3. Converting CSV to JSON...")
        if 'parse_result' in locals() and parse_result['success']:
            json_result = await agent.convert_csv_to_json(result['content'])
            if json_result['success']:
                print(f"✅ Converted to JSON: {json_result['rows']} objects")
                print(f"JSON preview: {json_result['json_string'][:200]}...")
        
        # 4. Convert JSON back to CSV
        print("\n4. Converting JSON back to CSV...")
        if 'json_result' in locals() and json_result['success']:
            csv_result = await agent.convert_json_to_csv(json_result['json'])
            if csv_result['success']:
                print(f"✅ Converted back to CSV: {csv_result['rows']} rows")
                print(f"CSV preview:\n{csv_result['csv'][:200]}...")
        
        # 5. Read and parse in one operation
        print("\n5. Combined read and parse...")
        combined_result = await agent.read_and_parse_file("examples/sample.csv")
        if combined_result['success'] and combined_result['parsed']:
            print(f"✅ Combined operation successful")
            print(f"File info: {combined_result['size']} bytes, {combined_result['content_type']}")
            print(f"Parse info: {combined_result['parse_result']['type']}, {combined_result['parse_result']['row_count']} rows")
            
    finally:
        await agent.cleanup_session()


async def url_file_operations():
    """Demonstrate reading files from URLs"""
    print("\n\n🌐 URL File Operations Example")
    print("=" * 50)
    
    agent = AssistantAgent.create_simple(user_id="demo_user")
    
    try:
        # Read a public JSON file
        print("\n1. Reading JSON from URL...")
        url = "https://jsonplaceholder.typicode.com/users/1"
        
        try:
            result = await agent.read_file(url)
            if result['success']:
                print(f"✅ URL read successful: {result['size']} bytes")
                print(f"Content type: {result['content_type']}")
                
                # Parse the JSON
                parse_result = await agent.parse_file_content(result['content'], 'json')
                if parse_result['success']:
                    print(f"✅ JSON parsed: {parse_result['type']}")
                    print(f"Data keys: {list(parse_result['data'].keys()) if isinstance(parse_result['data'], dict) else 'Not a dict'}")
                    
        except Exception as e:
            print(f"⚠️  URL test skipped (network/dependency issue): {e}")
            
    finally:
        await agent.cleanup_session()


async def moderator_file_workflow():
    """Show how ModeratorAgent can use file operations in workflows"""
    print("\n\n🤖 ModeratorAgent File Workflow Example")
    print("=" * 50)
    
    moderator, context = ModeratorAgent.create(user_id="demo_user")
    
    try:
        # ModeratorAgent inherits all file operations too
        print("\n1. ModeratorAgent reading file...")
        result = await moderator.read_file("examples/sample.csv")
        if result['success']:
            print(f"✅ ModeratorAgent read file: {result['size']} bytes")
            
            # Convert to JSON for analytics
            json_result = await moderator.convert_csv_to_json(result['content'])
            if json_result['success']:
                print(f"✅ Converted for analytics: {len(json_result['json'])} records")
                
                # Now the moderator could route this to analytics agent
                # or database agent for further processing
                print("💡 Data ready for routing to analytics or database agents")
                
    finally:
        await moderator.cleanup_session()


async def real_world_example():
    """Real-world example: Processing a data file"""
    print("\n\n🚀 Real-World Example: Data Processing Pipeline")
    print("=" * 50)
    
    agent = AssistantAgent.create_simple(user_id="demo_user")
    
    try:
        # Create a more complex sample file
        import json
        sample_data = [
            {"id": 1, "product": "Laptop", "price": 999.99, "category": "Electronics", "in_stock": True},
            {"id": 2, "product": "Book", "price": 19.99, "category": "Education", "in_stock": True},
            {"id": 3, "product": "Coffee", "price": 4.99, "category": "Food", "in_stock": False},
            {"id": 4, "product": "Monitor", "price": 299.99, "category": "Electronics", "in_stock": True}
        ]
        
        with open("examples/products.json", "w") as f:
            json.dump(sample_data, f, indent=2)
        
        print("Created sample products.json file")
        
        # Step 1: Read and analyze the file
        print("\n1. Reading and analyzing products.json...")
        result = await agent.read_and_parse_file("examples/products.json")
        
        if result['success'] and result['parsed']:
            data = result['parse_result']['data']
            print(f"✅ Loaded {len(data)} products")
            
            # Step 2: Filter and transform data
            print("\n2. Processing data...")
            in_stock_products = [p for p in data if p['in_stock']]
            electronics = [p for p in data if p['category'] == 'Electronics']
            
            print(f"📊 Analysis:")
            print(f"   - Total products: {len(data)}")
            print(f"   - In stock: {len(in_stock_products)}")
            print(f"   - Electronics: {len(electronics)}")
            print(f"   - Average price: ${sum(p['price'] for p in data) / len(data):.2f}")
            
            # Step 3: Convert to CSV for export
            print("\n3. Converting to CSV for export...")
            csv_result = await agent.convert_json_to_csv(data)
            
            if csv_result['success']:
                print(f"✅ Converted to CSV: {csv_result['rows']} rows, {len(csv_result['columns'])} columns")
                
                # Save the CSV
                with open("examples/products_export.csv", "w") as f:
                    f.write(csv_result['csv'])
                
                print("💾 Saved to products_export.csv")
                
                # Step 4: Create filtered JSON for in-stock items
                print("\n4. Creating filtered dataset...")
                filtered_json = await agent.convert_csv_to_json(csv_result['csv'])
                
                if filtered_json['success']:
                    # Filter for in-stock only
                    filtered_data = [item for item in filtered_json['json'] if item['in_stock']]
                    
                    with open("examples/in_stock_products.json", "w") as f:
                        json.dump(filtered_data, f, indent=2)
                    
                    print(f"💾 Saved {len(filtered_data)} in-stock products to in_stock_products.json")
        
        print("\n🎉 Data processing pipeline complete!")
        print("Files created:")
        print("  - examples/products.json (original)")
        print("  - examples/products_export.csv (converted)")
        print("  - examples/in_stock_products.json (filtered)")
        
    finally:
        await agent.cleanup_session()


async def main():
    """Run all examples"""
    print("🎯 File Operations Examples for All Agents")
    print("=" * 60)
    
    await basic_file_operations()
    await url_file_operations()
    await moderator_file_workflow()
    await real_world_example()
    
    print("\n\n✅ All examples completed!")
    print("\n💡 Key takeaways:")
    print("  1. All agents inherit file reading capabilities from BaseAgent")
    print("  2. Support for local files and URLs")
    print("  3. Automatic parsing for JSON, CSV, XML, YAML")
    print("  4. Built-in format conversion (JSON ↔ CSV)")
    print("  5. Graceful handling of missing dependencies")
    print("  6. Can be used in any agent workflow")


if __name__ == "__main__":
    asyncio.run(main())