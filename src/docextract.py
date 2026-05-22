import pdfplumber
import hashlib
import docdatabase
from PyPDF2 import PdfReader


# Retrieve hash byte
def file_hash_bytes(data: bytes):
    return hashlib.sha256(data).hexdigest()


# ---- Converting TXT files to text ----
def index_txt_bytes(filename, data, conn, cur):
    TXT_LINES_PER_CHUNK = 10
    TXT_OVERLAP = 2
    lines = data.decode("utf-8", errors="ignore").splitlines()  # data arriving in binaries is being decoded
    i = 0
    while i < len(lines):
        start = i
        end = min(i + TXT_LINES_PER_CHUNK, len(lines))
        # the starting and ending lines are determined based on the increment value and the splitting interval, and that section is selected
        text = "\n".join(lines[start:end]).strip()

        if text:
            docdatabase.insert_row(cur, filename, "txt", None, start + 1, end, text)  # writing to the database
            conn.commit()
        i += TXT_LINES_PER_CHUNK - TXT_OVERLAP


# ---- Converting PDF files to text ----
def index_pdf_bytes(filename, data, conn, cur):
    PDF_CHARS_PER_CHUNK = 800
    PDF_OVERLAP = 200
    tmp_path = "/tmp/tmp_upload.pdf"
    with open(tmp_path, "wb") as f:
        f.write(data)
    extracted_any = False
    # ---------- primary: pdfplumber ----------
    with pdfplumber.open(tmp_path) as pdf:
        for page_no, page in enumerate(pdf.pages, start=1):
            text = None
            try:
                text = page.extract_text(x_tolerance=2, y_tolerance=2, layout=True)
            except Exception:
                   pass
            # If there is text, it is obtained in fragments
            if text and len(text.strip()) >= 20:
                extracted_any = True
                i = 0
                while i < len(text):  # the process of processing parts and printing them to the database
                    chunk = text[i:i + PDF_CHARS_PER_CHUNK].strip()
                    if chunk:
                        docdatabase.insert_row(cur, filename, "pdf", page_no, None, None, chunk)  # writing to the database
                        conn.commit()
                    i += PDF_CHARS_PER_CHUNK - PDF_OVERLAP
                continue

