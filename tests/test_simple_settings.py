#!/usr/bin/env python3
"""Test simplified settings"""

import os
from typing import List, Annotated, Any
from pydantic import Field, BeforeValidator
from pydantic_settings import BaseSettings, SettingsConfigDict


def parse_list_from_string(v: Any) -> list:
    """Parse a list from string or return as-is if already a list."""
    print(f"parse_list_from_string called with: {v!r} (type: {type(v)})")
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        # Try JSON parsing first
        if v.startswith("[") and v.endswith("]"):
            try:
                import json

                result = json.loads(v)
                print(f"  JSON parsed to: {result}")
                return result
            except json.JSONDecodeError as e:
                print(f"  JSON parse failed: {e}")
        # Otherwise split by comma
        result = [item.strip() for item in v.split(",") if item.strip()]
        print(f"  Comma split to: {result}")
        return result
    return v


class TestSettings(BaseSettings):
    # Test without annotation
    simple_list: List[str] = Field(default=["a", "b"])

    # Test with annotation
    annotated_list: Annotated[List[str], BeforeValidator(parse_list_from_string)] = (
        Field(default=["c", "d"]),
    )

    model_config = SettingsConfigDict(
        env_file=".env.test",
        case_sensitive=False,
    )


# Test 1: Without environment variables
print("=== Test 1: No env vars ===")
try:
    settings1 = TestSettings()
    print(
        f"Success: simple_list={settings1.simple_list}, annotated_list={settings1.annotated_list}",
    )
except Exception as e:
    print(f"Failed: {e}")

# Test 2: With simple comma-separated env var
print("\n=== Test 2: Comma-separated ===")
os.environ["SIMPLE_LIST"] = "x,y,z"
os.environ["ANNOTATED_LIST"] = "p,q,r"
try:
    settings2 = TestSettings()
    print(
        f"Success: simple_list={settings2.simple_list}, annotated_list={settings2.annotated_list}",
    )
except Exception as e:
    print(f"Failed: {e}")

# Test 3: With JSON env var
print("\n=== Test 3: JSON format ===")
os.environ["SIMPLE_LIST"] = '["x","y","z"]'
os.environ["ANNOTATED_LIST"] = '["p","q","r"]'
try:
    settings3 = TestSettings()
    print(
        f"Success: simple_list={settings3.simple_list}, annotated_list={settings3.annotated_list}",
    )
except Exception as e:
    print(f"Failed: {e}")
