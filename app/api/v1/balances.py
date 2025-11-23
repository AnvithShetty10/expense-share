"""Balance endpoints"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.exceptions import NotFoundError
from app.database import get_db
from app.models.user import User
from app.schemas.balance import (BalanceListResponse, BalanceSummary,
                                 UserBalanceDetail)
from app.services.balance_service import BalanceService

router = APIRouter(prefix="/balances", tags=["Balances"])


@router.get("", response_model=BalanceListResponse)
async def get_balances(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """
    Get all balances for the current user.

    Returns a list of balances showing who owes the user money and
    who the user owes money to. Balances are sorted by amount (descending).

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        List of balances with user details and amounts
    """
    balances = await BalanceService.get_user_balances(
        current_user.id, db, use_cache=True
    )

    return BalanceListResponse(balances=balances)


@router.get("/summary", response_model=BalanceSummary)
async def get_balance_summary(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """
    Get balance summary for the current user.

    Provides an overview of the user's financial situation including:
    - Overall balance (positive = owed money, negative = owes money)
    - Total amount owed to the user
    - Total amount the user owes
    - Number of people involved in each direction

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        Balance summary with aggregated statistics
    """
    summary = await BalanceService.get_balance_summary(
        current_user.id, db, use_cache=True
    )

    return summary


@router.get("/user/{user_id}", response_model=UserBalanceDetail)
async def get_balance_with_user(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get balance between current user and a specific other user.

    Returns the net balance along with the history of all shared expenses
    between the two users. This is useful for understanding how the
    balance was calculated.

    Args:
        user_id: ID of the other user
        current_user: Current authenticated user
        db: Database session

    Returns:
        Balance details with shared expense history

    Raises:
        404: If the specified user doesn't exist
    """
    try:
        balance_detail = await BalanceService.get_balance_with_user(
            current_user.id, user_id, db
        )
        return balance_detail
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
