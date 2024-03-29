from . import *
from django import db
from django.views.decorators.http import condition
from uuid import UUID

EMBEDDED_SUBMIT_VALUE = "embedded"
LINK_SUBMIT_VALUE = "link"


@staff_member_required
@condition(last_modified_func=last_modified_document)
def view_document(request, uuid):
    uuid = UUID(uuid)
    try:
        doc = Document.objects.all().get(uuid=uuid)
    except Document.DoesNotExist:
        raise Http404("Document with this uuid does not exist.")
    backrefs = None
    try:
        with connections["bibliothecula"].cursor() as cursor:
            cursor.execute(
                f"SELECT referrer FROM backrefs_fts WHERE target = '{doc.uuid.hex}'"
            )
            backrefs = cursor.fetchall()
        print("backrefs: ", backrefs)
    except db.OperationalError:
        pass
    if backrefs is not None:
        objs = []
        for ref in backrefs:
            try:
                _doc = Document.objects.all().get(
                    binary_metadata__metadata__uuid=ref[0]
                )
                met = BinaryMetadata.objects.all().get(uuid=ref[0])
                objs.append((_doc, met))
            except Document.DoesNotExist:
                continue
        backrefs = objs
    context = {
        "title": doc.title,
        "document": doc,
        "EMBEDDED_SUBMIT_VALUE": EMBEDDED_SUBMIT_VALUE,
        "LINK_SUBMIT_VALUE": LINK_SUBMIT_VALUE,
        "add_link_form": DocumentAddLinkStorage(),
        "add_embedded_form": DocumentAddEmbeddedStorage(),
        "add_document_form": AddDocument(),
        "add_tag": DocumentSetTag(),
        "backrefs": None if backrefs == [] else backrefs,
    }
    return render(request, "document.html", context)


@staff_member_required
def add_document_tag(request, uuid, tag=None):
    uuid = UUID(uuid)
    try:
        doc = Document.objects.all().get(uuid=uuid)
    except Document.DoesNotExist:
        raise Http404("Document with this uuid does not exist.")
    if request.method == "POST":
        add_tag_form = DocumentSetTag(request.POST)
        if add_tag_form.is_valid():
            tag = add_tag_form.cleaned_data["tag"]
        else:
            messages.add_message(
                request,
                messages.INFO,
                f"Programming error? DocumentSetTag() form was not valid",
            )
    if tag is not None:
        try:
            u = uuid_lib.UUID(tag)
            print("U=", u)
            tag_m = get_object_or_404(TextMetadata, uuid=u)
            tag = tag_m.data
        except ValueError:
            tag_m, _ = TextMetadata.objects.get_or_create(name=TAG_NAME, data=tag)
        has, created = DocumentHasTextMetadata.objects.get_or_create(
            name=TAG_NAME, document=doc, metadata=tag_m
        )
        if not created:
            messages.add_message(
                request, messages.INFO, f'Tag "{tag}" already set, did nothing.'
            )
        else:
            doc.set_last_modified()
            messages.add_message(request, messages.SUCCESS, f'Added tag "{tag}"')
    return redirect(doc)


@staff_member_required
def remove_document_tag(request, uuid, tag=None):
    uuid = UUID(uuid)
    doc = get_object_or_404(Document, uuid=uuid)
    if request.method == "POST":
        tag_form = DocumentSetTag(request.POST)
        if tag_form.is_valid():
            tag = tag_form.cleaned_data["tag"]
        else:
            messages.add_message(
                request,
                messages.INFO,
                f"Programming error? DocumentSetTag() form was not valid",
            )
    if tag is not None:
        try:
            u = uuid_lib.UUID(tag)
            tag_m = get_object_or_404(TextMetadata, uuid=u)
            tag = tag_m.data
        except ValueError:
            tag_m = get_object_or_404(TextMetadata, name=TAG_NAME, data=tag)
        try:
            has = DocumentHasTextMetadata.objects.get(document=doc, metadata=tag_m)
            has.delete()
            doc.set_last_modified()
            messages.add_message(request, messages.SUCCESS, f'Removed tag "{tag}".')
        except Exception as exc:
            messages.add_message(
                request, messages.ERROR, f'Tag "{tag}" could not be removed: {exc}.'
            )
    return redirect(doc)


@staff_member_required
def add_document_storage(request, uuid):
    uuid = UUID(uuid)
    try:
        doc = Document.objects.all().get(uuid=uuid)
    except Document.DoesNotExist:
        raise Http404("Document with this uuid does not exist.")
    if request.method == "POST":
        if EMBEDDED_SUBMIT_VALUE in request.POST:
            add_embedded_form = DocumentAddEmbeddedStorage(request.POST, request.FILES)
            add_link_form = DocumentAddLinkStorage()
            if add_embedded_form.is_valid():
                _f = request.FILES["_file"]
                print("Added file", _f)
                bm = BinaryMetadata.from_file(_f)
                print("new met", bm)
                has, _ = DocumentHasBinaryMetadata.objects.get_or_create(
                    name=STORAGE_NAME, document=doc, metadata=bm
                )
                bm.save()
                has.save()
                doc.set_last_modified()
                messages.add_message(
                    request, messages.SUCCESS, f"Added file {_f} with uuid {bm.uuid}"
                )
                return redirect(doc)
        elif LINK_SUBMIT_VALUE in request.POST:
            add_embedded_form = DocumentAddEmbeddedStorage()
            add_link_form = DocumentAddLinkStorage(request.POST)
            if add_link_form.is_valid():
                _p = add_link_form.cleaned_data["path"]
                print("Added path", _p)
                bm = BinaryMetadata.objects.create(name=PATH_NAME, data=str.encode(_p))
                print("new met", bm)
                has, _ = DocumentHasBinaryMetadata.objects.get_or_create(
                    name=STORAGE_NAME, document=doc, metadata=bm
                )
                bm.save()
                has.save()
                doc.set_last_modified()
                messages.add_message(request, messages.SUCCESS, f"Added path {_p}")
                return redirect(doc)
        else:
            raise Http400(
                f"Programming error: form submit values ({[EMBEDDED_SUBMIT_VALUE, LINK_SUBMIT_VALUE]}) were not in request.POST headers."
            )
    return redirect(doc)


@staff_member_required
def add_document(request):
    if request.method == "POST":
        add_doc = AddDocument(request.POST)
        if add_doc.is_valid():
            title = add_doc.cleaned_data["title"]
            doc, created = Document.objects.get_or_create(title=title)
            if not created:
                messages.add_message(
                    request,
                    messages.INFO,
                    f"Document {doc.title} exists with uuid {doc.uuid}",
                )
            else:
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    f"Document {doc.title} added with uuid {doc.uuid}",
                )
            return redirect(doc)
    return redirect(reverse("view_collection"))


@staff_member_required
def set_document_thumbnail(request, uuid, metadata_uuid=None):
    uuid = UUID(uuid)
    if metadata_uuid:
        metadata_uuid = UUID(metadata_uuid)
    try:
        doc = Document.objects.all().get(uuid=uuid)
    except Document.DoesNotExist:
        raise Http404("Document with this uuid does not exist.")
    if metadata_uuid is not None:
        try:
            m = BinaryMetadata.objects.get(pk=metadata_uuid)
        except BinaryMetadata.DoesNotExist:
            raise Http404("Binary metadata with this uuid does not exist")
    created = doc.create_thumbnail(binary_metadata_uuid=metadata_uuid, force=True)
    if created:
        doc.set_last_modified()
        messages.add_message(request, messages.SUCCESS, f"Thumbnail created.")
    else:
        messages.add_message(
            request, messages.WARNING, f"Thumbnail could not be created."
        )
    return redirect(doc)


@staff_member_required
def add_document_metadata(request, uuid, name=None, data=None):
    uuid = UUID(uuid)
    try:
        doc = Document.objects.all().get(uuid=uuid)
    except Document.DoesNotExist:
        raise Http404("Document with this uuid does not exist.")
    if request.method == "POST":
        metadata_form = DocumentSetMetadata(request.POST)
        if metadata_form.is_valid():
            name = metadata_form.cleaned_data["name"]
            data = metadata_form.cleaned_data["data"]
        else:
            messages.add_message(
                request,
                messages.INFO,
                f"Programming error? DocumentSetMetadata() form was not valid",
            )
    if name is not None and data is not None:
        m, created = TextMetadata.objects.get_or_create(name=name, data=data)
        has, created = DocumentHasTextMetadata.objects.get_or_create(
            name=name, document=doc, metadata=m
        )
        if not created:
            messages.add_message(
                request,
                messages.INFO,
                f'Metadata "{name}:{data}" already set, did nothing.',
            )
        else:
            doc.set_last_modified()
            messages.add_message(
                request, messages.SUCCESS, f'Added metadata "{name}:{data}"'
            )
    return redirect(doc)


@staff_member_required
def remove_document_metadata(request, uuid, metadata_uuid=None):
    uuid = UUID(uuid)
    doc = get_object_or_404(Document, uuid=uuid)
    if metadata_uuid is not None:
        try:
            has = DocumentHasBinaryMetadata.objects.all().get(
                document=doc, metadata=metadata_uuid
            )
        except DocumentHasBinaryMetadata.DoesNotExist:
            has = get_object_or_404(
                DocumentHasTextMetadata, document=doc, metadata=metadata_uuid
            )
        m = has.metadata
        try:
            has.delete()
            doc.set_last_modified()
            messages.add_message(
                request, messages.SUCCESS, f'Removed metadata "{m.name}".'
            )
        except Exception as exc:
            messages.add_message(
                request,
                messages.ERROR,
                f'Metadata "{m.name}" could not be removed: {exc}.',
            )
    return redirect(doc)


@staff_member_required
def remove_document_storage(request, uuid, metadata_uuid=None):
    uuid = UUID(uuid)
    if metadata_uuid is not None:
        metadata_uuid = UUID(metadata_uuid)
    doc = get_object_or_404(Document, uuid=uuid)
    if metadata_uuid is not None:
        has = get_object_or_404(
            DocumentHasBinaryMetadata,
            name=STORAGE_NAME,
            document=doc,
            metadata=metadata_uuid,
        )
        m = has.metadata
        try:
            has.delete()
            doc.set_last_modified()
            messages.add_message(
                request, messages.SUCCESS, f'Removed storage "{m.name}".'
            )
        except Exception as exc:
            messages.add_message(
                request,
                messages.ERROR,
                f'Metadata "{m.name}" could not be removed: {exc}.',
            )
    return redirect(doc)


from django.core.cache import cache


@staff_member_required
def import_documents(request):
    if request.method == "POST":
        print(request.POST)
        form = ImportDocumentsForm(request.POST, request.FILES)
        print(form)
        files = request.FILES.getlist("files")
        print(files)
        if form.is_valid():
            print("got ", len(files), "files")
            data_urls = []
            for f in files:
                dbg(f.name)
                data_url = None
                try:
                    dbg(f.name.endswith(".pdf"))
                    dbg(f.name.endswith(".epub"))
                    if f.name.endswith(".pdf"):
                        data_url = generate_pdf_thumbnail(f.name, blob=f.read())
                    elif f.name.endswith(".epub"):
                        data_url = generate_epub_thumbnail(f.name, blob=f.read())
                    elif f.content_type.startswith("image"):
                        data_url = generate_image_thumbnail(f.name, blob=f.read())
                except Exception as exc:
                    messages.add_message(
                        request,
                        messages.WARNING,
                        f"Could not create thumbnail for {f.name}: {exc}",
                    )
                data_urls.append(data_url)
            request.session["import_thumbnails"] = json.dumps(data_urls)
            cache.set("import_files", files, timeout=15 * 60)
            return HttpResponseRedirect(reverse("import_documents_2"))
        else:
            messages.add_message(request, messages.ERROR, f"Form data is invalid.")
    else:
        form = ImportDocumentsForm()
    template_name = "import.html"
    context = {
        "title": "import files",
        "form": form,
        "add_document_form": AddDocument(),
    }
    template = loader.get_template("import.html")
    return HttpResponse(template.render(context, request))


@staff_member_required
def import_documents_2(request, files=None):
    print()
    print()
    print("import_documents_2")
    dbg(request)
    dbg(request.method)
    dbg("import_files" in cache)
    if "import_files" not in cache:
        messages.add_message(request, messages.ERROR, f"Files were not in cache?")
        return HttpResponseRedirect(reverse("import_documents"))
    files = cache.get("import_files")
    DocFormSet = formset_factory(NewDocument, extra=0)
    try:
        thumbnails = json.loads(request.session["import_thumbnails"])
    except Exception as exc:
        dbg(exc)
        thumbnails = [None for f in files]
    if request.method == "POST":
        print(request.POST)
        formset = DocFormSet(request.POST)
        if "submit" in request.POST:
            if formset.is_valid():
                print("is valid")
                new_docs = []
                errored = False
                try:
                    with transaction.atomic():
                        for index, form in enumerate(formset):
                            f = files[index]
                            title = form.cleaned_data["title"]
                            index_flag = form.cleaned_data["index"]
                            is_pdf = f.name.endswith(".pdf")
                            f.name = form.cleaned_data["filename"]
                            dbg(f)
                            dbg(form.cleaned_data.items())
                            print("transaction for index =", index, " title", title)
                            doc = Document.objects.create(title=title)
                            _type = None
                            for (field_name, field_value) in [
                                (TYPE_NAME, form.cleaned_data["_type"]),
                                (DATE_NAME, form.cleaned_data["date"]),
                                (AUTHOR_NAME, form.cleaned_data["author0"]),
                                (TAG_NAME, form.cleaned_data["tag0"]),
                            ]:
                                if field_value != "":
                                    try:
                                        u = uuid_lib.UUID(field_value)
                                        m = TextMetadata.objects.all().get(uuid=u)
                                    except ValueError:
                                        m, _ = TextMetadata.objects.get_or_create(
                                            name=field_name, data=field_value
                                        )
                                    has = DocumentHasTextMetadata.objects.create(
                                        name=field_name, document=doc, metadata=m
                                    )
                                    m.save()
                                    has.save()
                            thumbnail = thumbnails[index]
                            if thumbnail is not None:
                                # print("thumbnail for idx =", index," is ", thumbnail)
                                m = BinaryMetadata.objects.create(
                                    name=THUMBNAIL_NAME, data=str.encode(thumbnail)
                                )
                                has = DocumentHasBinaryMetadata.objects.create(
                                    name=THUMBNAIL_NAME, document=doc, metadata=m
                                )
                                m.save()
                                has.save()
                            text = None
                            if is_pdf and index_flag:
                                f.seek(0)
                                contents = f.read()
                                text = get_pdf_text(io.BytesIO(contents))
                            if text is not None:
                                m = BinaryMetadata.objects.create(
                                    name=FULL_TEXT_NAME, data=str.encode(text)
                                )
                                has = DocumentHasBinaryMetadata.objects.create(
                                    name=FULL_TEXT_NAME, document=doc, metadata=m
                                )
                                m.save()
                                has.save()
                            bm = BinaryMetadata.from_file(f)
                            has = DocumentHasBinaryMetadata.objects.create(
                                name=STORAGE_NAME, document=doc, metadata=bm
                            )
                            bm.save()
                            has.save()
                            doc.save()
                            new_docs.append(doc)
                except Exception as exc:
                    dbg(exc)
                    messages.add_message(request, messages.ERROR, f"Exception: {exc}.")
                    errored = True
                if not errored:
                    for doc in new_docs:
                        messages.add_message(
                            request,
                            messages.SUCCESS,
                            f'Added document "{doc.title}" with uuid {doc.uuid}',
                        )
                    if len(new_docs) == 1:
                        return redirect(new_docs[0])
                    return redirect(reverse("view_collection"))

        else:
            pass
            """
            for k in request.POST:
                if k.startswith("add-author-"):
                    k = int(k[len("add-author-"):])
                    dbg(formset[k])
                    formset[k].fields['author1'] = new_author_field()
                    print("add author for ", k)
                elif k.startswith("add-tag-"):
                    k = int(k[len("add-tag-"):])
                    dbg(formset[k])
                    formset[k].fields['tag1'] = new_tag_field()
                    print("add tag for ", k)
            """
    else:
        try:
            book_type_uuid = (
                TextMetadata.objects.all()
                .filter(name=TYPE_NAME, data="book")
                .first()
                .uuid
            )
        except:
            book_type_uuid = None
        initials = []
        for f in files:
            title = f.name
            author = ""
            date = ""
            _type = "book"
            _type_uuid = book_type_uuid
            if _type_uuid is not None:
                _type = ""
            try:
                date_m = year_pattern.search(f.name)
                date = date_m[1]
            except:
                pass
            try:
                author_title = author_title_pattern.search(f.name)
                author = author_title[1]
                title = author_title[2]
            except:
                pass
            try:
                author_title_medium = author_title_medium_pattern.search(f.name)
                author = author_title[1]
                title = author_title[2]
            except:
                pass
            try:
                if f.content_type.startswith("image"):
                    _type_uuid = (
                        TextMetadata.objects.all()
                        .filter(name=TYPE_NAME, data="artwork")
                        .first()
                        .uuid
                    )
                    _type = "artwork"
            except:
                pass
            print("\n\ninitials\\")
            dbg(f.name)
            initials.append(
                {
                    "original_filename": f.name,
                    "filename": f.name,
                    "index": _type
                    not in [
                        "artwork",
                    ],
                    "title": title,
                    "date": date,
                    "_type": str(_type_uuid) if _type_uuid is not None else "",
                    "author0": author,
                    "tag0": "",
                }
            )
        formset = DocFormSet(initial=initials)
        # return HttpResponseRedirect(reverse('import_documents'))
    # request.session['import_files'] = files
    context = {
        "title": f'import {len(files)} file{"" if len(files) == 1 else "s"}',
        "formset": formset,
        "thumbnails": thumbnails,
        "add_document_form": AddDocument(),
    }
    template = loader.get_template("import2.html")
    return HttpResponse(template.render(context, request))
