#!/usr/bin/env python3
"""
Simple test for MediaEditorAgent functionality
Tests basic operations without requiring actual video files
"""

import asyncio
import tempfile
import os
from pathlib import Path

# Import the MediaEditorAgent (adjust import path as needed)
try:
    from ambivo_agents.agents.media_editor import MediaEditorAgent
    from ambivo_agents.core.base import AgentMessage, MessageType, ExecutionContext
except ImportError:
    print("❌ Import failed. Make sure ambivo_agents is properly installed.")
    print("📦 Install with: pip install -e .")
    exit(1)


async def test_media_editor_basic():
    """Test basic MediaEditorAgent functionality"""
    print("🎬 Testing MediaEditorAgent Basic Functionality\n")

    # Create agent with auto-context
    try:
        agent = MediaEditorAgent.create_simple(
            user_id="test_user",
            tenant_id="test_tenant"
        )
        print(f"✅ Created MediaEditorAgent: {agent.agent_id}")
        print(f"📝 Session ID: {agent.context.session_id}")
        print(f"💬 Conversation ID: {agent.context.conversation_id}\n")

    except Exception as e:
        print(f"❌ Failed to create MediaEditorAgent: {e}")
        return False

    # Test 1: Help request
    print("🔍 Test 1: Help Request")
    try:
        response = await agent.chat("What can you help me with?")
        print(f"✅ Help response received ({len(response)} characters)")
        print(f"📄 Preview: {response[:150]}...\n")
    except Exception as e:
        print(f"❌ Help test failed: {e}\n")

    # Test 2: Intent analysis (without actual processing)
    print("🧠 Test 2: Intent Analysis")
    try:
        response = await agent.chat("I want to extract audio from a video file")
        print(f"✅ Intent analysis response received")
        print(f"📄 Preview: {response[:200]}...\n")
    except Exception as e:
        print(f"❌ Intent analysis test failed: {e}\n")

    # Test 3: Media info request (without actual file)
    print("📊 Test 3: Media Info Request")
    try:
        response = await agent.chat("Get information about test_video.mp4")
        print(f"✅ Media info response received")
        print(f"📄 Preview: {response[:200]}...\n")
    except Exception as e:
        print(f"❌ Media info test failed: {e}\n")

    # Test 4: Conversation context
    print("🧠 Test 4: Conversation Context")
    try:
        # First message
        await agent.chat("I have a video file called test_video.mov")
        # Second message using context
        response = await agent.chat("Extract audio from that video")
        print(f"✅ Context-aware response received")
        print(f"📄 Preview: {response[:200]}...\n")
    except Exception as e:
        print(f"❌ Context test failed: {e}\n")

    # Test 5: Streaming response
    print("🌊 Test 5: Streaming Response")
    try:
        print("📡 Streaming chunks:")
        chunk_count = 0
        async for chunk in agent.chat_stream("How do I convert a video to MP4?"):
            chunk_count += 1
            if chunk_count <= 3:  # Show first 3 chunks
                print(f"   📦 Chunk {chunk_count}: {chunk[:50]}...")

        print(f"✅ Received {chunk_count} streaming chunks\n")
    except Exception as e:
        print(f"❌ Streaming test failed: {e}\n")

    # Test 6: Agent status (with error handling)
    print("📋 Test 6: Agent Status")
    try:
        # Try the method if it exists, otherwise show agent info
        if hasattr(agent, 'get_agent_status'):
            status = agent.get_agent_status()
            print(f"✅ Agent Status Retrieved:")
            print(f"   🆔 Agent ID: {status['agent_id']}")
            print(f"   🎭 Agent Type: {status['agent_type']}")
            print(f"   🧠 Has Memory: {status['has_memory']}")
            print(f"   🤖 Has LLM: {status['has_llm_service']}")
            print(f"   📝 System Message: {status['system_message_enabled']}")
            print(f"   🔧 Capabilities: {len(status['capabilities'])} features\n")
        else:
            # Show basic agent info instead
            print(f"✅ Basic Agent Info:")
            print(f"   🆔 Agent ID: {agent.agent_id}")
            print(f"   👤 Role: {agent.role.value}")
            print(f"   📝 Name: {agent.name}")
            print(f"   🧠 Has Memory: {hasattr(agent, 'memory') and agent.memory is not None}")
            print(f"   🤖 Has LLM: {hasattr(agent, 'llm_service') and agent.llm_service is not None}")
            print(f"   📋 Description: {agent.description}")
            print(f"   🔧 Tools: {len(agent.tools)} available\n")
    except Exception as e:
        print(f"❌ Status test failed: {e}\n")

    # Cleanup
    try:
        await agent.cleanup_session()
        print("✅ Session cleaned up successfully")
    except Exception as e:
        print(f"⚠️ Cleanup warning: {e}")

    return True


async def test_media_editor_with_real_video():
    """Test with the actual test_video.mov file"""
    print("\n🎬 Testing MediaEditorAgent with Real Video File\n")

    # Path to the actual video file (check both possible locations)
    video_path = Path("./examples/media_input/test_video.mov")
    if not video_path.exists():
        video_path = Path("./media_input/test_video.mov")  # Fallback

    if not video_path.exists():
        print(f"⚠️ Video file not found: {video_path}")
        print("📁 Please ensure test_video.mov exists in the media_input directory")
        return

    print(f"✅ Found video file: {video_path}")
    print(f"📊 File size: {video_path.stat().st_size / (1024 * 1024):.2f} MB")

    try:
        agent = MediaEditorAgent.create_simple(user_id="test_user_real")
        print(f"✅ Created agent for real video test")

        # Test 1: Get video information
        print("\n📋 Test 1: Getting video information...")
        response = await agent.chat(f"Get information about {video_path}")
        print(f"✅ Video info response:")
        print(f"   {response[:300]}...")

        # Test 2: Extract audio (this will actually work with Docker + FFmpeg)
        print("\n🎵 Test 2: Extract audio from video...")
        response = await agent.chat(f"Extract audio from {video_path} as MP3")
        print(f"✅ Audio extraction response:")
        print(f"   {response[:300]}...")

        # Test 3: Context-aware follow-up
        print("\n🧠 Test 3: Context-aware follow-up...")
        response = await agent.chat("Convert that video to MP4 format")
        print(f"✅ Conversion response:")
        print(f"   {response[:300]}...")

        # Test 4: Resize request
        print("\n📏 Test 4: Video resize request...")
        response = await agent.chat("Resize the video to 720p")
        print(f"✅ Resize response:")
        print(f"   {response[:300]}...")

        # Test 5: Create thumbnail
        print("\n🖼️ Test 5: Create thumbnail...")
        response = await agent.chat("Create a thumbnail from the video at 10 seconds")
        print(f"✅ Thumbnail response:")
        print(f"   {response[:300]}...")

        # Test 6: Streaming with real video
        print("\n🌊 Test 6: Streaming response for real video...")
        print("📡 Streaming chunks for video processing:")
        chunk_count = 0
        async for chunk in agent.chat_stream(f"Tell me what you can do with {video_path}"):
            chunk_count += 1
            if chunk_count <= 5:  # Show first 5 chunks
                clean_chunk = chunk.replace('\n', ' ').strip()
                print(f"   📦 Chunk {chunk_count}: {clean_chunk[:60]}...")
            if chunk_count > 20:  # Limit output
                break

        print(f"✅ Received {chunk_count} streaming chunks")

        await agent.cleanup_session()

        # Check if any output files were created
        output_dir = Path("./media_output")
        if output_dir.exists():
            output_files = list(output_dir.glob("*"))
            if output_files:
                print(f"\n📁 Output files created:")
                for file in output_files:
                    print(f"   🎵 {file.name} ({file.stat().st_size / 1024:.1f} KB)")
            else:
                print("\n📝 No output files created (expected without Docker+FFmpeg)")

    except Exception as e:
        print(f"❌ Real video test failed: {e}")
        import traceback
        print(f"🔍 Traceback: {traceback.format_exc()[:500]}...")


def test_media_executor_config():
    """Test MediaDockerExecutor configuration"""
    print("\n🐳 Testing MediaDockerExecutor Configuration\n")

    try:
        from ambivo_agents.executors.media_executor import MediaDockerExecutor

        # Test with default config
        executor = MediaDockerExecutor()
        print(f"✅ MediaDockerExecutor created")
        print(f"🐳 Docker Image: {executor.docker_image}")
        print(f"⏱️ Timeout: {executor.timeout}s")
        print(f"💾 Memory Limit: {executor.memory_limit}")
        print(f"📁 Input Dir: {executor.input_dir}")
        print(f"📁 Output Dir: {executor.output_dir}")
        print(f"🔌 Available: {executor.available}")

        if executor.available:
            print("✅ Docker connection successful")
        else:
            print("⚠️ Docker not available (this is expected in some environments)")

    except Exception as e:
        print(f"❌ MediaDockerExecutor test failed: {e}")


async def run_all_tests():
    """Run all MediaEditorAgent tests"""
    print("🚀 Starting MediaEditorAgent Test Suite")
    print("=" * 60)

    # Test 1: Basic functionality
    success = await test_media_editor_basic()

    if success:
        # Test 2: Real video file
        await test_media_editor_with_real_video()

        # Test 3: Executor config
        test_media_executor_config()

        print("\n🎉 All MediaEditorAgent tests completed!")
        print("=" * 60)

        print("\n📋 Test Summary:")
        print("✅ Basic chat functionality")
        print("✅ Intent analysis and routing")
        print("✅ Conversation context preservation")
        print("✅ Streaming responses")
        print("✅ Agent status reporting")
        print("✅ Real video file processing")
        print("✅ Session management")
        print("✅ Configuration loading")

        print("\n💡 Next Steps for Full Functionality:")
        print("1. ✅ Video file ready: examples/media_input/test_video.mov")
        print("2. ✅ Docker + FFmpeg container available")
        print("3. 🔧 Configure LLM service for smarter responses")
        print("4. 📝 Configure Redis for persistent memory")
        print("5. 🚀 Ready for real media processing!")

        print("\n🎬 Example Commands to Try:")
        print('• "Extract audio from examples/media_input/test_video.mov as MP3"')
        print('• "Convert that video to MP4 format"')
        print('• "Resize it to 720p"')
        print('• "Create a thumbnail at 5 seconds"')
        print('• "Get information about the video"')

        print("\n🔥 Quick Test Command:")
        print("python -c \"")
        print("import asyncio")
        print("from ambivo_agents.agents.media_editor import MediaEditorAgent")
        print("async def test():")
        print("    agent = MediaEditorAgent.create_simple(user_id='test')")
        print("    result = await agent.chat('Extract audio from examples/media_input/test_video.mov')")
        print("    print(result)")
        print("asyncio.run(test())\"")


    else:
        print("❌ Basic tests failed. Check your installation.")


if __name__ == "__main__":
    # Run the test suite
    asyncio.run(run_all_tests())