from jikanpy import Jikan


class AniGetter():
    def __init__(self, username):
        self.user_name = username
        self.aniHunter = Jikan()

    def user_statistics(self):
        """
        :return
        list(total_entries, watching, completed, on_hold, dropped, plan_to_watch)
        """
        aniPrey = self.aniHunter.users(username=self.user_name, extension="statistics")["data"]["anime"]
        scavenge = list(aniPrey.values())[2:-2]
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
