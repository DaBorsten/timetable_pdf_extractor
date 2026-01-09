from typing import Annotated, Dict, List, TypedDict
from contextlib import asynccontextmanager
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pdfplumber
from io import BytesIO
import asyncio
from concurrent.futures import ThreadPoolExecutor
import functools

# Thread pool for CPU-intensive PDF processing
executor = ThreadPoolExecutor(max_workers=4)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: executor is already created
    yield
    # Shutdown: clean up the executor
    executor.shutdown(wait=True)

app = FastAPI(
    title="Timetable-Parser API",
    description="API for parsing timetables from pdf file.",
    version="1.0.0",
    lifespan=lifespan
)

origins = [
    "http://localhost:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

weekdays = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag"]

class Entry(TypedDict):
    subject: str
    teacher: str
    room: str
    specialization: int

def extract_pdf_data_sync(pdf_data: bytes):
    """Synchronous PDF processing function to be run in thread pool"""
    json_output: Dict[str, Dict[str, List[Entry]]] = {tag: {} for tag in weekdays}
    class_name = None
    weekdays_len = len(weekdays)
    
    try:
        with pdfplumber.open(BytesIO(pdf_data)) as pdf:
            page = pdf.pages[0]
            table = page.extract_table({
                "vertical_strategy": "lines",
                "horizontal_strategy": "lines"
            })

            if table is None:
                raise ValueError("No table found in the PDF.")

            hour_rows = table[3:]

            for row in hour_rows:
                # Optimize: avoid multiple method calls
                first_cell = row[0]
                if not first_cell:
                    continue
                hour = first_cell.strip(".")
                if not hour:
                    continue

                for i, cell in enumerate(row[1:], start=1):
                    day_index = (i - 1) // 2
                    if day_index >= weekdays_len:
                        continue

                    day = weekdays[day_index]

                    # Optimize: check None first (cheaper than strip)
                    if not cell or not cell.strip():
                        continue

                    blocks = cell.strip().split("\n")

                    for j in range(0, len(blocks), 2):
                        class_subject = blocks[j]
                        teacher_room = blocks[j + 1] if j + 1 < len(blocks) else ""

                        # Optimize: split with maxsplit for performance
                        if "--" in class_subject:
                            class_parts = class_subject.split("--", 1)
                            school_class = class_parts[0].strip()
                            school_subject = class_parts[1].strip()
                        else:
                            school_class = class_subject.strip()
                            school_subject = ""

                        if "--" in teacher_room:
                            teacher_parts = teacher_room.split("--", 1)
                            school_teacher = teacher_parts[0].strip()
                            school_room = teacher_parts[1].strip()
                        else:
                            school_teacher = teacher_room.strip()
                            school_room = ""

                        # Optimize: direct assignment for group specialization
                        if "/" in school_class:
                            class_parts = school_class.split("/", 1)
                            base_class = class_parts[0].strip()
                            group = class_parts[1].strip().upper()
                            specialization = 2 if group == "A" else 3 if group == "B" else 1
                        else:
                            base_class = school_class.strip()
                            specialization = 1

                        if class_name is None:
                            class_name = base_class

                        # Optimize: use setdefault to reduce dict lookups
                        day_dict = json_output.setdefault(day, {})
                        hour_list = day_dict.setdefault(hour, [])

                        # Optimize: check for merge before creating entry
                        merged = False
                        for existing in hour_list:
                            if (existing["subject"] == school_subject and
                                existing["teacher"] == school_teacher and
                                existing["room"] == school_room and
                                {existing["specialization"], specialization} == {2, 3}):
                                existing["specialization"] = 1
                                merged = True
                                break

                        if not merged:
                            hour_list.append({
                                "subject": school_subject,
                                "teacher": school_teacher,
                                "room": school_room,
                                "specialization": specialization
                            })

    except ValueError as e:
        raise
    except Exception as e:
        raise RuntimeError("Error processing the PDF file.") from e

    return json_output, class_name


async def extract_pdf_data(pdf_file: UploadFile):
    """Async wrapper that runs PDF extraction in thread pool"""
    pdf_data = await pdf_file.read()
    loop = asyncio.get_running_loop()
    # Run CPU-intensive work in thread pool to avoid blocking the event loop
    try:
        return await loop.run_in_executor(
            executor,
            functools.partial(extract_pdf_data_sync, pdf_data)
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Unexpected error processing the PDF file.")


@app.post("/upload",
        summary="Upload pdf timetables",
        description="Upload a pdf file and extract all the information from the timetable. The pdf file has to include a table.")
async def upload_file(file: Annotated[UploadFile, File(description="pdf file with timetable")]):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are allowed.")
    
    timetable, class_name = await extract_pdf_data(file)
    
    return JSONResponse(content={
        "class": class_name,
        "timetable": timetable
    })