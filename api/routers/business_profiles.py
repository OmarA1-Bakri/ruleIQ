from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from api.dependencies.database import get_async_db
from api.dependencies.rbac_auth import (
    UserWithRoles,
    require_permission
)
from services.data_access_service import DataAccessService
from database.db_setup import get_db
from api.schemas.models import BusinessProfileCreate, BusinessProfileResponse, BusinessProfileUpdate
from database.business_profile import BusinessProfile
from utils.input_validation import validate_business_profile_update, ValidationError

router = APIRouter()

# Field mapping no longer needed - column names match API field names after migration


@router.post("/", response_model=BusinessProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_business_profile(
    profile: BusinessProfileCreate,
    current_user: UserWithRoles = Depends(require_permission("user_create")),
    db: AsyncSession = Depends(get_async_db),
):
    # Check if profile already exists
    stmt = select(BusinessProfile).where(BusinessProfile.user_id == current_user.id)
    result = await db.execute(stmt)
    existing = result.scalars().first()

    if existing:
        # Instead of deleting and recreating, update the existing profile
        # This prevents foreign key constraint violations with evidence_items
        profile_data = profile.model_dump()

        # Validate input data against whitelist and security patterns
        try:
            validated_data = validate_business_profile_update(profile_data)
        except ValidationError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # Update existing profile fields with validated data
        ALLOWED_FIELDS = [
            "company_name",
            "industry",
            "company_size",
            "description",
            "data_sensitivity",
            "geographic_scope",
            "target_frameworks",
        ]
        for key, value in validated_data.items():
            if key in ALLOWED_FIELDS:
                setattr(existing, key, value)

        # The updated_at field is automatically handled by the database
        await db.commit()
        await db.refresh(existing)
        return existing
    else:
        # Create new profile only if none exists
        profile_data = profile.model_dump()

        # Validate input data against whitelist and security patterns
        try:
            validated_data = validate_business_profile_update(profile_data)
        except ValidationError as e:
            raise HTTPException(status_code=400, detail=str(e))

        db_profile = BusinessProfile(id=uuid4(), user_id=current_user.id, **validated_data)
        db.add(db_profile)
        await db.commit()
        await db.refresh(db_profile)
        return db_profile


@router.get("/", response_model=BusinessProfileResponse)
async def get_business_profile(
    current_user: UserWithRoles = Depends(require_permission("user_list")),
    db: AsyncSession = Depends(get_async_db)
):
    stmt = select(BusinessProfile).where(BusinessProfile.user_id == current_user.id)
    result = await db.execute(stmt)
    profile = result.scalars().first()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Business profile not found"
        )
    return profile


@router.get("/{id}", response_model=BusinessProfileResponse)
async def get_business_profile_by_id(
    profile_id: UUID,
    current_user: UserWithRoles = Depends(require_permission("user_list")),
    db: AsyncSession = Depends(get_async_db),
    sync_db: Session = Depends(get_db),
):
    """Get a specific business profile by ID - access controlled by RBAC data visibility."""
    # First get the profile to check ownership
    stmt = select(BusinessProfile).where(BusinessProfile.id == profile_id)
    result = await db.execute(stmt)
    profile = result.scalars().first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Business profile not found"
        )

    # Check data access permissions
    data_access_service = DataAccessService(sync_db)
    if not data_access_service.can_access_business_profile(
        current_user, profile_id, profile.user_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Insufficient permissions to view this profile"
        )

    return profile


@router.put("/", response_model=BusinessProfileResponse)
async def update_business_profile(
    profile_update: BusinessProfileUpdate,
    current_user: UserWithRoles = Depends(require_permission("user_update")),
    db: AsyncSession = Depends(get_async_db),
):
    stmt = select(BusinessProfile).where(BusinessProfile.user_id == current_user.id)
    result = await db.execute(stmt)
    profile = result.scalars().first()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Business profile not found"
        )

    update_data = profile_update.model_dump(exclude_unset=True)
    # Remove fields that are not in the BusinessProfile model
    update_data.pop("data_sensitivity", None)  # Temporarily removed until migration is run

    # Validate input data against whitelist and security patterns
    try:
        validated_data = validate_business_profile_update(update_data)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    ALLOWED_FIELDS = [
        "company_name",
        "industry",
        "company_size",
        "description",
        "data_sensitivity",
        "geographic_scope",
        "target_frameworks",
    ]
    for key, value in validated_data.items():
        if key in ALLOWED_FIELDS:
            setattr(profile, key, value)

    # The updated_at field is automatically handled by the database
    await db.commit()
    await db.refresh(profile)

    return profile


@router.put("/{id}", response_model=BusinessProfileResponse)
async def update_business_profile_by_id(
    profile_id: UUID,
    profile_update: BusinessProfileUpdate,
    current_user: UserWithRoles = Depends(require_permission("user_update")),
    db: AsyncSession = Depends(get_async_db),
    sync_db: Session = Depends(get_db),
):
    """Update a specific business profile by ID - access controlled by RBAC data visibility."""
    # First get the profile to check ownership
    stmt = select(BusinessProfile).where(BusinessProfile.id == profile_id)
    result = await db.execute(stmt)
    profile = result.scalars().first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Business profile not found"
        )

    # Check data access permissions
    data_access_service = DataAccessService(sync_db)
    if not data_access_service.can_access_business_profile(
        current_user, profile_id, profile.user_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Insufficient permissions to update this profile"
        )

    update_data = profile_update.model_dump(exclude_unset=True)
    # Remove fields that are not in the BusinessProfile model
    update_data.pop("data_sensitivity", None)  # Temporarily removed until migration is run

    # Validate input data against whitelist and security patterns
    try:
        validated_data = validate_business_profile_update(update_data)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    ALLOWED_FIELDS = [
        "company_name",
        "industry",
        "company_size",
        "description",
        "data_sensitivity",
        "geographic_scope",
        "target_frameworks",
    ]
    for key, value in validated_data.items():
        if key in ALLOWED_FIELDS:
            setattr(profile, key, value)

    # The updated_at field is automatically handled by the database
    await db.commit()
    await db.refresh(profile)

    return profile


@router.delete("/{id}")
async def delete_business_profile_by_id(
    profile_id: UUID,
    current_user: UserWithRoles = Depends(require_permission("user_delete")),
    db: AsyncSession = Depends(get_async_db),
    sync_db: Session = Depends(get_db),
):
    """Delete a specific business profile by ID - access controlled by RBAC data visibility."""
    # First get the profile to check ownership
    stmt = select(BusinessProfile).where(BusinessProfile.id == profile_id)
    result = await db.execute(stmt)
    profile = result.scalars().first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Business profile not found"
        )

    # Check data access permissions
    data_access_service = DataAccessService(sync_db)
    if not data_access_service.can_access_business_profile(
        current_user, profile_id, profile.user_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Insufficient permissions to delete this profile"
        )

    await db.delete(profile)
    await db.commit()

    return {"message": "Business profile deleted successfully"}


@router.patch("/{id}", response_model=BusinessProfileResponse)
async def patch_business_profile(
    profile_id: UUID,
    profile_update: BusinessProfileUpdate,
    current_user: UserWithRoles = Depends(require_permission("user_update")),
    db: AsyncSession = Depends(get_async_db),
    sync_db: Session = Depends(get_db),
):
    """Update a specific business profile by ID with partial data - access controlled by RBAC."""
    # First get the profile to check ownership
    stmt = select(BusinessProfile).where(BusinessProfile.id == profile_id)
    result = await db.execute(stmt)
    profile = result.scalars().first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Business profile not found"
        )

    # Check data access permissions
    data_access_service = DataAccessService(sync_db)
    if not data_access_service.can_access_business_profile(
        current_user, profile_id, profile.user_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Insufficient permissions to update this profile"
        )

    update_data = profile_update.model_dump(exclude_unset=True)
    # Remove fields that are not in the BusinessProfile model
    update_data.pop("data_sensitivity", None)  # Temporarily removed until migration is run

    # Handle version-based optimistic locking if version is provided
    if "version" in update_data:
        expected_version = update_data.pop("version")
        current_version = getattr(profile, "version", 1)
        if expected_version != current_version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": {"message": "Conflict: Profile has been modified by another user"}
                },
            )

    # Validate input data against whitelist and security patterns
    try:
        validated_data = validate_business_profile_update(update_data)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    ALLOWED_FIELDS = [
        "company_name",
        "industry",
        "company_size",
        "description",
        "data_sensitivity",
        "geographic_scope",
        "target_frameworks",
    ]
    for key, value in validated_data.items():
        if key in ALLOWED_FIELDS:
            setattr(profile, key, value)

    # The updated_at field is automatically handled by the database
    await db.commit()
    await db.refresh(profile)

    return profile
