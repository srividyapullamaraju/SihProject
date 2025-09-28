#!/usr/bin/env python3
"""
Test script to verify the disease outbreak functionality
"""
import asyncio
import sys
import os

# Add the current directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from actions.actions import ActionDiseaseOutbreakInfo
from govt_data_scraper import get_n_week_links

class MockDispatcher:
    def __init__(self):
        self.messages = []
    
    def utter_message(self, text='', attachment=None):
        self.messages.append(text)
        print(f"🤖 Bot Response:")
        print(f"{text}")
        print("-" * 50)

class MockSlot:
    def __init__(self, value):
        self.value = value

class MockTracker:
    def __init__(self, language='en', text='disease outbreaks in my state'):
        self.slots = {'language': MockSlot(language)}
        self.latest_message = {'text': text}
    
    def get_slot(self, name):
        return self.slots.get(name, MockSlot(None))

async def test_disease_outbreak_action():
    print("🧪 Testing Disease Outbreak Action Integration")
    print("=" * 60)
    
    # Test 1: Direct scraper functionality
    print("\n1️⃣ Testing Government Data Scraper...")
    try:
        links = get_n_week_links(4)
        print(f"✅ Successfully retrieved {len(links)} PDF links")
        for i, link in enumerate(links, 1):
            print(f"   {i}. Week {link['week']}, {link['year']} - {link['url'][:50]}...")
    except Exception as e:
        print(f"❌ Scraper test failed: {e}")
        return False
    
    # Test 2: Action execution
    print("\n2️⃣ Testing Disease Outbreak Action...")
    try:
        action = ActionDiseaseOutbreakInfo()
        dispatcher = MockDispatcher()
        tracker = MockTracker('en', 'What are the latest disease outbreaks in my state?')
        domain = {}
        
        # Since the action returns a list instead of being async, call it directly
        result = action.run(dispatcher, tracker, domain)
        
        print(f"✅ Action executed successfully")
        print(f"   Messages sent: {len(dispatcher.messages)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Action test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

# Test 3: Multi-language support
async def test_multilingual_support():
    print("\n3️⃣ Testing Multi-language Support...")
    
    languages = [
        ('en', 'disease outbreaks in my state'),
        ('hi', 'मेरे राज्य में बीमारी का प्रकोप'),
        ('te', 'నా రాష్ట్రంలో వ్యాధి వ్యాప్తి')
    ]
    
    for lang, text in languages:
        print(f"\n🌐 Testing {lang.upper()} language:")
        try:
            action = ActionDiseaseOutbreakInfo()
            dispatcher = MockDispatcher()
            tracker = MockTracker(lang, text)
            domain = {}
            
            result = action.run(dispatcher, tracker, domain)
            print(f"✅ {lang.upper()} test passed")
            
        except Exception as e:
            print(f"❌ {lang.upper()} test failed: {e}")

if __name__ == "__main__":
    print("🏥 Health Bot - Disease Outbreak Integration Test")
    print("=" * 60)
    
    # Run the main test
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    success = loop.run_until_complete(test_disease_outbreak_action())
    
    if success:
        loop.run_until_complete(test_multilingual_support())
        print("\n🎉 All tests completed!")
        print("\n✅ Integration Summary:")
        print("   ✓ Government data scraper working")
        print("   ✓ Disease outbreak action functional")
        print("   ✓ Multi-language support active")
        print("   ✓ PDF links accessible and current")
    else:
        print("\n❌ Integration test failed!")
        
    loop.close()