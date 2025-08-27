"""
Intelligent Conversation System with Multi-Source Orchestration and Quality Assessment

This script provides a complete conversation interface that uses the KnowledgeSynthesisAgent
to intelligently gather information from multiple sources and ensure high-quality responses.
"""

import asyncio
import sys
import os
from typing import Dict, Any, Optional
from datetime import datetime
import json
from pathlib import Path

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ambivo_agents.agents.knowledge_synthesis import KnowledgeSynthesisAgent, SearchStrategy
from ambivo_agents.agents.response_quality_assessor import QualityLevel
from ambivo_agents.core import AgentSession
from ambivo_agents.config.loader import load_config
import logging


class IntelligentConversationSystem:
    """
    A conversation system that uses multiple information sources
    and ensures response quality through assessment.
    """
    
    def __init__(
        self,
        user_id: str = "default_user",
        config_path: Optional[str] = None,
        quality_threshold: QualityLevel = QualityLevel.GOOD,
        enable_logging: bool = True
    ):
        """
        Initialize the intelligent conversation system.
        
        Args:
            user_id: User identifier
            config_path: Path to configuration file
            quality_threshold: Minimum acceptable quality level
            enable_logging: Enable detailed logging
        """
        self.user_id = user_id
        self.config = load_config(config_path) if config_path else None
        self.quality_threshold = quality_threshold
        
        # Setup logging
        if enable_logging:
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        self.logger = logging.getLogger(__name__)
        
        # Initialize conversation components
        self.moderator = None
        self.context = None
        self.conversation_history = []
        self.session_metadata = {
            'start_time': datetime.now().isoformat(),
            'user_id': user_id,
            'quality_threshold': quality_threshold.value
        }
    
    async def initialize(self):
        """Initialize the conversation system and agents"""
        self.logger.info("Initializing Intelligent Conversation System...")
        
        # Create enhanced moderator with quality assessment
        self.moderator, self.context = KnowledgeSynthesisAgent.create(
            user_id=self.user_id,
            config=self.config,
            auto_configure=True,
            quality_threshold=self.quality_threshold,
            max_iterations=3,
            enable_auto_scraping=True,
            max_scrape_urls=3
        )
        
        self.logger.info(f"System initialized with session ID: {self.context.session_id}")
        
        # Display welcome message
        print("\n" + "="*80)
        print("🤖 Intelligent Conversation System")
        print("="*80)
        print(f"Session ID: {self.context.session_id}")
        print(f"Quality Threshold: {self.quality_threshold.value}")
        print("\nFeatures:")
        print("- Multi-source information gathering (Knowledge Base, Web Search, Web Scraping)")
        print("- Automatic response quality assessment")
        print("- Intelligent source prioritization based on query analysis")
        print("- Iterative improvement until quality threshold is met")
        print("\nCommands:")
        print("  /help - Show this help message")
        print("  /status - Show system status and last response quality")
        print("  /sources - Show available information sources")
        print("  /history - Show conversation history")
        print("  /clear - Clear conversation history")
        print("  /config - Show current configuration")
        print("  /prefer <source> - Set source preference (kb/web/all)")
        print("  /quality - Show last response quality assessment")
        print("  /exit or /quit - Exit the system")
        print("="*80 + "\n")
    
    async def process_command(self, command: str) -> bool:
        """
        Process system commands.
        
        Args:
            command: Command string starting with /
            
        Returns:
            True if command was processed, False if it's exit command
        """
        command = command.lower().strip()
        
        if command in ['/exit', '/quit']:
            return False
        
        elif command == '/help':
            print("\n📚 Available Commands:")
            print("  /help - Show this help message")
            print("  /status - Show system status")
            print("  /sources - Show information sources status")
            print("  /history - Show conversation history")
            print("  /clear - Clear conversation history")
            print("  /config - Show current configuration")
            print("  /prefer <source> - Set source preference")
            print("    - /prefer kb - Prioritize knowledge base")
            print("    - /prefer web - Prioritize web search")
            print("    - /prefer all - Use all sources in parallel")
            print("  /quality - Show last response quality assessment")
            print("  /exit or /quit - Exit the system\n")
        
        elif command == '/status':
            print("\n📊 System Status:")
            print(f"  Session ID: {self.context.session_id}")
            print(f"  User ID: {self.user_id}")
            print(f"  Quality Threshold: {self.quality_threshold.value}")
            print(f"  Conversation Length: {len(self.conversation_history)} messages")
            print(f"  Session Started: {self.session_metadata['start_time']}")
            if self.conversation_history:
                last_entry = self.conversation_history[-1]
                if 'quality_assessment' in last_entry:
                    qa = last_entry['quality_assessment']
                    print(f"  Last Response Quality: {qa.get('quality_level', 'N/A')}")
                    print(f"  Last Confidence Score: {qa.get('confidence_score', 0):.2f}")
        
        elif command == '/sources':
            print("\n🔍 Information Sources:")
            print("  1. Knowledge Base - Curated information repository")
            print("  2. Web Search - Real-time internet search")
            print("  3. Web Scraping - Deep content extraction from URLs")
            print("\nCurrent Strategy: Adaptive (based on query analysis)")
        
        elif command == '/history':
            if not self.conversation_history:
                print("\n📜 No conversation history yet.")
            else:
                print("\n📜 Conversation History:")
                print("-" * 60)
                for i, entry in enumerate(self.conversation_history, 1):
                    print(f"\n[{i}] {entry['timestamp']}")
                    print(f"User: {entry['user_message'][:100]}...")
                    print(f"Assistant: {entry['assistant_response'][:100]}...")
                    if 'quality_assessment' in entry:
                        qa = entry['quality_assessment']
                        print(f"Quality: {qa.get('quality_level', 'N/A')} (confidence: {qa.get('confidence_score', 0):.2f})")
        
        elif command == '/clear':
            self.conversation_history = []
            await self.moderator.clear_conversation_history()
            print("\n🧹 Conversation history cleared.")
        
        elif command == '/config':
            print("\n⚙️ Current Configuration:")
            print(f"  Quality Threshold: {self.quality_threshold.value}")
            print(f"  Max Iterations: {self.moderator.max_iterations}")
            print(f"  Auto Scraping: {self.moderator.enable_auto_scraping}")
            print(f"  Max Scrape URLs: {self.moderator.max_scrape_urls}")
        
        elif command.startswith('/prefer '):
            preference = command.split(' ', 1)[1] if ' ' in command else ''
            if preference == 'kb':
                self.session_metadata['preference'] = 'knowledge_base'
                print("\n✅ Preference set: Prioritize Knowledge Base")
            elif preference == 'web':
                self.session_metadata['preference'] = 'web_search'
                print("\n✅ Preference set: Prioritize Web Search")
            elif preference == 'all':
                self.session_metadata['preference'] = 'all'
                print("\n✅ Preference set: Use all sources in parallel")
            else:
                print("\n❌ Invalid preference. Use: kb, web, or all")
        
        elif command == '/quality':
            if self.conversation_history and 'quality_assessment' in self.conversation_history[-1]:
                qa = self.conversation_history[-1]['quality_assessment']
                print("\n📊 Last Response Quality Assessment:")
                print(f"  Quality Level: {qa.get('quality_level', 'N/A')}")
                print(f"  Confidence Score: {qa.get('confidence_score', 0):.2f}")
                print(f"  Sources Used: {', '.join(qa.get('sources_used', []))}")
                
                if qa.get('strengths'):
                    print(f"\n  ✅ Strengths:")
                    for strength in qa['strengths']:
                        print(f"    - {strength}")
                
                if qa.get('weaknesses'):
                    print(f"\n  ⚠️ Weaknesses:")
                    for weakness in qa['weaknesses']:
                        print(f"    - {weakness}")
            else:
                print("\n📊 No quality assessment available yet.")
        
        else:
            print(f"\n❌ Unknown command: {command}")
            print("Type /help for available commands.")
        
        return True
    
    async def process_message(self, message: str) -> Dict[str, Any]:
        """
        Process a user message and return response with quality assessment.
        
        Args:
            message: User's message
            
        Returns:
            Response dictionary with quality assessment
        """
        # Prepare user preferences
        user_preferences = {}
        if 'preference' in self.session_metadata:
            user_preferences['prioritize'] = self.session_metadata['preference']
        
        # Process message through enhanced moderator
        self.logger.info(f"Processing message: {message[:50]}...")
        
        print("\n🔄 Processing your query...")
        print("  1️⃣ Analyzing query to determine optimal search strategy...")
        
        result = await self.moderator.process_message(
            message,
            user_preferences=user_preferences
        )
        
        # Display progress information
        if 'query_analysis' in result:
            qa = result['query_analysis']
            print(f"  2️⃣ Strategy selected: {qa.get('strategy_used', 'adaptive')}")
            print(f"  3️⃣ Consulting {qa.get('sources_consulted', 0)} information sources...")
        
        if 'quality_assessment' in result:
            quality = result['quality_assessment']
            print(f"  4️⃣ Response quality: {quality.get('quality_level', 'unknown')} (confidence: {quality.get('confidence_score', 0):.2f})")
        
        # Store in conversation history
        history_entry = {
            'timestamp': datetime.now().isoformat(),
            'user_message': message,
            'assistant_response': result.get('response', ''),
            'quality_assessment': result.get('quality_assessment', {}),
            'query_analysis': result.get('query_analysis', {}),
            'metadata': result.get('metadata', {})
        }
        self.conversation_history.append(history_entry)
        
        return result
    
    async def run(self):
        """Run the interactive conversation loop"""
        await self.initialize()
        
        try:
            while True:
                # Get user input
                try:
                    user_input = input("\n💬 You: ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\n\n👋 Goodbye!")
                    break
                
                if not user_input:
                    continue
                
                # Check for commands
                if user_input.startswith('/'):
                    if not await self.process_command(user_input):
                        print("\n👋 Thank you for using the Intelligent Conversation System!")
                        break
                    continue
                
                # Process user message
                try:
                    result = await self.process_message(user_input)
                    
                    # Display response
                    print(f"\n🤖 Assistant: {result.get('response', 'No response generated.')}")
                    
                    # Display quality indicator
                    if 'quality_assessment' in result:
                        quality = result['quality_assessment']
                        quality_level = quality.get('quality_level', 'unknown')
                        confidence = quality.get('confidence_score', 0)
                        
                        # Quality indicator emoji
                        quality_emoji = {
                            'excellent': '🌟',
                            'good': '✅',
                            'fair': '⚠️',
                            'poor': '❌',
                            'unacceptable': '🚫'
                        }.get(quality_level, '❓')
                        
                        print(f"\n{quality_emoji} Response Quality: {quality_level} (confidence: {confidence:.2%})")
                        
                        # Show sources used
                        if quality.get('sources_used'):
                            sources_display = ', '.join(quality['sources_used'])
                            print(f"📚 Sources: {sources_display}")
                
                except Exception as e:
                    self.logger.error(f"Error processing message: {e}")
                    print(f"\n❌ Error: {str(e)}")
                    print("Please try again or rephrase your question.")
        
        finally:
            # Cleanup
            await self.cleanup()
    
    async def cleanup(self):
        """Clean up resources"""
        self.logger.info("Cleaning up conversation system...")
        
        # Save conversation history if needed
        if self.conversation_history:
            history_file = f"conversation_history_{self.context.session_id}.json"
            try:
                with open(history_file, 'w') as f:
                    json.dump({
                        'session_metadata': self.session_metadata,
                        'conversation_history': self.conversation_history
                    }, f, indent=2, default=str)
                print(f"\n💾 Conversation history saved to: {history_file}")
            except Exception as e:
                self.logger.error(f"Failed to save conversation history: {e}")
        
        # Cleanup moderator
        if self.moderator:
            await self.moderator.cleanup_session()
        
        self.logger.info("Conversation system cleaned up successfully")


async def main():
    """Main entry point for the intelligent conversation system"""
    print("\n" + "="*80)
    print("🚀 Intelligent Conversation System with Quality Assessment")
    print("="*80)
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Intelligent Conversation System')
    parser.add_argument('--user-id', default='default_user', help='User identifier')
    parser.add_argument('--config', help='Path to configuration file')
    parser.add_argument('--quality', default='good', 
                       choices=['excellent', 'good', 'fair', 'poor'],
                       help='Minimum quality threshold')
    parser.add_argument('--no-logging', action='store_true', help='Disable logging')
    
    args = parser.parse_args()
    
    # Map quality string to enum
    quality_map = {
        'excellent': QualityLevel.EXCELLENT,
        'good': QualityLevel.GOOD,
        'fair': QualityLevel.FAIR,
        'poor': QualityLevel.POOR
    }
    quality_threshold = quality_map[args.quality]
    
    # Create and run the conversation system
    system = IntelligentConversationSystem(
        user_id=args.user_id,
        config_path=args.config,
        quality_threshold=quality_threshold,
        enable_logging=not args.no_logging
    )
    
    try:
        await system.run()
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())