import os
import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel
from typing import Optional, Any

router = APIRouter()

MAX_FILE_BYTES = 5 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png"}


def get_current_user_id() -> str:
    return "user-123"

class JobResponse(BaseModel):
    job_id: str
    status: str
    message: Optional[str] = None
    prediction: Optional[str] = None
    extra_info: Optional[Any] = None
    error_message: Optional[str] = None


_JOBS = {} 

def _save_upload_to_disk(job_id: str, upload: UploadFile) -> str:
    os.makedirs("media", exist_ok=True)
        ext = ".jpg" if upload.content_type == "image/jpeg" else ".png"
    path = os.path.join("media", f"{job_id}{ext}")
    with open(path, "wb") as f:
        f.write(upload.file.read())
    return path

def _run_model(file_path: str) -> tuple[str, dict]:
    # TODO: здесь ваш инференс
    # возвращаем (prediction, extra_info)
    return "Это кот породы: Мейн-кун", {"confidence": 0.93, "top_k": ["Мейн-кун", "Сибирская", "Британская"]}

def _process_job(job_id: str) -> None:
    job = _JOBS[job_id]
    try:
        pred, extra = _run_model(job["file_path"])
        job["status"] = "done"
        job["prediction"] = pred
        job["extra_info"] = extra
    except Exception:
        job["status"] = "failed"
        job["error_message"] = "Не удалось обработать изображение. Попробуйте снова."

@router.post("/jobs", response_model=JobResponse)
async def create_job(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
):
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Неверный формат файла. Разрешены: image/jpeg, image/png.",
        )

    # Проверка размера (упрощённо). Для больших файлов лучше потоковый контроль.
    contents = await file.read()
    if len(contents) > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=400,
            detail="Файл слишком большой. Максимальный размер: 5MB.",
        )

    # Вернём указатель в начало, т.к. read() уже прочитал
    file.file.seek(0)

    job_id = str(uuid.uuid4())
    file_path = _save_upload_to_disk(job_id, file)

    _JOBS[job_id] = {
        "job_id": job_id,
        "user_id": user_id,
        "status": "processing",
        "file_path": file_path,
        "prediction": None,
        "extra_info": None,
        "error_message": None,
    }

    background_tasks.add_task(_process_job, job_id)

    return JobResponse(
        job_id=job_id,
        status="processing",
        message="Идёт распознавание вашего кота...",
    )

@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, user_id: str = Depends(get_current_user_id)):
    job = _JOBS.get(job_id)
    if not job or job["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Задание не найдено.")

    if job["status"] == "processing":
        return JobResponse(job_id=job_id, status="processing", message="Идёт распознавание вашего кота...")

    if job["status"] == "failed":
        return JobResponse(
            job_id=job_id,
            status="failed",
            error_message=job["error_message"] or "Не удалось обработать изображение. Попробуйте снова.",
        )

    return JobResponse(
        job_id=job_id,
        status="done",
        prediction=job["prediction"],
        extra_info=job["extra_info"],
    )

@router.get("/jobs", response_model=list[JobResponse])
async def list_jobs(limit: int = 20, offset: int = 0, user_id: str = Depends(get_current_user_id)):
    items = [j for j in _JOBS.values() if j["user_id"] == user_id]
    items = items[offset : offset + limit]
    # В истории обычно достаточно status + prediction (если есть)
    return [
        JobResponse(
            job_id=j["job_id"],
            status=j["status"],
            prediction=j.get("prediction"),
            extra_info=j.get("extra_info"),
            error_message=j.get("error_message"),
            message="Идёт распознавание вашего кота..." if j["status"] == "processing" else None,
        )
        for j in items
    ]


