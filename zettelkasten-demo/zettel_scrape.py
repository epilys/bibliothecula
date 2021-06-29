import urllib.parse
import urllib.request
import http.cookiejar
import json
import time
import collections
import random
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any, Set

def scraper():
    API_URL = "https://v0.api.niklas-luhmann-archiv.de/ZK/zettel/"
    seen_zettels: Set[str] = set([])
    to_see: Set[str] = set([])
    def make_get(zettel: str) -> Dict[str, Any]:
        url = API_URL + zettel
        headers={"Content-Type":"application/json;charset=utf-8",
        "User-agent":"Mozilla/5.0 Chrome/81.0.4044.92",    # Chrome 80+ as per web search
        "Host":API_URL,
        "Origin":url,
        "Referer":url}
        request = urllib.request.Request(url)
        response = urllib.request.urlopen(request)
        contents = response.read()
        print("got", zettel)

        with open(f"{zettel}.json", "wb") as f:
            f.write(contents)

        json_data = json.loads(contents.decode("utf-8"))
        return json_data

    def get_refs(json_data: Dict[str, Any])-> Set[str]:
        out = set([])
        if 'navigation' in json_data:
            for r in json_data['navigation']:
                for e in json_data['navigation'][r]:
                    out.add(e["ekin"])
        return out

    #q = collections.deque(["ZK_1_NB_1_1_V"])

    p = Path('.')
    for j in p.glob('**/ZK*.json'):
        with open(j, 'r') as f:
            json_data = json.loads(f.read())
            id = json_data["ekin"]
            seen_zettels.add(id)
            if id in to_see:
                to_see.remove(id)
            for ref in get_refs(json_data):
                if not ref in seen_zettels:
                    to_see.add(ref)
    print(len(seen_zettels))
    print(len(to_see))
    print(len(seen_zettels - to_see))
    #q = collections.deque(to_see)


    failures = 0
    while len(to_see) > 0:
        zettel_id = to_see.pop()
        if zettel_id in seen_zettels:
            continue
        try:
            json_data = make_get(zettel_id)
        except Exception as exc:
            if failures > 5:
                raise exc from None
            else:
                print("Exception for ", zettel_id, exc)
                continue
        seen_zettels.add(zettel_id)
        for ref in get_refs(json_data):
            if ref not in seen_zettels:
                to_see.add(ref)
        #time.sleep(random.randint(0, 1))
        print("Left: ", len(to_see))



scraper()

print("done, saw", len(seen_zettels),"zettels")
