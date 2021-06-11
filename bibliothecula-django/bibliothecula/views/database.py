from . import *
from django.db import connections
from django.template.defaultfilters import filesizeformat
import inspect
from bibliothecula import sql_statements
from bibliothecula.sql_statements import SqlStatement, StatementKind

try:
    from .database_treemap import Treemap
except Exception as exc:
    Treemap = exc

def make_treemap(q, trees):
    dbg(Treemap)
    if isinstance(Treemap, BaseException):
        q.put(Treemap)
    else:
        parser = SVGParser()
        t = Treemap(trees)
        t.compute()
        parser.feed(t.as_svg())

        q.put(parser.output)
    q.put("Q")


def make_treemap_svg(request, fts5_size):
    import multiprocessing, queue

    labels = "embedded files", "linked files"
    no_linked_size = (
        DocumentHasBinaryMetadata.objects.all()
        .filter(name=STORAGE_NAME, metadata__name=PATH_NAME)
        .count()
    )
    no_total_storages = (
        DocumentHasBinaryMetadata.objects.all().filter(name=STORAGE_NAME).count()
    )
    if no_total_storages > 0:
        no_embedded_size = no_total_storages - no_linked_size
    else:
        no_linked_size = 0
        no_embedded_size = 0

    size_linked_size = sum(
        has.metadata.size()
        for has in DocumentHasBinaryMetadata.objects.all().filter(
            name=STORAGE_NAME, metadata__name=PATH_NAME
        )
    )
    size_total_storages = sum(
        has.metadata.size()
        for has in DocumentHasBinaryMetadata.objects.all().filter(name=STORAGE_NAME)
    )
    if size_total_storages > 0:
        size_embedded_size = size_total_storages - size_linked_size
    else:
        size_linked_size = 0
        size_embedded_size = 0

    dbg("Make treemap called!")
    no_tree = (no_embedded_size, no_linked_size)
    if fts5_size and fts5_size > 0:
        size_tree = (size_embedded_size, size_linked_size, fts5_size)
    else:
        size_tree = (size_embedded_size, size_linked_size)
    size_l = {size_tree[0]: "embedded files size", size_tree[1]: "linked files size"}
    if fts5_size and fts5_size > 0:
        size_l[fts5_size] = "fts5 size"

    size_sizes = {
        size_tree[0]: filesizeformat(size_embedded_size),
        size_tree[1]: filesizeformat(size_linked_size),
    }
    if fts5_size and fts5_size > 0:
        size_sizes[fts5_size] = filesizeformat(fts5_size)

    no_l = {no_tree[0]: "embedded files", no_tree[1]: "linked files"}
    no_sizes = {no_tree[0]: no_embedded_size, no_tree[1]: no_linked_size}

    trees = [
        ("no. of files", no_sizes, (no_tree,), no_l),
        ("total sizes", size_sizes, (size_tree,), size_l),
    ]

    q = multiprocessing.Queue()
    timeout = 10
    plot = multiprocessing.Process(None, make_treemap, args=(q, trees))
    plot.start()
    result = None
    try:
        result = q.get(True, timeout)
        if result != "Q":
            done = q.get(True, timeout)
            if done != "Q":
                messages.add_message(
                    request, messages.ERROR, f"Treemap process returned {done}"
                )
        else:
            messages.add_message(
                request, messages.ERROR, f"Treemap process returned nothing"
            )
    except queue.Empty:
        messages.add_message(
            request, messages.ERROR, f"Treemap process timed out ({timeout} seconds)"
        )
    except Exception as exc:
        messages.add_message(
            request, messages.ERROR, f"Treemap process returned exception: {exc}"
        )
    return result


class Trigger:
    def __init__(self, name, table, sql):
        self.name = name
        self.table = table
        self.sql = SqlStatement(name, sql)


@staff_member_required
# @cache_page(15*60)
def database_overview(request):
    fts5_table_exists = None
    fts5_indexed_documents_no = 0
    fts5_size = None
    triggers = []
    tables = []
    indexes = []
    with connections["bibliothecula"].cursor() as cursor:
        cursor.execute(f"SELECT name FROM sqlite_master WHERE name = '{FTS_NAME}'")
        try:
            fts5_table_exists = len(cursor.fetchone()) != 0
        except:
            fts5_table_exists = False
        if fts5_table_exists:
            cursor.execute(f"SELECT COUNT(uuid) FROM {FTS_NAME}")
            fts5_indexed_documents_no = cursor.fetchone()[0]
            cursor.execute(
                f"SELECT SUM(pgsize) FROM dbstat WHERE name = '{FTS_CONTENT_NAME}'"
            )
            fts5_size = cursor.fetchone()[0]
        cursor.execute(
            "SELECT * FROM sqlite_master WHERE type IN ('trigger', 'table', 'index')"
        )
        table_names = []
        index_names = []
        for r in cursor.fetchall():
            if r[0] == "trigger":
                new = Trigger(r[1], r[2], r[4])
                triggers.append(new)
            elif r[0] == "table":
                table_names.append(r[1])
            else:
                index_names.append(r[1])
        for tbl in table_names:
            cursor.execute(f"SELECT SUM(pgsize) FROM dbstat WHERE name = '{tbl}'")
            size = cursor.fetchone()[0]
            tables.append((tbl, size))
        for idx in index_names:
            cursor.execute(f"SELECT SUM(pgsize) FROM dbstat WHERE name = '{idx}'")
            size = cursor.fetchone()[0]
            indexes.append((idx, size))
        cursor.execute("SELECT SUM(pgsize) FROM dbstat")
        total_size = cursor.fetchone()[0]
        cursor.execute(
            "SELECT t.data, COUNT(has.document_uuid) AS count FROM TextMetadata AS t, DocumentHasTextMetadata AS has WHERE has.metadata_uuid = t.uuid AND t.name = 'tag' GROUP BY t.data ORDER BY count DESC LIMIT 5;"
        )
        top_tags = cursor.fetchall()

    tables.sort(key=lambda x: x[1] if x[1] else 0, reverse=True)
    indexes.sort(key=lambda x: x[1] if x[1] else 0, reverse=True)

    # Generate the figures in a lambda so that it is called inside the
    # template, and thus it can be cached as a template fragment
    svg = lambda: mark_safe(make_treemap_svg(request, fts5_size))

    statements = [
        getattr(sql_statements, item, None)
        for item in sorted(dir(sql_statements))
        if not item.startswith("__")
        and isinstance(getattr(sql_statements, item, None), SqlStatement)
    ]
    schema = [s for s in statements if s.kind == StatementKind.TABLE]
    d = {
        "INDEX": {
            "title": "Indices and searching",
            "statements": [],
        },
        "CLI": {
            "title": "Using the CLI",
            "statements": [],
        },
        "EXAMPLE": {
            "title": "Example queries",
            "statements": [],
        },
    }
    for s in statements:
        if s.kind == StatementKind.TABLE:
            continue
        if StatementKind.CLI in s.kind:
            d["CLI"]["statements"].append(s)
        elif StatementKind.INDEX in s.kind or StatementKind.VIEW in s.kind:
            d["INDEX"]["statements"].append(s)
        elif StatementKind.EXAMPLE in s.kind:
            d["EXAMPLE"]["statements"].append(s)
    context = {
        "total_size": total_size,
        "total_tags": TextMetadata.objects.all().filter(name=TAG_NAME).count(),
        "total_documents": Document.objects.all().count(),
        "top_tags": top_tags,
        "treemap": svg,
        "tables": tables,
        "tables_sum": sum(t[1] for t in tables if t[1]),
        "indexes": indexes,
        "indexes_sum": sum(t[1] for t in indexes if t[1]),
        "triggers": triggers,
        "fts5_table_exists": fts5_table_exists,
        "fts5_indexed_documents_no": fts5_indexed_documents_no,
        "schema": schema,
        "statements": [(k, d[k]) for k in ["CLI", "EXAMPLE", "INDEX"]],
        "add_document_form": AddDocument(),
    }
    template = loader.get_template("database.html")
    return HttpResponse(template.render(context, request))


@staff_member_required
def database_run_query(request, query):
    print(query)
    statements = {
        item: getattr(sql_statements, item, None)
        for item in sorted(dir(sql_statements))
        if not item.startswith("__")
        and isinstance(getattr(sql_statements, item, None), SqlStatement)
    }
    if query not in statements:
        raise Http404(f"Query named {query} not found.")
    if not statements[query].callable_:
        messages.add_message(
            request, messages.ERROR, f"{query} error: statement not meant to be run"
        )
        return HttpResponseRedirect(reverse("database_overview"))
    response = None
    errored = False
    with connections["bibliothecula"].cursor() as cursor:
        try:
            print("executing", str(statements[query]))
            cursor.execute(str(statements[query]))
            response = cursor.fetchone()
        except Exception as exc:
            errored = True
            messages.add_message(
                request, messages.ERROR, f"{query} error: database raised {exc}"
            )
    if response:
        messages.add_message(
            request, messages.INFO, f"{query}: Database replied with {response}"
        )
    elif not errored:
        messages.add_message(request, messages.INFO, f"{query}: Query ran successfuly.")
    return HttpResponseRedirect(reverse("database_overview"))


@staff_member_required
def database_drop_trigger(request, trigger):
    response = None
    errored = False
    with connections["bibliothecula"].cursor() as cursor:
        cursor.execute(
            "SELECT * FROM sqlite_master WHERE type = 'trigger' AND name = %s",
            [trigger],
        )
        response = cursor.fetchone()
        if response is None:
            raise Http404(f"Trigger named {trigger} not found.")
        try:
            cursor.execute(f"DROP TRIGGER IF EXISTS {trigger};")
            response = cursor.fetchone()
        except Exception as exc:
            errored = True
            messages.add_message(
                request, messages.ERROR, f"{trigger} error: database raised {exc}"
            )
    if response:
        messages.add_message(
            request, messages.INFO, f"{trigger}: Database replied with {response}"
        )
    elif not errored:
        messages.add_message(
            request, messages.INFO, f"{trigger}: Trigger deleted successfuly."
        )
    return HttpResponseRedirect(reverse("database_overview"))


@staff_member_required
def database_index(request, document_uuid=None):
    from ..background_tasks import TaskManager
    from django.apps import apps as django_apps

    def index_stats_fn():
        fts5_table_exists = None
        fts5_indexed_documents_no = 0
        fts5_size = ""
        integrity_check = None
        with connections["bibliothecula"].cursor() as cursor:
            cursor.execute(f"SELECT name FROM sqlite_master WHERE name = '{FTS_NAME}'")
            try:
                fts5_table_exists = len(cursor.fetchone()) != 0
            except:
                fts5_table_exists = False
            if fts5_table_exists:
                cursor.execute(f"SELECT COUNT(uuid) FROM {FTS_NAME}")
                fts5_indexed_documents_no = cursor.fetchone()[0]
                cursor.execute(
                    f"SELECT SUM(pgsize) FROM dbstat WHERE name = '{FTS_CONTENT_NAME}'"
                )
                fts5_size = filesizeformat(cursor.fetchone()[0])
                try:
                    cursor.execute(
                        f"INSERT INTO {FTS_NAME}({FTS_NAME}) VALUES('integrity-check')"
                    )
                except Exception as exc:
                    integrity_check = str(exc)
        return (
            {
                "no": fts5_indexed_documents_no,
                "size": fts5_size,
                "check": integrity_check,
            }
            if fts5_table_exists
            else None
        )

    def clear_index_stats_cache_fn():
        from django.core.cache import cache
        from django.core.cache.utils import make_template_fragment_key

        key = make_template_fragment_key("index_stats")
        cache.delete(key)

    config = django_apps.get_app_config("bibliothecula")
    active_tasks = config.workers_ns.active_tasks

    if request.method == "POST":
        errored = False
        if "start" in request.POST:
            force = "force" in request.GET
            forced = "forced " if force else ""
            try:
                tasks_no = TaskManager().index_document(
                    document_uuid=document_uuid, force=force
                )
            except Exception as exc:
                errored = True
                messages.add_message(
                    request,
                    messages.ERROR,
                    f"Error: could not schedule background tasks: {exc}",
                )
            if not errored:
                if document_uuid:
                    messages.add_message(
                        request,
                        messages.INFO,
                        f"Scheduled {forced}indexing task for uuid {document_uuid} with {tasks_no} tasks.",
                    )
                else:
                    messages.add_message(
                        request,
                        messages.INFO,
                        f"Scheduled {forced}indexing task for all documents with {tasks_no} tasks.",
                    )
        elif "stop" in request.POST:
            if active_tasks > 0:
                TaskManager().kill_all()
                clear_index_stats_cache_fn()
                messages.add_message(
                    request, messages.INFO, f"{active_tasks} tasks stopped."
                )
            else:
                messages.add_message(request, messages.INFO, f"No active tasks found.")
        elif "clear-index" in request.POST:
            with connections["bibliothecula"].cursor() as cursor:
                try:
                    cursor.execute(f"DELETE FROM {FTS_NAME}")
                except Exception as exc:
                    errored = True
                    messages.add_message(
                        request,
                        messages.ERROR,
                        f"Error: could not clear index: {exc}",
                    )
            if not errored:
                clear_index_stats_cache_fn()
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    f"Cleared index `{FTS_NAME}`.",
                )
        elif "build-index" in request.POST:
            with connections["bibliothecula"].cursor() as cursor:
                try:
                    cursor.execute(
                        f"""INSERT INTO {FTS_NAME}(uuid, title, authors, full_text)
                SELECT d.rowid AS rowid, d.title AS title, d.authors AS authors, d.full_text AS full_text
                FROM document_title_authors_text_view AS d"""
                    )
                    cursor.execute(
                        f"SELECT SUM(pgsize) FROM dbstat WHERE name = '{FTS_CONTENT_NAME}'"
                    )
                    size = filesizeformat(cursor.fetchone()[0])
                except Exception as exc:
                    errored = True
                    messages.add_message(
                        request,
                        messages.ERROR,
                        f"Error: could not build index: {exc}",
                    )
            if not errored:
                clear_index_stats_cache_fn()
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    f"Built index `{FTS_NAME}`: Size: {size}.",
                )

        elif "optimize-index" in request.POST:
            with connections["bibliothecula"].cursor() as cursor:
                try:
                    cursor.execute(
                        f"SELECT SUM(pgsize) FROM dbstat WHERE name = '{FTS_CONTENT_NAME}'"
                    )
                    size_before = filesizeformat(cursor.fetchone()[0])
                    cursor.execute(
                        f"INSERT INTO {FTS_NAME}({FTS_NAME}) VALUES('optimize')"
                    )
                    cursor.execute(
                        f"SELECT SUM(pgsize) FROM dbstat WHERE name = '{FTS_CONTENT_NAME}'"
                    )
                    size_after = filesizeformat(cursor.fetchone()[0])
                except Exception as exc:
                    errored = True
                    messages.add_message(
                        request,
                        messages.ERROR,
                        f"Error: could not optimize index: {exc}",
                    )
            if not errored:
                clear_index_stats_cache_fn()
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    f"Optimized index `{FTS_NAME}`: Size before: {size_before}, size after: {size_after}.",
                )
    active_tasks = config.workers_ns.active_tasks
    context = {
        "active_tasks": active_tasks,
        "index_stats_fn": index_stats_fn,
    }
    template = loader.get_template("database_index.html")
    return HttpResponse(template.render(context, request))
