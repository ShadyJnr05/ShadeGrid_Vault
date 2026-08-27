import os

METADATA_FILE = "files_metadata.csv"
STORAGE_DIR = "uploaded_files"


class FileRecord:
    def __init__(self, filename, owner, visibility):
        # Double underscore triggers Python's "name mangling" — these attributes
        # become _FileRecord__filename internally, which makes them awkward to
        # reach from outside the class by accident. This is Python's version of
        # "private" attributes: real encapsulation, not just a convention.
        self.__filename = filename
        self.__owner = owner
        self.__visibility = visibility  # "public" or "private"

    def get_filename(self):
        return self.__filename

    def get_owner(self):
        return self.__owner

    def get_visibility(self):
        return self.__visibility

    def can_be_accessed_by(self, username):
        # This is the ONLY place that decides who can see this file.
        # No other code — not the server, not FileStore — is allowed
        # to peek at __visibility or __owner directly and decide for itself.
        if self.__visibility == "public":
            return True
        return username == self.__owner


class FileStore:
    def __init__(self):
        # __records is also private — outside code can only interact with it
        # through upload(), list_available(), and download() below.
        self.__records = {}
        os.makedirs(STORAGE_DIR, exist_ok=True)
        self.__load_metadata()

    def __load_metadata(self):
        if not os.path.exists(METADATA_FILE):
            return
        with open(METADATA_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                stored_name, filename, owner, visibility = line.split(",")
                self.__records[stored_name] = FileRecord(filename, owner, visibility)

    def __save_metadata_line(self, stored_name, record):
        with open(METADATA_FILE, "a") as f:
            f.write(f"{stored_name},{record.get_filename()},{record.get_owner()},{record.get_visibility()}\n")

    def upload(self, owner, filename, file_bytes, visibility):
        # Prefix with the owner's username so two users uploading "notes.txt"
        # don't overwrite each other on disk.
        stored_name = f"{owner}_{filename}"
        filepath = os.path.join(STORAGE_DIR, stored_name)

        with open(filepath, "wb") as f:
            f.write(file_bytes)

        record = FileRecord(filename, owner, visibility)
        self.__records[stored_name] = record
        self.__save_metadata_line(stored_name, record)

        return True, f"'{filename}' uploaded as {visibility}."

    def list_available(self, requesting_user):
        # Only ever returns files this user is ALLOWED to see. The actual
        # permission check happens inside FileRecord, not here — this method
        # just asks each record "can this user see you?"
        visible = []
        for stored_name, record in self.__records.items():
            if record.can_be_accessed_by(requesting_user):
                visible.append((stored_name, record.get_filename(), record.get_owner(), record.get_visibility()))
        return visible

    def download(self, requesting_user, stored_name):
        if stored_name not in self.__records:
            return False, "File not found.", None

        record = self.__records[stored_name]

        if not record.can_be_accessed_by(requesting_user):
            return False, "You don't have permission to access this file.", None

        filepath = os.path.join(STORAGE_DIR, stored_name)
        with open(filepath, "rb") as f:
            file_bytes = f.read()

        return True, "File found.", file_bytes