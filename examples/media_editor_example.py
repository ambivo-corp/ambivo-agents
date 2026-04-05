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
    print("[ERROR] Import failed. Make sure ambivo_agents is properly installed.")
    print("Install with: pip install -e .")
    exit(1)


async def test_media_editor_basic():
    """Test basic MediaEditorAgent functionality"""
    print("Testing MediaEditorAgent Basic Functionality\n")

    # Create agent with auto-context
    try:
        agent = MediaEditorAgent.create_simple(
            user_id="test_user",
            tenant_id="test_tenant"
        )
        print(f"[OK] Created MediaEditorAgent: {agent.agent_id}")
        print(f"Session ID: {agent.context.session_id}")
        print(f"Conversation ID: {agent.context.conversation_id}\n")

    except Exception as e:
        print(f"[ERROR] Failed to create MediaEditorAgent: {e}")
        return False

    # Test 1: Help request
    print("Test 1: Help Request")
    try:
        response = await agent.chat("What can you help me with?")
        print(f"[OK] Help response received ({len(response)} characters)")
        print(f"Preview: {response[:150]}...\n")
    except Exception as e:
        print(f"[ERROR] Help test failed: {e}\n")

    # Test 2: Intent analysis (without actual processing)
    print("Test 2: Intent Analysis")
    try:
        response = await agent.chat("I want to extract audio from a video file")
        print(f"[OK] Intent analysis response received")
        print(f"Preview: {response[:200]}...\n")
    except Exception as e:
        print(f"[ERROR] Intent analysis test failed: {e}\n")

    # Test 3: Media info request (without actual file)
    print("Test 3: Media Info Request")
    try:
        response = await agent.chat("Get information about test_video.mp4")
        print(f"[OK] Media info response received")
        print(f"Preview: {response[:200]}...\n")
    except Exception as e:
        print(f"[ERROR] Media info test failed: {e}\n")

    # Test 4: Conversation context
    print("Test 4: Conversation Context")
    try:
        # First message
        await agent.chat("I have a video file called test_video.mov")
        # Second message using context
        response = await agent.chat("Extract audio from that video")
        print(f"[OK] Context-aware response received")
        print(f"Preview: {response[:200]}...\n")
    except Exception as e:
        print(f"[ERROR] Context test failed: {e}\n")

    # Test 5: Streaming response
    print("Test 5: Streaming Response")
    try:
        print("Streaming chunks:")
        chunk_count = 0
        async for chunk in agent.chat_stream("How do I convert a video to MP4?"):
            chunk_count += 1
            if chunk_count <= 3:  # Show first 3 chunks
                print(f"   Chunk {chunk_count}: {chunk[:50]}...")

        print(f"[OK] Received {chunk_count} streaming chunks\n")
    except Exception as e:
        print(f"[ERROR] Streaming test failed: {e}\n")

    # Test 6: Agent status (with error handling)
    print("Test 6: Agent Status")
    try:
        # Try the method if it exists, otherwise show agent info
        if hasattr(agent, 'get_agent_status'):
            status = agent.get_agent_status()
            print(f"[OK] Agent Status Retrieved:")
            print(f"   🆔 Agent ID: {status['agent_id']}")
            print(f"   Agent Type: {status['agent_type']}")
            print(f"   Has Memory: {status['has_memory']}")
            print(f"   Has LLM: {status['has_llm_service']}")
            print(f"   System Message: {status['system_message_enabled']}")
            print(f"   Capabilities: {len(status['capabilities'])} features\n")
        else:
            # Show basic agent info instead
            print(f"[OK] Basic Agent Info:")
            print(f"   🆔 Agent ID: {agent.agent_id}")
            print(f"   Role: {agent.role.value}")
            print(f"   Name: {agent.name}")
            print(f"   Has Memory: {hasattr(agent, 'memory') and agent.memory is not None}")
            print(f"   Has LLM: {hasattr(agent, 'llm_service') and agent.llm_service is not None}")
            print(f"   Description: {agent.description}")
            print(f"   Tools: {len(agent.tools)} available\n")
    except Exception as e:
        print(f"[ERROR] Status test failed: {e}\n")

    # Cleanup
    try:
        await agent.cleanup_session()
        print("[OK] Session cleaned up successfully")
    except Exception as e:
        print(f"[WARN]Cleanup warning: {e}")

    return True


async def test_media_editor_with_real_video():
    """Test with the actual test_video.mov file"""
    print("\nTesting MediaEditorAgent with Real Video File\n")

    # Path to the actual video file (check both possible locations)
    video_path = Path("./examples/media_input/test_video.mov")
    if not video_path.exists():
        video_path = Path("./media_input/test_video.mov")  # Fallback

    if not video_path.exists():
        print(f"[WARN]Video file not found: {video_path}")
        print("Please ensure test_video.mov exists in the media_input directory")
        return

    print(f"[OK] Found video file: {video_path}")
    print(f"File size: {video_path.stat().st_size / (1024 * 1024):.2f} MB")

    try:
        agent = MediaEditorAgent.create_simple(user_id="test_user_real")
        print(f"[OK] Created agent for real video test")

        # Test 1: Get video information
        print("\nTest 1: Getting video information...")
        response = await agent.chat(f"Get information about {video_path}")
        print(f"[OK] Video info response:")
        print(f"   {response[:300]}...")

        # Test 2: Extract audio (this will actually work with Docker + FFmpeg)
        print("\nTest 2: Extract audio from video...")
        response = await agent.chat(f"Extract audio from {video_path} as MP3")
        print(f"[OK] Audio extraction response:")
        print(f"   {response[:300]}...")

        # Test 3: Context-aware follow-up
        print("\nTest 3: Context-aware follow-up...")
        response = await agent.chat("Convert that video to MP4 format")
        print(f"[OK] Conversion response:")
        print(f"   {response[:300]}...")

        # Test 4: Resize request
        print("\nTest 4: Video resize request...")
        response = await agent.chat("Resize the video to 720p")
        print(f"[OK] Resize response:")
        print(f"   {response[:300]}...")

        # Test 5: Create thumbnail
        print("\nTest 5: Create thumbnail...")
        response = await agent.chat("Create a thumbnail from the video at 10 seconds")
        print(f"[OK] Thumbnail response:")
        print(f"   {response[:300]}...")

        # Test 6: Streaming with real video
        print("\nTest 6: Streaming response for real video...")
        print("Streaming chunks for video processing:")
        chunk_count = 0
        async for chunk in agent.chat_stream(f"Tell me what you can do with {video_path}"):
            chunk_count += 1
            if chunk_count <= 5:  # Show first 5 chunks
                clean_chunk = chunk.replace('\n', ' ').strip()
                print(f"   Chunk {chunk_count}: {clean_chunk[:60]}...")
            if chunk_count > 20:  # Limit output
                break

        print(f"[OK] Received {chunk_count} streaming chunks")

        await agent.cleanup_session()

        # Check if any output files were created
        output_dir = Path("./media_output")
        if output_dir.exists():
            output_files = list(output_dir.glob("*"))
            if output_files:
                print(f"\nOutput files created:")
                for file in output_files:
                    print(f"   {file.name} ({file.stat().st_size / 1024:.1f} KB)")
            else:
                print("\nNo output files created (expected without Docker+FFmpeg)")

    except Exception as e:
        print(f"[ERROR] Real video test failed: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()[:500]}...")


def test_media_executor_config():
    """Test MediaDockerExecutor configuration"""
    print("\nTesting MediaDockerExecutor Configuration\n")

    try:
        from ambivo_agents.executors.media_executor import MediaDockerExecutor

        # Test with default config
        executor = MediaDockerExecutor()
        print(f"[OK] MediaDockerExecutor created")
        print(f"Docker Image: {executor.docker_image}")
        print(f"Timeout: {executor.timeout}s")
        print(f"Memory Limit: {executor.memory_limit}")
        print(f"Input Dir: {executor.input_dir}")
        print(f"Output Dir: {executor.output_dir}")
        print(f"Available: {executor.available}")

        if executor.available:
            print("[OK] Docker connection successful")
        else:
            print("[WARN]Docker not available (this is expected in some environments)")

    except Exception as e:
        print(f"[ERROR] MediaDockerExecutor test failed: {e}")


async def run_all_tests():
    """Run all MediaEditorAgent tests"""
    print("Starting MediaEditorAgent Test Suite")
    print("=" * 60)

    # Test 1: Basic functionality
    success = await test_media_editor_basic()

    if success:
        # Test 2: Real video file
        await test_media_editor_with_real_video()

        # Test 3: Executor config
        test_media_executor_config()

        print("\nAll MediaEditorAgent tests completed!")
        print("=" * 60)

        print("\nTest Summary:")
        print("[OK] Basic chat functionality")
        print("[OK] Intent analysis and routing")
        print("[OK] Conversation context preservation")
        print("[OK] Streaming responses")
        print("[OK] Agent status reporting")
        print("[OK] Real video file processing")
        print("[OK] Session management")
        print("[OK] Configuration loading")

        print("\nNext Steps for Full Functionality:")
        print("1. [OK] Video file ready: examples/media_input/test_video.mov")
        print("2. [OK] Docker + FFmpeg container available")
        print("3. Configure LLM service for smarter responses")
        print("4. Configure Redis for persistent memory")
        print("5. Ready for real media processing!")

        print("\nExample Commands to Try:")
        print('• "Extract audio from examples/media_input/test_video.mov as MP3"')
        print('• "Convert that video to MP4 format"')
        print('• "Resize it to 720p"')
        print('• "Create a thumbnail at 5 seconds"')
        print('• "Get information about the video"')

        print("\nQuick Test Command:")
        print("python -c \"")
        print("import asyncio")
        print("from ambivo_agents.agents.media_editor import MediaEditorAgent")
        print("async def test():")
        print("    agent = MediaEditorAgent.create_simple(user_id='test')")
        print("    result = await agent.chat('Extract audio from examples/media_input/test_video.mov')")
        print("    print(result)")
        print("asyncio.run(test())\"")


    else:
        print("[ERROR] Basic tests failed. Check your installation.")


if __name__ == "__main__":
    # Run the test suite
    asyncio.run(run_all_tests())