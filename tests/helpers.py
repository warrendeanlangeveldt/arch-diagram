"""Shared test helpers: paths, model builders and the official XSDs."""
import copy
import json
import os
import shutil
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "skills", "arch-diagram", "scripts")
EXAMPLES = os.path.join(SCRIPTS, "examples")
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache")
sys.path.insert(0, SCRIPTS)

XSD = {
    "archimate": ("https://www.opengroup.org/xsd/archimate/3.1/",
                  ["archimate3_Model.xsd", "archimate3_View.xsd", "archimate3_Diagram.xsd"],
                  "archimate3_Diagram.xsd"),
    "bpmn": ("https://www.omg.org/spec/BPMN/20100501/",
             ["BPMN20.xsd", "Semantic.xsd", "BPMNDI.xsd", "DC.xsd", "DI.xsd"], "BPMN20.xsd"),
}


def example(name):
    with open(os.path.join(EXAMPLES, name, "model.json")) as f:
        return json.load(f)


def clone(m):
    return copy.deepcopy(m)


def schema(kind):
    """Local path of the official schema entry point, downloaded once into
    tests/.cache; None when offline or xmllint is missing."""
    if not shutil.which("xmllint"):
        return None
    base, files, entry = XSD[kind]
    d = os.path.join(CACHE, kind)
    os.makedirs(d, exist_ok=True)
    try:
        for fn in files:
            p = os.path.join(d, fn)
            if not os.path.exists(p):
                urllib.request.urlretrieve(base + fn, p)
        if kind == "archimate":
            xml = os.path.join(d, "xml.xsd")
            if not os.path.exists(xml):
                urllib.request.urlretrieve("https://www.w3.org/2001/xml.xsd", xml)
            mp = os.path.join(d, "archimate3_Model.xsd")
            with open(mp) as f:
                s = f.read()
            s = s.replace('schemaLocation="http://www.w3.org/2001/xml.xsd"', 'schemaLocation="xml.xsd"')
            with open(mp, "w") as f:
                f.write(s)
    except OSError:
        return None
    return os.path.join(d, entry)
