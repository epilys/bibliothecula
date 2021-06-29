import argparse
from pathlib import Path
import pprint
import json
from html.parser import HTMLParser
import re
import uuid


def zettel_id_to_uuid(id):
    return uuid.uuid5(uuid.NAMESPACE_OID, id)

ROOT_URL = 'https://niklas-luhmann-archiv.de'

class Textractor(HTMLParser):
    output = []

    def reset(self):
        self.output = []
        super().reset()

    def handle_starttag(self, tag, attrs):
        attrs = {a[0]: a[1] for a in attrs}
        if tag == "a" and "title" in attrs and attrs["title"].startswith("ZK_"):
            self.output.append(attrs["title"])

    def handle_endtag(self, tag):
        pass

    def handle_data(self, data):
        pass


class HTMLTransformer(HTMLParser):
    output = ""
    uuids = {}
    in_link = 0
    current_uuid = None

    def reset(self):
        self.output = ""
        self.uuids = {}
        self.in_link = 0
        super().reset()

    def handle_starttag(self, tag, attrs):
        if len(attrs) == 0:
            self.output += f"<{tag}>"
        else:
            self.output += f"<{tag}"
        attrs = {a[0]: a[1] for a in attrs}
        for x in attrs:
            if x.startswith("href"):
                if 'title' in attrs and attrs['title'].startswith("ZK_"):
                    self.in_link += 1
                    id = attrs["title"]
                    uuid = zettel_id_to_uuid(id)
                    self.uuids[id] = uuid
                    self.current_uuid = uuid.hex
                    self.output += f' data-original-{x}="{ROOT_URL}{attrs[x]}"'
                else:
                    self.output += f' {x}="{ROOT_URL}{attrs[x]}"'
            else:
                self.output += f' {x}="{attrs[x]}"'
        if len(attrs) != 0:
            self.output += ">"

    def handle_endtag(self, tag):
        if tag == 'a' and self.in_link != 0:
            self.in_link -= 1
        self.output += f"</{tag}>"

    def handle_data(self, data):
        if self.in_link != 0:
            self.output += self.current_uuid
            self.output += " "
        self.output += data




parser = argparse.ArgumentParser(description='Process some integers.')
parser.add_argument('path', type=str, help='an integer for the accumulator')

args = parser.parse_args()
table= {
        "ordnungsnummer": "order-number",
        "abteilung": "department",
        "Normaler Bestand": "normal inventory",
        "auszug": "abstract",
        "vorherige-": "previous-",
        "naechster-":"next-",
        "vorderseite-": "front-",
        "naechste-": "next-",
        "vorderseite-": "front-",
        "iscan-":"scan-",
        "-im-zettelkasten":"-in-note-box",
        "kehrseite-":"backside-",
        "im-nummerierten-Gliederungsverlauf":"in-numbered-outline",
        "vorwaerts-":"forward-",
        "rueckwaerts-":"backward-",
        "Zettelvorderseite": "Note front",
        }

p = Path(args.path)
"""
print()
count = 0
for j in p.glob('**/ZK*.json'):
    json_data = None
    with open(j, 'r') as f:
        #json_data = json.loads(f.read())
        json_data = f.read()
    for w in table:
        json_data = json_data.replace(w, table[w])
    with open(j, "w") as f:
        f.write(json_data)
    count += 1
    print("\r", count, end='', flush=True)

print(count)
"""

objs = []

count = 0
x = Textractor()
t = HTMLTransformer()
for j in p.glob('**/ZK*.json'):
    json_data = None
    with open(j, 'r') as f:
        json_data = json.loads(f.read())
    if "ekin" not in json_data:
        print(j, "doesn't have an ekin: ")
        print(json_data)
        continue
    try:
        html = json_data["transcription"]["html"]
    except:
        continue

    x.reset()
    x.feed(html)
    t.reset()
    t.feed(html)
    #print(f"zettel {json_data['ekin']} has references to {t.uuids}")


    name = {
        "content_type": "text/html",
        "filename": json_data["ekin"]+".html",
        "size": len(t.output),
    }
    name = json.dumps(name, separators=(",", ":"))
    objs.append({
            "uuid": zettel_id_to_uuid(json_data["ekin"]).hex,
            "name": name,
            "data": t.output,
            })
    count+=1
    print(count)

with open("total.json", 'w') as f:
    f.write(json.dumps(objs, separators=(",", ":")))
