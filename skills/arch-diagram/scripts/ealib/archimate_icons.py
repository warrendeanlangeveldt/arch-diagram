"""ArchiMate 3.2 type symbols, drawn in the top-right corner of an element
box (rectangle notation). Each glyph fits a 16 x 12 cell whose top-left is
(x, y); strokes are 1px in the layer stroke colour."""


def _g(x, y, c, body, fill="none"):
    return (f'<g transform="translate({x:.1f} {y:.1f})" fill="{fill}" stroke="{c}" '
            f'stroke-width="1" stroke-linecap="round" stroke-linejoin="round">{body}</g>')


def icon(kind, x, y, c):
    """SVG for glyph `kind` with its 16x12 cell at (x, y), colour c."""
    f = GLYPHS.get(kind)
    return f(x, y, c) if f else ""


GLYPHS = {
    # active structure
    "actor": lambda x, y, c: _g(x, y, c,
        '<circle cx="8" cy="2.4" r="2"/><line x1="8" y1="4.4" x2="8" y2="8.2"/>'
        '<line x1="4.6" y1="6" x2="11.4" y2="6"/><polyline points="5,11.6 8,8.2 11,11.6"/>'),
    "role": lambda x, y, c: _g(x, y, c,
        '<path d="M4 2.5 H12 M4 9.5 H12"/><path d="M4 2.5 A2 3.5 0 0 0 4 9.5"/>'
        '<ellipse cx="12" cy="6" rx="2" ry="3.5"/>'),
    "collaboration": lambda x, y, c: _g(x, y, c,
        '<circle cx="6" cy="6" r="4"/><circle cx="10" cy="6" r="4"/>'),
    "interface": lambda x, y, c: _g(x, y, c,
        '<circle cx="11" cy="6" r="3.2"/><line x1="2" y1="6" x2="7.8" y2="6"/>'),
    "component": lambda x, y, c: _g(x, y, c,
        '<rect x="4" y="1" width="10" height="10"/><rect x="2" y="3" width="4" height="2" fill="#fff"/>'
        '<rect x="2" y="7" width="4" height="2" fill="#fff"/>'),
    "node": lambda x, y, c: _g(x, y, c,
        '<path d="M2 4 L4.5 1.5 H14 V8.5 L11.5 11 H2 Z M2 4 H11.5 V11 M11.5 4 L14 1.5"/>'),
    "device": lambda x, y, c: _g(x, y, c,
        '<rect x="3" y="1" width="10" height="7" rx="1"/><path d="M1.5 11 L4 8 H12 L14.5 11 Z"/>'),
    "systemsoftware": lambda x, y, c: _g(x, y, c,
        '<circle cx="7" cy="6.8" r="4.2"/><path d="M5.6 2.9 A4.2 4.2 0 0 1 13.2 5.2 A4.2 4.2 0 0 1 11 9.4"/>'),
    "path": lambda x, y, c: _g(x, y, c,
        '<line x1="3" y1="6" x2="13" y2="6" stroke-dasharray="1.6 1.4"/>'
        '<polyline points="5,3.5 2,6 5,8.5"/><polyline points="11,3.5 14,6 11,8.5"/>'),
    "network": lambda x, y, c: _g(x, y, c,
        '<path d="M4 3 H14 L12 9 H2 Z"/><circle cx="4" cy="3" r="1.1" fill="' + c + '"/>'
        '<circle cx="14" cy="3" r="1.1" fill="' + c + '"/><circle cx="2" cy="9" r="1.1" fill="' + c + '"/>'
        '<circle cx="12" cy="9" r="1.1" fill="' + c + '"/>'),
    "equipment": lambda x, y, c: _g(x, y, c,
        '<circle cx="6" cy="7" r="3.2"/><circle cx="6" cy="7" r="1.1"/><circle cx="11.5" cy="3.5" r="2.2"/>'
        '<circle cx="11.5" cy="3.5" r="0.7"/>'),
    "facility": lambda x, y, c: _g(x, y, c,
        '<path d="M2 11 V1.5 H4.5 V6 L8 3.5 V6 L11.5 3.5 V6 L14 4 V11 Z"/>'),
    "distribution": lambda x, y, c: _g(x, y, c,
        '<line x1="3" y1="4.5" x2="13" y2="4.5"/><line x1="3" y1="7.5" x2="13" y2="7.5"/>'
        '<polyline points="5,2 2,6 5,10"/><polyline points="11,2 14,6 11,10"/>'),
    # behaviour
    "process": lambda x, y, c: _g(x, y, c,
        '<path d="M1.5 4 H10 V1.5 L14.5 6 L10 10.5 V8 H1.5 Z"/>'),
    "function": lambda x, y, c: _g(x, y, c,
        '<path d="M3.5 11 V3.5 L8 0.8 L12.5 3.5 V11 L8 8.3 Z"/>'),
    "interaction": lambda x, y, c: _g(x, y, c,
        '<path d="M7 1.5 A4.5 4.5 0 0 0 7 10.5 Z"/><path d="M9 1.5 A4.5 4.5 0 0 1 9 10.5 Z"/>'),
    "event": lambda x, y, c: _g(x, y, c,
        '<path d="M1.5 2 H11 A4 4 0 0 1 11 10 H1.5 L4.2 6 Z"/>'),
    "service": lambda x, y, c: _g(x, y, c,
        '<rect x="1.5" y="2.5" width="13" height="7" rx="3.5"/>'),
    # passive / composite
    "representation": lambda x, y, c: _g(x, y, c,
        '<path d="M2 1.5 H14 V9 Q11 7 8 9 T2 9 Z"/><line x1="2" y1="4" x2="14" y2="4"/>'),
    "artifact": lambda x, y, c: _g(x, y, c,
        '<path d="M3.5 0.8 H9.5 L12.5 3.8 V11.2 H3.5 Z M9.5 0.8 V3.8 H12.5"/>'),
    "material": lambda x, y, c: _g(x, y, c,
        '<path d="M5 1 H11 L14 6 L11 11 H5 L2 6 Z"/><line x1="5.5" y1="3" x2="10.5" y2="3"/>'
        '<line x1="11.6" y1="7" x2="9.8" y2="9.7"/><line x1="4.4" y1="7" x2="6.2" y2="9.7"/>'),
    "product": lambda x, y, c: _g(x, y, c,
        '<rect x="2" y="1.5" width="12" height="9"/><path d="M2 4 H8 V1.5"/>'),
    # motivation
    "driver": lambda x, y, c: _g(x, y, c,
        '<circle cx="8" cy="6" r="4.6"/><circle cx="8" cy="6" r="1" fill="' + c + '"/>'
        '<path d="M8 0 V12 M2 6 H14 M3.8 1.8 L12.2 10.2 M12.2 1.8 L3.8 10.2"/>'),
    "assessment": lambda x, y, c: _g(x, y, c,
        '<circle cx="9.5" cy="4.5" r="3.5"/><line x1="7" y1="7" x2="2" y2="11.5"/>'),
    "goal": lambda x, y, c: _g(x, y, c,
        '<circle cx="8" cy="6" r="5.2"/><circle cx="8" cy="6" r="3"/><circle cx="8" cy="6" r="1" fill="' + c + '"/>'),
    "outcome": lambda x, y, c: _g(x, y, c,
        '<circle cx="7" cy="7" r="4.6"/><circle cx="7" cy="7" r="2.4"/><circle cx="7" cy="7" r="0.8" fill="' + c + '"/>'
        '<path d="M7 7 L14.5 0.5 M11.5 0.8 H14.5 V3.8"/>'),
    "principle": lambda x, y, c: _g(x, y, c,
        '<rect x="3.5" y="0.8" width="9" height="10.4" rx="1"/><line x1="8" y1="3" x2="8" y2="7"/>'
        '<circle cx="8" cy="9" r="0.6" fill="' + c + '"/>'),
    "requirement": lambda x, y, c: _g(x, y, c,
        '<path d="M4.5 2 H15 L11.5 10 H1 Z"/>'),
    "constraint": lambda x, y, c: _g(x, y, c,
        '<path d="M4.5 2 H15 L11.5 10 H1 Z M7.5 2 L4 10"/>'),
    "meaning": lambda x, y, c: _g(x, y, c,
        '<path d="M4 10 C1 10 1 6 3.5 6 C2.5 2.5 7 1.5 8 3.5 C9 1 14 1.5 13 5 C15.5 5.5 15 10 12 10 Z"/>'),
    "value": lambda x, y, c: _g(x, y, c,
        '<ellipse cx="8" cy="6" rx="6.5" ry="4"/>'),
    # strategy
    "resource": lambda x, y, c: _g(x, y, c,
        '<rect x="1" y="2.5" width="12" height="7" rx="2"/><rect x="13" y="4.5" width="2" height="3"/>'
        '<line x1="4" y1="4.5" x2="4" y2="7.5"/><line x1="7" y1="4.5" x2="7" y2="7.5"/>'
        '<line x1="10" y1="4.5" x2="10" y2="7.5"/>'),
    "capability": lambda x, y, c: _g(x, y, c,
        '<path d="M2 11 V7.5 H5.5 V4.5 H9 V1 H12.5 V11 Z M2 11 H12.5 M5.5 7.5 H12.5 M9 4.5 H12.5 '
        'M5.5 7.5 V11 M9 4.5 V11"/>'),
    "valuestream": lambda x, y, c: _g(x, y, c,
        '<path d="M1 2 H11 L15 6 L11 10 H1 L5 6 Z"/>'),
    "courseofaction": lambda x, y, c: _g(x, y, c,
        '<circle cx="10" cy="4.5" r="3.6"/><circle cx="10" cy="4.5" r="1.6"/>'
        '<path d="M1 11.5 Q2 6 6.5 6.5"/><polyline points="4.8,4.6 6.8,6.5 4.6,8.2"/>'),
    # implementation & migration
    "workpackage": lambda x, y, c: _g(x, y, c,
        '<path d="M13 6 A5 4.5 0 1 1 9.5 1.6"/><polyline points="7.5,0 9.8,1.6 8,3.6"/>'),
    "deliverable": lambda x, y, c: _g(x, y, c,
        '<path d="M2 1.5 H14 V9 Q11 7 8 9 T2 9 Z"/>'),
    "plateau": lambda x, y, c: _g(x, y, c,
        '<line x1="5" y1="2.5" x2="15" y2="2.5" stroke-width="1.6"/>'
        '<line x1="3" y1="6" x2="13" y2="6" stroke-width="1.6"/>'
        '<line x1="1" y1="9.5" x2="11" y2="9.5" stroke-width="1.6"/>'),
    "gap": lambda x, y, c: _g(x, y, c,
        '<circle cx="8" cy="6" r="4.4"/><line x1="1.5" y1="4.5" x2="14.5" y2="4.5"/>'
        '<line x1="1.5" y1="7.5" x2="14.5" y2="7.5"/>'),
    "location": lambda x, y, c: _g(x, y, c,
        '<path d="M8 11.5 C4 7 3.5 5.5 3.5 4.5 A4.5 4.5 0 0 1 12.5 4.5 C12.5 5.5 12 7 8 11.5 Z"/>'
        '<circle cx="8" cy="4.5" r="1.5"/>'),
}
