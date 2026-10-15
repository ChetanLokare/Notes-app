from pydantic import BaseModel, Field, ConfigDict


class Note(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=200)
    note: str = Field(min_length=1)
    important: bool = False