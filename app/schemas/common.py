"""Common schemas used across multiple modules"""
from pydantic import BaseModel


class PaginationMeta(BaseModel):
    """Pagination metadata"""
    page: int
    page_size: int
    total_items: int
    total_pages: int
