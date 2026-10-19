"""BPMN collaboration for case lodgement, plus its BPMN 2.0 XML.

    python3 lodgement.py    # writes out/LODGEMENT.svg|html|png|objects.json
                            # and out/case-lodgement.bpmn
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
from ealib import load_model, make_theme, validate  # noqa: E402
from ealib.bpmn import BpmnView, write_bpmn_xml  # noqa: E402

model = load_model(os.path.join(HERE, "model.json"))
for w in validate(model)["warnings"]:
    print("warning:", w)
v = BpmnView(model, "LODGEMENT", title="Case lodgement: collaboration",
             theme=make_theme(width=960))
OUT = os.path.join(HERE, "out")

cust = v.pool("P-CUST", 16, 16, 928, 60)
svc = v.pool("P-SVC", 16, 116, 928, 430)
agent = v.lane("L-AGENT", svc["x"], 116, svc["w"], 230)
sys_ = v.lane("L-SYS", svc["x"], 346, svc["w"], 200)
A, S = 180, 420                                  # row centres: agent, system

start = v.event("E-START", 100, S)
reg = v.task("T-REG", 140, S - 32)
tri = v.gateway("G-TRIAGE", 300, S, label="above-right")
v.flow([(start["r"], S), (reg["x"] - 2, S)], ("E-START", "sequenceFlow", "T-REG"))
v.flow([(reg["r"], S), (tri["x"] - 2, S)], ("T-REG", "sequenceFlow", "G-TRIAGE"))

# no: ask the customer, then wait
req = v.task("T-REQ", 360, A - 32)
hold = v.event("E-HOLD", 520, A)
v.flow([(300, tri["y"]), (300, A), (req["x"] - 2, A)], ("G-TRIAGE", "sequenceFlow", "T-REQ"),
       label=(306, A + 60), label_anchor="start")
v.flow([(req["r"], A), (hold["x"] - 2, A)], ("T-REQ", "sequenceFlow", "E-HOLD"))

# yes: assess, with a non-interrupting SLA timer
ass = v.task("T-ASSESS", 610, A - 32)
v.flow([(tri["r"], S), (580, S), (580, A), (ass["x"] - 2, A)], ("G-TRIAGE", "sequenceFlow", "T-ASSESS"),
       label=(440, S - 6))
sla = v.event("B-SLA", 640, ass["b"], label=None)
v.text(662, ass["b"] + 14, "5 days", 8.5, v.t["ink"], weight=600)
esc = v.task("T-ESC", 610, 260)
v.flow([(640, sla["b"]), (640, esc["y"] - 2)], ("B-SLA", "sequenceFlow", "T-ESC"))
eesc = v.event("E-ESC", 790, esc["cy"])
v.flow([(esc["r"], esc["cy"]), (eesc["x"] - 2, esc["cy"])], ("T-ESC", "sequenceFlow", "E-ESC"))

# outcome
note = v.task("T-NOTIFY", 784, S - 32)
v.flow([(ass["r"], A), (840, A), (840, note["y"] - 2)], ("T-ASSESS", "sequenceFlow", "T-NOTIFY"))
end = v.event("E-END", 840, 500)
v.flow([(840, note["b"]), (840, end["y"] - 2)], ("T-NOTIFY", "sequenceFlow", "E-END"))

# data and annotation
case = v.data("D-CASE", 181, reg["b"] + 16)
v.flow([(196, reg["b"]), (196, case["y"] - 2)], ("T-REG", "dataOutput", "D-CASE"))
ann = v.annotation("A-TRIAGE", 360, 470, 190)
v.flow([(ann["x"], ann["cy"]), (tri["cx"], tri["b"] + 1)], ("A-TRIAGE", "association", "G-TRIAGE"))

# message flows between the pools
v.flow([(100, cust["b"] + 2), (100, start["y"] - 2)], ("P-CUST", "messageFlow", "E-START"),
       label=(104, 96), label_anchor="start")
v.flow([(416, req["y"]), (416, cust["b"] + 2)], ("T-REQ", "messageFlow", "P-CUST"),
       label=(420, 96), label_anchor="start")
v.flow([(880, note["y"]), (880, cust["b"] + 2)], ("T-NOTIFY", "messageFlow", "P-CUST"),
       label=(884, 96), label_anchor="start")

y = v.legend(svc["b"] + 20)
for p in v.save(y + 4, OUT):
    print(p)
print(write_bpmn_xml(model, os.path.join(OUT, "case-lodgement.bpmn"), view=v))
