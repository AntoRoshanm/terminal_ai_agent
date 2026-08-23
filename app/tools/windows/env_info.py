"""
Environment Variables and System PATH Inspection Tool
"""

from typing import Any, Dict, Optional
from app.models.tools import PermissionLevel
from app.tools.base import BaseTool
from app.tools.system.factory import SystemProviderFactory


class GetEnvironmentInfoTool(BaseTool):
    """Tool to inspect system and user environment variables and PATH breakdown."""

    name = "get_environment_info"
    description = "Inspect system and user environment variables, PATH configuration, and user profile paths."
    category = "system"
    permission_level = PermissionLevel.LEVEL_0_READ_ONLY

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "var_name": {
                    "type": "string",
                    "description": "Optional specific environment variable to inspect (e.g. 'PATH', 'JAVA_HOME', 'CUDA_PATH')",
                },
                "variable_name": {
                    "type": "string",
                    "description": "Alias for var_name",
                },
                "inspect_path": {
                    "type": "boolean",
                    "description": "Whether to inspect PATH components specifically",
                    "default": False,
                },
            },
            "additionalProperties": False,
        }

    def _run(
        self,
        var_name: Optional[str] = None,
        variable_name: Optional[str] = None,
        inspect_path: bool = False,
    ) -> Dict[str, Any]:
        provider = SystemProviderFactory.get_system_info_provider()
        if hasattr(provider, "get_environment_info"):
            try:
                return provider.get_environment_info(
                    var_name=var_name,
                    variable_name=variable_name,
                    inspect_path=inspect_path,
                )
            except TypeError:
                return provider.get_environment_info(var_name=var_name or variable_name)
        return {}


# Alias for backward compatibility
GetEnvInfoTool = GetEnvironmentInfoTool
