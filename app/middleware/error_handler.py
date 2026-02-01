from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError
import traceback

def add_exception_handlers(app: FastAPI):
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "message": exc.detail,
                "code": f"HTTP_{exc.status_code}"
            }
        )
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        errors = []
        for error in exc.errors():
            field = ".".join([str(loc) for loc in error["loc"]])
            errors.append(f"{field}: {error['msg']}")
        
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "message": "Validation error",
                "errors": errors,
                "code": "VALIDATION_ERROR"
            }
        )
    
    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"SQLAlchemy error: {str(exc)}")
        logger.error(traceback.format_exc())
        
        # Provide more detailed error message
        error_msg = str(exc)
        if "NOT NULL constraint" in error_msg or "null value" in error_msg.lower():
            error_msg = "Database error: Required field is missing. Please check all required fields are provided."
        elif "UNIQUE constraint" in error_msg:
            error_msg = "Database error: Duplicate entry. This record already exists."
        else:
            error_msg = f"Database error occurred: {error_msg}"
        
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": error_msg,
                "code": "DATABASE_ERROR"
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        # Log the error
        traceback.print_exc()
        error_message = str(exc)
        
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"An unexpected error occurred: {error_message}",
                "code": "INTERNAL_ERROR"
            }
        )
