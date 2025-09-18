from fastapi import HTTPException, status
from src.logger_instance import logger
from src.schemas.basic_response import BasicResponse


class GetRoot:
    def execute(self) -> BasicResponse[None]:
        try:
            logger.info("Processing root")
            logger.info("Processed root successfully")
            return BasicResponse(message="Hello World")
        except HTTPException as e:
            raise e
        except Exception as e:
            logger.error(f"Error processing root: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ocorreu um erro inesperado tente novamente mais tarde",
            )
