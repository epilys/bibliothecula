# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models
from django.urls import reverse
from django.utils.html import format_html, mark_safe
from django.utils import timezone
import uuid
import urllib.parse
import os
import io
import json
import datetime
from functools import reduce, lru_cache
from pathlib import PurePosixPath, Path

from . import *
from .thumbnails import (
    generate_pdf_thumbnail,
    generate_epub_thumbnail,
    generate_image_thumbnail,
)
from .text_extract import get_pdf_text, get_epub_text

PDF_MIME = "application/pdf"
EPUB_MIME = "application/epub+zip"

THUMBNAIL_MIMES = [PDF_MIME, EPUB_MIME]


class DateTimeField(models.DateTimeField):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_db_prep_value(self, value, connection, prepared=False):
        # Casts datetimes into the format expected by the backend
        if not prepared:
            value = self.get_prep_value(value)
        if value is None:
            return None

        # Expression values are adapted by the database.
        if hasattr(value, "resolve_expression"):
            return value

        # SQLite doesn't support tz-aware datetimes
        if timezone.is_aware(value):
            if settings.USE_TZ:
                value = timezone.make_naive(value, connection.timezone)
            else:
                raise ValueError(
                    "SQLite backend does not support timezone-aware datetimes when USE_TZ is False."
                )

        return value.isoformat(sep=" ", timespec="milliseconds")


class Document(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.TextField(null=False)
    title_suffix = models.TextField(null=True, blank=False)
    created = DateTimeField(null=False, auto_now_add=True)
    last_modified = DateTimeField(null=False, auto_now=True)

    def __str__(self):
        return f"{self.title}"

    def set_last_modified(self, datetime_=None):
        if datetime_ is None:
            datetime_ = timezone.now()
        self.last_modified = datetime_
        self.save()
        return self.last_modified

    def get_absolute_url(self):
        type_ = self.type_()
        return reverse(
            "view_notes" if type_ == "notes" else "view_document",
            kwargs={"uuid": self.uuid},
        )

    def get_thumbnail_html(self):
        data_url = self.get_thumbnail()
        if data_url is None:
            return None
        return (
            format_html(
                '<img src="{}" class="thumbnail metadata" alt="thumbnail" />',
                mark_safe(data_url[0]),
            ),
            data_url[1],
        )

    def get_thumbnail(self):
        if (
            not self.binary_metadata.all()
            .filter(metadata__name=THUMBNAIL_NAME)
            .exists()
        ):
            return None
        thumb = self.binary_metadata.all().get(metadata__name=THUMBNAIL_NAME)
        return (thumb.metadata.contents_as_str(), thumb.metadata.uuid)

    def total_metadata(self):
        return self.text_metadata.all().count()

    def type_(self):
        return next(
            (
                t.metadata.data
                for t in self.text_metadata.all()
                if t.metadata.name == TYPE_NAME
            ),
            None,
        )

    def authors(self):
        return ", ".join(
            [
                str(t.metadata.data)
                for t in self.text_metadata.all().filter(metadata__name=AUTHOR_NAME)
            ]
        )

    def doi(self):
        return " ".join(
            [
                str(t.metadata.data)
                for t in self.text_metadata.all().filter(metadata__name=DOI_NAME)
            ]
        )

    def tags(self):
        return ", ".join(
            [
                str(t.metadata.data)
                for t in self.text_metadata.all().filter(metadata__name=TAG_NAME)
            ]
        )

    def tags_list(self):
        return self.text_metadata.all().filter(metadata__name=TAG_NAME)

    def duplicates(self):
        others = Document.objects.all().filter(title=self.title).exclude(uuid=self.uuid)
        return others

    def has_thumbnail(self):
        return self.binary_metadata.all().filter(metadata__name=THUMBNAIL_NAME).exists()

    has_thumbnail.boolean = True

    def has_duplicates(self):
        others = self.duplicates()
        return len(others) > 0

    has_duplicates.boolean = True

    def file_format_list(self):
        file_list = [f.metadata.file_type() for f in self.files()]
        return ", ".join([str(f) for f in file_list if f is not None])

    def storage_size(self):
        def f(accum, el):
            if el.metadata.name == PATH_NAME:
                accum["linked"] += el.metadata.size()
            else:
                accum["embedded"] += el.metadata.size()
            return accum

        return reduce(f, self.files(), {"embedded": 0, "linked": 0})

    def files_no(self):
        return self.files().count()

    def files(self):
        return DocumentHasBinaryMetadata.objects.all().filter(
            name=STORAGE_NAME, document=self
        )

    def index_text(self, force=False):
        if (
            not force
            and self.binary_metadata.all()
            .filter(metadata__name=FULL_TEXT_NAME)
            .exists()
        ):
            return False
        files = self.files()
        for m in files:
            path = m.metadata.try_as_path()
            text = None
            if path and path.exists():
                if path.endswith(".pdf"):
                    text = get_pdf_text(path)
                elif path.endswith(".epub"):
                    text = get_epub_text(path)
            else:
                _t = m.metadata.try_get_content_type()
                if _t is None:
                    continue
                if _t["content_type"] == PDF_MIME:
                    text = get_pdf_text(io.BytesIO(m.metadata.data))
                elif _t["content_type"] == EPUB_MIME:
                    text = get_epub_text(io.BytesIO(m.metadata.data))
                    print("get_epub_text returned ", type(text))
            try:
                if text is not None and len(text) > 0:
                    m = BinaryMetadata.objects.create(
                        name=FULL_TEXT_NAME, data=str.encode(text)
                    )
                    has = DocumentHasBinaryMetadata.objects.create(
                        name=FULL_TEXT_NAME, document=self, metadata=m
                    )
                    m.save()
                    has.save()
                    return True
                elif text is not None and len(text) == 0:
                    print("Empty text!")
            except Exception as exc:
                print("EXCEPTION!", exc)
            break
        return False

    def create_thumbnail(self, force=False, binary_metadata_uuid=None):
        created = False
        previous_thumbnails = list(
            self.binary_metadata.all()
            .filter(metadata__name=THUMBNAIL_NAME)
            .values("metadata__uuid")
        )
        has_already = len(previous_thumbnails) > 0
        if not force and has_already:
            return False
        files = self.files()
        for m in files:
            if (
                binary_metadata_uuid is not None
                and binary_metadata_uuid != m.metadata.uuid
            ):
                continue
            path = m.metadata.try_as_path()
            data_url = None
            if path and path.exists(path):
                if path.endswith(".pdf"):
                    data_url = generate_pdf_thumbnail(path)
                elif path.endswith(".epub"):
                    data_url = generate_epub_thumbnail(path)
            else:
                _t = m.metadata.try_get_content_type()
                if _t is None:
                    continue
                if _t["content_type"] == PDF_MIME:
                    path = _t["filename"]
                    data_url = generate_pdf_thumbnail(path, blob=m.metadata.data)
                elif _t["content_type"].startswith("image/"):
                    path = _t["filename"]
                    data_url = generate_image_thumbnail(path, blob=m.metadata.data)
                elif _t["content_type"] == EPUB_MIME:
                    path = _t["filename"]
                    data_url = generate_epub_thumbnail(path, blob=m.metadata.data)
            if data_url is not None:
                m = BinaryMetadata.objects.create(
                    name=THUMBNAIL_NAME, data=str.encode(data_url)
                )
                has = DocumentHasBinaryMetadata.objects.create(
                    name=THUMBNAIL_NAME, document=self, metadata=m
                )
                m.save()
                has.save()
                created = True
        if created:
            self.set_last_modified()
            if has_already:
                for v in previous_thumbnails:
                    has = self.binary_metadata.all().get(
                        metadata__uuid=v["metadata__uuid"]
                    )
                    has.delete()
        return created

    class Meta:
        ordering = (
            "last_modified",
            "created",
        )
        db_table = "Documents"


class TextMetadata(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.TextField(null=True)
    data = models.TextField(null=False)
    created = DateTimeField(null=False, auto_now_add=True)
    last_modified = DateTimeField(null=False, auto_now=True)

    def document_len(self):
        return len(self.documents.all())

    def __str__(self):
        return f"{self.name}={self.data}"

    class Meta:
        ordering = (
            "last_modified",
            "created",
        )
        db_table = "TextMetadata"
        unique_together = (
            "name",
            "data",
        )


class BinaryMetadata(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.TextField(null=True)
    data = models.BinaryField(null=False)
    compressed = models.BooleanField(null=False,default=False)
    created = DateTimeField(null=False, auto_now_add=True)
    last_modified = DateTimeField(null=False, auto_now=True)

    def new_file(blob, size, uuid=None, content_type="", filename=""):
        d = {
            "content_type": content_type.strip(),
            "filename": filename.strip(),
            "size": size,
        }
        name = json.dumps(d, separators=(",", ":"))
        m = BinaryMetadata.objects.create(uuid=uuid, name=name, data=blob)
        return m

    def from_file(_file):
        _file.seek(0)
        buf = io.BytesIO()
        for chunk in _file.chunks():
            buf.write(chunk)
        buf.seek(0)
        return BinaryMetadata.new_file(
            buf.getvalue(),
            _file.size,
            content_type=_file.content_type,
            filename=_file.name,
        )

    def try_get_content_type(self):
        if self.name in [PATH_NAME, THUMBNAIL_NAME]:
            return None
        try:
            return json.loads(self.name)
        except Exception as exc:
            print(exc)
        return None

    def contents_as_fileurl(self):
        try:
            path = self.try_as_path()
            if path:
                url = urllib.parse.quote(path)
                return f"file://{url}"
        except Exception as e:
            print(e)
        return None

    def try_as_path(self):
        try:
            path = self.contents_as_str()
            path = Path(path)
            if path and path.exists():
                return path
            else:
                return None
        except OSError:
            return None

    @lru_cache(maxsize=32)
    def size(self):
        content_type = self.try_get_content_type()
        if content_type is None:
            path = self.try_as_path()
            if path:
                return path.stat().st_size
        else:
            return content_type["size"]
        return len(self.data)

    def size_str(self):
        len_ = self.size()
        from django.template.defaultfilters import filesizeformat

        return filesizeformat(len_)

    def is_str(self):
        try:
            self.data.decode(encoding="utf-8", errors="strict")
            return True
        except:
            return False

    def contents_as_str(self):
        try:
            return self.data.decode(encoding="utf-8", errors="strict")
        except:
            pass
        return f"binary contents"

    def file_type(self):
        try:
            path = self.try_as_path()
            if path:
                suffix = path.suffix
                if suffix and len(suffix) > 1:
                    return suffix[1:]
        except:
            pass
        return None

    def __str__(self):
        return f"{self.name} [{self.uuid}]"

    class Meta:
        ordering = (
            "last_modified",
            "created",
        )
        db_table = "BinaryMetadata"
        unique_together = (
            "name",
            "data",
        )


class DocumentHasTextMetadata(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.TextField(null=False)
    document = models.ForeignKey(
        Document,
        null=False,
        related_name="text_metadata",
        db_column="document_uuid",
        on_delete=models.CASCADE,
    )
    metadata = models.ForeignKey(
        TextMetadata,
        null=False,
        related_name="documents",
        db_column="metadata_uuid",
        on_delete=models.CASCADE,
    )
    created = DateTimeField(null=False, auto_now_add=True)
    last_modified = DateTimeField(null=False, auto_now=True)

    def __str__(self):
        return f"{self.document}->{self.metadata}"

    class Meta:
        db_table = "DocumentHasTextMetadata"
        unique_together = (
            "document",
            "metadata",
        )


class DocumentHasBinaryMetadata(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.TextField(null=False)
    document = models.ForeignKey(
        Document,
        null=False,
        related_name="binary_metadata",
        db_column="document_uuid",
        on_delete=models.CASCADE,
    )
    metadata = models.ForeignKey(
        BinaryMetadata,
        null=False,
        related_name="documents",
        db_column="metadata_uuid",
        on_delete=models.CASCADE,
    )
    created = DateTimeField(null=False, auto_now_add=True)
    last_modified = DateTimeField(null=False, auto_now=True)

    def contents_as_str(self):
        return self.metadata.contents_as_str()

    def __str__(self):
        return f"{self.document}->{self.metadata}"

    class Meta:
        db_table = "DocumentHasBinaryMetadata"
        unique_together = (
            "document",
            "metadata",
        )


def last_modified_document(request, uuid):
    try:
        doc = Document.objects.get(uuid=uuid)
        return doc.last_modified
    except Document.DoesNotExist:
        return datetime.datetime.now()


def last_modified_binary_metadata(request, uuid, metadata_uuid):
    try:
        m = BinaryMetadata.objects.get(pk=metadata_uuid)
        return m.last_modified
    except BinaryMetadata.DoesNotExist:
        return datetime.datetime.now()


def last_modified_collection():
    lasts = []
    for model in (
        Document,
        TextMetadata,
        BinaryMetadata,
        DocumentHasTextMetadata,
        DocumentHasBinaryMetadata,
    ):
        try:
            m = model.objects.all().latest("last_modified").last_modified
            lasts.append(m)
        except model.DoesNotExist:
            pass
    if len(lasts) == 0:
        return datetime.datetime.now()
    return max(lasts)
