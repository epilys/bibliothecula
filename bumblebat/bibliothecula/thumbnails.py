import os
import re
from io import BytesIO
import sys
from xml.dom import minidom
from urllib.request import urlopen
import zipfile
from wand.image import Image
import subprocess


def open_blob_from_path(path):
    if os.path.isfile(path):
        file_url = open(path, "rb")
    else:
        file_url = urlopen(path)
    return file_url.read()


def generate_image_thumbnail(path, blob=None):
    if blob is not None and path is not None and len(path) > 0:
        format_ = path
    else:
        blob = open_blob_from_path(path)
        format_ = None

    with Image(format=format_, blob=blob) as i:
        with i.convert("webp") as page:
            width = page.width
            height = page.height
            ratio = 100.0 / (width * 1.0)
            new_height = int(ratio * height)
            page.thumbnail(width=100, height=new_height)
            return page.data_url()


def generate_pdf_thumbnail(path, blob=None):
    if blob is None:
        with subprocess.Popen(
            [
                "gs",
                "-sDEVICE=jpeg",
                "-r72x72",
                "-o%stdout%",
                "-q",
                "-dFirstPage=1",
                "-dLastPage=1",
                "-dUseCropBox",
                "-dJPEQ=30",
                path,
            ],
            stdout=subprocess.PIPE,
        ) as gs:
            try:
                outs, errs = gs.communicate(timeout=60)
            except subprocess.TimeoutExpired:
                print("expired")
                gs.kill()
                outs, errs = gs.communicate()
                print(outs, errs)
                return None
            with Image(format="jpg:file.jpg", blob=outs) as i:
                with i.convert("webp") as first_page:
                    width = first_page.width
                    height = first_page.height
                    ratio = 100.0 / (width * 1.0)
                    new_height = int(ratio * height)
                    # print("webp dims before:", first_page.width, " x ", first_page.height)
                    first_page.thumbnail(width=100, height=new_height)
                    # print("webp dims after:", first_page.width, " x ", first_page.height)
                    return first_page.data_url()
    else:
        with subprocess.Popen(
            [
                "gs",
                "-sDEVICE=jpeg",
                "-r72x72",
                "-o%stdout%",
                "-q",
                "-dFirstPage=1",
                "-dLastPage=1",
                "-dUseCropBox",
                "-dJPEQ=30",
                "%stdin%",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        ) as gs:
            # gs.stdin.write(blob)
            try:
                outs, errs = gs.communicate(input=blob, timeout=120)
            except subprocess.TimeoutExpired:
                print("expired")
                gs.kill()
                outs, errs = gs.communicate()
                print(outs, errs)
                return None
            with Image(format="jpg:file.jpg", blob=outs) as i:
                with i.convert("webp") as first_page:
                    width = first_page.width
                    height = first_page.height
                    ratio = 100.0 / (width * 1.0)
                    new_height = int(ratio * height)
                    # print("webp dims before:", first_page.width, " x ", first_page.height)
                    first_page.thumbnail(width=100, height=new_height)
                    # print("webp dims after:", first_page.width, " x ", first_page.height)
                    return first_page.data_url()


def generate_pdf_thumbnail_imagemagick(path, blob=None):
    def first_page_fn(first_page):
        # print("dims before:", first_page.width, " x ", first_page.height)
        with first_page.convert("webp") as first_page:
            width = first_page.width
            height = first_page.height
            ratio = 100.0 / (width * 1.0)
            new_height = int(ratio * height)
            # print("webp dims before:", first_page.width, " x ", first_page.height)
            first_page.thumbnail(width=100, height=new_height)
            # print("webp dims after:", first_page.width, " x ", first_page.height)
            return first_page.data_url()
        return None

    if blob is not None:
        if path is None or path == "":
            path = "pdf:file.pdf"
        with Image(format=path + "[0]", blob=blob) as first_page:
            return first_page_fn(first_page)
    else:
        with Image(filename="pdf:" + path + "[0]") as first_page:
            return first_page_fn(first_page)
    return None


# by https://github.com/marianosimone/epub-thumbnailer
def generate_epub_thumbnail(input_file, blob=None):
    # An epub is just a zip
    if blob is None:
        blob = open_blob_from_path(input_file)
    epub = zipfile.ZipFile(BytesIO(blob), "r")
    extraction_strategies = [
        get_cover_from_manifest,
        get_cover_by_guide,
        get_cover_by_filename,
    ]
    for strategy in extraction_strategies:
        try:
            cover_path = strategy(epub)
            cover = extract_cover(epub, cover_path)
            if cover is not None:
                return cover.data_url()
        except Exception as ex:
            print("Error getting cover using %s: " % strategy.__name__, ex)
    return None


img_ext_regex = re.compile(r"^.*\.(jpg|jpeg|png)$", flags=re.IGNORECASE)
cover_regex = re.compile(r".*cover.*\.(jpg|jpeg|png)", flags=re.IGNORECASE)


def get_cover_from_manifest(epub):
    print("epub is ", epub)

    # open the main container
    container = epub.open("META-INF/container.xml")
    container_root = minidom.parseString(container.read())

    # locate the rootfile
    elem = container_root.getElementsByTagName("rootfile")[0]
    rootfile_path = elem.getAttribute("full-path")

    # open the rootfile
    rootfile = epub.open(rootfile_path)
    rootfile_root = minidom.parseString(rootfile.read())

    # find possible cover in meta
    cover_id = None
    for meta in rootfile_root.getElementsByTagName("meta"):
        if meta.getAttribute("name") == "cover":
            cover_id = meta.getAttribute("content")
            break

    # find the manifest element
    manifest = rootfile_root.getElementsByTagName("manifest")[0]
    for item in manifest.getElementsByTagName("item"):
        item_id = item.getAttribute("id")
        item_properties = item.getAttribute("properties")
        item_href = item.getAttribute("href")
        item_href_is_image = img_ext_regex.match(item_href.lower())
        item_id_might_be_cover = item_id == cover_id or (
            "cover" in item_id and item_href_is_image
        )
        item_properties_might_be_cover = item_properties == cover_id or (
            "cover" in item_properties and item_href_is_image
        )
        if item_id_might_be_cover or item_properties_might_be_cover:
            return os.path.join(os.path.dirname(rootfile_path), item_href)

    return None


def get_cover_by_guide(epub):

    # open the main container
    container = epub.open("META-INF/container.xml")
    container_root = minidom.parseString(container.read())

    # locate the rootfile
    elem = container_root.getElementsByTagName("rootfile")[0]
    rootfile_path = elem.getAttribute("full-path")

    # open the rootfile
    rootfile = epub.open(rootfile_path)
    rootfile_root = minidom.parseString(rootfile.read())
    for ref in rootfile_root.getElementsByTagName("reference"):
        if ref.getAttribute("type") == "cover":
            cover_href = ref.getAttribute("href")
            cover_file_path = os.path.join(os.path.dirname(rootfile_path), cover_href)

            # is html
            cover_file = epub.open(cover_file_path)
            cover_dom = minidom.parseString(cover_file.read())
            imgs = cover_dom.getElementsByTagName("img")
            if imgs:
                img = imgs[0]
                img_path = img.getAttribute("src")
                return os.path.relpath(
                    os.path.join(os.path.dirname(cover_file_path), img_path)
                )
    return None


def get_cover_by_filename(epub):
    no_matching_images = []
    for fileinfo in epub.filelist:
        if cover_regex.match(fileinfo.filename):
            return fileinfo.filename
        if img_ext_regex.match(fileinfo.filename):
            no_matching_images.append(fileinfo)
    return _choose_best_image(no_matching_images)


def _choose_best_image(images):
    if images:
        return max(images, key=lambda f: f.file_size)
    return None


def extract_cover(epub, cover_path):
    if cover_path:
        cover_file = epub.open(cover_path)
        # im = PILImage.open(BytesIO(cover.read()))
        cover = Image(blob=BytesIO(cover_file.read()))
        if cover.mode == "CMYK":
            cover = cover.convert("RGB")
        width = cover.width
        height = cover.height
        ratio = 100.0 / (width * 1.0)
        new_height = int(ratio * height)
        # print("webp dims before:", first_page.width, " x ", first_page.height)
        webp = cover.convert("webp")
        webp.thumbnail(width=100, height=new_height)
        return webp
    return None
