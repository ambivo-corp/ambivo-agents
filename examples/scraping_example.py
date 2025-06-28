#!/usr/bin/env python3
"""
apartments_scraping.py
Real-world example of scraping apartments.com using Ambivo Agents Web Scraper

Author: Hemant Gosain 'Sunny'
Company: Ambivo
Email: sgosain@ambivo.com
License: MIT
"""

import asyncio
import os
import sys
import time
import json
import csv
import re
from pathlib import Path
from datetime import datetime
from urllib.parse import quote, urljoin

# Add the ambivo_agents package to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from ambivo_agents.services import create_agent_service


class ApartmentsScrapingDemo:
    """Demonstrate real apartments.com scraping using Ambivo Agents"""

    def __init__(self):
        print("🏠 Initializing Apartments.com Scraping Demo...")

        # Create agent service
        self.agent_service = create_agent_service()

        # Create session
        self.session_id = self.agent_service.create_session()
        self.user_id = "apartments_scraper_user"

        # Setup output directory
        self.setup_directories()

        # Scraped data storage
        self.scraped_data = []

    def setup_directories(self):
        """Setup output directories for scraped data"""
        self.output_dir = Path("./scraped_apartments")
        self.output_dir.mkdir(exist_ok=True)

        print(f"📁 Output directory: {self.output_dir.absolute()}")

    async def check_scraper_availability(self):
        """Check if web scraper agent is available"""
        print("\n🔍 Checking Web Scraper Agent Availability...")

        health = self.agent_service.health_check()
        available_agents = health.get('available_agent_types', {})
        print(f"<UNK> Available Agents: {available_agents}")

        if available_agents.get('web_scraper', False):
            print("✅ Web Scraper Agent is available")
            return True
        else:
            print("❌ Web Scraper Agent is not available")
            print("Please ensure web_scraping is enabled in agent_config.yaml")
            return False

    def generate_apartments_urls(self, city: str, state: str, max_pages: int = 3):
        """Generate apartments.com URLs for a specific city and state"""
        print(f"\n🔗 Generating apartments.com URLs for {city}, {state}...")

        # Format city and state for URL
        location = f"{city.lower().replace(' ', '-')}-{state.lower()}"
        base_url = f"https://www.apartments.com/{location}/"

        urls = [base_url]  # First page

        # Add pagination URLs
        for page in range(2, max_pages + 1):
            page_url = f"{base_url}{page}/"
            urls.append(page_url)

        print(f"📋 Generated {len(urls)} URLs to scrape:")
        for i, url in enumerate(urls, 1):
            print(f"  {i}. {url}")

        return urls

    async def scrape_apartments_page(self, url: str, extract_details: bool = True):
        """Scrape a single apartments.com page"""
        print(f"\n🕷️ Scraping apartments page: {url}")

        message = f"""Scrape the apartments.com page at this URL: {url}

Please extract the following information:
- Extract all apartment listing links
- Extract apartment images
- Get page content for parsing apartment details
- Use method: auto (Playwright preferred for JavaScript-heavy sites)
- Set extract_links: true
- Set extract_images: true

Use the scrape_url tool to fetch this content."""

        start_time = time.time()

        result = await self.agent_service.process_message(
            message=message,
            session_id=self.session_id,
            user_id=self.user_id,
            conversation_id="apartments_scraping_demo"
        )

        scrape_time = time.time() - start_time

        if result['success']:
            print(f"✅ Page scraped successfully!")
            print(f"⏱️  Scraping time: {scrape_time:.2f} seconds")

            # Extract response data
            response_content = result['response']

            # Parse the response to extract structured data
            return await self.parse_apartments_response(response_content, url)
        else:
            print(f"❌ Scraping failed: {result['error']}")
            return None

    async def parse_apartments_response(self, response_content: str, source_url: str):
        """Parse the scraper response to extract apartment data"""
        print("🔍 Parsing apartment data from scraped content...")

        # Use the agent to parse the scraped content
        parse_message = f"""Parse the following scraped content from apartments.com and extract structured apartment data:

Source URL: {source_url}

Scraped Content:
{response_content}

Please extract the following information for each apartment listing found:
1. Property name/title
2. Address or location
3. Rent price (if available)
4. Number of bedrooms/bathrooms
5. Square footage
6. Amenities mentioned
7. Contact information
8. Listing URL/link
9. Image URLs

Format the response as structured data (JSON-like) for each property found.
Focus on extracting real apartment listings, not ads or navigation elements."""

        result = await self.agent_service.process_message(
            message=parse_message,
            session_id=self.session_id,
            user_id=self.user_id,
            conversation_id="apartments_parsing_demo"
        )

        if result['success']:
            print("✅ Content parsed successfully!")
            parsed_response = result['response']

            # Extract apartment data from the AI response
            apartments = self.extract_apartment_data_from_response(parsed_response, source_url)

            if apartments:
                print(f"🏠 Found {len(apartments)} apartment listings")
                return apartments
            else:
                print("⚠️  No apartment listings extracted from response")
                return []
        else:
            print(f"❌ Parsing failed: {result['error']}")
            return []

    def extract_apartment_data_from_response(self, ai_response: str, source_url: str):
        """Extract structured apartment data from AI response"""
        apartments = []

        try:
            # Try to find JSON-like structures in the response
            json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
            json_matches = re.findall(json_pattern, ai_response, re.DOTALL)

            for match in json_matches:
                try:
                    # Attempt to parse as JSON
                    apartment_data = json.loads(match)
                    if isinstance(apartment_data, dict):
                        apartment_data['source_url'] = source_url
                        apartment_data['scraped_at'] = datetime.now().isoformat()
                        apartments.append(apartment_data)
                except json.JSONDecodeError:
                    continue

            # If no JSON found, parse text format
            if not apartments:
                apartments = self.parse_text_format_apartments(ai_response, source_url)

        except Exception as e:
            print(f"⚠️  Error extracting apartment data: {e}")

            # Fallback: create basic data structure from response
            apartments = [{
                'property_name': 'Parsed from response',
                'source_url': source_url,
                'scraped_at': datetime.now().isoformat(),
                'raw_response': ai_response[:500]  # First 500 chars
            }]

        return apartments

    def parse_text_format_apartments(self, response: str, source_url: str):
        """Parse apartment data from text format response"""
        apartments = []

        # Look for common apartment listing patterns
        lines = response.split('\n')
        current_apartment = {}

        for line in lines:
            line = line.strip()
            if not line:
                if current_apartment:
                    current_apartment['source_url'] = source_url
                    current_apartment['scraped_at'] = datetime.now().isoformat()
                    apartments.append(current_apartment)
                    current_apartment = {}
                continue

            # Extract specific fields using patterns
            if 'name:' in line.lower() or 'property:' in line.lower():
                current_apartment['property_name'] = line.split(':', 1)[1].strip()
            elif 'address:' in line.lower() or 'location:' in line.lower():
                current_apartment['address'] = line.split(':', 1)[1].strip()
            elif 'rent:' in line.lower() or 'price:' in line.lower():
                current_apartment['rent'] = line.split(':', 1)[1].strip()
            elif 'bedroom' in line.lower() or 'bath' in line.lower():
                current_apartment['bedrooms_bathrooms'] = line.strip()
            elif 'sqft' in line.lower() or 'square' in line.lower():
                current_apartment['square_footage'] = line.strip()

        # Add last apartment if exists
        if current_apartment:
            current_apartment['source_url'] = source_url
            current_apartment['scraped_at'] = datetime.now().isoformat()
            apartments.append(current_apartment)

        return apartments

    async def scrape_multiple_cities(self, cities_states: list, max_pages_per_city: int = 2):
        """Scrape apartments from multiple cities"""
        print(f"\n🌆 Scraping apartments from {len(cities_states)} cities...")

        all_apartments = []

        for i, (city, state) in enumerate(cities_states, 1):
            print(f"\n--- Processing City {i}/{len(cities_states)}: {city}, {state} ---")

            try:
                # Generate URLs for this city
                urls = self.generate_apartments_urls(city, state, max_pages_per_city)

                city_apartments = []

                # Scrape each URL
                for j, url in enumerate(urls, 1):
                    print(f"\n🔄 Processing page {j}/{len(urls)} for {city}, {state}")

                    apartments = await self.scrape_apartments_page(url)
                    if apartments:
                        city_apartments.extend(apartments)
                        all_apartments.extend(apartments)

                    # Rate limiting - wait between requests
                    if j < len(urls):
                        print("⏳ Waiting 3 seconds before next request...")
                        await asyncio.sleep(3)

                print(f"📊 Found {len(city_apartments)} apartments in {city}, {state}")

                # Save city data
                await self.save_apartments_data(city_apartments, f"{city}_{state}")

                # Wait between cities
                if i < len(cities_states):
                    print("⏳ Waiting 5 seconds before next city...")
                    await asyncio.sleep(5)

            except Exception as e:
                print(f"❌ Error processing {city}, {state}: {e}")
                continue

        print(f"\n📊 Total apartments found across all cities: {len(all_apartments)}")
        return all_apartments

    async def save_apartments_data(self, apartments: list, filename_prefix: str = "apartments"):
        """Save scraped apartment data to files"""
        if not apartments:
            print("⚠️  No apartment data to save")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save as JSON
        json_file = self.output_dir / f"{filename_prefix}_{timestamp}.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(apartments, f, indent=2, ensure_ascii=False)

        print(f"💾 Saved JSON data: {json_file}")

        # Save as CSV
        if apartments:
            csv_file = self.output_dir / f"{filename_prefix}_{timestamp}.csv"

            # Get all unique keys from all apartments
            all_keys = set()
            for apt in apartments:
                all_keys.update(apt.keys())

            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=sorted(all_keys))
                writer.writeheader()
                writer.writerows(apartments)

            print(f"📊 Saved CSV data: {csv_file}")

        # Save summary
        summary_file = self.output_dir / f"{filename_prefix}_summary_{timestamp}.txt"
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write(f"Apartments Scraping Summary\n")
            f.write(f"Generated on: {datetime.now().isoformat()}\n")
            f.write(f"Total apartments: {len(apartments)}\n\n")

            for i, apt in enumerate(apartments, 1):
                f.write(f"Apartment {i}:\n")
                for key, value in apt.items():
                    f.write(f"  {key}: {value}\n")
                f.write("\n")

        print(f"📝 Saved summary: {summary_file}")

    async def check_url_accessibility(self, urls: list):
        """Check if apartments.com URLs are accessible"""
        print("\n🔍 Checking URL accessibility...")

        accessible_urls = []

        for url in urls[:3]:  # Check first 3 URLs
            message = f"""Check if this URL is accessible: {url}

Use the check_accessibility tool to verify if the URL responds properly and is available for scraping."""

            result = await self.agent_service.process_message(
                message=message,
                session_id=self.session_id,
                user_id=self.user_id,
                conversation_id="accessibility_check"
            )

            if result['success']:
                print(f"✅ URL accessible: {url}")
                accessible_urls.append(url)
            else:
                print(f"❌ URL not accessible: {url}")

            await asyncio.sleep(1)

        print(f"📊 Accessible URLs: {len(accessible_urls)}/{len(urls[:3])}")
        return accessible_urls

    async def demonstrate_apartment_search(self, search_criteria: dict):
        """Demonstrate apartment search with specific criteria"""
        print(f"\n🔍 Demonstrating apartment search with criteria:")
        for key, value in search_criteria.items():
            print(f"  {key}: {value}")

        city = search_criteria.get('city', 'San Francisco')
        state = search_criteria.get('state', 'CA')
        max_price = search_criteria.get('max_price', 3000)
        min_bedrooms = search_criteria.get('min_bedrooms', 1)

        # Generate search URL
        search_location = f"{city.lower().replace(' ', '-')}-{state.lower()}"
        search_url = f"https://www.apartments.com/{search_location}/"

        print(f"🔗 Search URL: {search_url}")

        # Scrape the search results
        apartments = await self.scrape_apartments_page(search_url)

        if apartments:
            # Filter results based on criteria (if possible)
            filtered_apartments = []

            for apt in apartments:
                # Simple filtering based on available data
                rent_str = apt.get('rent', '').lower()
                bedrooms_str = apt.get('bedrooms_bathrooms', '').lower()

                # Extract price if available
                price_match = re.search(r'\$(\d{1,3}(?:,\d{3})*)', rent_str)
                if price_match:
                    price = int(price_match.group(1).replace(',', ''))
                    if price <= max_price:
                        filtered_apartments.append(apt)
                else:
                    # Include if we can't determine price
                    filtered_apartments.append(apt)

            print(f"🏠 Found {len(apartments)} total apartments")
            print(f"✅ {len(filtered_apartments)} apartments match criteria")

            # Save filtered results
            if filtered_apartments:
                await self.save_apartments_data(
                    filtered_apartments,
                    f"filtered_{city}_{state}"
                )

            return filtered_apartments
        else:
            print("❌ No apartments found for the search criteria")
            return []

    async def run_comprehensive_demo(self):
        """Run the complete apartments.com scraping demonstration"""
        print("\n" + "=" * 80)
        print("🏠 COMPREHENSIVE APARTMENTS.COM SCRAPING DEMO")
        print("=" * 80)

        try:
            # 1. Check scraper availability
            if not await self.check_scraper_availability():
                print("❌ Web Scraper agent not available. Exiting demo.")
                return

            # 2. Define cities to scrape
            cities_to_scrape = [
                ("San Francisco", "CA"),
                ("Austin", "TX"),
                ("Seattle", "WA")
            ]

            print(f"\n📍 Cities to scrape: {len(cities_to_scrape)}")
            for city, state in cities_to_scrape:
                print(f"  - {city}, {state}")

            # 3. Check URL accessibility
            sample_urls = [
                "https://www.apartments.com/san-francisco-ca/",
                "https://www.apartments.com/austin-tx/",
                "https://www.apartments.com/seattle-wa/"
            ]

            accessible_urls = await self.check_url_accessibility(sample_urls)

            if not accessible_urls:
                print("❌ No URLs are accessible. This might be due to:")
                print("  - Rate limiting by apartments.com")
                print("  - Network connectivity issues")
                print("  - Site blocking automated requests")
                print("\n💡 Try using proxy configuration in agent_config.yaml")
                return

            # 4. Demonstrate single city scraping
            print("\n--- Single City Scraping Demo ---")
            single_city_apartments = await self.scrape_apartments_page(accessible_urls[0])

            if single_city_apartments:
                await self.save_apartments_data(single_city_apartments, "single_city_demo")

            # 5. Demonstrate search with criteria
            print("\n--- Apartment Search with Criteria Demo ---")
            search_criteria = {
                'city': 'San Francisco',
                'state': 'CA',
                'max_price': 4000,
                'min_bedrooms': 2
            }

            search_results = await self.demonstrate_apartment_search(search_criteria)

            # 6. Multiple cities scraping (limited for demo)
            print("\n--- Multiple Cities Scraping Demo ---")

            # Limit to first 2 cities for demo
            limited_cities = cities_to_scrape[:2]
            all_apartments = await self.scrape_multiple_cities(limited_cities, max_pages_per_city=1)

            # 7. Save consolidated results
            if all_apartments:
                await self.save_apartments_data(all_apartments, "all_cities_consolidated")

            # 8. Generate final report
            print("\n--- Final Report ---")
            total_apartments = len(all_apartments)

            if total_apartments > 0:
                # Analyze data
                cities_found = set()
                price_ranges = []

                for apt in all_apartments:
                    source_url = apt.get('source_url', '')
                    if 'san-francisco' in source_url:
                        cities_found.add('San Francisco, CA')
                    elif 'austin' in source_url:
                        cities_found.add('Austin, TX')
                    elif 'seattle' in source_url:
                        cities_found.add('Seattle, WA')

                    # Extract price if available
                    rent = apt.get('rent', '')
                    price_match = re.search(r'\$(\d{1,3}(?:,\d{3})*)', rent)
                    if price_match:
                        price_ranges.append(int(price_match.group(1).replace(',', '')))

                print(f"📊 Scraping Results Summary:")
                print(f"  🏠 Total apartments found: {total_apartments}")
                print(f"  🌆 Cities covered: {len(cities_found)}")
                print(f"  📍 Cities: {', '.join(cities_found)}")

                if price_ranges:
                    print(f"  💰 Price range: ${min(price_ranges):,} - ${max(price_ranges):,}")
                    print(f"  💰 Average price: ${sum(price_ranges) // len(price_ranges):,}")

                print(f"  📁 Data saved to: {self.output_dir}")

                # List output files
                output_files = list(self.output_dir.glob("*"))
                print(f"  📄 Files generated: {len(output_files)}")
                for file in output_files[-5:]:  # Show last 5 files
                    print(f"    - {file.name}")

            print("\n✅ Apartments.com scraping demo completed successfully!")
            print("\n💡 Tips for production use:")
            print("  - Configure proxy settings for better success rates")
            print("  - Implement longer delays between requests")
            print("  - Use residential proxies for large-scale scraping")
            print("  - Respect robots.txt and terms of service")
            print("  - Consider using apartment APIs when available")

        except Exception as e:
            print(f"\n❌ Demo failed with error: {e}")
            import traceback
            traceback.print_exc()

    async def cleanup(self):
        """Clean up demo resources"""
        print("\n🧹 Cleaning up demo resources...")

        # Delete the demo session
        if self.session_id:
            success = self.agent_service.delete_session(self.session_id)
            if success:
                print(f"✅ Deleted demo session: {self.session_id}")

        print("✅ Cleanup completed")


async def main():
    """Main function to run the apartments.com scraping demo"""
    import argparse

    parser = argparse.ArgumentParser(description="Apartments.com Scraping Demo")
    parser.add_argument("--city", default="San Francisco", help="City to search")
    parser.add_argument("--state", default="CA", help="State abbreviation")
    parser.add_argument("--max-price", type=int, default=5000, help="Maximum rent price")
    parser.add_argument("--min-bedrooms", type=int, default=1, help="Minimum bedrooms")
    parser.add_argument("--max-pages", type=int, default=2, help="Maximum pages to scrape")
    parser.add_argument("--url", help="Specific apartments.com URL to scrape")

    args = parser.parse_args()

    try:
        demo = ApartmentsScrapingDemo()

        if args.url:
            # Scrape specific URL
            print(f"🎯 Scraping specific URL: {args.url}")

            if await demo.check_scraper_availability():
                apartments = await demo.scrape_apartments_page(args.url)
                if apartments:
                    await demo.save_apartments_data(apartments, "specific_url")
                    print(f"✅ Found {len(apartments)} apartments")
                else:
                    print("❌ No apartments found")
        else:
            # Use search criteria
            search_criteria = {
                'city': args.city,
                'state': args.state,
                'max_price': args.max_price,
                'min_bedrooms': args.min_bedrooms
            }

            print(f"🔍 Searching apartments with criteria: {search_criteria}")

            if await demo.check_scraper_availability():
                # Run targeted search
                apartments = await demo.demonstrate_apartment_search(search_criteria)

                if apartments:
                    print(f"✅ Found {len(apartments)} apartments matching criteria")
                else:
                    print("❌ No apartments found matching criteria")
                    print("\n🚀 Running full comprehensive demo instead...")
                    await demo.run_comprehensive_demo()

        await demo.cleanup()

    except KeyboardInterrupt:
        print("\n\n⚠️  Demo interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())