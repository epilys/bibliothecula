import itertools
import os
import pathlib
import tempfile
import zipfile
from collections import deque
from xml.dom import minidom

from .utils import Textractor
from pdfminer.high_level import extract_text


def get_pdf_text(input_):
    try:
        text = extract_text(input_)
    except Exception as exc:
        print("Could not extract PDF text:", exc)
        if isinstance(input_, str):
            print(repr(input_))
        else:
            print("Binary pdf")
        return None
    return text


def get_epub_text(input_):
    IGNORE_FILES = set(
        [
            "titlepage.xhtml",
            "halftitlepage.xhtml",
            "imprint.xhtml",
            "colophon.xhtml",
            "copyright.xhtml",
            "uncopyright.xhtml",
        ]
    )
    ret = ""
    try:
        with tempfile.TemporaryDirectory() as tmpdir, zipfile.ZipFile(input_, "r") as z:
            os.chdir(tmpdir)
            cwd = pathlib.Path.cwd()
            container = z.open("META-INF/container.xml")
            container_root = minidom.parseString(container.read())

            # locate the rootfile
            elem = container_root.getElementsByTagName("rootfile")[0]
            rootfile_path = elem.getAttribute("full-path")

            # open the rootfile
            rootfile = z.open(rootfile_path)
            rootfile_root = minidom.parseString(rootfile.read())

            spine = rootfile_root.getElementsByTagName("spine")
            manifest_items = {
                item.getAttribute("id"): item
                for item in rootfile_root.getElementsByTagName("manifest")[
                    0
                ].getElementsByTagName("item")
            }
            stuff = []

            def get_attrs(n):
                href = None
                _id = None
                for i in range(0, n.attributes.length):
                    if n.attributes.item(i).name == "href":
                        href = n.attributes.item(i).value
                    elif n.attributes.item(i).name == "id":
                        _id = n.attributes.item(i).value
                return {"href": href, "id": _id}

            if spine and len(spine) > 0:
                spine = spine[0]
                stuff = [
                    item["id"]
                    for item in map(
                        get_attrs,
                        (
                            manifest_items[item.getAttribute("idref")]
                            for item in spine.getElementsByTagName("itemref")
                        ),
                    )
                    if item["id"].lower() not in IGNORE_FILES
                ]
            members = list(
                itertools.filterfalse(
                    lambda m: not m.filename.endswith("html")
                    and m.filename not in stuff,
                    z.infolist(),
                )
            )
            members = z.extractall(members=members)
            file_queue = deque([])
            parser = Textractor()
            for c in cwd.iterdir():
                file_queue.append(c)
            while len(file_queue) > 0:
                p = file_queue.pop()
                if p.is_dir():
                    for c in p.iterdir():
                        file_queue.append(c)
                else:
                    try:
                        if p.suffix.endswith("html"):
                            parser.feed(p.read_text(errors="strict"))
                            print("parser output is ", len(parser.output), "bytes")
                            ret += parser.output.strip()
                            parser.reset()
                    except Exception as exc:
                        print("Exception:", exc)
    except Exception as exc:
        print("Could not extract epub text:", exc)
        if isinstance(input_, str):
            print(repr(input_))
        else:
            print("Binary epub")
        return None
    return ret
