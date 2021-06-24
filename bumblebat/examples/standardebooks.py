import xml.etree.ElementTree as ET
import urllib.request
import json
from bibliothecula import *
from bibliothecula.models import *

# Run this in the django shell!
# python3 manage.py shell
# exec(open('standardebooks.py').read())

# Max books to download
MAX_BOOKS = 30
# Download this from https://standardebooks.org/opds/all
tree = ET.parse('https _standardebooks.org_opds_all.xml')
root = tree.getroot()

NAMESPACE = "{http://www.w3.org/2005/Atom}"
ns = {x: NAMESPACE+x for x in ["author", "uri", "id", "summary", "title", "name", "category", "link", "entry"]}

entry_get_fn = lambda entry, keys: entry.findall("/".join([ns[k] for k in keys]))

root_uri = entry_get_fn(root, ["author", "uri"])[0].text
books = entry_get_fn(root, ["entry"])

print(root_uri)
print(len(books), "books.")

def add_text_metadata(doc, name, value):
    m,_ = TextMetadata.objects.get_or_create(name=name,data=value)
    has,_ = DocumentHasTextMetadata.objects.get_or_create(name=name, document=doc, metadata=m)
    m.save()
    has.save()

def add_storage(doc, mime_type, filename, blob):
    d = {
            'content_type': mime_type.strip(),
            'filename': filename.strip(),
            'size': len(blob),
            }
    name = json.dumps(d,  separators=(',', ':'))
    buf = io.BytesIO()
    buf.write(blob)
    buf.seek(0)
    m,_ = BinaryMetadata.objects.get_or_create(name=name,data=buf.getvalue())
    has,_ = DocumentHasBinaryMetadata.objects.get_or_create(name=STORAGE_NAME, document=doc, metadata=m)
    m.save()
    has.save()

epub_mime_type = 'application/epub+zip'
counter = 0

for b in books:
    url = entry_get_fn(b, ["id"])[0].text
    title = entry_get_fn(b, ["title"])[0].text
    author = entry_get_fn(b, ["author","name"])[0].text
    summary = entry_get_fn(b, ["summary"])[0].text
    tags = set(map(lambda t: t.strip(),reduce(lambda a, b: a + b, [cat.get('term').split('--') for cat in entry_get_fn(b,['category'])])))
    epub_url = b.findall(ns['link']+"[@title='Recommended compatible epub']")[0].get("href")
    print(counter, title, epub_url)
    with urllib.request.urlopen(root_uri+epub_url) as ebook:
        blob =  ebook.read()
    doc = Document.objects.create(title=title)
    doc.save()
    for t in tags:
        add_text_metadata(doc, TAG_NAME, t)
    add_text_metadata(doc, AUTHOR_NAME, author)
    add_text_metadata(doc, TYPE_NAME, 'book')
    add_text_metadata(doc, 'url', url)
    add_text_metadata(doc, 'summary', summary)
    filename = epub_url.rpartition('/')[2]
    add_storage(doc, epub_mime_type, filename, blob)
    doc.create_thumbnail()
    counter += 1
    if counter == MAX_BOOKS:
        break
