from uuid import UUID

from sqlalchemy import select

from mealie.db.models.recipe.ingredient import IngredientFoodModel
from mealie.repos.repository_factory import AllRepositories
from mealie.schema.openai.food import OpenAIFoodCategory
from mealie.services._base_service import BaseService
from mealie.services.openai.openai import OpenAIDataInjection, OpenAIService


class FoodCategorizationService(BaseService):
    def __init__(self, repos: AllRepositories) -> None:
        self.repos = repos
        self.openai_service = OpenAIService(repos)
        super().__init__()

    def _get_category_injections(self) -> list[OpenAIDataInjection]:
        labels = self.repos.group_multi_purpose_labels.get_all(order_by="name", order_descending=False)
        if not labels:
            return []

        label_lines = "\n".join(f"- {label.name}" for label in labels if label.name)
        if not label_lines:
            return []

        return [OpenAIDataInjection(description="Vorhandene Labels", value=label_lines)]

    async def _get_ai_category(self, food_name: str) -> OpenAIFoodCategory:
        prompt = self.openai_service.get_prompt(
            "recipes.classify-food-category",
            data_injections=self._get_category_injections(),
        )
        response = await self.openai_service.get_response(
            prompt,
            f"Artikel: {food_name}\nKategorie:",
            response_schema=OpenAIFoodCategory,
        )
        if response:
            self.logger.debug("Food '%s' classified as '%s'", food_name, response.category)
            return response

        return OpenAIFoodCategory(category="Other")

    async def classify_and_assign_to_food(self, food_name: str, *, food_id: UUID | None = None):
        if not food_name or food_id is None:
            return None

        ai_response = await self._get_ai_category(food_name)
        category_name = (ai_response.category or "Other").strip() or "Other"

        existing_label = self.repos.group_multi_purpose_labels.get_one(category_name, "name")
        if existing_label is None:
            return None

        stmt = select(IngredientFoodModel).where(IngredientFoodModel.id == food_id)
        food = self.repos.ingredient_foods.session.execute(stmt).scalars().one_or_none()
        if food is None:
            return None

        food.label_id = existing_label.id
        self.repos.ingredient_foods.session.commit()
        return existing_label
