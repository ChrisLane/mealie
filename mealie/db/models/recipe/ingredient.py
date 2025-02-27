from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, event, orm
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.orm.session import Session

from mealie.db.models._model_base import BaseMixins, SqlAlchemyBase
from mealie.db.models.labels import MultiPurposeLabel
from mealie.db.models.recipe.api_extras import IngredientFoodExtras, api_extras

from .._model_utils import auto_init
from .._model_utils.guid import GUID

if TYPE_CHECKING:
    from ..group import Group


class IngredientUnitModel(SqlAlchemyBase, BaseMixins):
    __tablename__ = "ingredient_units"
    id: Mapped[GUID] = mapped_column(GUID, primary_key=True, default=GUID.generate)

    # ID Relationships
    group_id: Mapped[GUID] = mapped_column(GUID, ForeignKey("groups.id"), nullable=False, index=True)
    group: Mapped["Group"] = orm.relationship("Group", back_populates="ingredient_units", foreign_keys=[group_id])

    name: Mapped[str | None] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(String)
    abbreviation: Mapped[str | None] = mapped_column(String)
    use_abbreviation: Mapped[bool | None] = mapped_column(Boolean, default=False)
    fraction: Mapped[bool | None] = mapped_column(Boolean, default=True)
    ingredients: Mapped[list["RecipeIngredientModel"]] = orm.relationship(
        "RecipeIngredientModel", back_populates="unit"
    )

    # Automatically updated by sqlalchemy event, do not write to this manually
    name_normalized: Mapped[str | None] = mapped_column(sa.String, index=True)
    abbreviation_normalized: Mapped[str | None] = mapped_column(String, index=True)

    @auto_init()
    def __init__(self, session: Session, name: str | None = None, abbreviation: str | None = None, **_) -> None:
        if name is not None:
            self.name_normalized = self.normalize(name)

        if abbreviation is not None:
            self.abbreviation = self.normalize(abbreviation)

        tableargs = [
            sa.UniqueConstraint("name", "group_id", name="ingredient_units_name_group_id_key"),
            sa.Index(
                "ix_ingredient_units_name_normalized",
                "name_normalized",
                unique=False,
            ),
            sa.Index(
                "ix_ingredient_units_abbreviation_normalized",
                "abbreviation_normalized",
                unique=False,
            ),
        ]

        if session.get_bind().name == "postgresql":
            tableargs.extend(
                [
                    sa.Index(
                        "ix_ingredient_units_name_normalized_gin",
                        "name_normalized",
                        unique=False,
                        postgresql_using="gin",
                        postgresql_ops={
                            "name_normalized": "gin_trgm_ops",
                        },
                    ),
                    sa.Index(
                        "ix_ingredient_units_abbreviation_normalized_gin",
                        "abbreviation_normalized",
                        unique=False,
                        postgresql_using="gin",
                        postgresql_ops={
                            "abbreviation_normalized": "gin_trgm_ops",
                        },
                    ),
                ]
            )

        self.__table_args__ = tuple(tableargs)


class IngredientFoodModel(SqlAlchemyBase, BaseMixins):
    __tablename__ = "ingredient_foods"
    id: Mapped[GUID] = mapped_column(GUID, primary_key=True, default=GUID.generate)

    # ID Relationships
    group_id: Mapped[GUID] = mapped_column(GUID, ForeignKey("groups.id"), nullable=False, index=True)
    group: Mapped["Group"] = orm.relationship("Group", back_populates="ingredient_foods", foreign_keys=[group_id])

    name: Mapped[str | None] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(String)
    ingredients: Mapped[list["RecipeIngredientModel"]] = orm.relationship(
        "RecipeIngredientModel", back_populates="food"
    )
    extras: Mapped[list[IngredientFoodExtras]] = orm.relationship("IngredientFoodExtras", cascade="all, delete-orphan")

    label_id: Mapped[GUID | None] = mapped_column(GUID, ForeignKey("multi_purpose_labels.id"), index=True)
    label: Mapped[MultiPurposeLabel | None] = orm.relationship(MultiPurposeLabel, uselist=False, back_populates="foods")

    # Automatically updated by sqlalchemy event, do not write to this manually
    name_normalized: Mapped[str | None] = mapped_column(sa.String, index=True)

    @api_extras
    @auto_init()
    def __init__(self, session: Session, name: str | None = None, **_) -> None:
        if name is not None:
            self.name_normalized = self.normalize(name)

        tableargs = [
            sa.UniqueConstraint("name", "group_id", name="ingredient_foods_name_group_id_key"),
            sa.Index(
                "ix_ingredient_foods_name_normalized",
                "name_normalized",
                unique=False,
            ),
        ]

        if session.get_bind().name == "postgresql":
            tableargs.extend(
                [
                    sa.Index(
                        "ix_ingredient_foods_name_normalized_gin",
                        "name_normalized",
                        unique=False,
                        postgresql_using="gin",
                        postgresql_ops={
                            "name_normalized": "gin_trgm_ops",
                        },
                    )
                ]
            )

        self.__table_args__ = tuple(tableargs)


class RecipeIngredientModel(SqlAlchemyBase, BaseMixins):
    __tablename__ = "recipes_ingredients"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    position: Mapped[int | None] = mapped_column(Integer, index=True)
    recipe_id: Mapped[GUID | None] = mapped_column(GUID, ForeignKey("recipes.id"))

    title: Mapped[str | None] = mapped_column(String)  # Section Header - Shows if Present
    note: Mapped[str | None] = mapped_column(String)  # Force Show Text - Overrides Concat

    # Scaling Items
    unit_id: Mapped[GUID | None] = mapped_column(GUID, ForeignKey("ingredient_units.id"), index=True)
    unit: Mapped[IngredientUnitModel | None] = orm.relationship(IngredientUnitModel, uselist=False)

    food_id: Mapped[GUID | None] = mapped_column(GUID, ForeignKey("ingredient_foods.id"), index=True)
    food: Mapped[IngredientFoodModel | None] = orm.relationship(IngredientFoodModel, uselist=False)
    quantity: Mapped[float | None] = mapped_column(Float)

    original_text: Mapped[str | None] = mapped_column(String)

    reference_id: Mapped[GUID | None] = mapped_column(GUID)  # Reference Links

    # Automatically updated by sqlalchemy event, do not write to this manually
    note_normalized: Mapped[str | None] = mapped_column(String, index=True)
    original_text_normalized: Mapped[str | None] = mapped_column(String, index=True)

    @auto_init()
    def __init__(self, session: Session, note: str | None = None, orginal_text: str | None = None, **_) -> None:
        # SQLAlchemy events do not seem to register things that are set during auto_init
        if note is not None:
            self.note_normalized = self.normalize(note)

        if orginal_text is not None:
            self.orginal_text = self.normalize(orginal_text)

        tableargs = [  # base set of indices
            sa.Index(
                "ix_recipes_ingredients_note_normalized",
                "note_normalized",
                unique=False,
            ),
            sa.Index(
                "ix_recipes_ingredients_original_text_normalized",
                "original_text_normalized",
                unique=False,
            ),
        ]
        if session.get_bind().name == "postgresql":
            tableargs.extend(
                [
                    sa.Index(
                        "ix_recipes_ingredients_note_normalized_gin",
                        "note_normalized",
                        unique=False,
                        postgresql_using="gin",
                        postgresql_ops={
                            "note_normalized": "gin_trgm_ops",
                        },
                    ),
                    sa.Index(
                        "ix_recipes_ingredients_original_text_normalized_gin",
                        "original_text",
                        unique=False,
                        postgresql_using="gin",
                        postgresql_ops={
                            "original_text_normalized": "gin_trgm_ops",
                        },
                    ),
                ]
            )
        # add indices
        self.__table_args__ = tuple(tableargs)


@event.listens_for(IngredientUnitModel.name, "set")
def receive_unit_name(target: IngredientUnitModel, value: str | None, oldvalue, initiator):
    if value is not None:
        target.name_normalized = IngredientUnitModel.normalize(value)
    else:
        target.name_normalized = None


@event.listens_for(IngredientUnitModel.abbreviation, "set")
def receive_unit_abbreviation(target: IngredientUnitModel, value: str | None, oldvalue, initiator):
    if value is not None:
        target.abbreviation_normalized = IngredientUnitModel.normalize(value)
    else:
        target.abbreviation_normalized = None


@event.listens_for(IngredientFoodModel.name, "set")
def receive_food_name(target: IngredientFoodModel, value: str | None, oldvalue, initiator):
    if value is not None:
        target.name_normalized = IngredientFoodModel.normalize(value)
    else:
        target.name_normalized = None


@event.listens_for(RecipeIngredientModel.note, "set")
def receive_ingredient_note(target: RecipeIngredientModel, value: str | None, oldvalue, initiator):
    if value is not None:
        target.note_normalized = RecipeIngredientModel.normalize(value)
    else:
        target.note_normalized = None


@event.listens_for(RecipeIngredientModel.original_text, "set")
def receive_ingredient_original_text(target: RecipeIngredientModel, value: str | None, oldvalue, initiator):
    if value is not None:
        target.original_text_normalized = RecipeIngredientModel.normalize(value)
    else:
        target.original_text_normalized = None
