"""bibliothecula URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.conf import settings
from django.urls import path, re_path
from django.conf.urls.static import static

from . import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.view_collection, name="view_collection"),
    path("database/", views.database_overview, name="database_overview"),
    path("database/index/", views.database_index, name="database_index"),
    path(
        "database/index/<document_uuid>",
        views.database_index,
        name="database_index_uuid",
    ),
    path("database/run/<query>/", views.database_run_query, name="database_run_query"),
    path(
        "database/drop/<trigger>/",
        views.database_drop_trigger,
        name="database_drop_trigger",
    ),
    path("add/document/", views.add_document, name="add_document"),
    path("document/<uuid>/", views.view_document, name="view_document"),
    path(
        "document/<uuid>/add-storage/",
        views.add_document_storage,
        name="add_document_storage",
    ),
    path(
        "document/<uuid>/remove-storage/<metadata_uuid>",
        views.remove_document_storage,
        name="remove_document_storage",
    ),
    path(
        "document/<uuid>/add-tag/<tag>", views.add_document_tag, name="add_document_tag"
    ),
    path(
        "document/<uuid>/add-metadata/<name>/<data>",
        views.add_document_metadata,
        name="add_document_metadata",
    ),
    path(
        "document/<uuid>/remove-metadata/<metadata_uuid>",
        views.remove_document_metadata,
        name="remove_document_metadata",
    ),
    path(
        "document/<uuid>/remove-tag/<tag>",
        views.remove_document_tag,
        name="remove_document_tag",
    ),
    path(
        "document/<uuid>/view/<metadata_uuid>",
        views.view_document_storage,
        name="view_document_storage",
    ),
    path(
        "document/<uuid>/edit/",
        views.edit_plain_text_document,
        name="edit_plain_text_document",
    ),
    path(
        "document/<uuid>/set-thumbnail/",
        views.set_document_thumbnail,
        name="set_document_thumbnail",
    ),
    path(
        "document/<uuid>/set-thumbnail/<metadata_uuid>/",
        views.set_document_thumbnail,
        name="set_document_thumbnail_2",
    ),
    path("tag/", views.view_tag, name="view_tag"),
    path("tag/<tag>/", views.view_tag, name="view_tag"),
    path("tag_d3/", views.view_tag_d3, name="view_tag_d3"),
    path("tag_d3/<tag>/", views.view_tag_d3, name="view_tag_d3"),
    path("import/", views.import_documents, name="import_documents"),
    path("import/edit", views.import_documents_2, name="import_documents_2"),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
