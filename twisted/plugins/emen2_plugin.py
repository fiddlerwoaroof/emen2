from twisted.application.service import ServiceMaker

EMEN2Server = ServiceMaker(
    "EMEN2",
    "emen2.tap",
    ("The emen2 server"),
    "emen2")
