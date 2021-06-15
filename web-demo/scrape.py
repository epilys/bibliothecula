# Login to website using just Python 3 Standard Library
import urllib.parse
import urllib.request
import http.cookiejar
from bs4 import BeautifulSoup

def scraper_login():
    # here goes URL that's found inside form action='.....'
    #   adjust as needed, can be all kinds of weird stuff
    authentication_url = '/admin/login/'

    # username and password for login
    username = ''
    password = ''

    # initiate the cookie jar (using : http.cookiejar and urllib.request)
    cookie_jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))
    urllib.request.install_opener(opener)

    def make_get(url):
        ####### change variables here, like URL, action URL, user, pass
        # your base URL here, will be used for headers and such, with and without https://
        base_url = '127.0.0.1:8000'
        https_base_url = 'http://127.0.0.1:8000'
        url = https_base_url + url


        ####### rest of the script is logic
        # but you will need to tweak couple things maybe regarding "token" logic
        #   (can be _token or token or _token_ or secret ... etc)

        # big thing! you need a referer for most pages! and correct headers are the key
        headers={"Content-Type":"application/x-www-form-urlencoded",
        "User-agent":"Mozilla/5.0 Chrome/81.0.4044.92",    # Chrome 80+ as per web search
        "Host":base_url,
        "Origin":https_base_url,
        "Referer":https_base_url}
        # first a simple request, just to get login page and parse out the token
        #       (using : urllib.request)
        request = urllib.request.Request(url)
        response = urllib.request.urlopen(request)
        contents = response.read()

        html = contents.decode("utf-8")
        return html

    def make_post(url, payload):
        ####### change variables here, like URL, action URL, user, pass
        # your base URL here, will be used for headers and such, with and without https://
        base_url = '127.0.0.1:8000'
        https_base_url = 'http://127.0.0.1:8000'
        url = https_base_url + url


        ####### rest of the script is logic
        # but you will need to tweak couple things maybe regarding "token" logic
        #   (can be _token or token or _token_ or secret ... etc)

        # big thing! you need a referer for most pages! and correct headers are the key
        headers={"Content-Type":"application/x-www-form-urlencoded",
        "User-agent":"Mozilla/5.0 Chrome/81.0.4044.92",    # Chrome 80+ as per web search
        "Host":base_url,
        "Origin":https_base_url,
        "Referer":https_base_url}
        # first a simple request, just to get login page and parse out the token
        #       (using : urllib.request)
        request = urllib.request.Request(url)
        response = urllib.request.urlopen(request)
        contents = response.read()

        # parse the page, we look for token eg. on my page it was something like this:
        #    <input type="hidden" name="_token" value="random1234567890qwertzstring">
        #       this can probably be done better with regex and similar
        #       but I'm newb, so bear with me
        html = contents.decode("utf-8")
        # text just before start and just after end of your token string
        mark_start = '<input type="hidden" name="csrfmiddlewaretoken" value="'
        mark_end = '">'
        # index of those two points
        start_index = html.find(mark_start) + len(mark_start)
        end_index = html.find(mark_end, start_index)
        # and text between them is our token, store it for second step of actual login
        token = html[start_index:end_index]

        # here we craft our payload, it's all the form fields, including HIDDEN fields!
        #   that includes token we scraped earler, as that's usually in hidden fields
        #   make sure left side is from "name" attributes of the form,
        #       and right side is what you want to post as "value"
        #   and for hidden fields make sure you replicate the expected answer,
        #       eg. "token" or "yes I agree" checkboxes and such

        payload['csrfmiddlewaretoken'] = token

        # now we prepare all we need for login
        #   data - with our payload (user/pass/token) urlencoded and encoded as bytes
        data = urllib.parse.urlencode(payload)
        binary_data = data.encode('UTF-8')
        # and put the URL + encoded data + correct headers into our POST request
        #   btw, despite what I thought it is automatically treated as POST
        #   I guess because of byte encoded data field you don't need to say it like this:
        #       urllib.request.Request(authentication_url, binary_data, headers, method='POST')
        request = urllib.request.Request(url, binary_data, headers)
        response = urllib.request.urlopen(request)
        contents = response.read()
        contents = contents.decode("utf-8")
        return contents

    login_data = {
            #'name':'value',    # make sure this is the format of all additional fields !
            'username':username,
            'password':password,
            'next':	"/",
        }
    contents = make_post(authentication_url, login_data)

    # just for kicks, we confirm some element in the page that's secure behind the login
    #   we use a particular string we know only occurs after login,
    #   like "logout" or "welcome" or "member", etc. I found "Logout" is pretty safe so far
    #with open('_scrape/index.html', 'w') as f:
    #    f.write(contents)
    """
    page = "/?full_text_query=abolition+of+private+property"
    html = make_get(page)
    filename = page.replace('/', '_').replace('?', '_') + '.html'
    print(filename)
    with open('_scrape/'+filename, 'w') as f:
        f.write(html)
    change_layout_data = { "layout": "table", "change-layout": "change" }
    make_post("", change_layout_data)
    page = "/?full_text_query=abolition+of+private+property"
    html = make_get(page)
    filename = 'table_'+page.replace('/', '_').replace('?', '_') + '.html'
    print(filename)
    with open('_scrape/'+filename, 'w') as f:
        f.write(html)
    """
    """
    doc_page = "/document/cefc21a0-f7ab-46ae-8824-46d254ba053d/"
    html = make_get(doc_page)
    filename = 'doc_'+doc_page.replace('/', '_').replace('?', '_') + '.html'
    print(filename)
    with open('_scrape/'+filename, 'w') as f:
        f.write(html)
    """
    change_layout_data = { "layout": "grid", "change-layout": "change" }
    make_post("", change_layout_data)
    page = ""
    html = make_get(page)
    filename = 'grid.html'
    print(filename)
    with open('web-demo/'+filename, 'w') as f:
        f.write(html)
    """
    for page in [
            ("get", "/database/"),
            ("get", "/tag/"),
            ("get", "/tag_d3/"),
            ("post", "", { "layout": "table", "change-layout": "change" }),
            ]:
        print()
        print()
        print()
        print()
        print()
        print()
        print(page)
        print()
        if page[0] is "get":
            html = make_get(page[1])
        else:
            html = make_post(page[1], page[2])

        #response = urllib.request.urlopen(page)
        #contents = response.read()
        #print(contents)
        filename = page[1].replace('/', '_') + '.html'
        print(filename)
        with open('_scrape/'+filename, 'w') as f:
            f.write(html)
            """



scraper_login()
