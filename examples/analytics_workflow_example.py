#!/usr/bin/env python3
"""
Enhanced Analytics Agent Workflow Example
==========================================

This example demonstrates integrating the enhanced Analytics Agent with other agents
for comprehensive data analysis workflows. Shows real Docker-based analytics,
Excel file support, and intelligent widget recommendations.

Workflow: Data Collection → Analysis → Insights → Recommendations
"""

import asyncio
import os
from ambivo_agents import ModeratorAgent, AnalyticsAgent


async def comprehensive_data_workflow():
    """Enhanced comprehensive workflow with real analytics"""
    print("🔄 Enhanced Data Analysis Workflow")
    print("🚀 Real Docker-based Analytics with Intelligence")
    print("=" * 60)
    
    # Use ModeratorAgent for intelligent routing to Analytics Agent
    moderator = ModeratorAgent.create_simple(user_id="workflow_user")
    
    try:
        # Step 1: Data loading and initial analysis
        print("\n1️⃣  Data Loading Phase - Comprehensive file analysis...")
        analysis_query = "load data from sample_sales.csv and provide comprehensive analysis with widget recommendations"
        analysis_result = await moderator.chat(analysis_query)
        print(f"📈 Analysis Result:\n{analysis_result}")
        
        # Step 2: Schema and quality assessment
        print("\n2️⃣  Schema Analysis Phase - Data quality assessment...")
        schema_query = "show detailed schema with data quality metrics and semantic types"
        schema_result = await moderator.chat(schema_query)
        print(f"📋 Schema Result:\n{schema_result}")
        
        # Step 3: Advanced analytical queries
        print("\n3️⃣  Advanced Analytics Phase - Docker-based queries...")
        analytical_queries = [
            "what are the top 5 revenue-generating records?",
            "count sales by region and customer segment", 
            "average revenue by product category",
            "summary statistics for all numeric fields"
        ]
        
        for i, query in enumerate(analytical_queries, 1):
            result = await moderator.chat(query)
            print(f"\n3.{i} Q: {query}")
            print(f"A: {result}")
            print("-" * 40)
            
    finally:
        await moderator.cleanup_session()


async def analytics_specific_workflow():
    """Direct Analytics Agent workflow with real functionality"""
    print("\n📈 Direct Analytics Agent Workflow")
    print("🔬 Real Docker-based Data Processing Pipeline")
    print("=" * 50)
    
    # Direct Analytics Agent usage
    analytics = AnalyticsAgent.create_simple(user_id="analytics_workflow")
    
    try:
        # Enhanced multi-step analysis workflow
        workflow_steps = [
            "load data from sample_sales.csv and analyze it",
            "show detailed schema with semantic types and data quality",
            "what are the top 10 highest revenue records?",
            "count records by region and product category",
            "average sales and revenue by customer segment",
            "summary statistics for price, quantity, and revenue fields"
        ]
        
        results = {}
        for i, step in enumerate(workflow_steps, 1):
            print(f"\n🔍 Step {i}: {step}")
            result = await analytics.chat(step)
            results[step] = result
            
            # Show truncated results for readability
            if len(result) > 300:
                print(f"✅ Result: {result[:300]}...\n[Truncated - Full result saved]")
            else:
                print(f"✅ Result: {result}")
            print("─" * 50)
        
        # Summary report
        print("\n📋 Workflow Execution Summary:")
        print("=" * 40)
        for i, (step, result) in enumerate(results.items(), 1):
            success = "✅ Completed" if result and "❌" not in result else "❌ Failed"
            print(f"{i}. {step[:50]}{'...' if len(step) > 50 else ''}: {success}")
            
    finally:
        await analytics.cleanup_session()


async def excel_workflow_example():
    """Excel file workflow example"""
    print("\n📊 Excel File Workflow")
    print("🔧 XLSX Support and XLS Error Handling")
    print("=" * 45)
    
    analytics = AnalyticsAgent.create_simple(user_id="excel_workflow")
    
    try:
        # Test XLSX workflow if file exists
        if os.path.exists("sample_sales.xlsx"):
            print("\n1️⃣  XLSX File Analysis Workflow...")
            xlsx_steps = [
                "load data from sample_sales.xlsx and analyze it",
                "show schema",
                "what are the top 3 sales by revenue?"
            ]
            
            for step in xlsx_steps:
                print(f"🔍 {step}")
                result = await analytics.chat(step)
                print(f"✅ {result[:200]}..." if len(result) > 200 else f"✅ {result}")
                print("-" * 30)
        else:
            print("📁 XLSX file not available - create one first using the main example")
        
        # Test XLS error handling
        print("\n2️⃣  XLS Error Handling Demonstration...")
        result = await analytics.chat("load data from sample_sales.xls and analyze it")
        print(f"🔧 XLS Result: {result}")
        
    finally:
        await analytics.cleanup_session()


async def streaming_workflow():
    """Streaming workflow for real-time analysis feedback"""
    print("\n🌊 Streaming Analytics Workflow")
    print("📡 Real-time Analysis with Live Feedback")
    print("=" * 50)
    
    analytics = AnalyticsAgent.create_simple(user_id="streaming_workflow")
    
    try:
        # Stream a comprehensive analysis
        print("\n📊 Streaming comprehensive analysis with widget recommendations...")
        
        query = "load data from sample_sales.csv and provide comprehensive analysis with widget recommendations and business insights"
        
        print("🔄 Starting stream...")
        async for chunk in analytics.chat_stream(query):
            if chunk.text:
                print(f"[📡 STREAM] {chunk.text}")
                
        print("\n✅ Streaming analysis completed!")
                
    finally:
        await analytics.cleanup_session()


def create_workflow_data():
    """Create comprehensive sample data for enhanced workflow examples"""
    # Enhanced sample data with realistic business patterns and more fields
    enhanced_data = """date,region,product,sales,quantity,price,category,customer_segment,revenue,margin,rep_id
2024-01-01,North,Widget A,1500,100,15.0,Electronics,Enterprise,150000,22.5,R001
2024-01-01,South,Widget B,2200,150,14.67,Software,SMB,323050,18.2,R002
2024-01-01,East,Widget A,1800,120,15.0,Electronics,Enterprise,270000,22.5,R003
2024-01-01,West,Widget C,2800,200,14.0,Hardware,Consumer,392000,15.8,R004
2024-01-02,North,Widget B,1900,130,14.62,Software,SMB,277660,18.2,R001
2024-01-02,South,Widget A,2100,140,15.0,Electronics,Enterprise,315000,22.5,R002
2024-01-02,East,Widget B,2400,160,15.0,Software,SMB,360000,18.2,R003
2024-01-02,West,Widget D,3200,250,12.8,Services,Enterprise,409600,25.0,R004
2024-01-03,North,Widget A,1700,115,14.78,Electronics,Enterprise,251270,22.5,R001
2024-01-03,South,Widget B,2300,155,14.84,Software,SMB,341220,18.2,R002
2024-01-03,East,Widget A,1950,130,15.0,Electronics,Enterprise,292500,22.5,R003
2024-01-03,West,Widget C,2900,210,13.81,Hardware,Consumer,400390,15.8,R004
2024-01-04,North,Widget B,2000,135,14.81,Software,SMB,296200,18.2,R001
2024-01-04,South,Widget A,2250,150,15.0,Electronics,Enterprise,337500,22.5,R002
2024-01-04,East,Widget B,2500,165,15.15,Software,SMB,378750,18.2,R003
2024-01-04,West,Widget D,3400,275,12.36,Services,Enterprise,420400,25.0,R004
2024-01-05,North,Widget C,3100,220,14.09,Hardware,Consumer,436790,15.8,R001
2024-01-05,South,Widget D,3600,290,12.41,Services,Enterprise,446760,25.0,R002
2024-01-05,East,Widget C,3000,215,13.95,Hardware,Consumer,418500,15.8,R003
2024-01-05,West,Widget A,2400,160,15.0,Electronics,Enterprise,360000,22.5,R004"""
    
    with open("sample_sales.csv", "w") as f:
        f.write(enhanced_data)
    print("📁 Created comprehensive sample_sales.csv for enhanced workflow testing")


def create_sample_xlsx():
    """Create XLSX version for Excel workflow testing"""
    try:
        # Try to create XLSX file using Docker since pandas may not be available locally
        import subprocess
        result = subprocess.run([
            "docker", "run", "--rm", "-v", f"{os.getcwd()}:/workspace", 
            "sgosain/amb-ubuntu-python-public-pod", "python", "-c",
            """
import pandas as pd
import os

if os.path.exists('/workspace/sample_sales.csv'):
    df = pd.read_csv('/workspace/sample_sales.csv')
    df.to_excel('/workspace/sample_sales.xlsx', index=False, engine='openpyxl')
    print('Created sample_sales.xlsx')
else:
    print('CSV file not found')
"""
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("📁 Created sample_sales.xlsx using Docker")
        else:
            print("⚠️  Could not create XLSX file via Docker")
            
    except Exception as e:
        print(f"⚠️  XLSX creation failed: {e}")


async def main():
    """Run all enhanced workflow examples"""
    print("🚀 Enhanced Analytics Agent Workflow Examples")
    print("🔗 Real Docker-based Analytics with Multi-Agent Integration")
    print("📊 Comprehensive File Support and Intelligent Recommendations")
    print("=" * 80)
    
    # Create comprehensive sample data
    create_workflow_data()
    create_sample_xlsx()
    
    # Run enhanced workflow examples
    await comprehensive_data_workflow()
    await analytics_specific_workflow()
    await excel_workflow_example()
    await streaming_workflow()
    
    print("\n✅ All enhanced workflow examples completed!")
    print("\n💡 Enhanced Workflow Capabilities:")
    print("  • ✅ Real Docker-based analytical processing")
    print("  • ✅ CSV and XLSX file support with proper error handling")
    print("  • ✅ Multi-agent coordination via ModeratorAgent")
    print("  • ✅ Step-by-step analysis pipelines with real results")
    print("  • ✅ Semantic field type detection and data quality metrics")
    print("  • ✅ Intelligent widget/visualization recommendations")
    print("  • ✅ Real-time streaming analysis with live feedback")
    print("  • ✅ Comprehensive business intelligence workflows")
    print("  • ✅ Advanced analytical queries (top, count, average, summary)")
    print("  • ✅ Secure containerized execution for all data processing")
    print("  • ✅ Error handling with user-friendly messages and suggestions")


if __name__ == "__main__":
    asyncio.run(main())