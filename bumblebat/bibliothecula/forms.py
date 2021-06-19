from django import forms
from django.forms import formset_factory, ModelForm
from django.forms import modelformset_factory
from django.apps import apps as django_apps
from bibliothecula import *

SORT_CHOICES = [
    ("title", "title"),
    ("last_modified", "last modified"),
    ("created", "creation date"),
]
LAYOUT_CHOICES = [("grid", "Grid"), ("table", "Table")]


class DocumentMetadataSearch(forms.Form):
    query = forms.CharField(
        label="Metadata query string", required=False, max_length=200
    )
    query.widget.input_type = "search"
    query.widget.attrs.update({"placeholder": "query"})


class DocumentFullTextSearch(forms.Form):
    full_text_query = forms.CharField(
        label="Full text query", required=False, max_length=200
    )
    full_text_query.widget.input_type = "search"
    full_text_query.widget.attrs.update({"placeholder": "full-text query"})


class CombinationForm(forms.Form):
    combination = forms.ChoiceField(
        label="Boolean operator",
        widget=forms.RadioSelect,
        required=False,
        choices=[("AND", "AND"), ("OR", "OR")],
    )


class CollectionLayout(forms.Form):
    layout = forms.ChoiceField(
        widget=forms.RadioSelect, required=False, choices=LAYOUT_CHOICES
    )


class CollectionType(forms.Form):
    null = forms.BooleanField(required=False)
    _type = forms.MultipleChoiceField(
        label="Document type",
        required=False,
        choices=[
            (t.uuid, t.data)
            for t in django_apps.get_model("bibliothecula.TextMetadata")
            .objects.all()
            .filter(name=TYPE_NAME)
            .all()
            .order_by("data")
        ],
    )
    _type.widget.attrs.update({"autocomplete": "off", "size": 4})


class CollectionSort(forms.Form):
    field = forms.ChoiceField(label="Sort field", required=False, choices=SORT_CHOICES)
    ascending = forms.BooleanField(required=False)


class DocumentAddLinkStorage(forms.Form):
    path = forms.CharField(label="Full document path", required=True, max_length=500)


class DocumentAddEmbeddedStorage(forms.Form):
    _file = forms.FileField(label="Browse and select files to upload", required=True)


class DocumentSetTag(forms.Form):
    tag = forms.CharField(required=True, max_length=500)


class DocumentSetMetadata(forms.Form):
    name = forms.CharField(required=True, max_length=500)
    data = forms.CharField(required=True, max_length=500)


class AddDocument(forms.Form):
    title = forms.CharField(label="document title", required=True)


class ImportDocumentsForm(forms.Form):
    files = forms.FileField(widget=forms.ClearableFileInput(attrs={"multiple": True}))


def new_author_field():
    author = forms.CharField(label="author", required=False)
    author.widget.attrs.update({"placeholder": "UUID or author name"})
    return author


def new_tag_field():
    tag = forms.CharField(label="tag", required=False)
    tag.widget.attrs.update({"placeholder": "UUID or tag name"})
    return tag


class NewDocument(forms.Form):
    original_filename = forms.CharField(
        label="original filename", required=False, disabled=True, widget=forms.Textarea
    )
    original_filename.widget.attrs.update(
        {"rows": 3, "placeholder": "Original filename cannot be empty."}
    )
    filename = forms.CharField(
        label="target filename", required=True, widget=forms.Textarea
    )
    filename.widget.attrs.update(
        {"rows": 3, "placeholder": "Filename cannot be empty."}
    )
    index = forms.BooleanField(label="full-text index", required=False, initial=True)
    title = forms.CharField(
        label="document title", required=True, widget=forms.Textarea
    )
    title.widget.attrs.update({"rows": 3, "placeholder": "Title cannot be empty."})
    _type = forms.ChoiceField(
        label="document type",
        required=False,
        choices=(
            [("", "-")]
            + [
                (t.uuid, t.data)
                for t in django_apps.get_model("bibliothecula.TextMetadata")
                .objects.all()
                .filter(name=TYPE_NAME)
                .all()
                .order_by("data")
            ]
        ),
    )
    date = forms.CharField(label="date", required=False)
    author0 = new_author_field()
    tag0 = new_tag_field()


class TextStorageEdit(forms.Form):
    datalist_id = "content-types"
    datalist_options = [
        "text/plain",
        "text/markdown",
        "text/csv",
        "text/html",
        "text/calendar",
        "application/json",
    ]
    uuid = forms.UUIDField(label="data uuid", required=False)
    uuid.widget.attrs.update({"placeholder": "leave empty to auto-generate one"})
    filename = forms.CharField(label="filename", required=False)
    content = forms.CharField(
        label="text", required=True, min_length=1, strip=True, widget=forms.Textarea
    )
    content_type = forms.CharField(
        label="content type",
        help_text="select suggested values ▾",
        required=False,
        strip=True,
        initial="text/plain",
    )
    content_type.widget.attrs.update({"list": datalist_id})
    content_type.widget.attrs.update({"placeholder": content_type.help_text})
