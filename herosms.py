import aiohttp
import json
import logging
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)


class HeroSMSError(Exception):
    pass

class NoNumbersError(HeroSMSError):
    pass

class InsufficientBalanceError(HeroSMSError):
    pass


class HeroSMSAPI:
    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url

    async def _get(self, params: Dict) -> str:
        params["api_key"] = self.api_key
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            async with session.get(self.base_url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                text = await resp.text()
                logger.info("HeroSMS %s → %s", params.get("action"), text[:200])
                return text.strip()

    async def get_balance(self) -> float:
        resp = await self._get({"action": "getBalance"})
        if resp.startswith("ACCESS_BALANCE:"):
            return float(resp.split(":")[1])
        raise HeroSMSError(f"getBalance שגיאה: {resp}")

    async def get_services_list(self) -> Dict[str, str]:
        """מחזיר {קוד: שם} לכל השירותים."""
        resp = await self._get({"action": "getServicesList"})
        try:
            data = json.loads(resp)
            if isinstance(data, list):
                return {item["code"]: item["name"] for item in data if "code" in item and "name" in item}
            if isinstance(data, dict):
                # פורמט חלופי: {code: name}
                return data
        except Exception as e:
            logger.error("getServicesList parse error: %s | resp: %s", e, resp[:300])
        return {}

    async def get_countries(self) -> List[Dict]:
        resp = await self._get({"action": "getCountries"})
        try:
            data = json.loads(resp)
            if isinstance(data, dict):
                return list(data.values())
            if isinstance(data, list):
                return data
        except Exception as e:
            logger.error("getCountries parse error: %s | resp: %s", e, resp[:300])
        return []

    async def get_prices(self, service: str = None, country: int = None) -> Dict:
        params: Dict[str, Any] = {"action": "getPrices"}
        if service:
            params["service"] = service
        if country is not None:
            params["country"] = country
        resp = await self._get(params)
        try:
            return json.loads(resp)
        except Exception:
            return {}

    async def get_numbers_status(self, country: int = 0) -> Dict[str, int]:
        resp = await self._get({"action": "getNumbersStatus", "country": country})
        try:
            return json.loads(resp)
        except Exception:
            return {}

    async def get_number(self, service: str, country: int) -> Dict:
        params: Dict[str, Any] = {"action": "getNumber", "service": service, "country": country}
        resp = await self._get(params)
        if resp.startswith("ACCESS_NUMBER:"):
            parts = resp.split(":")
            return {"activation_id": parts[1], "phone_number": parts[2]}
        if "NO_NUMBERS" in resp:
            raise NoNumbersError("אין מספרים זמינים לשירות/מדינה זו.")
        if "NO_BALANCE" in resp:
            raise InsufficientBalanceError("יתרה לא מספיקה בחשבון HeroSMS.")
        raise HeroSMSError(f"getNumber שגיאה: {resp}")

    async def set_status(self, activation_id: str, status: int) -> str:
        resp = await self._get({"action": "setStatus", "id": activation_id, "status": status})
        return resp

    async def get_status(self, activation_id: str) -> Dict:
        resp = await self._get({"action": "getStatus", "id": activation_id})
        if resp.startswith("STATUS_OK:"):
            return {"status": "STATUS_OK", "code": resp.split(":", 1)[1]}
        return {"status": resp, "code": None}

    async def cancel_activation(self, activation_id: str) -> bool:
        resp = await self.set_status(activation_id, 8)
        return "ACCESS_CANCEL" in resp or resp == "1"

    async def complete_activation(self, activation_id: str) -> bool:
        resp = await self.set_status(activation_id, 6)
        return "ACCESS_ACTIVATION" in resp or resp == "1"
