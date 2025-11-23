"""Main v1 router aggregator"""
from fastapi import APIRouter

from app.api.v1 import auth

# Create v1 router
api_router = APIRouter()

# Include all v1 routers
api_router.include_router(auth.router)

# Additional routers will be added here as we build them
# api_router.include_router(expenses.router)
# api_router.include_router(balances.router)
# api_router.include_router(users.router)
