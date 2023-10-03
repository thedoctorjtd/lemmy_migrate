import sys
from time import sleep
from urllib.parse import urlparse

import requests


class Lemmy:
    _api_version = "v3"
    _api_base_url = f"api/{_api_version}"

    def __init__(self, url) -> None:
        parsed_url = urlparse(url)
        url_path = parsed_url.netloc if parsed_url.netloc else parsed_url.path
        self.site_url = (
            urlparse(url_path)._replace(scheme="https", netloc=url_path, path="").geturl()
        )
        self._auth_token = None
        self._user_communities = set()

    def login(self, user: str, password: str) -> None:
        """authenticate to instance"""
        payload = {"username_or_email": user, "password": password}

        try:
            resp = self._request_it(
                f"{self.site_url}/" f"{self._api_base_url}/user/login",
                method="POST",
                json=payload,
            )
            self._auth_token = resp.json()["jwt"]
        except Exception as e:
            self._println(1, f"[ERROR]: login() failed for {user}" f" on {self.site_url}")
            self._println(2, f"-Details: {e}")
            sys.exit(1)

    def get_communities(self, type: str = "Subscribed") -> list:
        """Get list of currently subscribed communites"""
        payload = {"type_": type, "auth": self._auth_token, "limit": 50, "page": 1}

        # iterate over each page if needed
        fetched = 50  # max limit
        while fetched == 50:
            try:
                resp = self._request_it(
                    f"{self.site_url}/" f"{self._api_base_url}/community/list",
                    params=payload,
                )
                fetched = len(resp.json()["communities"])
                payload["page"] += 1

                for comm in resp.json()["communities"]:
                    url = comm["community"]["actor_id"]
                    self._user_communities.add(url)
            except Exception as err:
                print(f"error: {err}")

        return self._user_communities

    def subscribe(self, communities: list) -> None:
        """Subscribe to a community. It will first attempt to
        resolve community.
        """
        payload = {"community_id": None, "follow": True, "auth": self._auth_token}

        for url in communities:
            try:
                # resolve community first
                comm_id = self.resolve_community(url)

                if comm_id:
                    payload["community_id"] = comm_id
                    self._println(2, f"> Subscribing to {url} ({comm_id})")
                    resp = self._request_it(
                        f"{self.site_url}/" f"{self._api_base_url}/" f"community/follow",
                        json=payload,
                        method="POST",
                    )

                    if resp.status_code == 200:
                        self._user_communities.add(comm_id)
                        self._println(3, f"> Succesfully subscribed" f" to {url} ({comm_id})")
            except Exception as e:
                print(f"   API error: {e}")

    def resolve_community(self, community: str) -> int | None:
        """resolve a community"""
        payload = {"q": community, "auth": self._auth_token}

        community_id = None
        self._println(1, f"> Resolving {community}")
        try:
            resp = self._request_it(
                f"{self.site_url}/" f"{self._api_base_url}/resolve_object",
                params=payload,
            )
            community_id = resp.json()["community"]["community"]["id"]
        except Exception as e:
            self._println(2, f"> Failed to resolve community {e}")

        return community_id

    def get_comments(self, post_id: str, max_depth: int = 1, limit: int = 1000) -> dict:
        """Get all comments for a post"""
        payload = {
            "post_id": post_id,
            "max_depth": max_depth,
            "limit": limit,
        }

        try:
            r = self._request_it(
                f"{self.site_url}/{self._api_base_url}/" f"comment/list", params=payload
            )
        except Exception as e:
            self._println(2, f"> Failed to get comment list")

        return r.json()["comments"]

    def _rate_limit(self):
        sleep(1)

    def _request_it(
        self, endpoint: str, method: str = "GET", params: str = None, json: dict = None
    ) -> requests.Response:
        self._rate_limit()
        try:
            r = requests.request(method, url=endpoint, params=params, json=json)
            r.raise_for_status()
            return r
        except requests.exceptions.HTTPError as e:
            raise
        except requests.exceptions.RequestException as e:
            raise

    def _println(self, indent, line):
        print(f"{' ' * indent}{line}")
