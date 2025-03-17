from pydantic import BaseModel, Field


class RangeModel(BaseModel):
    mal_user_name: str = Field(default=None)
    anime_start: int = Field(default=0)
    anime_total: int = Field(default=100)
    category_type: int = Field(default=1)
    session_id: str = Field(default=None)
