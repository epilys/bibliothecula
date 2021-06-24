from django.contrib import admin, messages
from django.utils.translation import ngettext
from django.forms import Textarea
from .models import *
from wand.image import Image
import os

# class ValueInline(admin.TabularInline):
#    model = TestValue
#    fk_name = 'test'
#    extra = 10
#
# class TestPdfAdmin(admin.ModelAdmin):
#    save_on_top=True
#    inlines = [ValueInline,]
#    search_fields = ('name', )
#    #readonly_fields = ('pdf_preview',)
#    #def pdf_preview(self, instance):
#    #    from django.utils.html import mark_safe
#    #    return mark_safe('<iframe width=500 height=400 src="" />'%(instance.pk))
#    #pdf_preview.short_description = 'PDF preview'
#    #pdf_preview.allow_tags = True
#    list_display=('date_pretty', 'name', 'value_no')
#    def view_on_site(self, obj):
#        return f'/view/{obj.pk}'
#    formfield_overrides = {
#        models.TextField: {'widget': Textarea(attrs={'rows':2, 'cols':40})},
#    }
#
# class TestValueAdmin(admin.ModelAdmin):
#    search_fields = ('attribute', )
#    list_display = ('attribute_pretty', 'value_pretty', 'test')
#    list_filter = ('attribute', 'test' )
#    formfield_overrides = {
#        models.TextField: {'widget': Textarea(attrs={'rows':2, 'cols':40})},
#    }
#
# class AttributeAdmin(admin.ModelAdmin):
#    search_fields = ('name', )
#    list_display = ('name', 'unit', 'high_range', 'low_range')
#    formfield_overrides = {
#        models.TextField: {'widget': Textarea(attrs={'rows':2, 'cols':40})},
#    }
#
# admin.site.register(Attribute, AttributeAdmin)
# admin.site.register(TestPdf, TestPdfAdmin)
# admin.site.register(TestValue, TestValueAdmin)
class BinaryMetadataInline(admin.TabularInline):
    model = DocumentHasBinaryMetadata
    fk_name = "document"
    extra = 1


class BinaryMetadataInlineB(admin.TabularInline):
    model = DocumentHasBinaryMetadata
    fk_name = "metadata"
    extra = 1


class TextMetadataInline(admin.TabularInline):
    model = DocumentHasTextMetadata
    extra = 1


def index_documents(modeladmin, request, queryset):
    l = list(queryset)
    indexed = 0
    for doc in l:
        try:
            if doc.index_text(force=False):
                indexed += 1
        except Exception as exc:
            modeladmin.message_user(
                request, f"Could not index {doc.title}: {exc}", messages.ERROR
            )
    if indexed == 0:
        modeladmin.message_user(request, "No documents were indexed.", messages.INFO)
    else:
        modeladmin.message_user(
            request,
            ngettext(
                "%d document was indexed.",
                "%d documents were indexed.",
                indexed,
            )
            % indexed,
            messages.SUCCESS,
        )


index_documents.short_description = "Index a document's full text"


def add_missing_thumbnail(modeladmin, request, queryset):
    l = list(queryset)
    created = 0
    for doc in l:
        try:
            if doc.create_thumbnail(force=False):
                created += 1
        except Exception as exc:
            modeladmin.message_user(
                request,
                f"Could not create thumbnail for {doc.title}: {exc}",
                messages.ERROR,
            )
    if created == 0:
        modeladmin.message_user(request, "No thumbnails were created.", messages.INFO)
    else:
        modeladmin.message_user(
            request,
            ngettext(
                "%d thumbnail was generated.",
                "%d thumbnails were generated.",
                created,
            )
            % created,
            messages.SUCCESS,
        )


add_missing_thumbnail.short_description = "Add thumbnail if missing"


def merge_documents(modeladmin, request, queryset):
    l = list(queryset)
    first = l[0]
    for d in l:
        if d.uuid == first.uuid:
            continue
        for has_other_metadata in DocumentHasTextMetadata.objects.all().filter(
            document=d
        ):
            if (
                DocumentHasTextMetadata.objects.all()
                .filter(document=first, metadata=has_other_metadata.metadata)
                .exists()
            ):
                has_other_metadata.delete()
            else:
                has_other_metadata.update(document=first)
        d.delete()


merge_documents.short_description = "Merge documents"


class TagFilter(admin.SimpleListFilter):
    # Human-readable title which will be displayed in the
    # right admin sidebar just above the filter options.
    title = "tags"

    # Parameter for the filter that will be used in the URL query.
    parameter_name = "tag"

    def lookups(self, request, model_admin):
        """
        Returns a list of tuples. The first element in each
        tuple is the coded value for the option that will
        appear in the URL query. The second element is the
        human-readable name for the option that will appear
        in the right sidebar.
        """
        s = set()
        for tag in TextMetadata.objects.all().filter(name=TAG_NAME):
            s.add(tag.data)
        l = [("none", None)]
        for t in s:
            l.append((t, t))
        return l

    def queryset(self, request, queryset):
        """
        Returns the filtered queryset based on the value
        provided in the query string and retrievable via
        `self.value()`.
        """
        tag = self.value()
        if tag is None:
            return queryset.exclude(text_metadata__metadata__name=TAG_NAME)
        else:
            return queryset.filter(text_metadata__metadata__data=tag)


class DupFilter(admin.SimpleListFilter):
    # Human-readable title which will be displayed in the
    # right admin sidebar just above the filter options.
    title = "has duplicates"

    # Parameter for the filter that will be used in the URL query.
    parameter_name = "title"

    def lookups(self, request, model_admin):
        """
        Returns a list of tuples. The first element in each
        tuple is the coded value for the option that will
        appear in the URL query. The second element is the
        human-readable name for the option that will appear
        in the right sidebar.
        """
        return [
            (d.title, f"{d.title} {len(d.duplicates())}")
            for d in Document.objects.all()
            if d.has_duplicates()
        ]

    def queryset(self, request, queryset):
        """
        Returns the filtered queryset based on the value
        provided in the query string and retrievable via
        `self.value()`.
        """
        print(self.value())
        return queryset.filter(title=self.value())


class DocumentAdmin(admin.ModelAdmin):
    save_on_top = True
    inlines = [TextMetadataInline, BinaryMetadataInline]
    list_display = (
        "title",
        "authors",
        "doi",
        "tags",
        "total_metadata",
        "uuid",
        "has_duplicates",
        "has_thumbnail",
        "file_format_list",
        "created",
        "last_modified",
    )
    # list_filter = (TagFilter,)
    list_filter = ("text_metadata__metadata__data",)
    search_fields = ("title",)
    ordering = ("title", "created", "last_modified")
    actions = [add_missing_thumbnail, merge_documents, index_documents]
    list_per_page = 500

    class Media:
        css = {
            "all": ("column-widths.css",),
        }


class TextMetadataInlineB(admin.TabularInline):
    model = DocumentHasTextMetadata
    fk_name = "metadata"
    extra = 1


def merge_tags(modeladmin, request, queryset):
    l = list(queryset)
    first = l[0]
    for m in l:
        if m.uuid == first.uuid:
            continue
        DocumentHasTextMetadata.objects.all().filter(metadata=m).update(metadata=first)
        m.delete()


merge_tags.short_description = "Merge tags"


class TextMetadataAdmin(admin.ModelAdmin):
    save_on_top = True
    list_display = ("name", "data", "uuid")
    list_filter = ("name",)
    search_fields = ("data",)
    ordering = ("name",)
    inlines = [TextMetadataInline]
    actions = [merge_tags]
    list_per_page = 500


class DocumentHasBinaryAdmin(admin.ModelAdmin):
    save_on_top = True
    list_display = ("document", "contents_as_str")
    list_filter = ("document",)
    search_fields = ("document",)
    ordering = ("document",)
    list_per_page = 500

    class Media:
        css = {
            "all": ("column-widths.css",),
        }


def convertmime(modeladmin, request, queryset):
    import json

    converted = 0
    for b in queryset:
        ct = b.try_get_content_type()
        if ct is None:
            continue
        j = json.dumps(ct, separators=(",", ":"))
        b.name = j
        b.save()
        converted += 1
        print(b.uuid, j)
    if converted == 0:
        modeladmin.message_user(
            request, "No metadata name were converted.", messages.INFO
        )
    else:
        modeladmin.message_user(
            request,
            ngettext(
                "%d document was converted.",
                "%d metadata names were converted.",
                converted,
            )
            % converted,
            messages.SUCCESS,
        )


convertmime.short_description = "Convert mime"


class BinaryMetadataAdmin(admin.ModelAdmin):
    save_on_top = True
    inlines = [BinaryMetadataInlineB]
    list_display = (
        "uuid",
        "name",
        "size",
        "is_str",
        "created",
        "last_modified",
    )
    list_filter = ("documents",)
    search_fields = ("name",)
    ordering = ("name", "created", "last_modified")
    actions = [convertmime]
    list_per_page = 500

    class Media:
        css = {
            "all": ("column-widths.css",),
        }


admin.site.register(Document, DocumentAdmin)
admin.site.register(TextMetadata, TextMetadataAdmin)
admin.site.register(BinaryMetadata, BinaryMetadataAdmin)
admin.site.register(DocumentHasTextMetadata)
admin.site.register(DocumentHasBinaryMetadata, DocumentHasBinaryAdmin)
