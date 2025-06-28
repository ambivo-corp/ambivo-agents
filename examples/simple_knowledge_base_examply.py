#!/usr/bin/env python3
"""
knowledge_base_operations.py
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

from ambivo_agents import KnowledgeBaseAgent

# Add the ambivo_agents package to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


async def main():
    kb_agent = KnowledgeBaseAgent()
    result = await kb_agent.get_answer(
        kb_name="ambivo_demo_kb",
        query="What Product and services are offered?"
    )
    print(result)

    #success = self.agent_service.delete_session(self.session_id)



if __name__ == "__main__":
    asyncio.run(main())