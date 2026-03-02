#!/usr/bin/env python3
"""
Task-specific configuration loader for SWE-bench Pro evaluations.
Resolves images and metadata based on task groups and overrides.
"""

import os
import sys
import yaml
import re
from typing import Dict, Optional, Any


class TaskImageResolver:
    """
    Resolves Docker images and configuration for SWE-bench Pro tasks.

    Supports hierarchy:
    1. Task-specific overrides (highest priority)
    2. Task group pattern matching
    3. Repository defaults (fallback)
    """

    def __init__(self, repo: str):
        self.repo = repo
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load repository configuration from YAML file."""
        config_path = f"datasets/{self.repo}/config.yaml"

        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path, 'r') as f:
            return yaml.safe_load(f)

    def resolve_image(self, task_id: str) -> str:
        """
        Resolve Docker image for a task using priority order.

        Args:
            task_id: Task identifier (e.g., "ansible__ansible-0ea40e09...")

        Returns:
            Docker image URL
        """
        # 1. Task-specific override (highest priority)
        task_overrides = self.config.get('task_overrides', {})
        if task_id in task_overrides:
            override = task_overrides[task_id]
            if 'image' in override:
                print(f"[config] Task override: {task_id} -> {override['image']}", file=sys.stderr)
                return override['image']

        # 2. Task group pattern matching
        task_groups = self.config.get('task_groups', {})
        for group_name, group_config in task_groups.items():
            pattern = group_config.get('pattern', '')
            if pattern:
                if re.search(pattern, task_id):
                    image = group_config['image']
                    print(f"[config] Task group match: {task_id} -> {group_name} -> {image}", file=sys.stderr)
                    return image

        # 3. Repository default (fallback)
        default_image = self.config.get('image')
        if not default_image:
            raise ValueError(f"No default image configured for repository: {self.repo}")

        print(f"[config] Default image: {task_id} -> {default_image}", file=sys.stderr)
        return default_image

    def get_task_metadata(self, task_id: str) -> Dict[str, Any]:
        """
        Get all task-specific metadata including image, environment variables, etc.

        Args:
            task_id: Task identifier

        Returns:
            Dictionary with resolved metadata
        """
        metadata = {
            'image': self.resolve_image(task_id),
            'timemachine_date': None,
            'python_version': None,
            'environment_vars': {},
            'setup_commands': []
        }

        # Apply task group metadata
        task_groups = self.config.get('task_groups', {})
        for group_name, group_config in task_groups.items():
            pattern = group_config.get('pattern', '')
            if pattern and re.search(pattern, task_id):
                # Merge group metadata (excluding 'pattern' and 'image')
                group_metadata = {k: v for k, v in group_config.items()
                                if k not in ['pattern', 'image']}
                metadata.update(group_metadata)
                print(f"[config] Applied group metadata from {group_name}: {group_metadata}", file=sys.stderr)
                break

        # Apply task-specific overrides (highest priority)
        task_overrides = self.config.get('task_overrides', {})
        if task_id in task_overrides:
            override = task_overrides[task_id]
            metadata.update(override)
            print(f"[config] Applied task override: {override}", file=sys.stderr)

        return metadata

    def get_mcp_config(self, enable_mcp: bool) -> Dict[str, str]:
        """Get MCP configuration for the repository."""
        if not enable_mcp:
            return {'mcp_config': '', 'mcp_url': ''}

        mcp_config = self.config.get('mcp', {})
        mcp_url = mcp_config.get('url', '')

        if mcp_url:
            # Don't include the token in mcp_config - let run_claude.py handle it
            # This ensures the token comes from GitHub secrets, not config files
            # Return empty mcp_config to force run_claude.py to use MCP_URL/MCP_TOKEN path
            return {'mcp_config': '', 'mcp_url': mcp_url}

        return {'mcp_config': '', 'mcp_url': ''}


def resolve_task_config(repo: str, task_id: str, enable_mcp: bool = False) -> Dict[str, str]:
    """
    Main entry point for GitHub Actions workflow.

    Args:
        repo: Repository name (e.g., 'ansible', 'vuls')
        task_id: Task identifier
        enable_mcp: Whether to enable MCP

    Returns:
        Dictionary of resolved configuration for GitHub Actions
    """
    try:
        resolver = TaskImageResolver(repo)
        metadata = resolver.get_task_metadata(task_id)
        mcp_config = resolver.get_mcp_config(enable_mcp)

        # Format for GitHub Actions output
        return {
            'ar_image': metadata['image'],
            'timemachine_date': metadata.get('timemachine_date', ''),
            'python_version': metadata.get('python_version', ''),
            'timeout': str(resolver.config.get('timeout_minutes', 45)),
            **mcp_config
        }

    except Exception as e:
        print(f"[ERROR] Configuration resolution failed: {e}", file=sys.stderr)
        # Fallback to basic config
        fallback_image = f"swebench-pro-{repo}:latest"
        return {
            'ar_image': fallback_image,
            'timemachine_date': '',
            'python_version': '',
            'timeout': '45',
            'mcp_config': '',
            'mcp_url': ''
        }


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 4:
        print("Usage: python config_loader.py <repo> <task_id> <enable_mcp>")
        sys.exit(1)

    repo = sys.argv[1]
    task_id = sys.argv[2]
    enable_mcp = sys.argv[3].lower() == 'true'

    config = resolve_task_config(repo, task_id, enable_mcp)

    # Output for GitHub Actions
    for key, value in config.items():
        print(f"{key}={value}")