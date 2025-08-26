#!/usr/bin/env python3

import os
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Test API keys
api_keys = [
    "AIzaSyDkcp6_1PV5M56KSukTBzwqK4bKXOIo_cs",
    "AIzaSyA1oWpnRQ6Ik-gBGSeh6OO-2Il2gaMQzRI"
]

print("Testing Gemini API keys...\n")

for i, api_key in enumerate(api_keys, 1):
    print(f"Testing API Key {i}: {api_key[:15]}...")
    
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content("Say hello")
        print(f"✅ API Key {i} WORKS!")
        print(f"Response: {response.text[:100]}...")
        print()
        break
    except Exception as e:
        print(f"❌ API Key {i} failed: {str(e)[:100]}...")
        print()

print("Test complete!")
