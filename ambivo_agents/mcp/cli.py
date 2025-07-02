import asyncio
from .server import MCPAgentServer

async def main():
    server = MCPAgentServer()
    await server.run_stdio()

if __name__ == "__main__":
    asyncio.run(main())