from locust import HttpUser, task, between
from uuid import uuid4


class SynapseUser(HttpUser):
    host = "http://localhost:8000"
    wait_time = between(1, 3)

    def on_start(self):
        """
        Create a new user (unique email) and login to obtain auth cookies for subsequent requests.
        If registration fails because it already exists, we skip and try to login anyway.
        """
        self.email = f"perf_{uuid4().hex}@example.com"
        self.password = "password123"
        self.username = "perf_user"

        try:
            self.client.post(
                "/users/register",
                json={"username": self.username, "email": self.email, "password": self.password},
            )
        except Exception:
            pass
        resp = self.client.post(
            "/auth/login",
            json={"email": self.email, "password": self.password},
            allow_redirects=True,
        )
        if resp.status_code == 200:
            self.access_cookie = resp.cookies.get("access_token")
            self.refresh_cookie = resp.cookies.get("refresh_token")
            # build a cookie header string to bypass 'secure' flags for plain HTTP load testing
            self.cookie_header = (
                f"access_token={self.access_cookie}; refresh_token={self.refresh_cookie}"
            )
        else:
            self.access_cookie = None
            self.refresh_cookie = None
            self.cookie_header = None

    @task(3)
    def get_root(self):
        self.client.get("/")

    @task(5)
    def list_users(self):
        self.client.get("/users")

    @task(4)
    def me(self):
        if not self.access_cookie:
            resp = self.client.post(
                "/auth/login",
                json={"email": self.email, "password": self.password},
            )
            if resp.status_code == 200:
                self.access_cookie = resp.cookies.get("access_token")
        headers = {"Cookie": self.cookie_header} if getattr(self, "cookie_header", None) else None
        if headers:
            self.client.get("/users/me", headers=headers)
        else:
            self.client.get("/users/me")

    @task(2)
    def chat_history(self):
        self.client.get("/chat_history/", params={"user_id": 1})

    @task(2)
    def get_reports(self):
        self.client.get("/reports/")

    @task(1)
    def get_report_by_id(self):
        self.client.get("/reports/1")