from . import *
from django import db
from django.views.decorators.http import condition


def sql_list(iterable):
    it = iter(iterable)
    yield "'"
    yield next(it)
    yield "'"
    for x in it:
        yield ", '"
        yield x
        yield "'"


@staff_member_required
def view_notes(request, uuid):
    try:
        doc = Document.objects.all().get(uuid=uuid)
    except Document.DoesNotExist:
        raise Http404("Document with this uuid does not exist.")
    doc_backrefs = []
    file_backrefs = []
    file_refs = []
    files = [f.metadata.uuid.hex for f in doc.files()]
    try:
        with connections["bibliothecula"].cursor() as cursor:
            cursor.execute(
                f"SELECT referrer FROM backrefs_fts WHERE target = '{doc.uuid.hex}'"
            )
            doc_backrefs = cursor.fetchall()
            cursor.execute(
                f"""SELECT referrer, target FROM backrefs_fts WHERE target IN ({"".join(sql_list(files))})"""
            )
            file_backrefs = cursor.fetchall()
            cursor.execute(
                f"""SELECT  target, referrer FROM backrefs_fts WHERE referrer IN ({"".join(sql_list(files))})"""
            )
            file_refs = cursor.fetchall()
    except Exception as exc:
        print(exc)
    # except db.OperationalError:
    #    pass
    file_refs = {x[0]: x for x in file_refs}
    file_backrefs = {x[0]: x for x in file_backrefs if x[1] not in file_refs}
    print("doc_backrefs: ", doc_backrefs)
    print("file_refs: ", file_refs)
    print("file_backrefs: ", file_backrefs)
    if len(doc_backrefs) > 0:
        objs = []
        for ref in doc_backrefs:
            try:
                _doc = Document.objects.all().get(
                    binary_metadata__metadata__uuid=ref[0]
                )
                met = BinaryMetadata.objects.all().get(uuid=ref[0])
                objs.append((_doc, met))
                continue
            except Document.DoesNotExist:
                pass
            try:
                met = BinaryMetadata.objects.all().get(uuid=ref[0])
                _doc = met.documents.all().first()
                objs.append((_doc, met))
            except BinaryMetadata.DoesNotExist:
                pass
        doc_backrefs = objs
    context = {
        "title": doc.title,
        "document": doc,
        "EMBEDDED_SUBMIT_VALUE": EMBEDDED_SUBMIT_VALUE,
        "LINK_SUBMIT_VALUE": LINK_SUBMIT_VALUE,
        "add_link_form": DocumentAddLinkStorage(),
        "add_embedded_form": DocumentAddEmbeddedStorage(),
        "add_notes_form": AddDocument(),
        "add_tag": DocumentSetTag(),
        "doc_backrefs": None if doc_backrefs == [] else doc_backrefs,
        "file_backrefs": None if file_backrefs == {} else file_backrefs.values(),
        "file_refs": None if file_refs == {} else file_refs.values(),
    }
    return render(request, "notes.html", context)
