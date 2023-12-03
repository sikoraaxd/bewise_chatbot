import io
from PyPDF2 import PdfReader
from docx import Document as docx_doc
from base64 import b64decode, b64encode
import json
import re

from langchain.docstore.document import Document
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import Chroma

from sql import get_user_documents, update_user_documents


def clear_text(text):
    text = re.sub(r"(\w+)-\n(\w+)", r"\1\2", text)
    text = re.sub(r"(?<!\n\s)\n(?!\s\n)", " ", text.strip())
    text = re.sub(r"\n\s*\n", "\n\n", text)
    return text


def preprocess_pdf(file):
    pdf = PdfReader(file)
    output = []
    for page in pdf.pages:
        text = page.extract_text()
        text = clear_text(text)
        output.append(text)
    return output


def preprocess_doc(file):
    doc = docx_doc(file)
    output = []
    for paragraph in doc.paragraphs:
        text = clear_text(paragraph.text)
        if len(text):
            output.append(text)

    for table in doc.tables:
        table_text = ''
        for row in table.rows:
            row_text = ''
            for cell in row.cells:
                text = clear_text(cell.text)
                if len(text):
                    row_text += text + ' '
            table_text += row_text + '\n'
        output.append(table_text)
    return output


def text_to_docs(text):
    if isinstance(text, str):
        text = [text]

    page_docs = [Document(page_content=page) for page in text]
    for i, doc in enumerate(page_docs):
        doc.metadata["page"] = i + 1

    doc_chunks = []
    for doc in page_docs:
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=4000,
            separators=["\n\n", "\n", ".", "!", "?", ",", " ", ""],
            chunk_overlap=0.1,
            length_function=len,
        )
        chunks = text_splitter.split_text(doc.page_content)
        for i, chunk in enumerate(chunks):
            doc = Document(
                page_content=chunk, metadata={"page": doc.metadata["page"], "chunk": i}
            )
            doc.metadata["source"] = f"{doc.metadata['page']}-{doc.metadata['chunk']}"
            doc_chunks.append(doc)
    return doc_chunks


def docs_to_index(docs, openai_api_key):
    index = Chroma.from_documents(docs, OpenAIEmbeddings(openai_api_key=openai_api_key))
    return index


preprocess_functions = {
    'pdf': preprocess_pdf,
    'doc': preprocess_doc,
    'docx': preprocess_doc
}


def get_index(files, login, connection, openai_api_key, from_stored_data=False):
    documents = []
    if from_stored_data:
        stored_documents = get_user_documents(conn=connection, 
                                              login=login)
        if len(stored_documents) == 0:
            return None
        for elem in stored_documents:
            file_extension = elem['extension']
            _bytes = b64decode(elem['b64data'].encode('utf-8'))
            text = preprocess_functions[file_extension](io.BytesIO(_bytes))
            documents = documents + text_to_docs(text)
    else:
        stored_documents = []
        for file in files:
            file_extension = file.name.split('.')[-1].lower()
            if file_extension in preprocess_functions:
                _bytes = file.read()
                stored_documents.append({
                    'extension': file_extension,
                    'b64data': b64encode(_bytes).decode("utf-8")
                })
                text = preprocess_functions[file_extension](io.BytesIO(_bytes))
            else:
                return None
            documents = documents + text_to_docs(text)
        stored_data = json.dumps(stored_documents)
        update_user_documents(conn=connection, 
                            login=login,
                            new_documents=stored_data)
    index = docs_to_index(documents, openai_api_key)
    return index


def roles_cleaner(text):
    pattern = re.compile(r'^[A-Za-zА-Яа-я.]+[.:]? (.+)$')
    match = pattern.match(text)

    if match:
        return match.group(1)
    else:
        return text
