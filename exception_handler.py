from fastapi import HTTPException, status


class AniException:

    def user_exception(self, username):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Not a MAL {username}")

    def user_field_empty_exception(self):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Provide valid MAL username")

    def category_exception(self):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid category")
