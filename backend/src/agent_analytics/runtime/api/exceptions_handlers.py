from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

class BadRequestException(Exception):
    pass

class ValidationException(Exception):
    pass

class NotFoundException(Exception):
    pass

def setup_exception_handlers(app: FastAPI):
    @app.exception_handler(BadRequestException)
    async def bad_request_handler(request: Request, exc: BadRequestException):
        return JSONResponse(
            status_code=400,
            content={"detail": str(exc)}
        )

    @app.exception_handler(ValidationException)
    async def validation_error_handler(request: Request, exc: ValidationException):
        return JSONResponse(
            status_code=422,
            content={"detail": str(exc)}
        )

    @app.exception_handler(NotFoundException)
    async def not_found_error_handler(request: Request, exc: NotFoundException):
        return JSONResponse(
            status_code=404,
            content={"detail": str(exc)}
        )