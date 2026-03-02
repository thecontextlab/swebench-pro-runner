#!/usr/bin/env python3
"""
Base class for all AI agent adapters (Claude, Codex, Gemini, etc.)
Provides common functionality for tool execution, logging, and metrics tracking.
"""

import os
import json
import subprocess
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path


class BaseAgentAdapter(ABC):
    """Base class for all agent adapters"""

    def __init__(self, task_instruction: str, config: Dict[str, Any]):
        self.task_instruction = task_instruction
        self.config = config
        self.log_file = "agent.log"
        self.start_time = datetime.now()
        self.tool_usage = {}
        self.total_tokens = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}
        self.api_calls = 0
        self.errors = []

    @abstractmethod
    def initialize_client(self) -> Any:
        """Initialize the AI client with appropriate API keys"""
        pass

    @abstractmethod
    def format_tools(self) -> Any:
        """Format tool definitions for the specific agent API"""
        pass

    @abstractmethod
    def call_agent(self, messages: List[Dict], tools: Any) -> Tuple[str, Dict]:
        """Call the specific agent API and return response and metadata"""
        pass

    def log_interaction(self, event_type: str, content: Any):
        """Log interaction to JSONL file"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "content": content
        }
        with open(self.log_file, 'a') as f:
            f.write(json.dumps(entry) + '\n')

    def read_file(self, file_path: str) -> str:
        """Read contents of a file"""
        try:
            path = Path(file_path)
            if not path.is_absolute():
                path = Path('/testbed') / path

            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            self.track_tool_usage('read_file')
            return content
        except Exception as e:
            error_msg = f"Error reading {file_path}: {str(e)}"
            self.errors.append(error_msg)
            return error_msg

    def write_file(self, file_path: str, content: str) -> str:
        """Write content to a file"""
        try:
            path = Path(file_path)
            if not path.is_absolute():
                path = Path('/testbed') / path

            # Create parent directories if they don't exist
            path.parent.mkdir(parents=True, exist_ok=True)

            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)

            self.track_tool_usage('write_file')
            return f"Successfully wrote to {file_path}"
        except Exception as e:
            error_msg = f"Error writing to {file_path}: {str(e)}"
            self.errors.append(error_msg)
            return error_msg

    def edit_file(self, file_path: str, old_string: str, new_string: str, replace_all: bool = False) -> str:
        """Edit a file by replacing text"""
        try:
            content = self.read_file(file_path)
            if content.startswith("Error reading"):
                return content

            if replace_all:
                if old_string not in content:
                    return f"String not found in {file_path}"
                new_content = content.replace(old_string, new_string)
            else:
                if old_string not in content:
                    return f"String not found in {file_path}"
                # Replace only first occurrence
                new_content = content.replace(old_string, new_string, 1)

            result = self.write_file(file_path, new_content)
            self.track_tool_usage('edit_file')
            return result
        except Exception as e:
            error_msg = f"Error editing {file_path}: {str(e)}"
            self.errors.append(error_msg)
            return error_msg

    def run_bash(self, command: str, timeout: int = 120) -> str:
        """Execute a bash command"""
        try:
            # Change to testbed directory
            full_command = f"cd /testbed && {command}"

            result = subprocess.run(
                full_command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            output = result.stdout + result.stderr
            self.track_tool_usage('run_bash')

            return output if output else f"Command executed with exit code {result.returncode}"
        except subprocess.TimeoutExpired:
            error_msg = f"Command timed out after {timeout} seconds: {command}"
            self.errors.append(error_msg)
            return error_msg
        except Exception as e:
            error_msg = f"Error executing command: {str(e)}"
            self.errors.append(error_msg)
            return error_msg

    def execute_tool(self, tool_name: str, args: Dict) -> str:
        """Execute a tool based on its name and arguments"""
        if tool_name in ['read_file', 'Read']:
            return self.read_file(args.get('path', args.get('file_path', '')))
        elif tool_name in ['write_file', 'Write']:
            return self.write_file(
                args.get('path', args.get('file_path', '')),
                args.get('content', '')
            )
        elif tool_name in ['edit_file', 'Edit']:
            return self.edit_file(
                args.get('path', args.get('file_path', '')),
                args.get('old_string', ''),
                args.get('new_string', ''),
                args.get('replace_all', False)
            )
        elif tool_name in ['run_bash', 'Bash']:
            return self.run_bash(
                args.get('command', ''),
                args.get('timeout', 120)
            )
        else:
            return f"Unknown tool: {tool_name}"

    def track_tool_usage(self, tool_name: str):
        """Track usage of a specific tool"""
        if tool_name not in self.tool_usage:
            self.tool_usage[tool_name] = 0
        self.tool_usage[tool_name] += 1

    def get_metrics(self) -> Dict:
        """Get execution metrics"""
        duration = (datetime.now() - self.start_time).total_seconds()

        return {
            "duration_seconds": duration,
            "duration_api_seconds": duration,  # Can be overridden by specific adapters
            "total_cost_usd": self.calculate_cost(),
            "tokens": self.total_tokens,
            "tool_usage": {
                "all_tools": self.tool_usage,
                "mcp_tools": {}  # No MCP for these adapters
            },
            "api_calls": self.api_calls,
            "errors": self.errors,
            "resolved": False  # Will be determined by test verification
        }

    def calculate_cost(self) -> float:
        """Calculate API cost based on token usage"""
        # Override in specific adapters with correct pricing
        return 0.0

    @abstractmethod
    def run(self) -> Dict:
        """Main execution method - must be implemented by each adapter"""
        pass