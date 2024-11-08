import asyncio
import aiohttp

from core.utils import logger
class BaseClient:
    def __init__(self, user_agent: str, proxy: str = None):
        self.session = None
        self.ip = None
        self.username = None
        self.proxy = None

        self.user_agent = user_agent
        self.proxy = proxy

        self.website_headers = {
            'authority': 'api.getgrass.io',
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'en-US,en;q=0.9',
            'content-type': 'application/json',
            'origin': 'https://app.getgrass.io',
            'referer': 'https://app.getgrass.io/',
            'sec-ch-ua': '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'user-agent': self.user_agent
        }

    async def _make_request(self, method, url, **kwargs):
        kwargs['proxy'] = self.proxy
        kwargs['timeout'] = aiohttp.ClientTimeout(total=15)
        
        try:
            async with self.session.request(method, url, **kwargs) as response:
                await response.read()
                return response
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.error(f"Connection failed: {e}")
            raise

        finally:
            await self.session.close()

