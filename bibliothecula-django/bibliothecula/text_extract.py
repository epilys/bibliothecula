import itertools
import os
import pathlib
import re
import tempfile
import zipfile
from collections import deque
from html.parser import HTMLParser
from xml.dom import minidom

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
    IGNORE_FILES = set(['titlepage.xhtml', 'halftitlepage.xhtml', 'imprint.xhtml', 'colophon.xhtml', 'copyright.xhtml', 'uncopyright.xhtml'])
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
            manifest_items = {item.getAttribute("id"): item for item in rootfile_root.getElementsByTagName("manifest")[0].getElementsByTagName("item")}
            stuff = []
            def get_attrs(n):
                href = None
                _id = None
                for i in range(0, n.attributes.length):
                    if n.attributes.item(i).name == "href":
                        href = n.attributes.item(i).value
                    elif n.attributes.item(i).name == "id":
                        _id = n.attributes.item(i).value
                return {
                        "href" : href,
                        "id": _id
                        }
            if spine and len(spine) > 0:
                spine = spine[0]
                stuff = [item["id"] for item in map(get_attrs, (manifest_items[item.getAttribute("idref")] for item in spine.getElementsByTagName("itemref"))) if item["id"].lower() not in IGNORE_FILES]
            members = list(
                itertools.filterfalse(
                    lambda m: not m.filename.endswith("html") and m.filename not in stuff, z.infolist()
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


"""Extract plain text from HTML. """


class Textractor(HTMLParser):
    whitespace = r"\s{2,}"
    output = ""
    ignore = 2
    in_header= False

    def reset(self):
        self.output = ""
        self.ignore = 2
        self.in_header = False
        super().reset()

    def handle_starttag(self, tag, attrs):
        attrs = {a[0]: a[1] for a in attrs}
        if tag == "body" and ("bodymatter" in attrs["epub:type"] if "epub:type" in attrs else True):
            self.ignore -= 1
        if tag in ["h1", "h2", "h3", "h4", "h5", "h6"] and "epub:type" in attrs and "ordinal" in attrs["epub:type"]:
            self.ignore += 1
            self.in_header=True

    def handle_endtag(self, tag):
        if tag == "head":
            self.ignore -= 1
        elif tag in ["h1", "h2", "h3", "h4", "h5", "h6"] and self.in_header:
            self.ignore -= 1
            self.in_header = False

    def handle_data(self, data):
        if self.ignore == 0:
            self.output += re.sub(self.whitespace, " ", data).replace("\ufeff", "")
