#!/usr/bin/env python3
"""
One-Liner YouTube Download Example
The absolute simplest way to download from YouTube
"""

import asyncio
from ambivo_agents.agents.youtube_download import YouTubeDownloadAgent


async def one_liner_example():
    """Absolute simplest example - just one line to create agent"""

    print("🎬 One-Liner YouTube Download")
    print("=" * 40)

    # ONE LINE: Create agent with auto-configuration
    agent = YouTubeDownloadAgent.create(userid='123')


    # Better test URL (Big Buck Bunny - open source, usually available)
    url = "https://www.youtube.com/watch?v=C0DPdy98e4c"

    # Download audio
    print("🎵 Downloading audio...")
    result = await agent._download_youtube_audio(url)
    print("Audio result:", "✅ Success" if result['success'] else f"❌ {result['error']}")

    # Get video info
    print("📋 Getting video info...")
    result = await agent._get_youtube_info(url)
    print("Info result:", "✅ Success" if result['success'] else f"❌ {result['error']}")


# Even simpler: No agent, just executor
async def direct_executor_example():
    """Bypass agent completely - use executor directly"""

    print("\n🔧 Direct Executor (No Agent)")
    print("=" * 40)

    from ambivo_agents.executors.youtube_executor import YouTubeDockerExecutor

    # Minimal config
    config = {'docker_image': 'sgosain/amb-ubuntu-python-public-pod'}
    executor = YouTubeDockerExecutor(config)

    # Download directly
    url = "https://www.youtube.com/watch?v=C0DPdy98e4c"
    result = executor.download_youtube_video(url, audio_only=True)
    print("Direct result:", "✅ Success" if result['success'] else f"❌ {result['error']}")


if __name__ == "__main__":
    try:
        asyncio.run(one_liner_example())
        asyncio.run(direct_executor_example())
    except Exception as e:
        print(f"❌ Failed: {e}")
        print("\n🔧 Quick fixes:")
        print("1. Start Redis: docker run -d -p 6379:6379 redis")
        print("2. Check Docker: docker --version")
        print("3. Try a different YouTube URL")