from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class TestCase:
    name: str
    command: str
    expected_patterns: List[str]
    forbidden_patterns: List[str]
    timeout_sec: float = 30.0


@dataclass
class TestResult:
    case_name: str
    passed: bool
    duration_sec: float
    output: str
    error: Optional[str]
    details: Dict[str, Any]


class PluginTestFramework:
    """Test framework for validating plugin implementations."""
    
    def __init__(self, plugins_dir: str = "./autodetector/plugins/builtin"):
        self.plugins_dir = plugins_dir
        self.test_results: List[TestResult] = []
    
    def test_plugin_structure(self, os_name: str) -> TestResult:
        """Test that plugin has required files."""
        plugin_dir = os.path.join(self.plugins_dir, os_name)
        
        start_time = __import__('time').time()
        
        required_files = [
            "command_map.yaml",
            "variable_map.yaml",
            "parser.py",
        ]
        
        missing = []
        for f in required_files:
            if not os.path.exists(os.path.join(plugin_dir, f)):
                missing.append(f)
        
        duration = __import__('time').time() - start_time
        
        return TestResult(
            case_name="plugin_structure",
            passed=len(missing) == 0,
            duration_sec=duration,
            output=f"Plugin directory: {plugin_dir}",
            error=f"Missing files: {missing}" if missing else None,
            details={"missing_files": missing}
        )
    
    def test_variable_map_schema(self, os_name: str) -> TestResult:
        """Test that variable_map.yaml has valid schema."""
        import yaml
        
        start_time = __import__('time').time()
        
        var_map_path = os.path.join(self.plugins_dir, os_name, "variable_map.yaml")
        
        try:
            with open(var_map_path) as f:
                data = yaml.safe_load(f)
            
            schema = data.get("schema", {})
            os_in_schema = schema.get("os")
            variables = schema.get("variables", {})
            
            errors = []
            
            if os_in_schema != os_name:
                errors.append(f"OS mismatch: expected {os_name}, got {os_in_schema}")
            
            # Validate each variable
            for var_name, var_def in variables.items():
                if "type" not in var_def:
                    errors.append(f"Variable {var_name} missing 'type'")
                if "unit" not in var_def:
                    errors.append(f"Variable {var_name} missing 'unit'")
                if "source_command" not in var_def:
                    errors.append(f"Variable {var_name} missing 'source_command'")
            
            duration = __import__('time').time() - start_time
            
            return TestResult(
                case_name="variable_map_schema",
                passed=len(errors) == 0,
                duration_sec=duration,
                output=f"Found {len(variables)} variables",
                error="; ".join(errors) if errors else None,
                details={"variable_count": len(variables), "errors": errors}
            )
            
        except Exception as e:
            duration = __import__('time').time() - start_time
            return TestResult(
                case_name="variable_map_schema",
                passed=False,
                duration_sec=duration,
                output="",
                error=str(e),
                details={}
            )
    
    def test_parser_imports(self, os_name: str) -> TestResult:
        """Test that parser.py can be imported without errors."""
        start_time = __import__('time').time()
        
        try:
            # Add plugins dir to path temporarily
            import sys
            sys.path.insert(0, self.plugins_dir)
            
            module_name = f"{os_name}.parser"
            __import__(module_name)
            
            duration = __import__('time').time() - start_time
            
            return TestResult(
                case_name="parser_import",
                passed=True,
                duration_sec=duration,
                output=f"Successfully imported {module_name}",
                error=None,
                details={}
            )
            
        except Exception as e:
            duration = __import__('time').time() - start_time
            return TestResult(
                case_name="parser_import",
                passed=False,
                duration_sec=duration,
                output="",
                error=str(e),
                details={}
            )
        finally:
            if self.plugins_dir in sys.path:
                sys.path.remove(self.plugins_dir)
    
    def test_parser_function(self, os_name: str) -> TestResult:
        """Test that parser.parse function exists and is callable."""
        start_time = __import__('time').time()
        
        try:
            import sys
            sys.path.insert(0, self.plugins_dir)
            
            module = __import__(f"{os_name}.parser", fromlist=["parse"])
            parse_func = getattr(module, "parse", None)
            
            if not parse_func:
                return TestResult(
                    case_name="parser_function",
                    passed=False,
                    duration_sec=__import__('time').time() - start_time,
                    output="",
                    error="parse function not found",
                    details={}
                )
            
            if not callable(parse_func):
                return TestResult(
                    case_name="parser_function",
                    passed=False,
                    duration_sec=__import__('time').time() - start_time,
                    output="",
                    error="parse is not callable",
                    details={}
                )
            
            # Test with empty inputs
            result = parse_func({}, {}, {"id": "test"})
            
            duration = __import__('time').time() - start_time
            
            return TestResult(
                case_name="parser_function",
                passed="metrics" in result,
                duration_sec=duration,
                output=f"parse returned: {result.keys()}",
                error=None,
                details={"return_keys": list(result.keys())}
            )
            
        except Exception as e:
            duration = __import__('time').time() - start_time
            return TestResult(
                case_name="parser_function",
                passed=False,
                duration_sec=duration,
                output="",
                error=str(e),
                details={}
            )
        finally:
            if self.plugins_dir in sys.path:
                sys.path.remove(self.plugins_dir)
    
    def run_all_tests(self, os_name: str) -> Dict[str, Any]:
        """Run all tests for a plugin."""
        tests = [
            self.test_plugin_structure,
            self.test_variable_map_schema,
            self.test_parser_imports,
            self.test_parser_function,
        ]
        
        results = []
        for test in tests:
            result = test(os_name)
            results.append(result)
        
        passed = sum(1 for r in results if r.passed)
        failed = len(results) - passed
        
        return {
            "os_name": os_name,
            "total_tests": len(results),
            "passed": passed,
            "failed": failed,
            "success_rate": passed / len(results) if results else 0,
            "results": [
                {
                    "name": r.case_name,
                    "passed": r.passed,
                    "duration_sec": r.duration_sec,
                    "error": r.error,
                }
                for r in results
            ],
        }
    
    def run_batch_tests(self, os_names: List[str]) -> Dict[str, Any]:
        """Run tests for multiple plugins."""
        batch_results = {}
        
        for os_name in os_names:
            batch_results[os_name] = self.run_all_tests(os_name)
        
        total_passed = sum(r["passed"] for r in batch_results.values())
        total_tests = sum(r["total_tests"] for r in batch_results.values())
        
        return {
            "batch_summary": {
                "total_plugins": len(os_names),
                "total_tests": total_tests,
                "total_passed": total_passed,
                "total_failed": total_tests - total_passed,
                "overall_success_rate": total_passed / total_tests if total_tests else 0,
            },
            "per_plugin": batch_results,
        }


class MockDataGenerator:
    """Generate mock CLI outputs for testing parsers."""
    
    MOCK_OUTPUTS = {
        "cisco_ios": {
            "cpu": "CPU utilization for five seconds: 15%/0%; one minute: 12%; five minutes: 10%",
            "memory": "Processor Pool Total: 234567890 Used: 123456789 Free: 111111101",
            "interfaces": "Interface IP-Address OK? Method Status Protocol\nGigabitEthernet0/0 10.0.0.1 YES NVRAM up up",
        },
        "junos": {
            "cpu": "CPU utilization: 25 percent",
            "memory": "Memory: 2048 MB total, 1024 MB used",
            "interfaces": "ge-0/0/0 up up",
        },
        "ubuntu": {
            "cpu": "%Cpu(s): 10.0 us, 5.0 sy, 0.0 ni, 85.0 id",
            "memory": "Mem: 8192 4096 4096",
            "disk": "Filesystem Size Used Avail Use%\n/dev/sda1 100G 50G 50G 50%",
        },
    }
    
    def get_mock_output(self, os_name: str, command: str) -> str:
        """Get mock output for a command."""
        os_mocks = self.MOCK_OUTPUTS.get(os_name, {})
        return os_mocks.get(command, "")
    
    def generate_test_case(
        self,
        os_name: str,
        expected_metrics: List[str]
    ) -> Dict[str, Any]:
        """Generate a test case with expected metrics."""
        commands = list(self.MOCK_OUTPUTS.get(os_name, {}).keys())
        outputs = {cmd: self.get_mock_output(os_name, cmd) for cmd in commands}
        
        return {
            "os_name": os_name,
            "mock_outputs": outputs,
            "expected_metrics": expected_metrics,
            "description": f"Test {os_name} parser with mock data",
        }
