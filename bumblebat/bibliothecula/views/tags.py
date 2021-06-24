from . import *


@staff_member_required
def view_tag(request, tag=None):
    try:
        import networkx as nx
        import matplotlib.pyplot as plt
        import math
    except ImportError as exc:
        messages.add_message(
            request,
            messages.ERROR,
            f'Could not import python3 package "{exc.name}" for the graph visualization.',
        )
        template = loader.get_template("tag.html")
        return HttpResponse(template.render({}, request))
    if tag:
        try:
            u = uuid_lib.UUID(tag)
            tag_m = get_object_or_404(TextMetadata, uuid=u)
            tag = tag_m.data
        except ValueError:
            tag_m = get_object_or_404(TextMetadata, name=TAG_NAME, data=tag)
        max_depth = 3
    else:
        tag_m = TextMetadata.objects.all().filter(name=TAG_NAME).first()
        max_depth = 9999999
    G = nx.Graph()
    visited = set()

    def BFS(tag_m, visited, depth):
        if tag_m.uuid in visited:
            return
        visited.add(tag_m.uuid)
        if depth == max_depth:
            return
        siblings = (
            tag_m.documents.all()
            .filter(document__text_metadata__metadata__name=TAG_NAME)
            .values_list("document__text_metadata__metadata__uuid", flat=True)
        )
        siblings = [s for s in siblings if s not in visited]
        siblings = TextMetadata.objects.all().filter(uuid__in=siblings).all()
        for s in siblings:
            G.add_node(s.data, label=s.uuid)
            G.add_edge(tag_m.data, s.data)
            BFS(s, visited, depth + 1)
        return

    if tag_m is not None:
        G.add_node(tag_m.data, label=tag_m.uuid)
        BFS(tag_m, visited, 0)
    if tag is None:
        orphans = (
            TextMetadata.objects.all().filter(name=TAG_NAME).exclude(uuid__in=visited)
        )
        for orph in orphans:
            BFS(orph, visited, 0)

    options = {
        "font_size": 2,
        "node_size": [len(n) * 300 for n in G.nodes()],
        "node_color": "white",
        "edgecolors": "black",
        "linewidths": 1,
        "width": 1,
        "node_shape": "",
    }
    fig, ax = plt.subplots(figsize=(10, 10))
    if len(G.nodes()) > 0:
        try:
            pos = nx.drawing.nx_agraph.graphviz_layout(G)
        except AttributeError:
            pos = nx.spring_layout(
                G, k=1.6 * 1 / math.sqrt(len(G.nodes())), iterations=20, fixed=None
            )
        nx.draw_networkx(G, pos, **options)
        nx.draw_networkx_labels(G, pos, bbox=dict(boxstyle="square", fc="w", ec="k"))
    # Set margins for the axes so that nodes aren't clipped
    ax.margins(0.20)
    fig.tight_layout()
    plt.axis("off")
    svg = io.BytesIO()
    plt.savefig(svg, format="svg")
    parser = SVGParser()
    parser.feed(svg.getvalue().decode(encoding="UTF-8").strip())
    svg = parser.output

    context = {
        "tag": tag,
        "network": mark_safe(svg),
        "add_document_form": AddDocument(),
    }
    template = loader.get_template("tag.html")
    return HttpResponse(template.render(context, request))


@staff_member_required
def view_tag_d3(request, tag=None):
    nodes = {}
    links = []

    def add_node(n):
        nodes[n.uuid] = {
            "id": n.data,
            "uuid": str(n.uuid),
            "group": None,
        }

    if tag:
        try:
            u = uuid_lib.UUID(tag)
            tag_m = get_object_or_404(TextMetadata, uuid=u)
            tag = tag_m.data
        except ValueError:
            tag_m = get_object_or_404(TextMetadata, name=TAG_NAME, data=tag)
        max_depth = 3
    else:
        tag_m = TextMetadata.objects.all().filter(name=TAG_NAME).first()
        max_depth = 9999999
    visited = set()
    group = 0

    def BFS(tag_m, visited, depth):
        if tag_m.uuid in visited:
            return
        add_node(tag_m)
        visited.add(tag_m.uuid)
        nodes[tag_m.uuid]["group"] = group
        if depth == max_depth:
            return
        siblings = (
            tag_m.documents.all()
            .filter(document__text_metadata__metadata__name=TAG_NAME)
            .values_list("document__text_metadata__metadata__uuid", flat=True)
        )
        siblings = [s for s in siblings if s not in visited]
        siblings = TextMetadata.objects.all().filter(uuid__in=siblings).all()
        for s in siblings:
            BFS(s, visited, depth + 1)
            links.append(
                {
                    "source": nodes[tag_m.uuid]["id"],
                    "target": nodes[s.uuid]["id"],
                    "value": 2,
                }
            )
        return

    if tag_m is not None:
        BFS(tag_m, visited, 0)
        group += 1
    if tag is None:
        orphans = (
            TextMetadata.objects.all().filter(name=TAG_NAME).exclude(uuid__in=visited)
        )
        for orph in orphans:
            BFS(orph, visited, 0)
            group += 1
    context = {
        "tag": tag,
        "add_document_form": AddDocument(),
        "node_data": {"nodes": [nodes[k] for k in nodes], "links": links},
    }
    template = loader.get_template("tag_d3.html")
    return HttpResponse(template.render(context, request))
