import re

from django import forms
from django.contrib.postgres.forms import SimpleArrayField
from django.core.exceptions import ObjectDoesNotExist
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from core.models import ContentType
from extras.choices import *
from extras.models import *
from netbox.forms import NetBoxModelImportForm
from utilities.forms import CSVModelForm
from utilities.forms.fields import (
    CSVChoiceField, CSVContentTypeField, CSVModelChoiceField, CSVMultipleContentTypeField, SlugField,
)

__all__ = (
    'ConfigTemplateImportForm',
    'CustomFieldChoiceSetImportForm',
    'CustomFieldImportForm',
    'CustomLinkImportForm',
    'EventRuleImportForm',
    'ExportTemplateImportForm',
    'JournalEntryImportForm',
    'SavedFilterImportForm',
    'TagImportForm',
    'WebhookImportForm',
)


class CustomFieldImportForm(CSVModelForm):
    content_types = CSVMultipleContentTypeField(
        label=_('Content types'),
        queryset=ContentType.objects.with_feature('custom_fields'),
        help_text=_("One or more assigned object types")
    )
    type = CSVChoiceField(
        label=_('Type'),
        choices=CustomFieldTypeChoices,
        help_text=_('Field data type (e.g. text, integer, etc.)')
    )
    object_type = CSVContentTypeField(
        label=_('Object type'),
        queryset=ContentType.objects.public(),
        required=False,
        help_text=_("Object type (for object or multi-object fields)")
    )
    choice_set = CSVModelChoiceField(
        label=_('Choice set'),
        queryset=CustomFieldChoiceSet.objects.all(),
        to_field_name='name',
        required=False,
        help_text=_('Choice set (for selection fields)')
    )
    ui_visible = CSVChoiceField(
        label=_('UI visible'),
        choices=CustomFieldUIVisibleChoices,
        required=False,
        help_text=_('Whether the custom field is displayed in the UI')
    )
    ui_editable = CSVChoiceField(
        label=_('UI editable'),
        choices=CustomFieldUIEditableChoices,
        required=False,
        help_text=_('Whether the custom field is editable in the UI')
    )

    class Meta:
        model = CustomField
        fields = (
            'name', 'label', 'group_name', 'type', 'content_types', 'object_type', 'required', 'description',
            'search_weight', 'filter_logic', 'default', 'choice_set', 'weight', 'validation_minimum',
            'validation_maximum', 'validation_regex', 'ui_visible', 'ui_editable', 'is_cloneable',
        )


class CustomFieldChoiceSetImportForm(CSVModelForm):
    base_choices = CSVChoiceField(
        choices=CustomFieldChoiceSetBaseChoices,
        required=False,
        help_text=_('The base set of predefined choices to use (if any)')
    )
    extra_choices = SimpleArrayField(
        base_field=forms.CharField(),
        required=False,
        help_text=_(
            'Quoted string of comma-separated field choices with optional labels separated by colon: '
            '"choice1:First Choice,choice2:Second Choice"'
        )
    )

    class Meta:
        model = CustomFieldChoiceSet
        fields = (
            'name', 'description', 'extra_choices', 'order_alphabetically',
        )

    def clean_extra_choices(self):
        if isinstance(self.cleaned_data['extra_choices'], list):
            data = []
            for line in self.cleaned_data['extra_choices']:
                try:
                    value, label = re.split(r'(?<!\\):', line, maxsplit=1)
                    value = value.replace('\\:', ':')
                    label = label.replace('\\:', ':')
                except ValueError:
                    value, label = line, line
                data.append((value, label))
            return data


class CustomLinkImportForm(CSVModelForm):
    content_types = CSVMultipleContentTypeField(
        label=_('Content types'),
        queryset=ContentType.objects.with_feature('custom_links'),
        help_text=_("One or more assigned object types")
    )

    class Meta:
        model = CustomLink
        fields = (
            'name', 'content_types', 'enabled', 'weight', 'group_name', 'button_class', 'new_window', 'link_text',
            'link_url',
        )


class ExportTemplateImportForm(CSVModelForm):
    content_types = CSVMultipleContentTypeField(
        label=_('Content types'),
        queryset=ContentType.objects.with_feature('export_templates'),
        help_text=_("One or more assigned object types")
    )

    class Meta:
        model = ExportTemplate
        fields = (
            'name', 'content_types', 'description', 'mime_type', 'file_extension', 'as_attachment', 'template_code',
        )


class ConfigTemplateImportForm(CSVModelForm):

    class Meta:
        model = ConfigTemplate
        fields = (
            'name', 'description', 'environment_params', 'template_code', 'tags',
        )


class SavedFilterImportForm(CSVModelForm):
    content_types = CSVMultipleContentTypeField(
        label=_('Content types'),
        queryset=ContentType.objects.all(),
        help_text=_("One or more assigned object types")
    )

    class Meta:
        model = SavedFilter
        fields = (
            'name', 'slug', 'content_types', 'description', 'weight', 'enabled', 'shared', 'parameters',
        )


class WebhookImportForm(NetBoxModelImportForm):

    class Meta:
        model = Webhook
        fields = (
            'name', 'payload_url', 'http_method', 'http_content_type', 'additional_headers', 'body_template',
            'secret', 'ssl_verification', 'ca_file_path', 'description', 'tags'
        )


class EventRuleImportForm(NetBoxModelImportForm):
    content_types = CSVMultipleContentTypeField(
        label=_('Content types'),
        queryset=ContentType.objects.with_feature('event_rules'),
        help_text=_("One or more assigned object types")
    )
    action_object = forms.CharField(
        label=_('Action object'),
        required=True,
        help_text=_('Webhook name or script as dotted path module.Class')
    )

    class Meta:
        model = EventRule
        fields = (
            'name', 'description', 'enabled', 'conditions', 'content_types', 'type_create', 'type_update',
            'type_delete', 'type_job_start', 'type_job_end', 'action_type', 'action_object', 'comments', 'tags'
        )

    def clean(self):
        super().clean()

        action_object = self.cleaned_data.get('action_object')
        action_type = self.cleaned_data.get('action_type')
        if action_object and action_type:
            # Webhook
            if action_type == EventRuleActionChoices.WEBHOOK:
                try:
                    webhook = Webhook.objects.get(name=action_object)
                except Webhook.DoesNotExist:
                    raise forms.ValidationError(f"Webhook {action_object} not found")
                self.instance.action_object = webhook
            # Script
            elif action_type == EventRuleActionChoices.SCRIPT:
                from extras.scripts import get_module_and_script
                module_name, script_name = action_object.split('.', 1)
                try:
                    module, script = get_module_and_script(module_name, script_name)
                except ObjectDoesNotExist:
                    raise forms.ValidationError(f"Script {action_object} not found")
                self.instance.action_object = module
                self.instance.action_object_type = ContentType.objects.get_for_model(module, for_concrete_model=False)
                self.instance.action_parameters = {
                    'script_name': script_name,
                }


class TagImportForm(CSVModelForm):
    slug = SlugField()

    class Meta:
        model = Tag
        fields = ('name', 'slug', 'color', 'description')
        help_texts = {
            'color': mark_safe(_('RGB color in hexadecimal. Example:') + ' <code>00ff00</code>'),
        }


class JournalEntryImportForm(NetBoxModelImportForm):
    assigned_object_type = CSVContentTypeField(
        queryset=ContentType.objects.all(),
        label=_('Assigned object type'),
    )
    kind = CSVChoiceField(
        label=_('Kind'),
        choices=JournalEntryKindChoices,
        help_text=_('The classification of entry')
    )

    class Meta:
        model = JournalEntry
        fields = (
            'assigned_object_type', 'assigned_object_id', 'created_by', 'kind', 'comments', 'tags'
        )
