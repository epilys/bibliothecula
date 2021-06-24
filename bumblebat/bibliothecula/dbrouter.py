class MainRouter:
    DB_NAME = "default"
    route_app_labels = {"auth", "contenttypes"}

    """
    A router to control all database operations on models in the
    auth and contenttypes applications.
    """

    def db_for_read(self, model, **hints):
        if model._meta.app_label in self.route_app_labels:
            return self.DB_NAME
        return None

    def db_for_write(self, model, **hints):
        """
        Attempts to write auth and contenttypes models go to self.DB_NAME
        """
        if model._meta.app_label in self.route_app_labels:
            return self.DB_NAME
        return None

    def allow_relation(self, obj1, obj2, **hints):
        """
        Allow relations if a model in the auth or contenttypes apps is
        involved.
        """
        if (
            obj1._meta.app_label in self.route_app_labels
            or obj2._meta.app_label in self.route_app_labels
        ):
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Make sure the auth and contenttypes apps only appear in the
        'self.DB_NAME' database.
        """
        if app_label in self.route_app_labels:
            return db == self.DB_NAME
        return None


class BibliotheculaRouter:
    DB_NAME = "bibliothecula"
    route_app_labels = {"bibliothecula"}

    def db_for_read(self, model, **hints):
        if model._meta.app_label in self.route_app_labels:
            return self.DB_NAME
        return None

    def db_for_write(self, model, **hints):
        """
        Attempts to write auth and contenttypes models go to auth_db.
        """
        if model._meta.app_label in self.route_app_labels:
            return self.DB_NAME
        return None

    def allow_relation(self, obj1, obj2, **hints):
        """
        Allow relations if a model in the auth or contenttypes apps is
        involved.
        """
        if (
            obj1._meta.app_label in self.route_app_labels
            or obj2._meta.app_label in self.route_app_labels
        ):
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Make sure the auth and contenttypes apps only appear in the
        'DB_NAME' database.
        """
        if app_label in self.route_app_labels:
            return db == self.DB_NAME
        return None
