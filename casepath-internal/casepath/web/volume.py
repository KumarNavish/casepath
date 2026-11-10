"""A Databricks Unity Catalog volume through the workspace Files API: list a folder, read and write a file."""
from urllib.parse import quote

import httpx


class VolumeError(RuntimeError):
    pass


class VolumeClient:
    def __init__(self, host, token, *, transport=None, timeout=300):
        self.host, self.token = host.rstrip("/"), token
        self._client = httpx.Client(timeout=timeout, transport=transport)

    def _call(self, method, kind, path, **kwargs):
        response = self._client.request(method, f"{self.host}/api/2.0/fs/{kind}{quote(path)}",
                                        headers={"Authorization": "Bearer " + self.token()}, **kwargs)
        if response.status_code == 404:
            return None
        if response.status_code >= 300:
            raise VolumeError(f"The volume answered {response.status_code} for {kind}.")
        return response

    def list(self, path):
        """Entries of a folder: path, is_directory and file_size; empty when the folder does not exist."""
        entries, token = [], None
        while True:
            response = self._call("GET", "directories", path, params={"page_token": token} if token else None)
            if response is None:
                return entries
            body = response.json()
            entries += body.get("contents", [])
            token = body.get("next_page_token")
            if not token:
                return entries

    def get(self, path):
        response = self._call("GET", "files", path)
        return None if response is None else response.content

    def put(self, path, data):
        self._call("PUT", "files", path, params={"overwrite": "true"}, content=data)
