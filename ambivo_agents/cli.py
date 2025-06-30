#!/usr/bin/env python3
"""
ModeratorAgent CLI - Command Line Interface for the Ambivo ModeratorAgent

A comprehensive CLI tool for interacting with the ModeratorAgent that orchestrates
multiple specialized agents for various tasks including web search, knowledge base
operations, media editing, YouTube downloads, and more.

Features:
- Interactive chat interface with the ModeratorAgent
- Configuration management and validation
- Agent status monitoring and debugging
- Session management with conversation history
- Automated testing capabilities
- Multi-mode operation (interactive, single query, test mode)

Requirements:
- agent_config.yaml must be present in the current directory
- All required dependencies must be installed
- Redis server running (if configured)

Author: Hemant Gosain 'Sunny'
Company: Ambivo
Email: sgosain@ambivo.com
License: MIT
"""

import asyncio
import argparse
import json
import os
import sys
import time
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import signal

# Configure logging before other imports
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Import ModeratorAgent and related components
try:
    from ambivo_agents.agents.moderator import ModeratorAgent
    from ambivo_agents.config.loader import load_config, ConfigurationError
    from ambivo_agents.core.base import AgentContext

    MODERATOR_AVAILABLE = True
except ImportError as e:
    print(f"❌ ModeratorAgent not available: {e}")
    print("💡 Make sure ambivo_agents package is installed and configured properly")
    MODERATOR_AVAILABLE = False
    sys.exit(1)


class ModeratorCLI:
    """Comprehensive CLI for ModeratorAgent interactions"""

    def __init__(self, config_path: str = "agent_config.yaml"):
        """Initialize the CLI with configuration"""
        self.config_path = config_path
        self.config = None
        self.moderator = None
        self.context = None
        self.session_start_time = None
        self.message_count = 0
        self.conversation_history = []
        self.enabled_agents = []

        # CLI state
        self.running = True
        self.debug_mode = False
        self.quiet_mode = False

        # Load configuration
        self._load_configuration()

        # Setup signal handlers
        self._setup_signal_handlers()

    def _load_configuration(self):
        """Load and validate configuration from YAML file"""
        if not Path(self.config_path).exists():
            print(f"❌ Configuration file not found: {self.config_path}")
            print("💡 Create a configuration file using: ambivo-agents config save-sample agent_config.yaml")
            sys.exit(1)

        try:
            self.config = load_config(self.config_path)
            print(f"✅ Configuration loaded from {self.config_path}")
        except ConfigurationError as e:
            print(f"❌ Configuration error: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Failed to load configuration: {e}")
            sys.exit(1)

        # Validate required sections
        required_sections = ['agent_capabilities']
        for section in required_sections:
            if section not in self.config:
                print(f"❌ Missing required configuration section: {section}")
                sys.exit(1)

    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""

        def signal_handler(signum, frame):
            print(f"\n🔄 Received signal {signum}, initiating graceful shutdown...")
            self.running = False
            asyncio.create_task(self._shutdown())

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def _get_enabled_agents_from_config(self) -> List[str]:
        """Get enabled agents from configuration"""
        capabilities = self.config.get('agent_capabilities', {})
        enabled_agents = []

        # Always include assistant as base agent
        enabled_agents.append('assistant')

        # Add agents based on capabilities
        if capabilities.get('enable_knowledge_base', False):
            enabled_agents.append('knowledge_base')

        if capabilities.get('enable_web_search', False):
            enabled_agents.append('web_search')

        if capabilities.get('enable_code_execution', False):
            enabled_agents.append('code_executor')

        if capabilities.get('enable_media_editor', False):
            enabled_agents.append('media_editor')

        if capabilities.get('enable_youtube_download', False):
            enabled_agents.append('youtube_download')

        if capabilities.get('enable_web_scraping', False):
            enabled_agents.append('web_scraper')

        return enabled_agents

    async def _initialize_moderator(self, user_id: str = None, enabled_agents: List[str] = None):
        """Initialize the ModeratorAgent"""
        if not user_id:
            user_id = f"cli_user_{int(time.time())}"

        if not enabled_agents:
            enabled_agents = self._get_enabled_agents_from_config()

        self.enabled_agents = enabled_agents

        try:
            print("🚀 Initializing ModeratorAgent...")
            print(f"👤 User ID: {user_id}")
            print(f"🤖 Enabled agents: {', '.join(enabled_agents)}")

            # Create ModeratorAgent with enabled agents
            self.moderator, self.context = ModeratorAgent.create(
                user_id=user_id,
                tenant_id="cli_tenant",
                enabled_agents=enabled_agents
            )

            self.session_start_time = datetime.now()

            print(f"✅ ModeratorAgent initialized successfully!")
            print(f"🆔 Agent ID: {self.moderator.agent_id}")
            print(f"📋 Session ID: {self.context.session_id}")
            print(f"🗣️ Conversation ID: {self.context.conversation_id}")

            # Get and display agent status
            status = await self.moderator.get_agent_status()
            print(f"📊 Active specialized agents: {status['total_agents']}")

            if not self.quiet_mode:
                for agent_type, agent_info in status['active_agents'].items():
                    print(f"   • {agent_type}: {agent_info['status']}")

        except Exception as e:
            print(f"❌ Failed to initialize ModeratorAgent: {e}")
            if self.debug_mode:
                import traceback
                traceback.print_exc()
            sys.exit(1)

    async def _shutdown(self):
        """Graceful shutdown"""
        if self.moderator:
            try:
                print("🧹 Cleaning up ModeratorAgent session...")
                await self.moderator.cleanup_session()
                print("✅ Cleanup completed")
            except Exception as e:
                print(f"⚠️ Cleanup warning: {e}")

    def _print_banner(self):
        """Print CLI banner"""
        if self.quiet_mode:
            return

        print("=" * 70)
        print("🎛️  MODERATOR AGENT CLI")
        print("=" * 70)
        print("🤖 AI Agent Orchestrator - Route queries to specialized agents")
        print("📖 Type 'help' for commands, 'quit' to exit")
        print("🔧 Configuration loaded from:", self.config_path)
        print("=" * 70)

    def _print_help(self):
        """Print help information"""
        help_text = """
🆘 MODERATOR AGENT CLI HELP

📋 BASIC COMMANDS:
   help, h          - Show this help message
   quit, exit, bye  - Exit the CLI
   status           - Show agent status and session info
   config           - Display current configuration
   history          - Show conversation history
   clear            - Clear conversation history
   debug            - Toggle debug mode
   agents           - List active agents and their status

💬 CHAT COMMANDS:
   Just type your message and press Enter to chat with the ModeratorAgent!

   Examples:
   • "Search for latest AI trends"
   • "Download https://youtube.com/watch?v=example"
   • "Ingest document.pdf into knowledge_base"
   • "Extract audio from video.mp4"
   • "Scrape https://example.com for content"

🎯 AGENT ROUTING:
   The ModeratorAgent automatically routes your queries to appropriate agents:
   • 🔍 Web searches → WebSearchAgent
   • 📺 YouTube operations → YouTubeDownloadAgent  
   • 📚 Knowledge base → KnowledgeBaseAgent
   • 🎬 Media editing → MediaEditorAgent
   • 🕷️ Web scraping → WebScraperAgent
   • 💻 Code execution → CodeExecutorAgent
   • 💬 General chat → AssistantAgent

🔧 ADVANCED:
   Use Ctrl+C for graceful shutdown
   Session state is maintained throughout your conversation
        """
        print(help_text)

    def _format_duration(self, seconds: float) -> str:
        """Format duration in human readable format"""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            remaining_seconds = seconds % 60
            return f"{minutes}m {remaining_seconds:.1f}s"
        else:
            hours = int(seconds // 3600)
            remaining_minutes = int((seconds % 3600) // 60)
            remaining_seconds = seconds % 60
            return f"{hours}h {remaining_minutes}m {remaining_seconds:.1f}s"

    async def _handle_status_command(self):
        """Handle status command"""
        try:
            status = await self.moderator.get_agent_status()
            session_duration = time.time() - self.session_start_time.timestamp()

            print("\n📊 MODERATOR AGENT STATUS")
            print("=" * 50)
            print(f"🆔 Moderator ID: {status['moderator_id']}")
            print(f"📋 Session ID: {self.context.session_id}")
            print(f"👤 User ID: {self.context.user_id}")
            print(f"⏱️ Session Duration: {self._format_duration(session_duration)}")
            print(f"💬 Messages Processed: {self.message_count}")
            print(f"🤖 Total Agents: {status['total_agents']}")
            print(f"🎯 Enabled Agents: {', '.join(self.enabled_agents)}")
            print(f"🔀 Routing Patterns: {status['routing_patterns']}")

            print(f"\n🏃 ACTIVE AGENTS:")
            for agent_type, agent_info in status['active_agents'].items():
                agent_status = agent_info.get('status', 'unknown')
                agent_id = agent_info.get('agent_id', 'unknown')
                session_id = agent_info.get('session_id', 'unknown')

                status_emoji = "✅" if agent_status == "active" else "❌"
                print(f"   {status_emoji} {agent_type}")
                print(f"      ID: {agent_id}")
                print(f"      Session: {session_id}")
                if 'error' in agent_info:
                    print(f"      Error: {agent_info['error']}")

        except Exception as e:
            print(f"❌ Error getting status: {e}")

    def _handle_config_command(self):
        """Handle config command"""
        print("\n⚙️ CONFIGURATION")
        print("=" * 50)
        print(f"📄 Config File: {self.config_path}")

        # Agent capabilities
        capabilities = self.config.get('agent_capabilities', {})
        print(f"\n🎛️ AGENT CAPABILITIES:")
        for capability, enabled in capabilities.items():
            emoji = "✅" if enabled else "❌"
            print(f"   {emoji} {capability}: {enabled}")

        # Service configuration
        service_config = self.config.get('service', {})
        if service_config:
            print(f"\n🔧 SERVICE CONFIG:")
            for key, value in service_config.items():
                print(f"   • {key}: {value}")

        # Memory configuration
        memory_config = self.config.get('memory_management', {})
        if memory_config:
            print(f"\n🧠 MEMORY CONFIG:")
            for key, value in memory_config.items():
                if isinstance(value, dict):
                    print(f"   • {key}:")
                    for sub_key, sub_value in value.items():
                        print(f"     - {sub_key}: {sub_value}")
                else:
                    print(f"   • {key}: {value}")

    def _handle_history_command(self):
        """Handle history command"""
        if not self.conversation_history:
            print("\n📝 No conversation history yet")
            return

        print(f"\n📝 CONVERSATION HISTORY ({len(self.conversation_history)} messages)")
        print("=" * 50)

        for i, entry in enumerate(self.conversation_history[-10:], 1):  # Show last 10
            timestamp = entry['timestamp'].strftime("%H:%M:%S")
            message_type = entry['type']
            content = entry['content']

            if message_type == 'user':
                print(f"{i:2d}. [{timestamp}] 👤 You: {content}")
            else:
                agent_name = entry.get('agent', 'Assistant')
                print(f"{i:2d}. [{timestamp}] 🤖 {agent_name}: {content[:100]}{'...' if len(content) > 100 else ''}")

    async def _handle_agents_command(self):
        """Handle agents command"""
        try:
            status = await self.moderator.get_agent_status()

            print(f"\n🤖 AGENT REGISTRY")
            print("=" * 50)
            print(f"📊 Total Active Agents: {status['total_agents']}")
            print(f"🎯 Enabled Agent Types: {', '.join(self.enabled_agents)}")

            print(f"\n🏃 DETAILED AGENT STATUS:")
            for agent_type, agent_info in status['active_agents'].items():
                agent_status = agent_info.get('status', 'unknown')
                agent_id = agent_info.get('agent_id', 'unknown')

                status_emoji = "✅" if agent_status == "active" else "❌"
                print(f"\n   {status_emoji} {agent_type.upper()}")
                print(f"      🆔 Agent ID: {agent_id}")
                print(f"      📊 Status: {agent_status}")
                print(f"      📋 Session: {agent_info.get('session_id', 'unknown')}")

                if 'error' in agent_info:
                    print(f"      ❌ Error: {agent_info['error']}")

                # Add agent-specific capabilities description
                if agent_type == 'web_search':
                    print(f"      🔍 Capabilities: Web search, news search, academic search")
                elif agent_type == 'youtube_download':
                    print(f"      📺 Capabilities: YouTube video/audio download, info extraction")
                elif agent_type == 'knowledge_base':
                    print(f"      📚 Capabilities: Document ingestion, semantic search, Q&A")
                elif agent_type == 'media_editor':
                    print(f"      🎬 Capabilities: Video/audio conversion, extraction, editing")
                elif agent_type == 'web_scraper':
                    print(f"      🕷️ Capabilities: Web scraping, content extraction")
                elif agent_type == 'code_executor':
                    print(f"      💻 Capabilities: Python/Bash code execution")
                elif agent_type == 'assistant':
                    print(f"      💬 Capabilities: General conversation, help, coordination")

        except Exception as e:
            print(f"❌ Error getting agent information: {e}")

    async def _handle_clear_command(self):
        """Handle clear command"""
        self.conversation_history.clear()
        self.message_count = 0
        print("🧹 Conversation history cleared")

    def _handle_debug_command(self):
        """Handle debug command"""
        self.debug_mode = not self.debug_mode
        status = "enabled" if self.debug_mode else "disabled"
        print(f"🐛 Debug mode {status}")

        # Update logging level
        if self.debug_mode:
            logging.getLogger().setLevel(logging.DEBUG)
            logging.getLogger("ambivo_agents").setLevel(logging.DEBUG)
        else:
            logging.getLogger().setLevel(logging.INFO)
            logging.getLogger("ambivo_agents").setLevel(logging.INFO)

    async def _process_user_input(self, user_input: str) -> bool:
        """Process user input and return True if should continue"""
        user_input = user_input.strip()

        if not user_input:
            return True

        # Handle commands
        if user_input.lower() in ['quit', 'exit', 'bye']:
            return False
        elif user_input.lower() in ['help', 'h']:
            self._print_help()
            return True
        elif user_input.lower() == 'status':
            await self._handle_status_command()
            return True
        elif user_input.lower() == 'config':
            self._handle_config_command()
            return True
        elif user_input.lower() == 'history':
            self._handle_history_command()
            return True
        elif user_input.lower() == 'agents':
            await self._handle_agents_command()
            return True
        elif user_input.lower() == 'clear':
            await self._handle_clear_command()
            return True
        elif user_input.lower() == 'debug':
            self._handle_debug_command()
            return True

        # Process as chat message
        await self._handle_chat_message(user_input)
        return True

    async def _handle_chat_message(self, user_input: str):
        """Handle chat message through ModeratorAgent"""
        start_time = time.time()

        try:
            # Store user message in history
            self.conversation_history.append({
                'type': 'user',
                'content': user_input,
                'timestamp': datetime.now()
            })

            # Send to ModeratorAgent
            if not self.quiet_mode:
                print("🤖 Processing...")

            response = await self.moderator.chat(user_input)

            processing_time = time.time() - start_time
            self.message_count += 1

            # Store response in history
            self.conversation_history.append({
                'type': 'agent',
                'content': response,
                'timestamp': datetime.now(),
                'agent': 'ModeratorAgent'
            })

            # Display response
            print(f"\n🤖 ModeratorAgent: {response}")

            if not self.quiet_mode:
                print(f"⏱️ Processed in {processing_time:.2f}s")

        except Exception as e:
            print(f"❌ Error processing message: {e}")
            if self.debug_mode:
                import traceback
                traceback.print_exc()

    async def run_interactive(self, user_id: str = None):
        """Run interactive CLI mode"""
        await self._initialize_moderator(user_id)

        self._print_banner()

        print(f"\n💡 ModeratorAgent ready! Type 'help' for commands or start chatting.")
        print(f"🚀 Your queries will be intelligently routed to appropriate agents.")

        while self.running:
            try:
                user_input = input("\n🗣️  You: ").strip()

                if not await self._process_user_input(user_input):
                    break

            except KeyboardInterrupt:
                print(f"\n👋 Shutting down gracefully...")
                break
            except EOFError:
                print(f"\n👋 Session ended")
                break

        await self._shutdown()

    async def run_single_query(self, query: str, user_id: str = None):
        """Run single query mode"""
        await self._initialize_moderator(user_id)

        print(f"🗣️  Query: {query}")
        print("🤖 Processing...")

        try:
            start_time = time.time()
            response = await self.moderator.chat(query)
            processing_time = time.time() - start_time

            print(f"\n🤖 Response: {response}")
            print(f"⏱️ Processed in {processing_time:.2f}s")

        except Exception as e:
            print(f"❌ Error: {e}")
            if self.debug_mode:
                import traceback
                traceback.print_exc()

        await self._shutdown()

    async def run_test_mode(self, user_id: str = None):
        """Run automated test mode"""
        await self._initialize_moderator(user_id)

        print("\n🧪 RUNNING AUTOMATED TESTS")
        print("=" * 50)

        test_queries = [
            "Hello, I need help with something",
            "Search for latest AI trends in 2025",
            "Download https://youtube.com/watch?v=dQw4w9WgXcQ",
            "Extract audio from video.mp4 as MP3",
            "What is machine learning and how does it work?",
            "Scrape https://example.com for content"
        ]

        results = []

        for i, query in enumerate(test_queries, 1):
            print(f"\n📝 Test {i}/{len(test_queries)}: {query}")
            print("-" * 30)

            try:
                start_time = time.time()
                response = await self.moderator.chat(query)
                processing_time = time.time() - start_time

                print(f"✅ Response: {response[:100]}{'...' if len(response) > 100 else ''}")
                print(f"⏱️ Time: {processing_time:.2f}s")

                results.append({
                    'query': query,
                    'success': True,
                    'response_length': len(response),
                    'processing_time': processing_time
                })

            except Exception as e:
                print(f"❌ Error: {e}")
                results.append({
                    'query': query,
                    'success': False,
                    'error': str(e)
                })

        # Print summary
        print(f"\n📊 TEST SUMMARY")
        print("=" * 50)

        successful = sum(1 for r in results if r['success'])
        total = len(results)

        print(f"✅ Successful: {successful}/{total}")
        print(f"❌ Failed: {total - successful}/{total}")

        if successful == total:
            print("🎉 All tests passed!")
        else:
            print("⚠️ Some tests failed")

        avg_time = sum(r.get('processing_time', 0) for r in results if r['success']) / max(successful, 1)
        print(f"⏱️ Average processing time: {avg_time:.2f}s")

        await self._shutdown()


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="ModeratorAgent CLI - AI Agent Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                    # Interactive mode
  %(prog)s -q "Search for Python tutorials"  # Single query
  %(prog)s --test                            # Run automated tests
  %(prog)s --config custom_config.yaml      # Use custom config
  %(prog)s --user myuser --debug             # Debug mode with custom user
        """
    )

    parser.add_argument(
        '-q', '--query',
        type=str,
        help='Run a single query and exit'
    )

    parser.add_argument(
        '--test',
        action='store_true',
        help='Run automated test suite'
    )

    parser.add_argument(
        '--config',
        type=str,
        default='agent_config.yaml',
        help='Path to configuration file (default: agent_config.yaml)'
    )

    parser.add_argument(
        '--user',
        type=str,
        help='User ID for the session'
    )

    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug mode'
    )

    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Quiet mode - minimal output'
    )

    args = parser.parse_args()

    if not MODERATOR_AVAILABLE:
        print("❌ ModeratorAgent not available. Please install the ambivo_agents package.")
        sys.exit(1)

    try:
        # Initialize CLI
        cli = ModeratorCLI(config_path=args.config)
        cli.debug_mode = args.debug
        cli.quiet_mode = args.quiet

        # Determine mode and run
        if args.query:
            # Single query mode
            asyncio.run(cli.run_single_query(args.query, args.user))
        elif args.test:
            # Test mode
            asyncio.run(cli.run_test_mode(args.user))
        else:
            # Interactive mode
            asyncio.run(cli.run_interactive(args.user))

    except KeyboardInterrupt:
        print("\n👋 CLI interrupted by user")
    except Exception as e:
        print(f"❌ CLI error: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()