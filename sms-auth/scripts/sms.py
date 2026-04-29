import re
import time

from alibabacloud_dypnsapi20170525.client import Client
from alibabacloud_dypnsapi20170525.models import (
    CheckSmsVerifyCodeRequest,
    SendSmsVerifyCodeRequest,
)
from alibabacloud_tea_openapi.models import Config

from config import settings

SIGN_NAME = "速通互联验证码"
TEMPLATE_CODE = "100001"
SMS_CODE_EXPIRE_MINUTES = 5
SMS_COOLDOWN_SECONDS = 60

PHONE_REGEX = re.compile(r"^1[3-9]\d{9}$")

_cooldown: dict[str, float] = {}


def _create_client() -> Client:
    config = Config(
        access_key_id=settings.ALIBABA_CLOUD_ACCESS_KEY_ID,
        access_key_secret=settings.ALIBABA_CLOUD_ACCESS_KEY_SECRET,
        endpoint="dypnsapi.aliyuncs.com",
    )
    return Client(config)


def send_sms_verify_code(phone_number: str) -> dict:
    if not PHONE_REGEX.match(phone_number):
        return {"success": False, "message": "Invalid phone number format"}

    last_sent = _cooldown.get(phone_number, 0)
    if time.time() - last_sent < SMS_COOLDOWN_SECONDS:
        remaining = int(SMS_COOLDOWN_SECONDS - (time.time() - last_sent))
        return {"success": False, "message": f"Please wait {remaining}s before retrying"}

    try:
        client = _create_client()
        request = SendSmsVerifyCodeRequest(
            sign_name=SIGN_NAME,
            template_code=TEMPLATE_CODE,
            phone_number=phone_number,
            template_param='{"code":"##code##","min":"5"}',
        )
        response = client.send_sms_verify_code(request)

        if response.body and response.body.code == "OK":
            _cooldown[phone_number] = time.time()
            return {"success": True, "message": "Code sent", "cooldown_seconds": SMS_COOLDOWN_SECONDS}

        msg = response.body.message if response.body else "Unknown error"
        return {"success": False, "message": f"Send failed: {msg}"}
    except Exception as e:
        return {"success": False, "message": f"Send error: {e}"}


def check_sms_verify_code(phone_number: str, verify_code: str) -> dict:
    if not verify_code:
        return {"success": False, "message": "Code is required", "error_type": "missing_code"}

    try:
        client = _create_client()
        request = CheckSmsVerifyCodeRequest(
            phone_number=phone_number,
            verify_code=verify_code,
        )
        response = client.check_sms_verify_code(request)

        if response.body and response.body.code == "OK":
            return {"success": True, "message": "Verified"}

        return {"success": False, "message": "Invalid or expired code", "error_type": "invalid_code"}
    except Exception as e:
        return {"success": False, "message": f"Verify error: {e}"}
