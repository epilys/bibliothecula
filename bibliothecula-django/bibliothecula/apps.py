from django.apps import AppConfig
import multiprocessing
import concurrent.futures
import atexit
from .background_tasks import TaskManager


class BibliotheculaAppConfig(AppConfig):
    MAX_WORKERS = 5
    name = "bibliothecula"
    verbose_name = "bibliothecula"

    def ready(self):
        self.tasks = concurrent.futures.ThreadPoolExecutor(max_workers=self.MAX_WORKERS)
        self.manager = multiprocessing.Manager()
        self.workers_ns = self.manager.Namespace()
        self.workers_ns.kill_workers = False
        self.workers_ns.active_tasks = 0
