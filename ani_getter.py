import srsly

class AniMemory:
    def __init__(self):
        self.memory = srsly.read_json(r"D:\AniTune\ani_memory.json")

    def check_memory(self, song_id):
        return song_id in self.memory

    def add_song_memory(self, song_id, track_id):
        self.memory[song_id] = track_id
