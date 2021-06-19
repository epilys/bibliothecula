from . import *
from django import db
from django.http import FileResponse
from django.views.decorators.http import condition
from django.utils.safestring import mark_safe
from uuid import UUID
import html


@staff_member_required
@condition(last_modified_func=last_modified_binary_metadata)
def view_document_storage(request, uuid, metadata_uuid):
    uuid = UUID(uuid)
    metadata_uuid = UUID(metadata_uuid)

    try:
        m = BinaryMetadata.objects.get(pk=metadata_uuid)
    except BinaryMetadata.DoesNotExist:
        raise Http404("Binary metadata with this uuid does not exist")
    _t = m.try_get_content_type()
    if _t is not None:
        filename = _t["filename"]
        response = FileResponse(
            io.BytesIO(m.data),
            filename=filename,
            as_attachment=(
                _t["content_type"]
                not in [
                    "application/pdf",
                ]
                and not _t["content_type"].startswith("text/")
                and not _t["content_type"].startswith("image/")
            ),
        )
        response["Content-Type"] = _t["content_type"]
        if _t["content_type"].startswith("text/"):
            response["Content-Type"] += "; charset=UTF-8"
    else:
        response = FileResponse(io.BytesIO(m.data), filename=m.name, as_attachment=True)
    return response


def text2html(text, content_type):
    def newliner49er(iterable):
        it = iter(iterable)
        yield next(it)
        for x in it:
            yield "<br />"
            yield x

    if content_type == "text/markdown":
        try:
            from markdown_it import MarkdownIt

            md = MarkdownIt()
            return mark_safe(md.render(text))
        except ModuleNotFoundError:
            pass
        except ValueError:
            pass

    return mark_safe(
        "\n".join(
            newliner49er(
                map(lambda line: html.escape(line, quote=True), iter(text.split("\n")))
            )
        )
    )


@staff_member_required
@condition(last_modified_func=last_modified_binary_metadata)
def document_storage_viewer(request, uuid, metadata_uuid):
    uuid = UUID(uuid)
    metadata_uuid = UUID(metadata_uuid)
    text = None
    text_raw = None
    try:
        doc = Document.objects.all().get(uuid=uuid)
    except Document.DoesNotExist:
        raise Http404("Document with this uuid does not exist.")
    try:
        m = BinaryMetadata.objects.get(pk=metadata_uuid)
    except BinaryMetadata.DoesNotExist:
        raise Http404("Binary metadata with this uuid does not exist")
    _t = m.try_get_content_type()
    if _t is None or not _t["content_type"].startswith("text/"):
        return HttpResponseRedirect(reverse("view_document_storage"))
    try:
        text = m.data.decode("utf-8")
        text_raw = text

        text = text2html(text, _t["content_type"])
        text_raw = html.escape(text_raw, quote=True)
        # text_raw = text2html(text_raw, "text/plain")
    except Exception as exc:
        print(exc)
        return HttpResponseRedirect(reverse("view_document_storage"))
    filename = _t["filename"]

    refs = None
    try:
        with connections["bibliothecula"].cursor() as cursor:
            cursor.execute(
                f"SELECT target FROM backrefs_fts WHERE referrer = '{doc.uuid.hex}'"
            )
            refs = cursor.fetchall()
        print("refs: ", refs)
    except db.OperationalError:
        pass
    if refs is not None:
        objs = []
        for ref in refs:
            try:
                _doc = Document.objects.all().get(
                    binary_metadata__metadata__uuid=ref[0]
                )
                met = BinaryMetadata.objects.all().get(uuid=ref[0])
                objs.append((_doc, met))
            except Document.DoesNotExist:
                continue
        refs = objs

    context = {
        "title": doc.title,
        "document": doc,
        "m": m,
        "text": text,
        "text_raw": text_raw,
        "type_": _t,
        "refs": None if refs == [] else refs,
        "add_document_form": AddDocument(),
    }
    template = loader.get_template("text_viewer.html")
    return HttpResponse(template.render(context, request))


@staff_member_required
def edit_plain_text_document(request, uuid, metadata_uuid=None):
    uuid = UUID(uuid)
    if metadata_uuid is not None:
        metadata_uuid = UUID(metadata_uuid)
    try:
        doc = Document.objects.all().get(uuid=uuid)
    except Document.DoesNotExist:
        raise Http404("Document with this uuid does not exist.")
    has_metadata = None
    if metadata_uuid is not None:
        try:
            has_metadata = doc.binary_metadata.all().get(metadata__uuid=metadata_uuid)
        except DocumentHasBinaryMetadata.DoesNotExist:
            raise Http404(
                f"Document {doc} does not have associated metadata with uuid {metadata_uuid}."
            )

    if request.method == "POST":
        form = TextStorageEdit(request.POST)
        if form.is_valid():
            uuid = form.cleaned_data["uuid"]
            filename = form.cleaned_data["filename"]
            blob = str.encode(form.cleaned_data["content"])
            content_type = form.cleaned_data["content_type"]
            if has_metadata:
                # Create new dummy BinaryMetadata
                m = BinaryMetadata.new_file(
                    blob,
                    len(blob),
                    uuid=None,
                    content_type=content_type,
                    filename=filename,
                )
                has_metadata.metadata.name = m.name
                has_metadata.metadata.data = m.data
                has_metadata.metadata.set_last_modified()
                has_metadata.set_last_modified()
                doc.set_last_modified()
                m.delete()
            else:
                m = BinaryMetadata.new_file(
                    blob,
                    len(blob),
                    uuid=uuid,
                    content_type=content_type,
                    filename=filename,
                )
                m.save()
                has, _ = DocumentHasBinaryMetadata.objects.get_or_create(
                    name=STORAGE_NAME, document=doc, metadata=m
                )
                has.save()
            messages.add_message(
                request,
                messages.SUCCESS,
                f'Added file "{filename if filename else m.uuid}" {m.uuid if filename else ""} for {doc}',
            )
            return redirect(doc)
    elif has_metadata:
        _t = has_metadata.metadata.try_get_content_type()
        if _t is None:
            return HttpResponseBadRequest(
                request, f"{has_metadata.metadata} is not a plaintext file."
            )
        filename = _t["filename"]
        _type = _t["content_type"]
        try:
            content = has_metadata.metadata.data.decode(
                encoding="utf-8", errors="strict"
            )
        except:
            return HttpResponseBadRequest(
                request, f"{has_metadata.metadata} is not a plaintext file."
            )

        form = TextStorageEdit(
            initial={
                "uuid": has_metadata.metadata.uuid,
                "content_type": _type,
                "filename": filename,
                "content": content,
            }
        )
    else:
        form = TextStorageEdit()
    context = {
        "document": doc,
        "form": form,
        "add_document_form": AddDocument(),
    }
    template = loader.get_template("plain_text_edit.html")
    return HttpResponse(template.render(context, request))
