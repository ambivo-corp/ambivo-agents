#!/usr/bin/env python3
"""
Direct Media Tool Execution Demo
Actually calls the MediaEditorAgent tools directly
"""

import asyncio
import os
import sys
import time
from pathlib import Path

# Add the ambivo_agents package to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from ambivo_agents.services import create_agent_service
from ambivo_agents.config.loader import load_config, get_config_section
from ambivo_agents.core.base import AgentMessage, MessageType, ExecutionContext
import uuid


class DirectMediaDemo:
    """Demo that directly calls MediaEditorAgent tools"""

    def __init__(self):
        print("🎥 Direct Media Tool Execution Demo")
        print("=" * 40)

        # Load configuration
        self.config = load_config()
        self.media_config = get_config_section('media_editor', self.config)

        self.input_dir = Path(self.media_config.get('input_dir', './examples/media_input'))
        self.output_dir = Path(self.media_config.get('output_dir', './examples/media_output'))

        print(f"📁 Input directory: {self.input_dir}")
        print(f"📁 Output directory: {self.output_dir}")

        # Create agent service
        self.agent_service = create_agent_service()
        self.session_id = self.agent_service.create_session()
        self.user_id = "direct_media_user"

        # Get the session to access agents directly
        self.session = self.agent_service.sessions[self.session_id]

        # Find the MediaEditorAgent
        self.media_agent = None
        for agent_key, agent in self.session.agents.items():
            if 'MediaEditorAgent' in agent.__class__.__name__:
                self.media_agent = agent
                print(f"✅ Found MediaEditorAgent: {agent_key}")
                break

        if not self.media_agent:
            raise RuntimeError("MediaEditorAgent not found in session")

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def find_video_files(self):
        """Find video files"""
        video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv', '.m4v', '.3gp'}

        video_files = []
        if self.input_dir.exists():
            for file_path in self.input_dir.iterdir():
                if file_path.is_file() and file_path.suffix.lower() in video_extensions:
                    video_files.append(file_path)

        return video_files

    async def test_direct_tool_execution(self, video_file: Path):
        """Test calling MediaEditorAgent tools directly"""

        print(f"\n🔧 Direct Tool Execution Test")
        print(f"📄 Video file: {video_file}")
        print("-" * 40)

        # Check what tools the agent has
        tools = self.media_agent.tools
        print(f"🛠️  Available tools ({len(tools)}):")
        for tool in tools:
            print(f"   - {tool.name}: {tool.description}")

        # Test extract_audio_from_video tool directly
        if any(tool.name == "extract_audio_from_video" for tool in tools):
            print(f"\n🎵 Testing extract_audio_from_video tool...")

            try:
                # Call the tool directly
                result = await self.media_agent.execute_tool(
                    "extract_audio_from_video",
                    {
                        "input_video": str(video_file),
                        "output_format": "mp3",
                        "audio_quality": "high"
                    }
                )

                print(f"🔧 Tool execution result:")
                print(f"   Success: {result.get('success', False)}")

                if result.get('success'):
                    tool_result = result.get('result', {})
                    print(f"   Output: {tool_result}")

                    # Check for output files
                    self.check_output_files()
                else:
                    print(f"   Error: {result.get('error', 'Unknown error')}")

                return result

            except Exception as e:
                print(f"❌ Tool execution failed: {e}")
                return None
        else:
            print(f"❌ extract_audio_from_video tool not found")
            return None

    async def test_media_info_tool(self, video_file: Path):
        """Test get_media_info tool directly"""

        print(f"\n📊 Testing get_media_info tool...")

        try:
            result = await self.media_agent.execute_tool(
                "get_media_info",
                {"file_path": str(video_file)}
            )

            print(f"🔧 Media info result:")
            print(f"   Success: {result.get('success', False)}")

            if result.get('success'):
                info = result.get('result', {})
                print(f"   Media info: {info}")
            else:
                print(f"   Error: {result.get('error', 'Unknown error')}")

            return result

        except Exception as e:
            print(f"❌ Media info tool failed: {e}")
            return None

    async def test_message_based_execution(self, video_file: Path):
        """Test message-based execution with specific tool names"""

        print(f"\n💬 Testing Message-Based Execution")
        print("-" * 35)

        # Create a message that explicitly mentions the tool
        message_content = f"""Please use the extract_audio_from_video tool to extract audio from:

File: {video_file}
Format: mp3
Quality: high

This should use your extract_audio_from_video tool function directly."""

        message = AgentMessage(
            id=str(uuid.uuid4()),
            sender_id=self.user_id,
            recipient_id=self.media_agent.agent_id,
            content=message_content,
            message_type=MessageType.USER_INPUT
        )

        context = ExecutionContext(
            session_id=self.session_id,
            conversation_id="direct_tool_test",
            user_id=self.user_id,
            tenant_id="demo"
        )

        print(f"📤 Sending message to MediaEditorAgent...")

        try:
            response = await self.media_agent.process_message(message, context)

            print(f"📥 Response received:")
            print(f"   Content: {response.content}")

            # Check for output files
            self.check_output_files()

            return response

        except Exception as e:
            print(f"❌ Message processing failed: {e}")
            return None

    def check_output_files(self):
        """Check for output files in the output directory"""

        print(f"\n📁 Checking output directory: {self.output_dir}")

        if not self.output_dir.exists():
            print(f"❌ Output directory doesn't exist")
            return []

        output_files = list(self.output_dir.iterdir())
        print(f"📄 Files found: {len(output_files)}")

        for file in output_files:
            if file.is_file():
                size = file.stat().st_size
                modified = file.stat().st_mtime
                print(f"   📄 {file.name} ({size:,} bytes, modified: {time.ctime(modified)})")

        return output_files

    def check_docker_availability(self):
        """Check if Docker is available"""

        print(f"\n🐳 Checking Docker Availability")
        print("-" * 25)

        try:
            import docker
            client = docker.from_env()
            client.ping()
            print(f"✅ Docker is available and running")

            # Check if our image exists
            docker_image = self.media_config.get('docker_image', 'sgosain/amb-ubuntu-python-public-pod')
            try:
                image = client.images.get(docker_image)
                print(f"✅ Docker image available: {docker_image}")
                print(f"   Image ID: {image.id[:12]}")
            except docker.errors.ImageNotFound:
                print(f"⚠️  Docker image not found locally: {docker_image}")
                print(f"   Will try to pull when needed")

            return True

        except ImportError:
            print(f"❌ Docker Python package not installed")
            return False
        except Exception as e:
            print(f"❌ Docker not available: {e}")
            return False

    async def run_comprehensive_test(self):
        """Run comprehensive testing"""

        print(f"\n" + "=" * 60)
        print("🧪 COMPREHENSIVE MEDIA TOOL TESTING")
        print("=" * 60)

        # Check Docker
        docker_available = self.check_docker_availability()

        # Find video files
        video_files = self.find_video_files()

        if not video_files:
            print(f"\n❌ No video files found in: {self.input_dir}")
            return False

        print(f"\n🎥 Video files found: {len(video_files)}")
        for video in video_files:
            size_mb = video.stat().st_size / (1024 * 1024)
            print(f"   📄 {video.name} ({size_mb:.1f} MB)")

        # Test with first video file
        test_video = video_files[0]
        print(f"\n🎯 Testing with: {test_video.name}")

        # Test 1: Direct tool execution
        print(f"\n" + "=" * 40)
        print("TEST 1: Direct Tool Execution")
        print("=" * 40)

        tool_result = await self.test_direct_tool_execution(test_video)

        # Test 2: Media info tool
        print(f"\n" + "=" * 40)
        print("TEST 2: Media Info Tool")
        print("=" * 40)

        info_result = await self.test_media_info_tool(test_video)

        # Test 3: Message-based execution
        print(f"\n" + "=" * 40)
        print("TEST 3: Message-Based Execution")
        print("=" * 40)

        message_result = await self.test_message_based_execution(test_video)

        # Final output check
        print(f"\n" + "=" * 40)
        print("FINAL OUTPUT CHECK")
        print("=" * 40)

        final_files = self.check_output_files()

        # Summary
        print(f"\n📊 Test Summary:")
        print(f"   🐳 Docker available: {'✅' if docker_available else '❌'}")
        print(f"   🔧 Direct tool: {'✅' if tool_result and tool_result.get('success') else '❌'}")
        print(f"   📊 Media info: {'✅' if info_result and info_result.get('success') else '❌'}")
        print(f"   💬 Message test: {'✅' if message_result else '❌'}")
        print(f"   📁 Output files: {len(final_files)}")

        if len(final_files) == 0:
            print(f"\n⚠️  No output files created - ffmpeg/Docker execution may have failed")
            print(f"💡 Check Docker logs: docker logs $(docker ps -l -q)")

        return len(final_files) > 0

    async def cleanup(self):
        """Cleanup"""
        if self.session_id:
            self.agent_service.delete_session(self.session_id)
            print(f"✅ Cleaned up session")


async def main():
    """Main function"""

    try:
        demo = DirectMediaDemo()
        success = await demo.run_comprehensive_test()

        if success:
            print(f"\n🎉 Media tools are working - output files created!")
        else:
            print(f"\n❌ Media tools not working properly - no output files")
            print(f"\n🔧 Troubleshooting steps:")
            print(f"   1. Check Docker is running: docker ps")
            print(f"   2. Check image is available: docker images")
            print(f"   3. Check output directory permissions")
            print(f"   4. Check Docker logs for errors")

        await demo.cleanup()

    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())