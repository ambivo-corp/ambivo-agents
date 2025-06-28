# examples/configuration_examples.py
"""
Examples of different configuration scenarios
"""

from ambivo_agents.config.loader import (
    load_config,
    validate_agent_capabilities,
    get_config_section,
    ConfigurationError
)


def main():
    """Configuration examples"""

    try:
        # Load full configuration
        config = load_config()
        print("✅ Configuration loaded successfully")

        # Validate capabilities
        capabilities = validate_agent_capabilities(config)
        print(f"\n🚀 Available capabilities:")
        for capability, enabled in capabilities.items():
            status = "✅" if enabled else "❌"
            print(f"   {status} {capability}")

        # Get specific sections
        redis_config = get_config_section('redis', config)
        print(f"\n🔧 Redis Configuration:")
        print(f"   Host: {redis_config.get('host')}")
        print(f"   Port: {redis_config.get('port')}")
        print(f"   DB: {redis_config.get('db')}")

        llm_config = get_config_section('llm', config)
        print(f"\n🧠 LLM Configuration:")
        print(f"   Preferred Provider: {llm_config.get('preferred_provider')}")
        print(f"   Temperature: {llm_config.get('temperature')}")

        # Check optional sections
        optional_sections = ['web_scraping', 'knowledge_base', 'web_search', 'media_editor']

        print(f"\n📦 Optional Sections:")
        for section in optional_sections:
            try:
                section_config = get_config_section(section, config)
                print(f"   ✅ {section}: configured")
            except ConfigurationError:
                print(f"   ❌ {section}: not configured")

    except ConfigurationError as e:
        print(f"❌ Configuration Error: {e}")
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")


if __name__ == "__main__":
    main()
