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
        self.parameters: list[DocParameter] = []


class DocConstructor(DocExecutable):
    pass


class DocParameter(DocNode, Nameable):
    def __init__(self) -> None:
        super().__init__()


class DocReturn(DocNode, Nameable):
    def __init__(self) -> None:
        super().__init__()


class DocMethod(DocExecutable):
    def __init__(self) -> None:
        super().__init__()
        self.returns: DocReturn | None = None


class DocClass(DocNode, Deprecable):
    def __init__(self) -> None:
        super().__init__()


class DocField(DocNode, Deprecable):
    def __init__(self) -> None:
        super().__init__()
