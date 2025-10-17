import pypdfium2.internal as pdfium_i


class PdfTextPage(pdfium_i.AutoCloseable):
    def get_text_bounded(
        self,
        left: float | None = None,
        bottom: float | None = None,
        right: float | None = None,
        top: float | None = None,
        errors: str = "ignore",
    ) -> str: ...
