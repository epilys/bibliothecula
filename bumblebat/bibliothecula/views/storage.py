from . import *
from django import db
from django.http import FileResponse
from django.views.decorators.http import condition
from django.utils.safestring import mark_safe
from django.urls import reverse
from uuid import UUID
import html

from markdown_it.rules_inline import StateInline
from markdown_it.token import Token


def reflink(md):
    def reflink_render(self, tokens, idx, options, env):
        dbg(self)
        dbg(idx)
        dbg([x for x in enumerate(tokens)])
        tok = tokens[idx]
        dbg(tok)
        return self.renderToken(tokens, idx, options, env)

    def reflink_def(state: StateInline, silent: bool) -> bool:
        pos = state.pos

        if state.srcCharCode[pos] != 0x3C:  # /* < */
            return False

        start = state.pos
        maximum = state.posMax

        while True:
            pos += 1
            if pos >= maximum:
                return False

            ch = state.srcCharCode[pos]

            if ch == 0x3C:  # /* < */
                return False
            if ch == 0x3E:  # /* > */
                break

        url = state.src[start + 1 : pos]
        print("url is ", url)
        try:
            uuid = UUID(url)
        except ValueError:
            print("valuerror", url)
            return False
        print("uuid success ", uuid)

        target = None
        try:
            _doc = Document.objects.all().get(binary_metadata__metadata__uuid=uuid)
            met = BinaryMetadata.objects.all().get(uuid=uuid)
            target = (_doc, met)
        except Document.DoesNotExist:
            pass
        except BinaryMetadata.DoesNotExist:
            pass
        print("first get result", target)
        if target is None:
            try:
                _doc = Document.objects.all().get(uuid=uuid)
                target = (_doc, None)
            except Document.DoesNotExist:
                pass
            except BinaryMetadata.DoesNotExist:
                pass
        print("sec get result", target)

        if target is None:
            return False

        if not silent:
            token = state.push("link_open", "a", 1)
            token.attrs = {}
            if target[1] is None:
                token.attrs["href"] = target[0].get_absolute_url()
                token.attrs["id"] = f"ref-{target[0].uuid}"
            else:
                token.attrs["href"] = reverse(
                    "document_storage_viewer", args=[target[0].uuid, target[1].uuid]
                )
                token.attrs["id"] = f"ref-{target[1].uuid}"
            token.attrs["class"] = "ref"
            token.markup = "reflink"
            token.info = "auto"
            token.meta["id"] = reflink_def.refcount
            token.meta["ref"] = {}

            token = state.push("text", "", 0)
            if target[1] is None:
                token.content = str(target[0].uuid)
            else:
                token.content = str(target[1].uuid)

            token = state.push("link_close", "a", -1)
            token.markup = "reflink"
            token.info = "auto"
            token = state.push("sup_open", "sup", 1)
            token = state.push("text", "", 0)
            token = state.push("sup_close", "sup", -1)
            token = state.push("span_open", "span", 1)
            token.attrs["class"] = "ref-expand"
            token.attrs["data-ref-num"] = reflink_def.refcount
            if target[1] is None:
                token.attrs["id"] = f"ref-expand-{target[1].uuid}"
                token = state.push("text", "", 0)
                _type = target[0].try_get_content_type()
                token.content = _type["filename"] if _type else str(target[0])
                token.attrs["id"] = f"ref-expand-{target[0].uuid}"
            else:
                token.attrs["id"] = f"ref-expand-{target[1].uuid}"
                token = state.push("text", "", 0)
                _type = target[1].try_get_content_type()
                token.content = _type["filename"] if _type else str(target[1])
            token = state.push("span_close", "span", -1)

            reflink_def.refcount += 1

        dbg(dir(state))
        state.pos += len(url) + 2
        return True

    reflink_def.refcount = 1
    md.inline.ruler.after("autolink", "reflink_def", reflink_def)
    md.add_render_rule("link_open", reflink_render, fmt="html")


@staff_member_required
@condition(last_modified_func=last_modified_binary_metadata)
def view_document_storage(request, uuid, metadata_uuid):
    if not isinstance(uuid, UUID):
        uuid = UUID(uuid)
    if not isinstance(metadata_uuid, UUID):
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

            md = MarkdownIt().use(reflink)
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
    backrefs = None
    try:
        with connections["bibliothecula"].cursor() as cursor:
            cursor.execute(
                f"SELECT target FROM backrefs_fts WHERE referrer = '{m.uuid.hex}'"
            )
            refs = cursor.fetchall()
            cursor.execute(
                f"SELECT referrer FROM backrefs_fts WHERE target = '{m.uuid.hex}'"
            )
            backrefs = cursor.fetchall()
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
                objs.append((_doc, met, met.try_get_content_type()))
            except Document.DoesNotExist:
                continue
        refs = objs
    if backrefs is not None:
        objs = []
        for backref in backrefs:
            try:
                _doc = Document.objects.all().get(
                    binary_metadata__metadata__uuid=backref[0]
                )
                met = BinaryMetadata.objects.all().get(uuid=backref[0])
                objs.append((_doc, met, met.try_get_content_type()))
            except Document.DoesNotExist:
                continue
        backrefs = objs

    context = {
        "title": doc.title,
        "document": doc,
        "m": m,
        "text": text,
        "text_raw": text_raw,
        "type_": _t,
        "refs": None if refs == [] else refs,
        "backrefs": None if backrefs == [] else backrefs,
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
