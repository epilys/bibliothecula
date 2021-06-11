from django.db import connections, close_old_connections
from django.db.utils import DEFAULT_DB_ALIAS, load_backend
from django.apps import apps as django_apps
from django.core.paginator import Paginator

import multiprocessing
from importlib import import_module
from django.conf import settings


class TaskManager:
    def __init__(self):
        pass

    def index_document(self, document_uuid=None, force=False):
        def index_fn(workers_ns, documents, total, force=False):
            ctr = 0
            for doc in documents:
                if workers_ns.kill_workers:
                    break
                retries = 0
                while retries < 5:
                    try:
                        ret = doc.index_text(force=force)
                        print("finished ", doc, " with", ret)
                        break
                    except OperationalError as exc:
                        print("locked: ", exc, "?", retries)
                        # Database might be locked from other task workers
                        retries += 1
                    except Exception as exc:
                        print(f"exc: {exc} for doc {doc}")
                        break
                ctr += 1
                # print(f"Done {ctr}/{total}")
            close_old_connections()
            workers_ns.active_tasks -= 1
            return 0

        config = django_apps.get_app_config("bibliothecula")
        active_tasks = config.workers_ns.active_tasks
        if active_tasks > 0:
            raise RuntimeError(f"{active_tasks} tasks are already running.")
        config.workers_ns.kill_workers = False
        from .models import Document

        all_docs = Document.objects.all()
        if document_uuid is None:
            docs_per_worker, rem_docs = divmod(all_docs.count(), config.MAX_WORKERS)
            paginator = Paginator(all_docs, docs_per_worker, orphans=rem_docs)
            print("Will schedule", paginator.num_pages, "tasks.")
            for idx in range(0, paginator.num_pages):
                page = paginator.get_page(idx)
                config.tasks.submit(
                    index_fn, config.workers_ns, page, docs_per_worker, force
                )
                config.workers_ns.active_tasks += 1
            return paginator.num_pages
        else:
            doc = all_docs.get(uuid=document_uuid)
            # Prev line raised exception if it doesn't exist
            config.tasks.submit(
                index_fn,
                config.workers_ns,
                all_docs.filter(uuid=document_uuid),
                1,
                force,
            )
            config.workers_ns.active_tasks += 1
            return 1

    def kill_all(self):
        config = django_apps.get_app_config("bibliothecula")
        config.workers_ns.kill_workers = True
