from typing import Annotated, Dict, List, TypedDict
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pdfplumber
from io import BytesIO


app = FastAPI(title="Timetable-Parser API", description="API for parsing timetables from pdf file.", version="1.0.0")

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

def extract_pdf_data(pdf_file: UploadFile):
    json_output: Dict[str, Dict[str, List[Entry]]] = {tag: {} for tag in weekdays}
    class_name = None

    pdf_data = pdf_file.file.read()
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
                hour = row[0].strip(".") if row[0] else None
                if not hour:
                    continue

                for i, cell in enumerate(row[1:], start=1):
                    day_index = (i - 1) // 2
                    if day_index >= len(weekdays):
                        continue

                    day = weekdays[day_index]

                    if cell is None or cell.strip() == "":
                        continue

                    blocks = cell.strip().split("\n")

                    for j in range(0, len(blocks), 2):
                        try:
                            class_subject = blocks[j]
                            teacher_room = blocks[j + 1] if j + 1 < len(blocks) else ""
                        except IndexError:
                            continue

                        if "--" in class_subject:
                            class_parts = class_subject.split("--")
                            school_class = class_parts[0].strip()
                            school_subject = class_parts[1].strip() if len(class_parts) > 1 else ""
                        else:
                            school_class = class_subject.strip()
                            school_subject = ""

                        if "--" in teacher_room:
                            teacher_parts = teacher_room.split("--")
                            school_teacher = teacher_parts[0].strip()
                            school_room = teacher_parts[1].strip() if len(teacher_parts) > 1 else ""
                        else:
                            school_teacher = teacher_room.strip()
                            school_room = ""

                        if "/" in school_class:
                            class_parts = school_class.split("/")
                            base_class = class_parts[0].strip()
                            group = class_parts[1].strip().upper() if len(class_parts) > 1 else ""
                            if group == "A":
                                specialization = 2
                            elif group == "B":
                                specialization = 3
                            else:
                                specialization = 1
                        else:
                            base_class = school_class.strip()
                            specialization = 1

                        if class_name is None:
                            class_name = base_class

                        entry: Entry = {
                            "subject": school_subject,
                            "teacher": school_teacher,
                            "room": school_room,
                            "specialization": specialization
                        }

                        if day not in json_output:
                            json_output[day] = {}
                        if hour not in json_output[day]:
                            json_output[day][hour] = []

                        merged = False
                        for existing in json_output[day][hour]:
                            if (existing["subject"] == school_subject and
                                existing["teacher"] == school_teacher and
                                existing["room"] == school_room):

                                if {existing["specialization"], specialization} == {2, 3}:
                                    existing["specialization"] = 1
                                    merged = True
                                    break

                        if not merged:
                            json_output[day][hour].append(entry)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error processing the PDF file.")

    return json_output, class_name


@app.post("/upload",
        summary="Upload pdf timetables",
        description="Upload a pdf file and extract all the information from the timetable. The pdf file has to include a table.")
async def upload_file(file: Annotated[UploadFile, File(description="pdf file with timetable")]):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are allowed.")
    
    timetable, class_name = extract_pdf_data(file)
    
    return JSONResponse(content={
        "class": class_name,
        "timetable": timetable
    })