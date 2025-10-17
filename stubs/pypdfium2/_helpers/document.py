import pathlib
from collections.abc import Iterator
from typing import BinaryIO

import pypdfium2.internal as pdfium_i
from pypdfium2._helpers.page import PdfPage


class PdfDocument(pdfium_i.AutoCloseable):
    def __init__(
        self,
        input: str | pathlib.Path | bytes | BinaryIO,
        password: str | None = None,
        autoclose: bool = False,
    ) -> None: ...
    def __iter__(self) -> Iterator[PdfPage]: ...
