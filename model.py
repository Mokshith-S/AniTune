from pydantic import BaseModel, Field


class InputModel(BaseModel):
    mal_user_name: str = Field(default=None)


class RangeModel(InputModel):
    anime_start: int = Field(default=0)
    anime_total: int = Field(default=100)
    category_type: int = Field(default=1)
