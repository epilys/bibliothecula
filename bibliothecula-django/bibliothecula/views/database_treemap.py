import matplotlib

matplotlib.use("Agg")  # Use pixel canvas backend instead of GUI backend
matplotlib.rcParams["hatch.linewidth"] = 0.9
from matplotlib import pylab
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

from functools import reduce
import io

# Hatch reference: https://matplotlib.org/stable/gallery/shapes_and_collections/hatch_style_reference.html#sphx-glr-gallery-shapes-and-collections-hatch-style-reference-py
# Doubling the size of a string (i.e. '+'*2) makes the hatches thicker
# Use matplotlib.rcParams['hatch.linewidth'] to set the linewidth
def hatches():
    list_ = ["/", "\\", "|", "-", "+", "x", "o", "O", ".", "*"]
    i = 0
    wraps = 1
    while True:
        index = i % len(list_)
        yield list_[i] * (wraps + 1)
        i = i + 1
        if i >= len(list_):
            i -= len(list_)
            wraps += 1


"""
Code adapted from https://scipy-cookbook.readthedocs.io/items/Matplotlib_TreeMap.html
"""


class Treemap:
    """
    Treemap builder using pylab.

    Uses algorithm straight from http://hcil.cs.umd.edu/trs/91-03/91-03.html

    James Casbon 29/7/2006
    """

    def __init__(self, trees):
        """example trees:
        tree= ((5,(3,5)), 4, (5,2,(2,3,(3,2,2)),(3,3)), (3,2) )
        tree = ((6, 5))
        """
        self.done = False
        self.trees = trees
        self.hatches_gen = hatches()

    def compute(self):
        def new_size_method():
            size_cache = {}

            def _size(thing):
                if isinstance(thing, int):
                    return thing
                if thing in size_cache:
                    return size_cache[thing]
                else:
                    size_cache[thing] = reduce(int.__add__, [_size(x) for x in thing])
                    return size_cache[thing]

            return _size

        fig, (ax1, ax2) = plt.subplots(
            1, 2, figsize=(6, 3.5), constrained_layout=True, sharey=True
        )
        # pylab.subplots_adjust(left=0, right=1, top=1, bottom=0)
        ax1.set_xticks([])
        ax1.set_yticks([])
        ax2.set_xticks([])
        ax2.set_yticks([])

        self.iter_method = iter
        for ((title, sizes, tree, labels), ax) in zip(self.trees, [ax1, ax2]):
            self.size_method = new_size_method()
            self.ax = ax
            self.rectangles = []
            self.addnode(tree, lower=[0, 0], upper=[1, 1], axis=0)
            ax.set_xlabel(title)
            for (n, r) in self.rectangles:
                if isinstance(n, int):
                    size = str(sizes[n])
                    label = str(labels[n])
                    rx, ry = r.get_xy()
                    cx = rx + r.get_width() / 2.0
                    cy = ry + r.get_height() / 2.0
                    ax.annotate(
                        f"{size}\n{label}",
                        (cx, cy),
                        color="k",
                        backgroundcolor="w",
                        weight="bold",
                        fontsize=9,
                        ha="center",
                        va="center",
                    )

        self.done = True

    def as_svg(self):
        if not self.done:
            self.compute()
        svg = io.BytesIO()
        plt.savefig(svg, format="svg")
        return svg.getvalue().decode(encoding="UTF-8").strip()

    def addnode(self, node, lower=[0, 0], upper=[1, 1], axis=0):
        axis = axis % 2
        hatch = self.draw_rectangle(lower, upper, node)
        width = upper[axis] - lower[axis]
        try:
            for child in self.iter_method(node):
                if self.size_method(node) == 0:
                    continue
                upper[axis] = lower[axis] + (
                    width * float(self.size_method(child))
                ) / self.size_method(node)
                self.addnode(child, list(lower), list(upper), axis + 1)
                lower[axis] = upper[axis]

        except TypeError:
            pass

    def draw_rectangle(self, lower, upper, node):
        h = None
        if isinstance(node, int):
            h = next(self.hatches_gen)
        r = Rectangle(
            lower,
            upper[0] - lower[0],
            upper[1] - lower[1],
            edgecolor="k",
            fill=False,
            hatch=h,
        )
        self.ax.add_patch(r)
        self.rectangles.append((node, r))
        return h
