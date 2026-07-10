import requests
from requests.adapters import HTTPAdapter, Retry


def get_http_session() -> requests.Session:
    session = requests.Session()

    retries = Retry(
        total=5,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )

    adapter = HTTPAdapter(max_retries=retries, pool_connections=20, pool_maxsize=20)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    return session


SESSION = get_http_session()
DEFAULT_TIMEOUT = (5, 30)  # (connect timeout, read timeout)
