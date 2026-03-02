#!/usr/bin/env python3
"""
Gemini adapter for SWE-bench Pro evaluation.
Supports Gemini 1.5 Pro, Flash, and 2.0 models with function calling.
"""

import os
import sys
import json
import yaml
import time
from typing import Dict, Any, List, Tuple
from pathlib import Path

# Add common directory to path for base adapter
# Import from same directory
# sys.path.append('/testbed/datasets/common')
from base_agent_adapter import BaseAgentAdapter

# Google AI imports
try:
    import google.generativeai as genai
except ImportError:
    print("ERROR: Google Generative AI library not installed. Run: pip install google-generativeai")
    sys.exit(1)


class GeminiAdapter(BaseAgentAdapter):
    """Adapter for Google Gemini models"""

    # Model pricing (per 1M tokens)
    PRICING = {
        "gemini-1.5-pro": {"input": 3.5, "output": 10.5, "cache_read": 0.875},
        "gemini-1.5-flash": {"input": 0.075, "output": 0.3, "cache_read": 0.01875},
        "gemini-1.5-flash-8b": {"input": 0.0375, "output": 0.15, "cache_read": 0.01},
        "gemini-2.0-flash-exp": {"input": 0.0, "output": 0.0},  # Free during preview
        "gemini-1.0-pro": {"input": 0.5, "output": 1.5}
    }

    def __init__(self, task_instruction: str, config: Dict[str, Any]):
        super().__init__(task_instruction, config)
        self.model = None
        self.model_name = os.environ.get('GEMINI_MODEL', 'gemini-1.5-pro')

    def initialize_client(self):
        """Initialize Gemini client"""
        api_key = os.environ.get('GEMINI_API_KEY', os.environ.get('GOOGLE_API_KEY'))
        if not api_key:
            raise ValueError("GEMINI_API_KEY or GOOGLE_API_KEY environment variable not set")

        genai.configure(api_key=api_key)

        # Create the model with function declarations
        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            tools=self.format_tools()
        )

        self.log_interaction("system", f"Initialized Gemini client with model: {self.model_name}")

    def format_tools(self):
        """Format tools in Gemini function declaration format"""
        # Gemini uses a different format for function declarations
        return [
            genai.protos.Tool(
                function_declarations=[
                    genai.protos.FunctionDeclaration(
                        name="read_file",
                        description="Read the contents of a file at the specified path",
                        parameters=genai.protos.Schema(
                            type=genai.protos.Type.OBJECT,
                            properties={
                                "path": genai.protos.Schema(
                                    type=genai.protos.Type.STRING,
                                    description="The path to the file to read"
                                )
                            },
                            required=["path"]
                        )
                    ),
                    genai.protos.FunctionDeclaration(
                        name="write_file",
                        description="Write content to a file at the specified path",
                        parameters=genai.protos.Schema(
                            type=genai.protos.Type.OBJECT,
                            properties={
                                "path": genai.protos.Schema(
                                    type=genai.protos.Type.STRING,
                                    description="The path to the file to write"
                                ),
                                "content": genai.protos.Schema(
                                    type=genai.protos.Type.STRING,
                                    description="The content to write to the file"
                                )
                            },
                            required=["path", "content"]
                        )
                    ),
                    genai.protos.FunctionDeclaration(
                        name="edit_file",
                        description="Edit a file by replacing a specific string with new content",
                        parameters=genai.protos.Schema(
                            type=genai.protos.Type.OBJECT,
                            properties={
                                "path": genai.protos.Schema(
                                    type=genai.protos.Type.STRING,
                                    description="The path to the file to edit"
                                ),
                                "old_string": genai.protos.Schema(
                                    type=genai.protos.Type.STRING,
                                    description="The exact string to find and replace"
                                ),
                                "new_string": genai.protos.Schema(
                                    type=genai.protos.Type.STRING,
                                    description="The new string to replace the old string with"
                                ),
                                "replace_all": genai.protos.Schema(
                                    type=genai.protos.Type.BOOL,
                                    description="Whether to replace all occurrences or just the first",
                                    default_value=False
                                )
                            },
                            required=["path", "old_string", "new_string"]
                        )
                    ),
                    genai.protos.FunctionDeclaration(
                        name="run_bash",
                        description="Execute a bash command in the /testbed directory",
                        parameters=genai.protos.Schema(
                            type=genai.protos.Type.OBJECT,
                            properties={
                                "command": genai.protos.Schema(
                                    type=genai.protos.Type.STRING,
                                    description="The bash command to execute"
                                ),
                                "timeout": genai.protos.Schema(
                                    type=genai.protos.Type.INTEGER,
                                    description="Command timeout in seconds",
                                    default_value=120
                                )
                            },
                            required=["command"]
                        )
                    )
                ]
            )
        ]

    def call_agent(self, chat_session, message: str) -> Tuple[Any, Dict]:
        """Call Gemini API and return response and metadata"""
        try:
            # Send message to Gemini
            response = chat_session.send_message(message)
            self.api_calls += 1

            # Track token usage if available
            if hasattr(response, 'usage_metadata'):
                usage = response.usage_metadata
                self.total_tokens["input"] += getattr(usage, 'prompt_token_count', 0)
                self.total_tokens["output"] += getattr(usage, 'candidates_token_count', 0)
                self.total_tokens["cache_read"] += getattr(usage, 'cached_content_token_count', 0)

            metadata = {
                "model": self.model_name,
                "usage": {
                    "prompt_tokens": getattr(usage, 'prompt_token_count', 0),
                    "completion_tokens": getattr(usage, 'candidates_token_count', 0),
                    "cached_tokens": getattr(usage, 'cached_content_token_count', 0)
                } if hasattr(response, 'usage_metadata') else {}
            }

            return response, metadata

        except Exception as e:
            error_msg = f"Error calling Gemini API: {str(e)}"
            self.errors.append(error_msg)
            self.log_interaction("error", error_msg)
            raise

    def calculate_cost(self) -> float:
        """Calculate API cost based on token usage"""
        if self.model_name not in self.PRICING:
            return 0.0

        pricing = self.PRICING[self.model_name]
        input_cost = (self.total_tokens["input"] / 1_000_000) * pricing["input"]
        output_cost = (self.total_tokens["output"] / 1_000_000) * pricing["output"]
        cache_cost = (self.total_tokens["cache_read"] / 1_000_000) * pricing.get("cache_read", 0)

        return round(input_cost + output_cost + cache_cost, 4)

    def run(self) -> Dict:
        """Main execution loop"""
        self.initialize_client()

        # System instruction for Gemini
        system_instruction = """You are an expert software engineer tasked with solving a coding problem.
You have access to tools to read files, write files, edit files, and run bash commands.
Work step by step to understand the problem, explore the codebase, and implement a solution.
Always verify your changes with appropriate tests."""

        # Create a chat session
        chat = self.model.start_chat(history=[])

        # Initial message with task instruction
        initial_message = f"{system_instruction}\n\nTask: {self.task_instruction}"

        max_iterations = 30
        iteration = 0

        self.log_interaction("task_start", {
            "instruction": self.task_instruction,
            "model": self.model_name
        })

        while iteration < max_iterations:
            iteration += 1

            try:
                # Send message or continue conversation
                if iteration == 1:
                    response, metadata = self.call_agent(chat, initial_message)
                else:
                    # For continuation, check if we need to prompt
                    response, metadata = self.call_agent(chat,
                        "Is there anything else you need to do to complete the task? If not, say 'Task complete'.")

                self.log_interaction("assistant_response", {
                    "iteration": iteration,
                    "content": response.text if hasattr(response, 'text') else str(response),
                    "function_calls": len(response.parts) if hasattr(response, 'parts') else 0
                })

                # Handle function calls
                if hasattr(response, 'parts'):
                    for part in response.parts:
                        if hasattr(part, 'function_call'):
                            fc = part.function_call
                            function_name = fc.name

                            # Parse arguments - Gemini returns them as a struct
                            function_args = {}
                            for key, value in fc.args.items():
                                function_args[key] = value

                            self.log_interaction("tool_call", {
                                "tool": function_name,
                                "args": function_args
                            })

                            # Execute the tool
                            tool_result = self.execute_tool(function_name, function_args)

                            # Send function response back to model
                            response_parts = [
                                genai.protos.Part(
                                    function_response=genai.protos.FunctionResponse(
                                        name=function_name,
                                        response={"result": tool_result[:10000]}  # Limit result size
                                    )
                                )
                            ]

                            # Continue the conversation with function result
                            response, _ = self.call_agent(chat, response_parts)

                            self.log_interaction("tool_result", {
                                "tool": function_name,
                                "result_preview": tool_result[:500]
                            })

                # Check if task is complete
                if response.text and "task complete" in response.text.lower():
                    self.log_interaction("task_complete", {
                        "iterations": iteration,
                        "reason": "Model indicated completion"
                    })
                    break

            except Exception as e:
                self.log_interaction("error", {
                    "iteration": iteration,
                    "error": str(e)
                })

                # Try to recover
                if iteration >= max_iterations - 5:
                    break

                # Continue conversation with error context
                try:
                    response, _ = self.call_agent(chat,
                        f"An error occurred: {str(e)}. Please continue working on the task.")
                except:
                    break

        # Return metrics
        metrics = self.get_metrics()
        metrics["iterations"] = iteration
        metrics["model"] = self.model_name

        self.log_interaction("task_end", metrics)

        # Write metrics to result.json
        with open("/testbed/result.json", "w") as f:
            json.dump(metrics, f, indent=2)

        return metrics


def main():
    """Main entry point"""
    # Read task instruction
    instruction_file = "/testbed/task_instruction.txt"
    if not os.path.exists(instruction_file):
        print(f"ERROR: Task instruction file not found: {instruction_file}")
        sys.exit(1)

    with open(instruction_file, 'r') as f:
        task_instruction = f.read()

    # Load configuration
    config_file = Path(__file__).parent / "config.yaml"
    config = {}
    if config_file.exists():
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f) or {}

    # Create and run adapter
    adapter = GeminiAdapter(task_instruction, config)

    try:
        result = adapter.run()
        print(f"Task completed. Iterations: {result.get('iterations', 0)}, Cost: ${result.get('total_cost_usd', 0):.4f}")
        sys.exit(0 if result.get('resolved', False) else 1)
    except Exception as e:
        print(f"ERROR: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()