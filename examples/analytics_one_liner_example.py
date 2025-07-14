#!/usr/bin/env python3
"""
Analytics Agent One-Liner Examples
===================================

Quick examples showing the enhanced Analytics Agent with real Docker-based functionality.
Demonstrates CSV, XLSX support, and comprehensive analytical capabilities.
"""

import asyncio
from ambivo_agents import AnalyticsAgent

# Enhanced one-liner examples for Analytics Agent
async def analytics_one_liners():
    """Enhanced one-liner examples showcasing real Analytics Agent functionality"""
    
    print("📊 Enhanced Analytics Agent One-Liners")
    print("🔬 Real Docker-based Analytics with File Support")
    print("=" * 60)
    
    # Create agent
    agent = AnalyticsAgent.create_simple()
    
    try:
        # Quick data analysis - comprehensive functionality
        result = await agent.chat("load data from sample.csv and analyze it")
        print(f"📈 CSV Analysis:\n{result}")
        
        # Quick schema check with semantic analysis
        schema = await agent.chat("show schema")
        print(f"\n📋 Schema Analysis:\n{schema}")
        
        # Docker-executed analytical queries
        top_result = await agent.chat("what are the top 3 salary records?")
        print(f"\n🏆 Top Analysis:\n{top_result}")
        
        count_result = await agent.chat("count by department")
        print(f"\n📊 Count Analysis:\n{count_result}")
        
        average_result = await agent.chat("average salary")
        print(f"\n📊 Average Analysis:\n{average_result}")
        
        summary_result = await agent.chat("summary statistics")
        print(f"\n📈 Summary Statistics:\n{summary_result}")
        
    finally:
        await agent.cleanup_session()


async def excel_one_liners():
    """One-liner examples for Excel file support"""
    
    print("\n📊 Excel File Support One-Liners")
    print("=" * 40)
    
    agent = AnalyticsAgent.create_simple()
    
    try:
        # Test XLSX file if available
        try:
            result = await agent.chat("load data from sample.xlsx and analyze it")
            print(f"📈 XLSX Analysis:\n{result}")
        except:
            print("📂 XLSX file not available for testing")
        
        # Demonstrate XLS error handling
        try:
            result = await agent.chat("load data from sample.xls and analyze it")
            print(f"🔧 XLS Result:\n{result}")
        except:
            print("⚠️  XLS file would show helpful conversion message")
        
    finally:
        await agent.cleanup_session()

# CLI usage examples
def cli_examples():
    """Examples of using Enhanced Analytics Agent via CLI"""
    print("\n🖥️  Enhanced CLI Usage Examples:")
    print("# Load and analyze CSV data:")
    print("ambivo-agents -q 'load data from sales.csv and analyze it'")
    print("")
    print("# Schema analysis with semantic types:")
    print("ambivo-agents -q 'show schema with data quality metrics'")
    print("")
    print("# Real Docker-based analytical queries:")
    print("ambivo-agents -q 'what are the top 10 sales records?'")
    print("ambivo-agents -q 'count sales by region'")
    print("ambivo-agents -q 'average revenue by customer segment'")
    print("ambivo-agents -q 'summary statistics for all fields'")
    print("")
    print("# Excel file support:")
    print("ambivo-agents -q 'load data from report.xlsx and analyze'")
    print("")
    print("# Widget recommendations:")
    print("ambivo-agents -q 'recommend visualizations for this dataset'")


async def main():
    """Run all one-liner examples"""
    await analytics_one_liners()
    await excel_one_liners()
    cli_examples()


if __name__ == "__main__":
    asyncio.run(main())