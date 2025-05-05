import json
import os
import sys
import logging
from pathlib import Path
from typing import Dict, Any, Optional, TypeVar, Type

T = TypeVar('T')

# Configuration schema defining required fields and their types
CONFIG_SCHEMA = {
    "default_scope": {
        "type": str,
        "required": True,
        "default": "global",
        "env_var": "ROO_DEFAULT_SCOPE",
        "description": "Default installation scope for MCPs"
    },
    "manifest_format": {
        "type": str,
        "required": True,
        "default": "package.json",
        "env_var": "ROO_MANIFEST_FORMAT",
        "description": "Default manifest file format"
    },
    "log_lines_default": {
        "type": int,
        "required": True,
        "default": 50,
        "env_var": "ROO_LOG_LINES_DEFAULT",
        "description": "Default number of log lines to display"
    },
    "auto_detect_main": {
        "type": bool,
        "required": True,
        "default": True,
        "env_var": "ROO_AUTO_DETECT_MAIN",
        "description": "Whether to automatically detect main file"
    }
}

class ConfigurationError(Exception):
    """Custom exception for configuration-related errors."""
    pass

def validate_config_value(key: str, value: Any, schema_entry: Dict[str, Any]) -> Any:
    """Validate a configuration value against its schema definition."""
    if value is None:
        if schema_entry["required"]:
            raise ConfigurationError(f"Required configuration '{key}' is missing")
        return schema_entry["default"]

    expected_type = schema_entry["type"]
    try:
        # Handle boolean special case (environment variables are strings)
        if expected_type == bool and isinstance(value, str):
            return value.lower() in ('true', '1', 'yes', 'on')
        # Handle integer special case
        if expected_type == int and isinstance(value, str):
            return int(value)
        # Normal type conversion
        return expected_type(value)
    except (ValueError, TypeError):
        raise ConfigurationError(
            f"Invalid type for configuration '{key}'. Expected {expected_type.__name__}, got {type(value).__name__}"
        )

def get_config_from_env(schema_entry: Dict[str, Any]) -> Optional[Any]:
    """Get configuration value from environment variable if available."""
    env_var = schema_entry.get("env_var")
    if env_var and env_var in os.environ:
        return os.environ[env_var]
    return None

def validate_env_config(config: Dict[str, Dict[str, Any]]) -> None:
    """Validate the environment configuration section."""
    if not isinstance(config.get("env"), dict):
        raise ConfigurationError("'env' configuration must be a dictionary")
    
    for service, settings in config["env"].items():
        if not isinstance(settings, dict):
            raise ConfigurationError(f"Environment settings for '{service}' must be a dictionary")
        
        # Validate required fields for each service
        if service == "github":
            token = settings.get("GITHUB_PERSONAL_ACCESS_TOKEN")
            if token and not isinstance(token, str):
                raise ConfigurationError("GitHub personal access token must be a string")
        elif service == "gitlab":
            token = settings.get("GITLAB_PERSONAL_ACCESS_TOKEN")
            if token and not isinstance(token, str):
                raise ConfigurationError("GitLab personal access token must be a string")

def merge_configs(*configs: Dict[str, Any]) -> Dict[str, Any]:
    """Merge multiple configuration dictionaries, later ones taking precedence."""
    result = {}
    for config in configs:
        if not isinstance(config, dict):
            continue
        
        # Handle environment variables section specially
        if "env" in config and "env" in result:
            for group, envs in config["env"].items():
                if isinstance(envs, dict):
                    result["env"].setdefault(group, {}).update(envs)
        else:
            result.update(config)
    return result

def load_roo_config() -> Dict[str, Any]:
    """
    Load and validate Roo configuration from multiple sources.
    
    Priority order (highest to lowest):
    1. Environment variables
    2. Project-specific config (.roo/config.json)
    3. User-level config (~/.roo/config.json)
    4. Default values

    Returns:
        Dict[str, Any]: Validated configuration dictionary
    
    Raises:
        ConfigurationError: If configuration is invalid
    """
    # Default configuration values
    default_config = {
        key: schema["default"]
        for key, schema in CONFIG_SCHEMA.items()
    }
    default_config["env"] = {
        "github": {"GITHUB_PERSONAL_ACCESS_TOKEN": None, "HOST": "github.com"},
        "gitlab": {"GITLAB_PERSONAL_ACCESS_TOKEN": None, "HOST": "gitlab.com"}
    }

    config_sources = []

    # Load user configuration
    user_config_path = Path.home() / ".roo" / "config.json"
    if user_config_path.exists() and user_config_path.is_file():
        try:
            with open(user_config_path, "r", encoding='utf-8') as f:
                user_config = json.load(f)
                if isinstance(user_config, dict):
                    config_sources.append(user_config)
                else:
                    logging.warning(f"User config file {user_config_path} is not a valid JSON object")
        except Exception as e:
            logging.warning(f"Failed to load user config {user_config_path}: {e}")

    # Load project configuration
    project_config_path = Path.cwd() / ".roo" / "config.json"
    if project_config_path.exists() and project_config_path.is_file():
        try:
            with open(project_config_path, "r", encoding='utf-8') as f:
                project_config = json.load(f)
                if isinstance(project_config, dict):
                    config_sources.append(project_config)
                else:
                    logging.warning(f"Project config file {project_config_path} is not a valid JSON object")
        except Exception as e:
            logging.warning(f"Failed to load project config {project_config_path}: {e}")

    # Merge configurations
    merged_config = merge_configs(default_config, *config_sources)

    # Validate and apply environment variables
    for key, schema in CONFIG_SCHEMA.items():
        env_value = get_config_from_env(schema)
        if env_value is not None:
            merged_config[key] = env_value

        # Validate each config value
        try:
            merged_config[key] = validate_config_value(key, merged_config.get(key), schema)
        except ConfigurationError as e:
            logging.error(f"Configuration error: {e}")
            merged_config[key] = schema["default"]

    # Validate environment configuration
    try:
        validate_env_config(merged_config)
    except ConfigurationError as e:
        logging.error(f"Environment configuration error: {e}")
        merged_config["env"] = default_config["env"]

    return merged_config

def get_config_docs() -> str:
    """Generate documentation for all configuration options."""
    docs = ["Roo Configuration Options", "======================", ""]
    
    for key, schema in CONFIG_SCHEMA.items():
        docs.append(f"## {key}")
        docs.append(f"Description: {schema['description']}")
        docs.append(f"Type: {schema['type'].__name__}")
        docs.append(f"Required: {schema['required']}")
        docs.append(f"Default: {schema['default']}")
        if schema.get('env_var'):
            docs.append(f"Environment Variable: {schema['env_var']}")
        docs.append("")

    return "\n".join(docs)