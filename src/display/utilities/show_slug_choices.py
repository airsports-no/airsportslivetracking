from drf_yasg.inspectors import RelatedFieldInspector
from rest_framework.metadata import SimpleMetadata
from rest_framework.relations import ManyRelatedField, RelatedField, SlugRelatedField


class ShowChoicesMetadata(SimpleMetadata):
    def get_field_info(self, field):
        field_info = super().get_field_info(field)
        if (
            not field_info.get("read_only")
            and isinstance(field, (ManyRelatedField, RelatedField))
            and hasattr(field, "choices")
            and getattr(field, "show_choices", False)
        ):
            field_info["choices"] = [
                {"value": choice_value, "display_name": str(choice_name)}
                for choice_value, choice_name in field.choices.items()
            ]

        return field_info


class ShowChoicesMixin:
    show_choices = True


class ChoicesSlugRelatedField(ShowChoicesMixin, SlugRelatedField):
    pass


class ShowChoicesFieldInspector(RelatedFieldInspector):
    def field_to_swagger_object(self, field, swagger_object_type, use_references, **kwargs):
        dataobj = super().field_to_swagger_object(field, swagger_object_type, use_references, **kwargs)
        if (
            isinstance(field, ChoicesSlugRelatedField)
            and hasattr(field, "choices")
            and getattr(field, "show_choices", False)
            and "enum" not in dataobj
        ):
            dataobj["enum"] = [k for k, v in field.choices.items()]
        return dataobj
