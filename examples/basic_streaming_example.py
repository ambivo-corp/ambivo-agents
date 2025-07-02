import asyncio

from ambivo_agents import ModeratorAgent


async def main():
    """Basic streaming example"""
    agent, context = ModeratorAgent.create(user_id="john")

    print("🤖 Assistant: ", end='')
    async for chunk in agent.chat_stream("Download https://youtube.com/watch?v=C0DPdy98e4c"):
        print(chunk, end='', flush=True)
    print("\n")

if __name__ == "__main__":
    asyncio.run(main())