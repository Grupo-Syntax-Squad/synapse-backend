# from datetime import datetime
# from typing import Any
# from sqlalchemy import text
# from sqlalchemy.orm import Session
# from src.schemas.example import (
#     GetExampleResponse,
#     PostExampleRequest,
#     DeleteExampleRequest,
# )
# from src.schemas.basic_response import BasicResponse


# class GetExample:
#     def __init__(self, session: Session):
#         self._session = session

#     def execute(self) -> BasicResponse[list[GetExampleResponse]]:
#         self._get_examples()
#         response = self._format_response()
#         return BasicResponse(data=response)

#     def _get_examples(self) -> None:
#         with self._session as session:
#             query = text("""SELECT * FROM example""")
#             result = session.execute(query)
#             examples = result.fetchall()
#             self.result: list[dict[str, Any]] = [
#                 example._asdict() for example in examples
#             ]

#     def _format_response(self) -> list[GetExampleResponse]:
#         return [
#             GetExampleResponse(
#                 id=result["id"],
#                 name=result["name"],
#                 enabled=result["enabled"],
#                 created_at=result["created_at"].isoformat(),
#                 updated_at=result["updated_at"].isoformat(),
#             )
#             for result in self.result
#         ]


# class CreateExample:
#     def __init__(self, session: Session, example: PostExampleRequest):
#         self._session = session
#         self._example = example

#     def execute(self) -> BasicResponse[None]:
#         self._create_example()
#         return BasicResponse(message="Example created")

#     def _create_example(self) -> None:
#         with self._session as session:
#             example = Example(name=self._example.name, updated_at=datetime.now())
#             session.add(example)
#             session.commit()


# class DeleteExample:
#     def __init__(self, session: Session, example: DeleteExampleRequest):
#         self._session = session
#         self._example = example

#     def execute(self) -> BasicResponse[None]:
#         self._delete_example()
#         return BasicResponse(message="Example deleted")

#     def _delete_example(self) -> None:
#         with self._session as session:
#             query = text(
#                 """UPDATE example SET enabled = FALSE WHERE id=:id"""
#             ).bindparams(id=self._example.id)
#             session.execute(query)
