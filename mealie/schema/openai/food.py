from pydantic import Field

from ._base import OpenAIBase


class OpenAIFoodCategory(OpenAIBase):
    category: str = Field(..., description="A short category label for the food, such as Fruit or Vegetable")
