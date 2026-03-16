"""
HeroSMS API wrapper.
Compatible with the SMS-Activate REST protocol used by hero-sms.com.
"""

import aiohttp
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
        async with aiohttp.ClientSession() as session:
            async with session.get(self.base_url, params=params) as resp:
                text = await resp.text()
                logger.debug("HeroSMS %s → %s", params.get("action"), text[:120])
                return text.strip()

    # ── Balance ────────────────────────────────────────────────────────────────

    async def get_balance(self) -> float:
        """Returns current HeroSMS account balance in USD."""
        resp = await self._get({"action": "getBalance"})
        if resp.startswith("ACCESS_BALANCE:"):
            return float(resp.split(":")[1])
        raise HeroSMSError(f"getBalance error: {resp}")

    # ── Services & countries ───────────────────────────────────────────────────

    async def get_services_list(self) -> Dict[str, str]:
        """Returns dict of {service_code: service_name}."""
        resp = await self._get({"action": "getServicesList"})
        # Response is JSON array of {name, code} objects
        import json
        try:
            data = json.loads(resp)
            if isinstance(data, list):
                return {item["code"]: item["name"] for item in data}
            return {}
        except Exception:
            return {}

    async def get_countries(self) -> List[Dict]:
        """Returns list of {id, rus, eng, chn, visible, retry, multiService, freeprice}."""
        resp = await self._get({"action": "getCountries"})
        import json
        try:
            data = json.loads(resp)
            if isinstance(data, dict):
                return list(data.values())
            return data if isinstance(data, list) else []
        except Exception:
            return []

    async def get_prices(self, service: str = None, country: int = None) -> Dict:
        """Returns pricing dict. Can filter by service and/or country."""
        params: Dict[str, Any] = {"action": "getPrices"}
        if service:
            params["service"] = service
        if country is not None:
            params["country"] = country
        resp = await self._get(params)
        import json
        try:
            return json.loads(resp)
        except Exception:
            return {}

    async def get_numbers_status(self, country: int = 0) -> Dict[str, int]:
        """Returns available number counts per service for a country."""
        resp = await self._get({"action": "getNumbersStatus", "country": country})
        import json
        try:
            return json.loads(resp)
        except Exception:
            return {}

    # ── Number lifecycle ───────────────────────────────────────────────────────

    async def get_number(self, service: str, country: int, max_price: float = None) -> Dict:
        """
        Request a new number.
        Returns {"activation_id": str, "phone_number": str}
        """
        params: Dict[str, Any] = {"action": "getNumber", "service": service, "country": country}
        if max_price is not None:
            params["maxPrice"] = max_price
        resp = await self._get(params)
        if resp.startswith("ACCESS_NUMBER:"):
            parts = resp.split(":")
            return {"activation_id": parts[1], "phone_number": parts[2]}
        if resp == "NO_NUMBERS":
            raise NoNumbersError("No numbers available for this service/country.")
        if resp == "NO_BALANCE":
            raise InsufficientBalanceError("Insufficient HeroSMS balance.")
        raise HeroSMSError(f"getNumber error: {resp}")

    async def set_status(self, activation_id: str, status: int) -> str:
        """
        Update activation status.
        1 = SMS sent, ready
        3 = Request another code (free)
        6 = Complete activation
        8 = Cancel activation (refund)
        """
        resp = await self._get({"action": "setStatus", "id": activation_id, "status": status})
        return resp

    async def get_status(self, activation_id: str) -> Dict:
        """
        Poll for SMS status.
        Returns {"status": str, "code": str|None}
        Possible statuses: STATUS_WAIT_CODE, STATUS_OK:CODE, STATUS_CANCEL
        """
        resp = await self._get({"action": "getStatus", "id": activation_id})
        if resp.startswith("STATUS_OK:"):
            return {"status": "STATUS_OK", "code": resp.split(":", 1)[1]}
        return {"status": resp, "code": None}

    async def cancel_activation(self, activation_id: str) -> bool:
        """Cancel and request refund."""
        resp = await self.set_status(activation_id, 8)
        return resp == "ACCESS_CANCEL"

    async def complete_activation(self, activation_id: str) -> bool:
        """Mark activation as successfully completed."""
        resp = await self.set_status(activation_id, 6)
        return resp in ("ACCESS_ACTIVATION", "1")

    # ── Active activations ─────────────────────────────────────────────────────

    async def get_active_activations(self) -> List[Dict]:
        """Return list of currently active activations."""
        resp = await self._get({"action": "getActiveActivations"})
        import json
        try:
            data = json.loads(resp)
            if isinstance(data, dict) and "activeActivations" in data:
                return data["activeActivations"]
            return []
        except Exception:
            return []
