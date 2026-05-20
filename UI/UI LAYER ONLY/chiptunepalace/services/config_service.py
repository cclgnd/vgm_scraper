import json
import os

class ConfigService:
    """
    Handles persistence of user settings like download directory.
    """
    def __init__(self, config_path="config.json"):
        self.config_path = config_path
        self.defaults = {
            "download_dir": os.path.abspath("downloads"),
            "shuffle": False,
            "volume": 80
        }
        self.config = self.defaults.copy()
        self.load()

    def load(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    self.config.update(json.load(f))
            except Exception as e:
                print(f"ConfigService: Load failed: {e}")

    def save(self):
        try:
            with open(self.config_path, "w") as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"ConfigService: Save failed: {e}")

    def get(self, key):
        return self.config.get(key, self.defaults.get(key))

    def set(self, key, value):
        self.config[key] = value
        self.save()
