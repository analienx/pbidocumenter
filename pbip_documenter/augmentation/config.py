"""Configuration helpers for optional AI augmentation."""

import json
import os
import typing
from dataclasses import dataclass
from pathlib import Path


@dataclass
class AISettings:
    enabled: bool = False
    provider: str = ""
    endpoint: str = ""
    api_key_env_var: str = "AI_API_KEY"
    api_key: str = ""
    model: str = ""
    timeout_seconds: int = 30
    max_input_chars: int = 12000
    max_output_chars: int = 4000
    requirement_prompt_template: str = (
        "Generate requirement_spec_text, assumptions, missing_information, and traceability_notes "
        "from the provided deterministic context. Do not invent missing facts."
    )
    design_prompt_template: str = (
        "Generate design_spec_text, assumptions, missing_information, and traceability_notes "
        "from the provided deterministic context. Do not invent missing facts."
    )
    confidence_threshold_generate: str = "medium"
    confidence_threshold_warn: str = "medium"
    allow_local_model: bool = False

    @classmethod
    def load(cls: typing.Any, path: Path = Path("AI_SETTINGS.json")) -> typing.Any:
        if not path.exists():
            return cls()

        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            enabled=bool(data.get("enabled", False)),
            provider=str(data.get("provider", "")),
            endpoint=str(data.get("endpoint", "")),
            api_key_env_var=str(data.get("api_key_env_var", "AI_API_KEY")),
            api_key=str(data.get("api_key", "")),
            model=str(data.get("model", "")),
            timeout_seconds=int(data.get("timeout_seconds", 30)),
            max_input_chars=int(data.get("max_input_chars", 12000)),
            max_output_chars=int(data.get("max_output_chars", 4000)),
            requirement_prompt_template=str(data.get("requirement_prompt_template", cls.requirement_prompt_template)),
            design_prompt_template=str(data.get("design_prompt_template", cls.design_prompt_template)),
            confidence_threshold_generate=str(data.get("confidence_threshold_generate", "medium")).lower(),
            confidence_threshold_warn=str(data.get("confidence_threshold_warn", "medium")).lower(),
            allow_local_model=bool(data.get("allow_local_model", False)),
        )

    def resolved_api_key(self: typing.Any) -> typing.Any:
        if self.api_key:
            return self.api_key
        return os.environ.get(self.api_key_env_var, "")
