from html.parser import HTMLParser
import re


"""Extract plain text from HTML. """


class Textractor(HTMLParser):
    whitespace = r"\s{2,}"
    output = ""
    ignore = 2
    in_header = False
    extract_href = False

    def reset(self):
        self.output = ""
        self.ignore = 2
        self.in_header = False
        super().reset()

    def handle_starttag(self, tag, attrs):
        attrs = {a[0]: a[1] for a in attrs}
        if tag == "body" and (
            "bodymatter" in attrs["epub:type"] if "epub:type" in attrs else True
        ):
            self.ignore -= 1
        if (
            tag in ["h1", "h2", "h3", "h4", "h5", "h6"]
            and "epub:type" in attrs
            and "ordinal" in attrs["epub:type"]
        ):
            self.ignore += 1
            self.in_header = True
        if tag == "a" and self.extract_href and "href" in attrs:
            self.output += re.sub(self.whitespace, " ", attrs["href"]).replace(
                "\ufeff", ""
            )
            self.output += " "

    def handle_endtag(self, tag):
        if tag == "head":
            self.ignore -= 1
        elif tag in ["h1", "h2", "h3", "h4", "h5", "h6"] and self.in_header:
            self.ignore -= 1
            self.in_header = False

    def handle_data(self, data):
        if self.ignore == 0:
            self.output += re.sub(self.whitespace, " ", data).replace("\ufeff", "")
