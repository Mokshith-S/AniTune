from pydantic import BaseModel, Field


class InputModel(BaseModel):
    mal_user_name: str = Field(default=None)


class RangeModel(BaseModel):
    start_range: int = Field(default=0)
    song_limit: int = Field(default=100)
    category_type: int = Field(default=1)
