import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest

from core.exceptions import BusinessLogicException, NotFoundException
from database.generated_policy import GeneratedPolicy
from services.policy_service import (
    build_policy_generation_prompt,
    generate_compliance_policy,
    get_policy_by_id,
    get_user_policies,
    regenerate_policy_section,
)


def _mock_scalar_result(first_value=None, all_value=None):
    scalar_result = Mock()
    scalar_result.first.return_value = first_value
    scalar_result.all.return_value = all_value if all_value is not None else []
    result = Mock()
    result.scalars.return_value = scalar_result
    return result


def test_build_policy_generation_prompt_returns_string_prompt():
    profile = SimpleNamespace(industry="Technology", company_name="RuleIQ")
    framework = SimpleNamespace(name="GDPR")

    prompt = build_policy_generation_prompt(
        profile,
        framework,
        "comprehensive",
        ["Mention incident response"],
    )

    assert isinstance(prompt, str)
    assert "Generate a comprehensive compliance policy" in prompt
    assert "Technology" in prompt
    assert "RuleIQ" in prompt


@pytest.mark.asyncio
async def test_generate_compliance_policy_saves_json_response():
    db = AsyncMock()
    db.add = Mock()
    user_id = uuid4()
    framework_id = uuid4()
    profile = SimpleNamespace(id=uuid4(), industry="Technology", company_name="RuleIQ")
    framework = SimpleNamespace(id=framework_id, name="GDPR")
    db.execute.side_effect = [
        _mock_scalar_result(first_value=profile),
        _mock_scalar_result(first_value=framework),
    ]

    ai_payload = {
        "title": "GDPR Master Policy",
        "sections": [{"title": "Scope", "content": "Applies to all systems."}],
    }

    with patch(
        "services.policy_service._generate_policy_with_protection",
        AsyncMock(return_value=json.dumps(ai_payload)),
    ):
        policy = await generate_compliance_policy(db, user_id, framework_id)

    assert isinstance(policy, GeneratedPolicy)
    assert policy.user_id == user_id
    assert policy.business_profil == profile.id
    assert policy.framework_id == framework_id
    assert policy.policy_name == "GDPR Master Policy"
    assert json.loads(policy.policy_content) == ai_payload
    assert policy.sections == ai_payload["sections"]
    db.add.assert_called_once_with(policy)
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(policy)


@pytest.mark.asyncio
async def test_generate_compliance_policy_wraps_plain_text_response():
    db = AsyncMock()
    db.add = Mock()
    user_id = uuid4()
    framework_id = uuid4()
    profile = SimpleNamespace(id=uuid4(), industry="Technology", company_name="RuleIQ")
    framework = SimpleNamespace(id=framework_id, name="ISO 27001")
    db.execute.side_effect = [
        _mock_scalar_result(first_value=profile),
        _mock_scalar_result(first_value=framework),
    ]

    with patch(
        "services.policy_service._generate_policy_with_protection",
        AsyncMock(return_value="Plain text policy body"),
    ):
        policy = await generate_compliance_policy(db, user_id, framework_id, policy_type="summary")

    content = json.loads(policy.policy_content)
    assert content["title"] == "ISO 27001 Policy for RuleIQ"
    assert content["content"] == "Plain text policy body"
    assert policy.policy_type == "summary"


@pytest.mark.asyncio
async def test_generate_compliance_policy_raises_not_found_when_profile_missing():
    db = AsyncMock()
    user_id = uuid4()
    framework_id = uuid4()
    db.execute.return_value = _mock_scalar_result(first_value=None)

    with pytest.raises(NotFoundException):
        await generate_compliance_policy(db, user_id, framework_id)


@pytest.mark.asyncio
async def test_generate_compliance_policy_wraps_integration_failures():
    db = AsyncMock()
    user_id = uuid4()
    framework_id = uuid4()
    profile = SimpleNamespace(id=uuid4(), industry="Technology", company_name="RuleIQ")
    framework = SimpleNamespace(id=framework_id, name="GDPR")
    db.execute.side_effect = [
        _mock_scalar_result(first_value=profile),
        _mock_scalar_result(first_value=framework),
    ]

    with patch(
        "services.policy_service._generate_policy_with_protection",
        AsyncMock(side_effect=Exception("upstream blew up")),
    ):
        with pytest.raises(BusinessLogicException, match="unexpected error"):
            await generate_compliance_policy(db, user_id, framework_id)

    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_policy_by_id_raises_not_found_when_missing():
    db = AsyncMock()
    policy_id = uuid4()
    user_id = uuid4()
    db.execute.return_value = _mock_scalar_result(first_value=None)

    with pytest.raises(NotFoundException):
        await get_policy_by_id(db, policy_id, user_id)


@pytest.mark.asyncio
async def test_get_user_policies_returns_all_policies():
    db = AsyncMock()
    user_id = uuid4()
    policies = [SimpleNamespace(id=uuid4()), SimpleNamespace(id=uuid4())]
    db.execute.return_value = _mock_scalar_result(all_value=policies)

    result = await get_user_policies(db, user_id)

    assert result == policies


@pytest.mark.asyncio
async def test_regenerate_policy_section_updates_matching_section():
    db = AsyncMock()
    db.add = Mock()
    user_id = uuid4()
    policy_id = uuid4()
    policy = SimpleNamespace(
        content={
            "sections": [
                {"title": "Scope", "content": "Old text"},
                {"title": "Roles", "content": "Existing roles text"},
            ]
        },
        updated_at=None,
    )

    with patch("services.policy_service.get_policy_by_id", AsyncMock(return_value=policy)), patch(
        "services.policy_service._generate_policy_with_protection",
        AsyncMock(return_value="New section text"),
    ), patch("sqlalchemy.orm.attributes.flag_modified") as mock_flag_modified:
        result = await regenerate_policy_section(db, user_id, policy_id, "Scope", "Add UK context")

    assert result is policy
    assert policy.content["sections"][0]["content"] == "New section text"
    assert policy.updated_at is not None
    mock_flag_modified.assert_called_once_with(policy, "content")
    db.add.assert_called_once_with(policy)
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(policy)


@pytest.mark.asyncio
async def test_regenerate_policy_section_raises_business_logic_when_section_missing():
    db = AsyncMock()
    db.add = Mock()
    user_id = uuid4()
    policy_id = uuid4()
    policy = SimpleNamespace(content={"sections": [{"title": "Scope", "content": "Old text"}]})

    with patch("services.policy_service.get_policy_by_id", AsyncMock(return_value=policy)), patch(
        "services.policy_service._generate_policy_with_protection",
        AsyncMock(return_value="New section text"),
    ), patch("sqlalchemy.orm.attributes.flag_modified"):
        with pytest.raises(BusinessLogicException, match="Section 'Roles' not found"):
            await regenerate_policy_section(db, user_id, policy_id, "Roles")

    db.rollback.assert_awaited_once()