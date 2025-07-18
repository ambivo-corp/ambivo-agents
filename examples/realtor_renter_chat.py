#!/usr/bin/env python3
"""
Simple Interactive Realtor-Renter Chat System

This example demonstrates a simple interactive chat where users can participate
in a realtor-renter workflow with real-time terminal input.

Features:
- Simple interactive terminal chat
- Real property search using sample data
- Step-by-step rental process
- User can chat and participate in the workflow
"""

import asyncio
import json
import os
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

from ambivo_agents import AssistantAgent


def get_user_input(prompt: str) -> str:
    """Get user input with fallback for different environments"""
    try:
        return input(prompt)
    except (EOFError, KeyboardInterrupt):
        return ""


@dataclass
class RenterPreferences:
    """Data structure to track renter preferences"""
    bedrooms: Optional[int] = None
    budget_max: Optional[int] = None
    property_type: Optional[str] = None
    location: Optional[str] = None
    amenities: List[str] = field(default_factory=list)
    
    def is_complete(self) -> bool:
        """Check if we have enough information to search"""
        return (self.bedrooms is not None and 
                self.budget_max is not None and 
                self.property_type is not None)


# Sample property data
SAMPLE_PROPERTIES = [
    {
        "id": 1,
        "address": "123 Downtown Loft",
        "bedrooms": 1,
        "bathrooms": 1,
        "rent": 1200,
        "property_type": "apartment",
        "location": "downtown",
        "amenities": ["gym", "parking", "pool"]
    },
    {
        "id": 2,
        "address": "456 Midtown Studio",
        "bedrooms": 0,
        "bathrooms": 1,
        "rent": 900,
        "property_type": "studio",
        "location": "midtown", 
        "amenities": ["laundry", "gym"]
    },
    {
        "id": 3,
        "address": "789 Suburban House",
        "bedrooms": 2,
        "bathrooms": 2,
        "rent": 1500,
        "property_type": "house",
        "location": "suburbs",
        "amenities": ["parking", "yard", "laundry"]
    },
    {
        "id": 4,
        "address": "321 City Center Apt",
        "bedrooms": 2,
        "bathrooms": 1,
        "rent": 1400,
        "property_type": "apartment",
        "location": "downtown",
        "amenities": ["gym", "pool", "doorman"]
    },
    {
        "id": 5,
        "address": "654 Budget Friendly",
        "bedrooms": 1,
        "bathrooms": 1,
        "rent": 800,
        "property_type": "apartment",
        "location": "uptown",
        "amenities": ["laundry"]
    }
]


class SimpleRealtorChat:
    """Simple interactive realtor chat system"""
    
    def __init__(self):
        self.realtor = AssistantAgent.create_simple(
            user_id="realtor_agent",
            system_message="""You are a helpful realtor. Ask questions about housing needs:
            - How many bedrooms?
            - What's your budget?
            - Preferred location?
            - Any specific amenities?
            
            Be conversational and helpful. When presenting properties, highlight key features."""
        )
        self.preferences = RenterPreferences()
        self.properties = SAMPLE_PROPERTIES
    
    async def collect_preferences(self):
        """Collect user preferences step by step"""
        print("\\n🏠 Welcome! I'm your realtor assistant. Let's find you the perfect rental!")
        print("I'll ask you a few questions to understand your needs.\\n")
        
        # Get bedrooms
        while self.preferences.bedrooms is None:
            response = get_user_input("How many bedrooms do you need? (0 for studio, 1, 2, 3+): ")
            try:
                bedrooms = int(response)
                if 0 <= bedrooms <= 5:
                    self.preferences.bedrooms = bedrooms
                    break
                else:
                    print("Please enter a number between 0 and 5.")
            except ValueError:
                print("Please enter a valid number.")
        
        # Get budget
        while self.preferences.budget_max is None:
            response = get_user_input("What's your maximum monthly budget? $")
            try:
                budget = int(response)
                if budget > 0:
                    self.preferences.budget_max = budget
                    break
                else:
                    print("Please enter a positive number.")
            except ValueError:
                print("Please enter a valid number.")
        
        # Get property type
        while self.preferences.property_type is None:
            print("\\nProperty types: apartment, house, studio, condo")
            response = get_user_input("What type of property do you prefer? ").lower().strip()
            if response in ["apartment", "house", "studio", "condo"]:
                self.preferences.property_type = response
                break
            else:
                print("Please choose from: apartment, house, studio, condo")
        
        # Get location (optional)
        response = get_user_input("Preferred location? (downtown, midtown, suburbs, uptown, or press Enter to skip): ").lower().strip()
        if response in ["downtown", "midtown", "suburbs", "uptown"]:
            self.preferences.location = response
        
        # Get amenities (optional)
        print("\\nCommon amenities: gym, pool, parking, laundry, yard, doorman")
        response = get_user_input("Any important amenities? (comma-separated, or press Enter to skip): ").strip()
        if response:
            self.preferences.amenities = [a.strip().lower() for a in response.split(",")]
        
        print("\\n✅ Great! I have all the information I need. Let me search for properties...")
    
    def search_properties(self) -> List[Dict[str, Any]]:
        """Search properties based on preferences"""
        matches = []
        
        for prop in self.properties:
            score = 0
            
            # Check bedrooms
            if self.preferences.bedrooms is not None:
                if prop["bedrooms"] == self.preferences.bedrooms:
                    score += 10
                elif abs(prop["bedrooms"] - self.preferences.bedrooms) <= 1:
                    score += 5
            
            # Check budget
            if self.preferences.budget_max and prop["rent"] <= self.preferences.budget_max:
                score += 10
            
            # Check property type
            if self.preferences.property_type and prop["property_type"] == self.preferences.property_type:
                score += 8
            
            # Check location
            if self.preferences.location and prop["location"] == self.preferences.location:
                score += 6
            
            # Check amenities
            if self.preferences.amenities:
                matching_amenities = set(self.preferences.amenities) & set(prop["amenities"])
                score += len(matching_amenities) * 2
            
            if score > 0:
                matches.append({"property": prop, "score": score})
        
        # Sort by score
        matches.sort(key=lambda x: x["score"], reverse=True)
        return matches
    
    async def present_properties(self, matches: List[Dict[str, Any]]):
        """Present matching properties to user"""
        if not matches:
            print("\\n😞 Sorry, I couldn't find any properties matching your criteria.")
            print("Would you like to adjust your preferences?")
            return
        
        print(f"\\n🎉 Great! I found {len(matches)} properties that match your criteria:")
        print("=" * 60)
        
        for i, match in enumerate(matches[:5], 1):  # Show top 5
            prop = match["property"]
            score = match["score"]
            
            print(f"\\n{i}. {prop['address']}")
            print(f"   💰 Rent: ${prop['rent']}/month")
            print(f"   🛏️  {prop['bedrooms']} bedrooms, {prop['bathrooms']} bathrooms")
            print(f"   🏢 Type: {prop['property_type'].title()}")
            print(f"   📍 Location: {prop['location'].title()}")
            print(f"   ✨ Amenities: {', '.join(prop['amenities'])}")
            print(f"   📊 Match Score: {score}/30")
        
        # Ask for user feedback
        print("\\n" + "=" * 60)
        response = get_user_input("\\nWhich property interests you most? (Enter number 1-5, or 'none' if you'd like different options): ")
        
        if response.isdigit() and 1 <= int(response) <= min(5, len(matches)):
            selected_prop = matches[int(response)-1]["property"]
            await self.discuss_property(selected_prop)
        elif response.lower() == 'none':
            print("\\nNo problem! Let me know if you'd like to:")
            print("1. Adjust your budget")
            print("2. Look at different locations")
            print("3. Consider different property types")
            print("4. Start a new search")
        else:
            print("\\nI didn't understand that. Feel free to ask me about any of these properties!")
    
    async def discuss_property(self, prop: Dict[str, Any]):
        """Have a conversation about a specific property"""
        print(f"\\n🏠 Great choice! Let's talk about {prop['address']}")
        
        # Use the realtor agent to provide more details
        property_details = f"""
        Property: {prop['address']}
        Rent: ${prop['rent']}/month
        Bedrooms: {prop['bedrooms']}
        Bathrooms: {prop['bathrooms']}
        Type: {prop['property_type']}
        Location: {prop['location']}
        Amenities: {', '.join(prop['amenities'])}
        """
        
        realtor_response = await self.realtor.chat(
            f"A client is interested in this property: {property_details}. "
            "Tell them more about what makes this property special and ask if they have any questions."
        )
        
        print(f"\\n🏠 REALTOR: {realtor_response}")
        
        # Continue conversation
        while True:
            user_question = get_user_input("\\nYour question (or 'done' to finish): ")
            
            if user_question.lower() in ['done', 'quit', 'exit', '']:
                print("\\n👋 Thanks for looking at properties with me today!")
                break
            
            realtor_response = await self.realtor.chat(
                f"Client question about {prop['address']}: {user_question}. "
                "Provide a helpful, realistic response as a realtor."
            )
            
            print(f"\\n🏠 REALTOR: {realtor_response}")
    
    async def start_conversation(self):
        """Start the interactive conversation"""
        try:
            # Step 1: Collect preferences
            await self.collect_preferences()
            
            # Step 2: Search properties
            matches = self.search_properties()
            
            # Step 3: Present and discuss properties
            await self.present_properties(matches)
            
        except KeyboardInterrupt:
            print("\\n\\n👋 Thanks for using the realtor chat system!")
        except Exception as e:
            print(f"\\n❌ An error occurred: {e}")
        finally:
            await self.cleanup()
    
    async def cleanup(self):
        """Cleanup resources"""
        await self.realtor.cleanup_session()


async def main():
    """Main function to run the simple realtor chat"""
    print("🏠 Simple Interactive Realtor Chat System")
    print("=" * 50)
    print("This is a simple demonstration where you can:")
    print("• Answer questions about your housing preferences")
    print("• See matching properties from our sample database")
    print("• Ask questions about specific properties")
    print()
    
    chat = SimpleRealtorChat()
    await chat.start_conversation()


if __name__ == "__main__":
    asyncio.run(main())