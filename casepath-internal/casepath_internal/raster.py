"""Draw a page that is made only of vector paths, in the standard library, so the model can read it from an image.

Some PDFs carry text as outlines rather than as text (a redacted document printed to PDF, for example). Such a page
has no text layer and no embedded image; where PDFium is installed it renders the page, and this module is the
fallback. It fills and strokes paths (lines, Bézier curves, rectangles) with the page's transforms, rotation and grey
levels, follows Form XObjects, and leaves out what a reader needs least: clipping, shadings, patterns and font text.
"""
import math

MAX_EDGES = 600_000  # beyond this a page is left unread rather than drawn slowly


class TooComplex(Exception):
    pass


def _device(page_box, rotate, max_side):
    llx, lly, urx, ury = page_box
    width, height = urx - llx, ury - lly
    shown = (height, width) if rotate in (90, 270) else (width, height)
    scale = max_side / max(shown) if max(shown) > 0 else 1.0
    matrix = {0: (scale, 0.0, 0.0, -scale, -llx * scale, ury * scale),
              90: (0.0, scale, scale, 0.0, -lly * scale, -llx * scale),
              180: (-scale, 0.0, 0.0, scale, urx * scale, -lly * scale),
              270: (0.0, -scale, -scale, 0.0, ury * scale, urx * scale)}[rotate]
    return matrix, max(1, math.ceil(shown[0] * scale)), max(1, math.ceil(shown[1] * scale))


def _gray(values, kind):
    v = [max(0.0, min(1.0, float(x))) for x in values]
    if kind == "gray" or len(v) == 1:
        return int(round(v[0] * 255))
    if len(v) == 3:
        return int(round((0.299 * v[0] + 0.587 * v[1] + 0.114 * v[2]) * 255))
    if len(v) == 4:
        c, m, y, k = v
        return int(round((0.299 * (1 - c) * (1 - k) + 0.587 * (1 - m) * (1 - k) + 0.114 * (1 - y) * (1 - k)) * 255))
    return 0


class _Canvas:
    def __init__(self, width, height):
        self.width, self.height = width, height
        self.pixels = bytearray(b"\xff" * (width * height))
        self.edges, self.painted = 0, False

    def fill(self, subpaths, gray, even_odd=False):
        edges = []
        for points in subpaths:
            if len(points) < 2:
                continue
            for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1]):
                if y0 == y1:
                    continue
                direction = 1 if y1 > y0 else -1
                if y0 > y1:
                    x0, y0, x1, y1 = x1, y1, x0, y0
                edges.append((y0, y1, x0, (x1 - x0) / (y1 - y0), direction))
        if not edges:
            return
        self.edges += len(edges)
        if self.edges > MAX_EDGES:
            raise TooComplex()
        top = max(0, int(min(e[0] for e in edges)))
        bottom = min(self.height - 1, int(max(e[1] for e in edges)))
        if top > bottom:
            return
        edges.sort()
        active, index, colour, width = [], 0, bytes([gray]), self.width
        for row in range(top, bottom + 1):
            middle = row + 0.5
            while index < len(edges) and edges[index][0] <= middle:
                active.append(edges[index])
                index += 1
            active = [e for e in active if e[1] > middle]
            crossings = sorted((e[2] + (middle - e[0]) * e[3], e[4]) for e in active)
            winding, start = 0, 0.0
            for x, direction in crossings:
                before = winding
                winding = (winding ^ 1) if even_odd else winding + direction
                if before == 0 and winding != 0:
                    start = x
                elif before != 0 and winding == 0:
                    a, b = max(0, int(start + 0.5)), min(width, int(x + 0.5))
                    if b <= a and x - start > 0.15 and 0 <= int(start) < width:  # a hairline stays visible
                        a, b = int(start), int(start) + 1
                    if b > a:
                        self.pixels[row * width + a:row * width + b] = colour * (b - a)
                        self.painted = True

    def stroke(self, subpaths, closed, gray, half_width):
        for points in subpaths:
            pairs = list(zip(points, points[1:] + (points[:1] if closed and len(points) > 2 else [])))
            for (x0, y0), (x1, y1) in pairs:
                dx, dy = x1 - x0, y1 - y0
                length = math.hypot(dx, dy)
                if length == 0:
                    continue
                nx, ny = -dy / length * half_width, dx / length * half_width
                ex, ey = dx / length * half_width, dy / length * half_width  # square caps join neighbouring segments
                self.fill([[(x0 - ex + nx, y0 - ey + ny), (x1 + ex + nx, y1 + ey + ny), (x1 + ex - nx, y1 + ey - ny),
                            (x0 - ex - nx, y0 - ey - ny)]], gray)


def _apply(m, x, y):
    return m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]


def _bezier(p0, p1, p2, p3):
    length = math.hypot(p1[0] - p0[0], p1[1] - p0[1]) + math.hypot(p2[0] - p1[0], p2[1] - p1[1]) + math.hypot(p3[0] - p2[0], p3[1] - p2[1])
    steps = max(2, min(48, int(length / 2)))
    out = []
    for i in range(1, steps + 1):
        t = i / steps
        u = 1 - t
        out.append((u * u * u * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t * t * t * p3[0],
                    u * u * u * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t * t * t * p3[1]))
    return out


def render(doc, page, max_side=1700):
    """The page drawn as an 8-bit grey PNG, or None when it paints nothing. Raises TooComplex for huge pages."""
    from .pdfread import Lexer, Op, Stream, _list, _mult, _num, _png, MAX_DEPTH

    box = doc.resolve(page.get("CropBox")) or doc.resolve(page.get("MediaBox")) or [0, 0, 612, 792]
    values = [_num(doc.resolve(v)) for v in box[:4]] if isinstance(box, list) and len(box) >= 4 else [0, 0, 612, 792]
    page_box = (min(values[0], values[2]), min(values[1], values[3]), max(values[0], values[2]), max(values[1], values[3]))
    rotate = int(_num(doc.resolve(page.get("Rotate")))) % 360
    rotate = rotate if rotate in (0, 90, 180, 270) else 0
    device, width, height = _device(page_box, rotate, max_side)
    canvas = _Canvas(width, height)

    def walk(content, resources, ctm, depth):
        lex, operands, stack = Lexer(content), [], []
        state = {"ctm": ctm, "fill": 0, "stroke": 0, "width": 1.0}
        subpaths, current, start = [], None, None
        while True:
            token = lex.parse()
            if token is None:
                break
            if not isinstance(token, Op):
                operands.append(token)
                continue
            op, n = str(token), [v for v in operands if isinstance(v, (int, float))]
            m = state["ctm"]
            if op == "BI":
                import re
                end = re.compile(rb"\sEI(?=\s|$)").search(content, lex.pos)
                lex.pos = end.end() if end else len(content)
            elif op == "q":
                stack.append(dict(state))
            elif op == "Q":
                state = stack.pop() if stack else state
            elif op == "cm" and len(n) >= 6:
                state["ctm"] = _mult(tuple(float(v) for v in n[-6:]), m)
            elif op == "w" and n:
                state["width"] = float(n[-1])
            elif op in ("g", "rg", "k"):
                state["fill"] = _gray(n[-{"g": 1, "rg": 3, "k": 4}[op]:], "gray" if op == "g" else "")
            elif op in ("G", "RG", "K"):
                state["stroke"] = _gray(n[-{"G": 1, "RG": 3, "K": 4}[op]:], "gray" if op == "G" else "")
            elif op in ("sc", "scn"):
                state["fill"] = _gray(n, "") if n else 128
            elif op in ("SC", "SCN"):
                state["stroke"] = _gray(n, "") if n else 128
            elif op == "cs":
                state["fill"] = 0
            elif op == "CS":
                state["stroke"] = 0
            elif op == "m" and len(n) >= 2:
                current = start = _apply(m, n[-2], n[-1])
                subpaths.append([current])
            elif op == "l" and len(n) >= 2 and subpaths:
                current = _apply(m, n[-2], n[-1])
                subpaths[-1].append(current)
            elif op in ("c", "v", "y") and subpaths and current is not None:
                need = 6 if op == "c" else 4
                if len(n) >= need:
                    pts = [_apply(m, n[-need + i], n[-need + i + 1]) for i in range(0, need, 2)]
                    p1, p2, p3 = (pts[0], pts[1], pts[2]) if op == "c" else (current, pts[0], pts[1]) if op == "v" else (pts[0], pts[1], pts[1])
                    subpaths[-1].extend(_bezier(current, p1, p2, p3))
                    current = p3
            elif op == "h" and subpaths and start is not None:
                current = start
            elif op == "re" and len(n) >= 4:
                x, y, w, h = n[-4:]
                corners = [_apply(m, x, y), _apply(m, x + w, y), _apply(m, x + w, y + h), _apply(m, x, y + h)]
                subpaths.append(corners)
                current = start = corners[0]
            elif op in ("f", "F", "f*", "B", "B*", "b", "b*", "S", "s", "n"):
                if op not in ("S", "s", "n"):
                    canvas.fill([p for p in subpaths if len(p) > 1], state["fill"], even_odd=op.endswith("*"))
                if op in ("S", "s", "B", "B*", "b", "b*"):
                    scale = math.sqrt(abs(m[0] * m[3] - m[1] * m[2])) or 1.0
                    canvas.stroke([p for p in subpaths if len(p) > 1], op in ("s", "b", "b*"), state["stroke"], max(0.5, state["width"] * scale / 2))
                subpaths, current, start = [], None, None
            elif op == "Do" and operands and depth < MAX_DEPTH:
                xobjects = doc.resolve(resources.get("XObject")) if isinstance(resources, dict) else None
                form = doc.resolve(xobjects.get(operands[-1])) if isinstance(xobjects, dict) else None
                if isinstance(form, Stream) and form.get("Subtype") == "Form":
                    data, coding = doc.stream_bytes(form)
                    if coding is None:
                        matrix = doc.resolve(form.get("Matrix"))
                        inner = _mult(tuple(_num(v) for v in matrix), m) if isinstance(matrix, list) and len(matrix) == 6 else m
                        walk(data, doc.resolve(form.get("Resources")) or resources, inner, depth + 1)
            operands = []

    walk(doc.page_content(page), doc.resolve(page.get("Resources")) or {}, device, 0)
    if not canvas.painted:
        return None
    rows = [bytes(canvas.pixels[y * width:(y + 1) * width]) for y in range(height)]
    return _png(width, height, 0, 8, rows)
