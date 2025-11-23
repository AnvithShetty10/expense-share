"""Expense endpoints"""
import json
from typing import Optional
from datetime import date
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.expense import (
    ExpenseCreate,
    ExpenseUpdate,
    ExpenseResponse,
    ExpenseListItem,
    ExpenseListResponse,
    PaginationMeta
)
from app.services.expense_service import ExpenseService
from app.services.cache_service import CacheService
from app.api.deps import get_current_user
from app.models.user import User
from app.core.exceptions import (
    ValidationError,
    NotFoundError,
    AuthorizationError
)
from decimal import Decimal

router = APIRouter(prefix="/expenses", tags=["Expenses"])


@router.post("", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
async def create_expense(
    expense_data: ExpenseCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")
):
    """
    Create a new expense.

    Supports idempotency via the `Idempotency-Key` header to prevent duplicate
    expense creation. If the same key is used within 24 hours, the original
    response will be returned.

    Args:
        expense_data: Expense creation data with participants
        current_user: Current authenticated user
        db: Database session
        idempotency_key: Optional idempotency key for preventing duplicates

    Returns:
        Created expense with all details

    Raises:
        400: If validation fails (invalid amounts, participants, etc.)
        404: If any participant user ID doesn't exist
    """
    # Check idempotency key in cache if provided
    if idempotency_key:
        cache_key = f"idempotency:expense:{idempotency_key}:{current_user.id}"
        cached_response = await CacheService.get(cache_key)

        if cached_response:
            # Return cached response to prevent duplicate creation
            cached_data = json.loads(cached_response)
            return ExpenseResponse(**cached_data)

    # Create new expense
    try:
        expense = await ExpenseService.create_expense(
            expense_data,
            current_user.id,
            db
        )
        response = ExpenseResponse.model_validate(expense)

        # Cache response if idempotency key provided
        if idempotency_key:
            cache_key = f"idempotency:expense:{idempotency_key}:{current_user.id}"
            # Convert response to dict for JSON serialization
            response_dict = response.model_dump(mode='json')
            await CacheService.set(
                cache_key,
                json.dumps(response_dict, default=str),
                ttl=86400  # 24 hours
            )

        return response
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message
        )
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message
        )


@router.get("", response_model=ExpenseListResponse)
async def list_expenses(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    start_date: Optional[date] = Query(None, description="Filter by start date"),
    end_date: Optional[date] = Query(None, description="Filter by end date"),
    group_name: Optional[str] = Query(None, description="Filter by group name"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get list of expenses for the current user with pagination and filters.

    Args:
        page: Page number (1-indexed)
        page_size: Number of items per page (max 100)
        start_date: Optional start date filter
        end_date: Optional end date filter
        group_name: Optional group name filter
        current_user: Current authenticated user
        db: Database session

    Returns:
        Paginated list of expenses with metadata
    """
    expenses, total_count = await ExpenseService.get_user_expenses(
        current_user.id,
        db,
        page=page,
        page_size=page_size,
        start_date=start_date,
        end_date=end_date,
        group_name=group_name
    )

    # Calculate total pages
    total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 0

    # Transform expenses to list items
    expense_items = []
    for expense in expenses:
        # Find current user's participation
        user_participant = next(
            (p for p in expense.participants if p.user_id == current_user.id),
            None
        )

        if user_participant:
            # Calculate user's share (amount_owed - amount_paid)
            # Positive = user owes money (debit)
            # Negative = user is owed money (credit)
            net_amount = user_participant.amount_owed - user_participant.amount_paid
            share_type = "debit" if net_amount > 0 else "credit"
            your_share = abs(net_amount)

            expense_item = ExpenseListItem(
                id=expense.id,
                date=expense.expense_date,
                group_name=expense.group_name,
                description=expense.description,
                total_amount=expense.total_amount,
                your_share=your_share,
                share_type=share_type,
                created_by=expense.creator
            )
            expense_items.append(expense_item)

    pagination = PaginationMeta(
        page=page,
        page_size=page_size,
        total_items=total_count,
        total_pages=total_pages
    )

    return ExpenseListResponse(
        items=expense_items,
        pagination=pagination
    )


@router.get("/{expense_id}", response_model=ExpenseResponse)
async def get_expense(
    expense_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get detailed information about a specific expense.

    User must be a participant in the expense to view it.

    Args:
        expense_id: Expense UUID
        current_user: Current authenticated user
        db: Database session

    Returns:
        Complete expense details with all participants

    Raises:
        404: If expense not found
        403: If user is not a participant in the expense
    """
    try:
        expense = await ExpenseService.get_expense_details(
            expense_id,
            current_user.id,
            db
        )
        return ExpenseResponse.model_validate(expense)
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message
        )
    except AuthorizationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=e.message
        )


@router.put("/{expense_id}", response_model=ExpenseResponse)
async def update_expense(
    expense_id: UUID,
    expense_data: ExpenseUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update an existing expense.

    Only the creator of the expense can update it.

    Args:
        expense_id: Expense UUID
        expense_data: Updated expense data
        current_user: Current authenticated user
        db: Database session

    Returns:
        Updated expense with all details

    Raises:
        400: If validation fails
        404: If expense not found or participant user doesn't exist
        403: If user is not the creator of the expense
    """
    try:
        expense = await ExpenseService.update_expense(
            expense_id,
            expense_data,
            current_user.id,
            db
        )
        return ExpenseResponse.model_validate(expense)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message
        )
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message
        )
    except AuthorizationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=e.message
        )


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_expense(
    expense_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete an expense.

    Only the creator of the expense can delete it.
    All associated participants will be cascade deleted.

    Args:
        expense_id: Expense UUID
        current_user: Current authenticated user
        db: Database session

    Returns:
        No content (204)

    Raises:
        404: If expense not found
        403: If user is not the creator of the expense
    """
    try:
        await ExpenseService.delete_expense(
            expense_id,
            current_user.id,
            db
        )
        return None
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message
        )
    except AuthorizationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=e.message
        )
