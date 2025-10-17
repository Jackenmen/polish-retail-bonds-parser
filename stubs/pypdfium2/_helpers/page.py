import pypdfium2.internal as pdfium_i
from pypdfium2._helpers.textpage import PdfTextPage


class PdfPage(pdfium_i.AutoCloseable):
    def get_textpage(self) -> PdfTextPage: ...
