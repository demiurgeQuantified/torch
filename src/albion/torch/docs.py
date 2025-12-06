"""
This whole thing is stupid and making the code way more complex.
The idea was that docs should be optional to save memory when they don't exist.
I'm not convinced it actually saves much, and it makes things harder at every step.
"""


class Deprecable:
    def __init__(self) -> None:
        super().__init__()
        self.deprecated: bool = False
        self.deprecation_message: str = ""


class Nameable:
    def __init__(self) -> None:
        super().__init__()
        self.name: str = ""


class DocNode:
    def __init__(self) -> None:
        super().__init__()
        self.notes: str = ""


class DocExecutable(DocNode, Deprecable):
    def __init__(self) -> None:
        super().__init__()


class DocConstructor(DocExecutable):
    pass


class DocMethod(DocExecutable):
    def __init__(self) -> None:
        super().__init__()


class DocClass(DocNode, Deprecable):
    def __init__(self) -> None:
        super().__init__()


class DocField(DocNode, Deprecable):
    def __init__(self) -> None:
        super().__init__()
