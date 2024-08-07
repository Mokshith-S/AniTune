from jikanpy import Jikan
import requests


class AniGetter():
    def __init__(self, username):
        self.user_name = username
        self.aniHunter = Jikan()

    def user_statistics(self, header):
        """
        :return
        list(total_entries, watching, completed, on_hold, dropped, plan_to_watch)
        """
        prey_url = f"https://api.jikan.moe/v4/users/{self.user_name}/statistics"
        aniPrey = requests.get(prey_url, headers=header, timeout=3)
        if aniPrey.status_code == 200:
            ani_res = aniPrey.json()
            prey = ani_res["data"]["anime"]
            scavenge = list(prey.values())[2:-2]
            fscavenge = [scavenge[-1], *scavenge[:-1]]
            return fscavenge

    def get_theme_songs(self, id):
        """
        Gets Opening and Ending themes songs of anime
        :param id: ID of the target anime
        :return: dict(opening_themes, ending_themes)
        """
        aniPrey = self.aniHunter.anime(id, extension="themes")["data"]
        return aniPrey
