"""
TATty Agent Installation Tests

This module provides basic tests to validate your TATty Agent installation.
After installation, you can run these tests to ensure everything works:

```python
from tatty_agent.tests import run_installation_tests, test_basic_functionality

# Run all installation tests
run_installation_tests()

# Test basic functionality
test_basic_functionality()
```
"""

import tempfile
import traceback
from pathlib import Path
from typing import Dict, Any

def test_basic_imports() -> Dict[str, Any]:
    """Test that all basic imports work"""
    result = {"test": "basic_imports", "passed": False, "error": None}

    try:
        # Test main package imports
        from tatty_agent import TattyAgent, run_agent, ask_agent, initialize_project
        from tatty_agent.config import TattyConfig, load_config
        from tatty_agent.core import AgentRuntime, AgentState, AgentCallbacks

        result["passed"] = True
        result["message"] = "All basic imports successful"

    except Exception as e:
        result["error"] = str(e)
        result["message"] = f"Import failed: {e}"

    return result

def test_agent_creation() -> Dict[str, Any]:
    """Test that we can create an agent instance"""
    result = {"test": "agent_creation", "passed": False, "error": None}

    try:
        from tatty_agent import TattyAgent

        with tempfile.TemporaryDirectory() as temp_dir:
            agent = TattyAgent(working_dir=temp_dir, verbose=False)

            assert hasattr(agent, 'working_dir')
            assert hasattr(agent, 'get_conversation_history')
            assert hasattr(agent, 'run')

            result["passed"] = True
            result["message"] = "Agent creation successful"

    except Exception as e:
        result["error"] = str(e)
        result["message"] = f"Agent creation failed: {e}"

    return result

def test_configuration() -> Dict[str, Any]:
    """Test configuration system"""
    result = {"test": "configuration", "passed": False, "error": None}

    try:
        from tatty_agent.config import TattyConfig, load_config

        # Test config creation
        config = TattyConfig(verbose=True, max_iterations=10)
        assert config.verbose is True
        assert config.max_iterations == 10

        # Test config loading
        loaded_config = load_config(verbose=False)
        assert hasattr(loaded_config, 'verbose')

        result["passed"] = True
        result["message"] = "Configuration system working"

    except Exception as e:
        result["error"] = str(e)
        result["message"] = f"Configuration test failed: {e}"

    return result

def test_project_initialization() -> Dict[str, Any]:
    """Test project initialization functionality"""
    result = {"test": "project_initialization", "passed": False, "error": None}

    try:
        from tatty_agent.config.initialization import ProjectInitializer

        with tempfile.TemporaryDirectory() as temp_dir:
            initializer = ProjectInitializer(temp_dir)

            # Test status check
            status = initializer.check_project_status()
            assert "initialized" in status

            # Test initialization
            init_result = initializer.initialize_project()
            assert init_result["success"] is True

            result["passed"] = True
            result["message"] = "Project initialization working"

    except Exception as e:
        result["error"] = str(e)
        result["message"] = f"Project initialization test failed: {e}"

    return result

def test_examples_access() -> Dict[str, Any]:
    """Test that examples are accessible"""
    result = {"test": "examples_access", "passed": False, "error": None}

    try:
        from tatty_agent.examples import list_examples, get_example_notebook

        examples = list_examples()
        assert isinstance(examples, list)

        # Try to get an example
        if examples:
            example_path = get_example_notebook(examples[0])
            assert example_path is not None
            assert example_path.exists()

        result["passed"] = True
        result["message"] = f"Examples accessible: {len(examples)} found"

    except Exception as e:
        result["error"] = str(e)
        result["message"] = f"Examples access test failed: {e}"

    return result

def test_docs_access() -> Dict[str, Any]:
    """Test that documentation is accessible"""
    result = {"test": "docs_access", "passed": False, "error": None}

    try:
        from tatty_agent.docs import list_docs, get_docs_dir

        docs = list_docs()
        assert isinstance(docs, list)

        docs_dir = get_docs_dir()
        assert docs_dir.exists()

        result["passed"] = True
        result["message"] = f"Documentation accessible: {len(docs)} files found"

    except Exception as e:
        result["error"] = str(e)
        result["message"] = f"Documentation access test failed: {e}"

    return result

def test_optional_imports() -> Dict[str, Any]:
    """Test optional feature imports"""
    result = {"test": "optional_imports", "passed": True, "error": None, "warnings": []}

    # Test Jupyter integration (optional)
    try:
        from tatty_agent.jupyter import create_chat_widget, display_agent_response
        result["jupyter"] = True
    except ImportError as e:
        result["jupyter"] = False
        result["warnings"].append(f"Jupyter integration not available: {e}")

    # Test TUI components (optional)
    try:
        from tatty_agent.tui import TattyApp
        result["tui"] = True
    except ImportError as e:
        result["tui"] = False
        result["warnings"].append(f"TUI components not available: {e}")

    result["message"] = "Optional imports checked"
    return result

def run_installation_tests() -> Dict[str, Any]:
    """
    Run all installation validation tests.

    Returns:
        Dictionary with test results and summary
    """
    print("🧪 Running TATty Agent Installation Tests")
    print("=" * 50)

    tests = [
        test_basic_imports,
        test_agent_creation,
        test_configuration,
        test_project_initialization,
        test_examples_access,
        test_docs_access,
        test_optional_imports,
    ]

    results = []
    passed = 0
    failed = 0

    for test_func in tests:
        try:
            result = test_func()
            results.append(result)

            if result["passed"]:
                print(f"✅ {result['test']}: {result['message']}")
                passed += 1
            else:
                print(f"❌ {result['test']}: {result['message']}")
                failed += 1

            # Show warnings if any
            if "warnings" in result and result["warnings"]:
                for warning in result["warnings"]:
                    print(f"   ⚠️  {warning}")

        except Exception as e:
            print(f"💥 {test_func.__name__}: Unexpected error: {e}")
            failed += 1
            results.append({
                "test": test_func.__name__,
                "passed": False,
                "error": str(e),
                "message": f"Unexpected error: {e}"
            })

    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed} passed, {failed} failed")

    if failed == 0:
        print("🎉 All tests passed! TATty Agent is properly installed.")
    else:
        print(f"❌ {failed} tests failed. Installation may have issues.")

    return {
        "summary": {"passed": passed, "failed": failed, "total": len(tests)},
        "results": results
    }

def test_basic_functionality():
    """Quick test of basic TATty Agent functionality"""
    print("⚡ Quick Functionality Test")
    print("-" * 30)

    try:
        from tatty_agent import TattyAgent

        agent = TattyAgent(verbose=False)
        print(f"✅ Agent created: {type(agent).__name__}")

        history = agent.get_conversation_history()
        print(f"✅ Conversation history accessible: {len(history)} items")

        print("🎉 Basic functionality working!")

    except Exception as e:
        print(f"❌ Basic functionality test failed: {e}")
        traceback.print_exc()

__all__ = [
    'test_basic_imports',
    'test_agent_creation',
    'test_configuration',
    'test_project_initialization',
    'test_examples_access',
    'test_docs_access',
    'test_optional_imports',
    'run_installation_tests',
    'test_basic_functionality'
]