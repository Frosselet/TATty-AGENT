#!/usr/bin/env python3
"""
Test script for the new intent classification system
"""
import asyncio
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from baml_client.async_client import b
from baml_client import types

async def test_intent_classification():
    """Test the intent classification system with various queries"""

    test_cases = [
        # These should be classified as ExecutableCode
        "Generate a small pandas DataFrame with sample data",
        "Create a plot showing sales over time",
        "Build me a simple machine learning model",
        "Calculate the mean of this dataset",
        "Make a histogram of the data",

        # These should be classified as TextResponse
        "What is pandas?",
        "How does machine learning work?",
        "Explain the difference between supervised and unsupervised learning",
        "What do you think about this approach?",

        # These should be classified as ToolExecution
        "Read the file data.csv",
        "Search for all Python files in the project",
        "Install the requests package",
        "Run the tests",
        "Find all TODO comments in the code"
    ]

    print("🧪 Testing Intent Classification System")
    print("=" * 50)

    for i, query in enumerate(test_cases, 1):
        print(f"\n{i}. Query: {query}")
        try:
            intent_result = await b.ClassifyUserIntent(user_query=query)
            print(f"   Intent: {intent_result.intent}")
            print(f"   Confidence: {intent_result.confidence}")
            print(f"   Reasoning: {intent_result.reasoning}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

    print("\n" + "=" * 50)
    print("✅ Intent classification test completed!")

async def test_agent_dispatcher():
    """Test the AgentDispatcher with a DataFrame generation request"""
    print("\n🚀 Testing AgentDispatcher for DataFrame Generation")
    print("=" * 50)

    query = "Generate a small pandas DataFrame with sample data"

    # Step 1: Classify intent
    print(f"Query: {query}")
    intent_result = await b.ClassifyUserIntent(user_query=query)
    print(f"Intent: {intent_result.intent}")

    # Step 2: Call AgentDispatcher
    response = await b.AgentDispatcher(
        user_query=query,
        intent=intent_result,
        state=[],  # Empty state for test
        working_dir="."
    )

    print(f"Response type: {type(response).__name__}")

    if isinstance(response, types.ReplyWithCode):
        print("✅ SUCCESS: Got ReplyWithCode response!")
        print(f"Message: {response.message}")
        print(f"Python code: {response.python_code}")
    elif isinstance(response, types.ReplyToUser):
        print(f"⚠️  Got ReplyToUser instead of ReplyWithCode")
        print(f"Message: {response.message}")
    else:
        print(f"❌ Unexpected response type: {type(response)}")
        print(f"Response: {response}")

if __name__ == "__main__":
    asyncio.run(test_intent_classification())
    asyncio.run(test_agent_dispatcher())