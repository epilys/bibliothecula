from django.http import HttpResponse, Http404, HttpResponseRedirect
from django.urls import reverse
from django.shortcuts import render, redirect, get_object_or_404
from django.template import loader
from django.db import transaction
from django.db.models.functions import Lower
from django.db.models import Count
from django.db.models.expressions import RawSQL
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.views.decorators.cache import cache_page
from django.forms import formset_factory
from ..models import *
from ..forms import *
from ..thumbnails import generate_pdf_thumbnail, generate_epub_thumbnail
from ..text_extract import get_pdf_text, get_epub_text
import re
import io
import uuid as uuid_lib
import urllib
import json
import uuid

# from django.contrib.auth.decorators import login_required

import inspect, ast

year_pattern = re.compile("[^\d]*([12]\d\d\d)[^\d]*")
author_title_pattern = re.compile("([^-]+)\s*-\s*([^.(]+).*$")
author_title_medium_pattern = re.compile("([^,]+)\s*,\s*([^,.(]+)\s*,\s*([^,.(]+).*$")


def dbg(result):
    """
    Recover the expression giving the result, and then
    print a helpful debug statement showing this
    """
    frame = inspect.stack()[1]
    expr = extract_dbg(frame.code_context[0])
    filename = frame.filename.split("/")[-1]
    print(f"[{filename}: {frame.lineno}] {expr} = {result}")
    return result


def extract_dbg(code_fragment):
    # from a line of source text, try and find the expression
    # given to a call to dbg
    expression_options = code_fragment.split("dbg(")
    if len(expression_options) != 2:
        # if there are either multiple dbg statements
        # or I can't find the dbg line, bail
        return "???"
    # get the part to the right of dbg(
    expr_candidate = expression_options[1]
    while expr_candidate:
        try:
            ast.parse(expr_candidate)
            return expr_candidate
        except SyntaxError:
            expr_candidate = expr_candidate[:-1]
    # didn't find anything, also give up
    return "???"


@staff_member_required
def view_collection(request):
    # print("\n\n")
    snippets = None
    request_object = request.GET
    get_request = request_object.copy()
    should_redirect_flag = request.method == "POST"
    document_types = request.session.get("document_types", [])
    document_type_null = request.session.get("document_type_null", False)
    combination = request.session.get("combination", "OR")
    layout_preference = request.session.get("layout", "grid")
    sort_field = request.session.get("sort_field", "last_modified")
    sort_ascending = request.session.get("sort_ascending", False)
    if combination not in ["AND", "OR"]:
        combination = "OR"
    if combination == "OR" and "combination" in get_request:
        get_request.pop("combination")
        should_redirect_flag = True

    query_string = None
    full_text_flag = False
    combination_form = CombinationForm({"combination": combination})
    layout_form = CollectionLayout({"layout": layout_preference})
    type_form = CollectionType(
        initial={"_type": document_types, "null": document_type_null}
    )
    sort_form = CollectionSort({"field": sort_field, "ascending": sort_ascending})
    search_form = DocumentMetadataSearch(request.GET)
    full_text_search_form = DocumentFullTextSearch(request.GET)
    if request.method == "POST":
        if "change-layout" in request.POST:
            layout_form = CollectionLayout(request.POST)
            if layout_form.is_valid():
                layout_preference = layout_form.cleaned_data["layout"]
        elif "change-sort" in request.POST:
            sort_form = CollectionSort(request.POST)
            if sort_form.is_valid():
                sort_field = sort_form.cleaned_data["field"]
                sort_ascending = sort_form.cleaned_data["ascending"]
        elif "change-type" in request.POST:
            type_form = CollectionType(request.POST)
            if type_form.is_valid():
                document_types = type_form.cleaned_data["_type"]
                document_type_null = type_form.cleaned_data["null"]
        elif "change-combination" in request.POST:
            combination_form = CombinationForm(request.POST)
            if combination_form.is_valid():
                combination = combination_form.cleaned_data["combination"]
        elif "full-text-query" in request.POST:
            full_text_search_form = DocumentFullTextSearch(request.POST)
            full_text_flag = True
        elif "reset-tags" in request.POST:
            get_request.setlist("tags", [])
        else:
            search_form = DocumentMetadataSearch(request.POST)
    else:
        full_text_flag = "full_text_query" in get_request
    if sort_field not in ["title", "created", "last_modified"]:
        sort_field = "last_modified"
    request.session["combination"] = combination
    request.session["document_types"] = document_types
    request.session["document_type_null"] = document_type_null
    request.session["layout"] = layout_preference
    request.session["sort_field"] = sort_field
    request.session["sort_ascending"] = sort_ascending
    # print("is valid", search_form.is_valid())

    if full_text_flag and full_text_search_form.is_valid():
        query_string = full_text_search_form.cleaned_data["full_text_query"]
        if query_string is not None and len(query_string) == 0:
            while "full_text_query" in get_request:
                # print("pop")
                # should_redirect_flag = True
                get_request.pop("full_text_query")
        if query_string is not None and len(query_string) != 0:
            get_request["full_text_query"] = query_string
    elif search_form.is_valid():
        # print("cleaned_data = ", list(search_form.cleaned_data))
        query_string = search_form.cleaned_data["query"]
        # print("query string = ", query_string)
        if query_string is not None and len(query_string) == 0:
            while "query" in get_request:
                # print("pop")
                should_redirect_flag = True
                get_request.pop("query")
        if query_string is not None and len(query_string) != 0:
            get_request["query"] = query_string
    tags = get_request.getlist("tags")
    # print("tags = ", tags)
    submitted_tags_len = len(tags)
    all_tags = TextMetadata.objects.all().filter(name="tag").order_by("data")
    tags = [t for t in tags if t in [t.data for t in all_tags]]
    # print("tags after = ", tags)
    get_request.setlist("tags", tags)
    should_redirect_flag |= submitted_tags_len != len(tags)

    for t in all_tags:
        t.active = t.data in tags
        query_dict = get_request.copy()
        if t.active:
            new_list = [tag for tag in tags if t.data != tag]
        else:
            new_list = tags.copy()
            new_list.append(t.data)
        query_dict.setlist("tags", new_list)
        t.url = query_dict.urlencode()
    # print("query_s=",query_string)
    if full_text_flag and query_string is not None and len(query_string) != 0:
        # results = Document.objects.raw('select uuid from document_title_authors_text_view_fts(%s);', params=["journal woodcut"])
        escaped = query_string.replace('"', '""')
        collection = Document.objects.all().filter(
            uuid__in=RawSQL(
                f"select uuid from {FTS_NAME}('\"{escaped}\"')",
                (),
            )
        )
        try:
            with connections["bibliothecula"].cursor() as cursor:
                cursor.execute(
                    f"select uuid, snippet({FTS_NAME},-1,'<b>','</b>','\u200a[…]\u200a',36) as snippet from {FTS_NAME}('\"{escaped}\"')"
                )
                snippets = {uuid.UUID(i[0]): i[1] for i in cursor.fetchall()}
        except Exception as exc:
            print("snippets exc:", exc)
    else:
        collection = Document.objects.all()
    if tags:
        # print("tag len is ", len(tags))
        if combination == "AND":
            tag_objects = all_tags.filter(data__in=tags)
            for tag_obj in tag_objects:
                collection = collection.filter(text_metadata__metadata__in=[tag_obj])
        else:
            metadata_objects = all_tags.filter(data__in=tags).values_list(
                "documents__document", flat=True
            )
            # print("len is ", len(metadata_objects))
            collection = collection.filter(uuid__in=metadata_objects)
        # print("col len is ", len(collection))
    if query_string and not full_text_flag:
        collection = collection.filter(title__icontains=query_string)
    if layout_preference == "grid":
        template = loader.get_template("collection_grid.html")
    elif layout_preference == "table":
        template = loader.get_template("collection_table.html")
    if document_type_null:
        collection = collection.exclude(text_metadata__metadata__name=TYPE_NAME)
    elif len(document_types) > 0:
        collection = collection.filter(text_metadata__metadata__uuid__in=document_types)

    collection = collection.order_by(
        ("-" + sort_field) if not sort_ascending else sort_field
    )
    result_tags = set(
        TextMetadata.objects.all().filter(
            name=TAG_NAME, documents__document__in=collection
        )
    )
    context = {
        "all_tags": [t for t in all_tags if t.active or t in result_tags],
        "has_selected_tags": len(tags) > 0,
        "collection": collection,
        "snippets": snippets,
        "search_form": search_form,
        "full_text_search_form": full_text_search_form,
        "layout_form": layout_form,
        "sort_form": sort_form,
        "type_form": type_form,
        "combination_form": combination_form,
        "add_document_form": AddDocument(),
        "total_documents": Document.objects.all().count(),
    }
    if "csrfmiddlewaretoken" in get_request:
        get_request.pop("csrfmiddlewaretoken")
    if request.method == "POST":
        request.POST = get_request.copy()
    request.GET = get_request
    # print("request.GET=", request.GET)
    # print("request.POST=", request.POST)
    if should_redirect_flag:
        # print("redirecting with parameters: ", dict(get_request))
        url_suffix = get_request.urlencode()
        # print("url_suffix = ", url_suffix)
        view_url = reverse("view_collection")
        # print("view_url = ", view_url)
        if len(url_suffix) == 0:
            redirect_url = view_url
        else:
            redirect_url = view_url + "?" + url_suffix
        # print("redirect = ", redirect_url)
        return HttpResponseRedirect(redirect_url, template.render(context, request))
    else:
        return HttpResponse(template.render(context, request))


from html.parser import HTMLParser

"""Remove namespaces and stuff that w3's html validator doesn't like."""


class SVGParser(HTMLParser):
    output = ""
    ignore = 0
    ignore_path = 0

    def handle_starttag(self, tag, attrs):
        if tag == "path" and "d" not in [a[0] for a in attrs]:
            self.ignore_path += 1
            return
        if (
            tag == "metadata"
            or tag.startswith("rdf")
            or tag.startswith("cc")
            or tag.startswith("dc")
        ):
            self.ignore += 1
            return
        if len(attrs) == 0:
            self.output += f"<{tag}>"
        else:
            self.output += f"<{tag}"
        for (x, y) in attrs:
            if x.startswith("xmlns"):
                continue
            self.output += f' {x}="{y}"'
        if len(attrs) != 0:
            self.output += ">"

    def handle_endtag(self, tag):
        if (
            tag == "metadata"
            or tag.startswith("rdf")
            or tag.startswith("cc")
            or tag.startswith("dc")
        ):
            self.ignore -= 1
            return
        if tag == "path" and self.ignore_path > 0:
            self.ignore_path -= 1
            return
        self.output += f"</{tag}>"

    def handle_data(self, data):
        if self.ignore == 0:
            self.output += data


from .database import *
from .tags import *
from .documents import *
