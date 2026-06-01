from upstash_redis import Redis

from app.config.settings import settings


class Cache:

    def __init__(self):

        self.client = Redis(
            url=settings.UPSTASH_REDIS_REST_URL,
            token=settings.UPSTASH_REDIS_REST_TOKEN
        )

    def set(
        self,
        key,
        value
    ):

        self.client.set(
            key,
            value
        )

    def get(
        self,
        key
    ):

        return self.client.get(
            key
        )

    def delete(
        self,
        key
    ):

        self.client.delete(
            key
        )


cache = Cache()