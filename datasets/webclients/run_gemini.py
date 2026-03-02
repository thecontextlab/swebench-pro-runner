#!/usr/bin/env python3
"""
Debug version of Gemini wrapper that lists available models first.
"""
import subprocess
import sys
import os
import json

def list_available_models(api_key):
    """List available Gemini models using the API"""
    print("[wrapper] Fetching available models from Gemini API...")

    cmd = [
        "curl", "-s",
        "-H", f"x-goog-api-key: {api_key}",
        "https://generativelanguage.googleapis.com/v1beta/models"
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"[wrapper] ERROR: Failed to list models: {result.stderr}")
        return []

    try:
        data = json.loads(result.stdout)
        models = data.get("models", [])

        print(f"[wrapper] Found {len(models)} total models")
        generate_capable = []

        for model in models:
            name = model.get("name", "")
            methods = model.get("supportedGenerationMethods", [])

            if "generateContent" in methods:
                generate_capable.append(name)
                print(f"[wrapper]   ✓ {name} - {model.get('displayName', 'N/A')}")

        return generate_capable

    except json.JSONDecodeError as e:
        print(f"[wrapper] ERROR: Failed to parse model list: {e}")
        return []

def main():
    # Read instruction from file
    with open("/instruction.txt", "r") as f:
        instruction = f.read().strip()

    model = os.environ.get("GEMINI_MODEL") or os.environ.get("MODEL", "gemini-1.5-pro")
    api_key = os.environ.get("GEMINI_API_KEY", "")

    if not api_key:
        print("[wrapper] ERROR: GEMINI_API_KEY environment variable not set", flush=True)
        sys.exit(1)

    # First, list available models
    print("[wrapper] ========================================", flush=True)
    print("[wrapper] STEP 1: LISTING AVAILABLE MODELS", flush=True)
    print("[wrapper] ========================================", flush=True)

    available_models = list_available_models(api_key)

    print("\n[wrapper] ========================================", flush=True)
    print("[wrapper] STEP 2: SELECTING MODEL", flush=True)
    print("[wrapper] ========================================", flush=True)

    print(f"[wrapper] Requested model: {model}", flush=True)

    # Try to find a compatible model from available ones
    if available_models:
        # Extract model names without "models/" prefix
        model_names = [m.replace("models/", "") for m in available_models]
        print(f"[wrapper] Available model names: {model_names}")

        # Check if requested model is available
        if f"models/{model}" in available_models:
            print(f"[wrapper] Model {model} is available!")
        elif model in model_names:
            print(f"[wrapper] Model {model} is available!")
        else:
            # Try to find a suitable fallback
            fallback = None

            # Priority order for fallbacks (based on actual available models)
            fallback_options = [
                "gemini-3-pro-preview",  # Latest Gemini 3 Pro Preview - TOP PRIORITY
                "gemini-2.5-pro",        # Previous pro model
                "gemini-2.5-flash",      # Latest flash model as fallback
                "gemini-2.0-flash",      # Previous generation flash
                "gemini-2.0-flash-001",
                "gemini-flash-latest",
                "gemini-pro-latest",
                "gemini-exp-1206",       # Experimental model
                "gemini-2.0-flash-lite"  # Lite version as last resort
            ]

            for option in fallback_options:
                if option in model_names or f"models/{option}" in available_models:
                    fallback = option
                    break

            if fallback:
                print(f"[wrapper] Model {model} not available, using fallback: {fallback}", flush=True)
                model = fallback
            else:
                print(f"[wrapper] WARNING: Model {model} not available and no fallback found", flush=True)
                print(f"[wrapper] Will try with {model} anyway...", flush=True)
    else:
        print("[wrapper] WARNING: Could not fetch available models, proceeding with requested model", flush=True)

    # Add "models/" prefix if not already present (required by Gemini API)
    if not model.startswith("models/"):
        model = f"models/{model}"

    # Build completion instruction
    completion_instruction = """IMPORTANT: You MUST complete the implementation fully. Do NOT stop after analysis.
Do NOT ask "Would you like me to proceed?" - just implement the fix.
After finding the issue, immediately edit files to make changes.
After editing, run the tests to verify.
Keep working until all tests pass or you hit an error.

""" + instruction

    # Build Gemini CLI command
    # Use stream-json to get turn-by-turn output similar to Claude
    cmd = [
        "gemini",
        completion_instruction,
        "--model", model,
        "--yolo",
        "--output-format", "stream-json"
    ]

    # Set up environment with API key
    env = os.environ.copy()
    env["GEMINI_API_KEY"] = api_key
    env["GOOGLE_API_KEY"] = api_key
    env["GEMINI_DISABLE_INTERACTIVE"] = "1"

    # Create temp home to avoid cached credentials
    temp_home = "/tmp/gemini_home"
    try:
        if not os.path.exists(temp_home):
            os.makedirs(temp_home)
        env["HOME"] = temp_home
    except:
        pass

    print(f"[wrapper] Final model: {model}", flush=True)
    print(f"[wrapper] YOLO mode: enabled", flush=True)

    print("\n[wrapper] ========================================", flush=True)
    print("[wrapper] STEP 3: RUNNING GEMINI CLI", flush=True)
    print("[wrapper] ========================================", flush=True)
    print("[wrapper] Starting Google Gemini...", flush=True)
    sys.stdout.flush()  # Ensure all wrapper output is flushed before starting Gemini
    sys.stderr.flush()

    # Run Gemini normally - let it output directly to stdout/stderr
    # This preserves the natural output order
    result = subprocess.run(cmd, cwd="/testbed", env=env)

    print("\n[wrapper] ========================================", flush=True)
    print(f"[wrapper] Gemini CLI exited with code: {result.returncode}", flush=True)
    print("[wrapper] ========================================", flush=True)

    sys.exit(result.returncode)

if __name__ == "__main__":
    main()