from fastapi import HTTPException, status


class AniException:

    def user_exception(self, username):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Not a MAL {username}")

    def user_field_empty_exception(self):
        raise HTTPException(status_code=status.HTTP_204_NO_CONTENT, detail=f"Provide valid MAL username")

    def category_exception(self):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid category")

    def empty_category_exception(self, category):
        raise HTTPException(status_code=status.HTTP_204_NO_CONTENT, detail=f"{category} is empty")

    def anime_range_exception(self):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Exceeded category anime range")
