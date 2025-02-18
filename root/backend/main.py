from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
import os
from typing import List

app = FastAPI()

UPLOAD_DIRECTORY = "project_root/data/uploads"

@app.post("/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    try:
        for file in files:
            file_extension = os.path.splitext(file.filename)[1]
            if file_extension not in [".ipynb", ".md"]:
                return JSONResponse(
                    content={"error": "Invalid file type. Only .ipynb and .md files are allowed."},
                    status_code=400,
                )
            file_path = os.path.join(UPLOAD_DIRECTORY, file.filename)
            with open(file_path, "wb") as f:
                f.write(await file.read())
        return JSONResponse(content={"message": "Files uploaded successfully"})
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)
