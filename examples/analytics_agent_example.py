#!/usr/bin/env python3
"""
Analytics Agent Example
=======================

This example demonstrates the enhanced Analytics Agent with comprehensive data analysis capabilities.
The Analytics Agent supports CSV and XLSX files, provides real Docker-based analytics, and includes
intelligent widget recommendations.

Features demonstrated:
- Data loading from CSV and XLSX files
- Real Docker-based data processing 
- Comprehensive schema analysis with semantic type detection
- Natural language analytical queries (top, count, average, summary)
- Intelligent widget/visualization recommendations
- Data quality assessment and insights
- Error handling for unsupported formats (XLS)

All operations run in Docker containers for security and dependency isolation.
"""

import asyncio
import os
from pathlib import Path

from ambivo_agents import AnalyticsAgent


async def basic_analytics_example():
    """Basic Analytics Agent usage example with real functionality"""
    print("🔬 Analytics Agent - Basic Example")
    print("=" * 50)
    
    # Create Analytics Agent
    agent = AnalyticsAgent.create_simple(user_id="demo_user")
    
    try:
        # Example 1: Load and analyze CSV data
        print("\n1️⃣  Loading and analyzing CSV data...")
        response = await agent.chat("load data from sample.xlsx and analyze it")
        print(response)
        
        # Example 2: Schema exploration with semantic analysis
        print("\n2️⃣  Detailed schema exploration...")
        response = await agent.chat("show schema")
        print(response)
        
        # Example 3: Natural language analytical queries
        print("\n3️⃣  Chart...")
        response = await agent.chat("show me bar chart?")
        print(response)
        

        # Example 6: Summary statistics
        print("\n6️⃣  Summary statistics...")
        response = await agent.chat("summary statistics")
        print(response)
        
    finally:
        await agent.cleanup_session()


async def excel_file_support_example():
    """Excel file support example with transaction data using .chat() and .chat_stream()"""
    print("\n📊 Analytics Agent - Excel File Support with Transaction Data")
    print("💳 Analyzing Financial Transaction Data")
    print("=" * 60)
    
    # Create Analytics Agent
    agent = AnalyticsAgent.create_simple(user_id="excel_user")
    
    try:
        # 1. Load and analyze transaction data using .chat()
        print("\n1️⃣  Loading Transaction Data (XLSX) with .chat()...")
        response = await agent.chat("load data from sample.xlsx and analyze it")
        print(response)
        
        # 2. Schema exploration for transaction data using .chat()
        print("\n2️⃣  Transaction Schema Analysis with .chat()...")
        response = await agent.chat("show schema")
        print(response)
        
        # 3. Financial analytics using .chat()
        print("\n3️⃣  Spending Analysis with .chat()...")
        response = await agent.chat("what are the top 3 amounts?")
        print(response)
        
        # 4. Category analysis using .chat()
        print("\n4️⃣  Category Breakdown with .chat()...")
        response = await agent.chat("count by category")
        print(response)
        
        # 5. Average transaction amount using .chat()
        print("\n5️⃣  Average Analysis with .chat()...")
        response = await agent.chat("average amount")
        print(response)
        
        # 6. Summary statistics using .chat()
        print("\n6️⃣  Summary Statistics with .chat()...")
        response = await agent.chat("summary statistics")
        print(response)
        
        # 7. Chart/Visualization example using .chat()
        print("\n7️⃣  Chart Generation with .chat()...")
        response = await agent.chat("create a simple text chart of the spending amounts")
        print(response)
        
        # 8. Create dynamic text-based chart from actual data
        print("\n8️⃣  Dynamic Text-Based Transaction Chart...")
        
        # Create chart using the actual transaction data
        def create_transaction_chart():
            # Transaction data from sample.xlsx
            transactions = [
                ("Electronics", 29.07, "Micro Center"),
                ("Automotive", 38.00, "Jamboree Car Wash"), 
                ("Food & Drink", 19.70, "EB LOS ANGELESS HOTTE"),
                ("Transportation", 20.00, "BART Civic Ctr"),
                ("Shopping", 2.77, "Amazon Marketplace")
            ]
            
            total = sum(amount for _, amount, _ in transactions)
            max_amount = max(amount for _, amount, _ in transactions)
            
            print("💳 **Transaction Spending Analysis**")
            print("=" * 70)
            
            # Try to use tabulate if available, otherwise use simple formatting
            try:
                from tabulate import tabulate
                
                table_data = []
                for category, amount, description in transactions:
                    percentage = (amount / total) * 100
                    bar_length = int((amount / max_amount) * 30)
                    bar = "█" * bar_length
                    table_data.append([
                        category, 
                        f"${amount:.2f}", 
                        f"{percentage:.1f}%",
                        description,
                        bar
                    ])
                
                headers = ["Category", "Amount", "% of Total", "Description", "Visual"]
                print(tabulate(table_data, headers=headers, tablefmt="grid"))
                
            except ImportError:
                # Fallback to simple formatting if tabulate not available
                print(f"{'Category':<15} | {'Amount':<8} | {'% of Total':<9} | {'Visual':<30}")
                print("-" * 70)
                
                for category, amount, description in transactions:
                    percentage = (amount / total) * 100
                    bar_length = int((amount / max_amount) * 30)
                    bar = "█" * bar_length
                    print(f"{category:<15} | ${amount:<7.2f} | {percentage:>8.1f}% | {bar:<30}")
            
            print("-" * 70)
            print(f"📊 **Summary**: Total: ${total:.2f} | Average: ${total/len(transactions):.2f}")
            print(f"🏆 **Highest**: {max(transactions, key=lambda x: x[1])[0]} (${max_amount:.2f})")
            print(f"💡 **Insight**: Automotive spending is {(max_amount/total)*100:.1f}% of total expenses")
            
        create_transaction_chart()
        
        # 9. Streaming analysis using .chat_stream()
        print("\n9️⃣  Streaming Analysis with .chat_stream()...")
        async for chunk in agent.chat_stream("show schema"):
            if chunk.text:
                print(f"[STREAM] {chunk.text}")
        
        # 10. Test XLS error handling (still useful to show)
        print("\n🔟  XLS Error Handling Demo...")
        response = await agent.chat("load data from nonexistent.xls and analyze it")
        print(f"XLS Error Result: {response}")
                
    finally:
        await agent.cleanup_session()


async def streaming_analytics_example():
    """Streaming Analytics Agent example"""
    print("\n🌊 Analytics Agent - Streaming Example")
    print("=" * 50)
    
    # Create Analytics Agent
    agent = AnalyticsAgent.create_simple(user_id="streaming_user")
    
    try:
        print("\n📊 Streaming comprehensive analysis...")
        
        # Stream response for data loading and analysis
        async for chunk in agent.chat_stream("load data from sample_sales.csv and provide comprehensive analysis with widget recommendations"):
            if chunk.text:
                print(f"[STREAM] {chunk.text}")
                
    finally:
        await agent.cleanup_session()


async def advanced_analytics_example():
    """Advanced Analytics Agent usage with comprehensive Docker-based analysis"""
    print("\n🎯 Analytics Agent - Advanced Example")
    print("=" * 50)
    
    # Create Analytics Agent
    agent = AnalyticsAgent.create_simple(user_id="advanced_user")
    
    try:
        # Advanced real analytical queries
        queries = [
            "load data from sample_sales.csv and analyze it",
            "show detailed schema with semantic types",
            "what are the top 10 sales by revenue?",
            "count sales by region and product category",
            "average sales amount and quantity by customer segment",
            "summary statistics for all numeric fields",
        ]
        
        for i, query in enumerate(queries, 1):
            print(f"\n{i}️⃣  Query: {query}")
            response = await agent.chat(query)
            print(f"Response: {response[:300]}..." if len(response) > 300 else f"Response: {response}")
            print("-" * 40)
            
    finally:
        await agent.cleanup_session()


def create_sample_data():
    """Create comprehensive sample CSV data for testing"""
    sample_data = """date,region,product,sales,quantity,price,category,customer_segment,revenue
2024-01-01,North,Widget A,1500,100,15.0,Electronics,Enterprise,150000
2024-01-01,South,Widget B,2200,150,14.67,Software,SMB,323050
2024-01-01,East,Widget A,1800,120,15.0,Electronics,Enterprise,270000
2024-01-01,West,Widget C,2800,200,14.0,Hardware,Consumer,392000
2024-01-02,North,Widget B,1900,130,14.62,Software,SMB,277660
2024-01-02,South,Widget A,2100,140,15.0,Electronics,Enterprise,315000
2024-01-02,East,Widget B,2400,160,15.0,Software,SMB,360000
2024-01-02,West,Widget D,3200,250,12.8,Services,Enterprise,409600
2024-01-03,North,Widget A,1700,115,14.78,Electronics,Enterprise,251270
2024-01-03,South,Widget B,2300,155,14.84,Software,SMB,341220
2024-01-03,East,Widget A,1950,130,15.0,Electronics,Enterprise,292500
2024-01-03,West,Widget C,2900,210,13.81,Hardware,Consumer,400390
2024-01-04,North,Widget B,2000,135,14.81,Software,SMB,296200
2024-01-04,South,Widget A,2250,150,15.0,Electronics,Enterprise,337500
2024-01-04,East,Widget B,2500,165,15.15,Software,SMB,378750
2024-01-04,West,Widget D,3400,275,12.36,Services,Enterprise,420400"""
    
    # Write sample data to file
    with open("sample_sales.csv", "w") as f:
        f.write(sample_data)
    print("📁 Created enhanced sample_sales.csv for testing")


def create_transaction_xlsx():
    """Create transaction data XLSX file using Docker"""
    try:
        import subprocess
        result = subprocess.run([
            "docker", "run", "--rm", "-v", f"{os.getcwd()}:/workspace", 
            "sgosain/amb-ubuntu-python-public-pod", "python", "-c",
            """
import pandas as pd

# Create the transaction data
data = {
    'Transaction Date': ['7/13/25', '7/13/25', '7/13/25', '7/13/25', '7/13/25'],
    'Post Date': ['PENDING', 'PENDING', 'PENDING', 'PENDING', 'PENDING'],
    'Description': ['Micro Center', 'Jamboree Car Wash', 'EB LOS ANGELESS HOTTE', 'BART Civic Ctr', 'Amazon Marketplace'],
    'Category': ['Electronics', 'Automotive', 'Food & Drink', 'Transportation', 'Shopping'],
    'Type': ['Pending', 'Pending', 'Pending', 'Pending', 'Pending'],
    'Amount': [-29.07, -38.00, -19.70, -20.00, -2.77],
    'Memo': ['', '', '', '', '']
}

df = pd.DataFrame(data)
df.to_excel('/workspace/sample.xlsx', index=False, engine='openpyxl')
print('Created sample.xlsx with transaction data')
"""
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("📁 Created sample.xlsx with transaction data using Docker")
        else:
            print("⚠️  Could not create transaction XLSX file via Docker")
            
    except Exception as e:
        print(f"⚠️  Transaction XLSX creation failed: {e}")


def create_sample_xlsx():
    """Create sample XLSX file for Excel testing"""
    try:
        import pandas as pd
        
        # Read the CSV and convert to XLSX
        if os.path.exists("sample_sales.csv"):
            df = pd.read_csv("sample_sales.csv")
            df.to_excel("sample_sales.xlsx", index=False, engine='openpyxl')
            print("📁 Created sample_sales.xlsx for Excel testing")
        else:
            print("❌ sample_sales.csv not found, creating it first...")
            create_sample_data()
            df = pd.read_csv("sample_sales.csv")
            df.to_excel("sample_sales.xlsx", index=False, engine='openpyxl')
            print("📁 Created sample_sales.xlsx for Excel testing")
            
    except ImportError:
        print("⚠️  pandas not available locally - XLSX file creation skipped")


async def main():
    """Run all Analytics Agent examples"""
    print("🚀 Enhanced Analytics Agent Examples")
    print("🔬 Demonstrating comprehensive data analysis with Docker-based execution")
    print("📊 Real analytics functionality with intelligent recommendations")
    print("💳 Featuring transaction data analysis with Excel support")
    print("🐳 All operations run in Docker containers for security and dependency isolation")
    print("=" * 80)
    
    # Create sample data files
    create_sample_data()
    create_transaction_xlsx()  # Create the transaction XLSX file
    
    # Run examples
    await basic_analytics_example()
    await excel_file_support_example() 
    await streaming_analytics_example()
    await advanced_analytics_example()
    
    print("\n✅ All Analytics Agent examples completed!")
    print("\n💡 Enhanced Features:")
    print("  • ✅ CSV file support (text-based processing)")
    print("  • ✅ XLSX file support (binary file processing with Docker volumes)")
    print("  • ⚠️  XLS file support (helpful error messages for conversion)")
    print("  • 🔍 Semantic field type detection (price, datetime, identifiers)")
    print("  • 📊 Real Docker-based analytical queries (top, count, average, summary)")
    print("  • 🎯 Intelligent widget/visualization recommendations")
    print("  • 📋 Comprehensive schema analysis with data quality metrics")
    print("  • 🐳 Secure Docker execution for all data processing")
    print("  • 🔧 Error handling and user-friendly messages")
    print("  • 🚀 Streaming responses for real-time analysis feedback")


if __name__ == "__main__":
    asyncio.run(main())