class PdfiumError(RuntimeError):
    err_code: int | None

    def __init__(self, msg: str, err_code: int | None = None) -> None: ...
