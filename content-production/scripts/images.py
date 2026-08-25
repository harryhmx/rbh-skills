"""
Image generation — multi-provider dispatch (OpenAI / Gemini / Agnes AI).

The provider is selected via ``IMAGE_PROVIDER`` in skills/.env:

- ``openai`` (default) — OpenAI Images API using ``gpt-image-2``.  Supports
  text-to-image via ``/images/generations`` and image-to-image via
  ``/images/edits`` (multipart, up to 4 reference images).
- ``gemini`` — Google Gemini API (native Gemini image models), image
  returned inline as base64 bytes.  Supports i2i by adding image blocks
  to the input array.
- ``agnes`` — Agnes AI ``POST /v1/images/generations``, image returned as
  a URL and downloaded.  Does **not** support i2i — requests with
  ``refs`` will raise ``provider_capability_unsupported``.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from pathlib import Path

from scripts.common import build_filename
from scripts.common import (
    IMAGE_PROVIDER,
    IMAGE_SIZE_DEFAULT,
    AGNES_API_KEY,
    AGNES_IMAGE_BASE_URL,
    AGNES_IMAGE_MODEL,
    AGNES_IMAGE_SIZE_DEFAULT,
    GEMINI_API_KEY,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_IMAGE_MODEL,
    OPENAI_IMAGE_TRANSPORT,
    OPENAI_IMAGE_TIMEOUT,
    MAX_RETRIES,
    download_with_retry,
    logger,
)

# ---------------------------------------------------------------------------
# Agnes AI provider
# ---------------------------------------------------------------------------


def _agnes_image_request(payload: dict) -> dict:
    """Send a JSON request to the Agnes AI images endpoint."""
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{AGNES_IMAGE_BASE_URL}/v1/images/generations",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {AGNES_API_KEY}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            text = resp.read().decode("utf-8")
            return json.loads(text) if text else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Agnes HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Agnes request failed: {exc}") from exc


def _extract_image_urls(data: dict) -> list[str]:
    """Extract image URLs from an Agnes API response."""
    urls: list[str] = []
    if isinstance(data.get("url"), str):
        urls.append(data["url"])
    if isinstance(data.get("image_url"), str):
        urls.append(data["image_url"])
    if isinstance(data.get("data"), list):
        for item in data["data"]:
            if isinstance(item, dict):
                for key in ("url", "image_url"):
                    if isinstance(item.get(key), str):
                        urls.append(item[key])
    return urls


def _generate_one_agnes(
    prompt: str, size: str | None, refs: list[Path] | None = None,
) -> tuple[bytes, str | None]:
    """Generate a single image via Agnes AI. Returns ``(png_bytes, source_url)``.

    Raises ``provider_capability_unsupported`` if *refs* is provided
    (Agnes does not support image-to-image).
    """
    if refs:
        raise RuntimeError(
            "provider_capability_unsupported: IMAGE_PROVIDER=agnes does not "
            "support image-to-image (image_refs). Switch to openai or gemini."
        )
    payload: dict = {
        "model": AGNES_IMAGE_MODEL,
        "prompt": prompt,
        "extra_body": {"response_format": "url"},
    }
    payload["size"] = size or AGNES_IMAGE_SIZE_DEFAULT

    data = _agnes_image_request(payload)
    urls = _extract_image_urls(data)
    if not urls:
        raise RuntimeError("No image URL in Agnes response")

    image_url = urls[0]
    logger.info("Downloading from %s...", image_url[:80])
    return download_with_retry(image_url), image_url


# ---------------------------------------------------------------------------
# Gemini provider
# ---------------------------------------------------------------------------


def _generate_one_gemini(
    prompt: str, size: str, refs: list[Path] | None = None,
) -> tuple[bytes, str | None]:
    """Generate a single image via the Gemini API. Returns ``(image_bytes, None)``."""
    from scripts.gemini import gemini_generate_image

    return gemini_generate_image(prompt, size, refs=refs), None


# ---------------------------------------------------------------------------
# OpenAI provider
# ---------------------------------------------------------------------------


def _generate_one_openai(
    prompt: str, size: str, refs: list[Path] | None = None,
) -> tuple[bytes, str | None]:
    """Generate one image through the OpenAI Images API.

    When *refs* is ``None``: text-to-image via ``/images/generations``
    (JSON payload, curl or SDK transport).

    When *refs* is provided: image-to-image via ``/images/edits``
    (multipart form, first ref as ``image``, optional second as ``mask``).
    """
    if refs:
        return _generate_one_openai_edits(prompt, size, refs)

    # --- text-to-image (existing path) ---
    if OPENAI_IMAGE_TRANSPORT not in {"curl", "sdk"}:
        raise RuntimeError(
            f"Unknown OPENAI_IMAGE_TRANSPORT '{OPENAI_IMAGE_TRANSPORT}'. "
            "Supported: curl, sdk."
        )
    if OPENAI_IMAGE_TRANSPORT == "sdk":
        return _generate_one_openai_sdk(prompt, size)

    import base64
    import subprocess

    payload = json.dumps({
        "model": OPENAI_IMAGE_MODEL,
        "prompt": prompt,
        "size": size,
        "response_format": "b64_json",
    })
    try:
        response = subprocess.run(
            [
                "curl", "-fsS", "--max-time", str(OPENAI_IMAGE_TIMEOUT),
                "-X", "POST", f"{OPENAI_BASE_URL}/images/generations",
                "-H", f"Authorization: Bearer {OPENAI_API_KEY}",
                "-H", "Content-Type: application/json",
                "--data-binary", "@-",
            ],
            input=payload.encode("utf-8"),
            capture_output=True,
            timeout=OPENAI_IMAGE_TIMEOUT + 10,
            check=True,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        detail = getattr(exc, "stderr", b"")
        if isinstance(detail, bytes):
            detail = detail.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"OpenAI curl request failed: {detail or exc}") from exc

    try:
        data = json.loads(response.stdout)
        item = data["data"][0]
    except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("OpenAI response did not contain image data") from exc

    if isinstance(item, dict) and isinstance(item.get("b64_json"), str):
        try:
            return base64.b64decode(item["b64_json"]), None
        except (ValueError, base64.binascii.Error) as exc:
            raise RuntimeError("OpenAI response contained invalid base64 image data") from exc

    if isinstance(item, dict) and isinstance(item.get("url"), str):
        image_url = item["url"]
        try:
            downloaded = subprocess.run(
                ["curl", "-fsSL", "--max-time", "120", image_url],
                capture_output=True,
                timeout=130,
                check=True,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            detail = getattr(exc, "stderr", b"")
            if isinstance(detail, bytes):
                detail = detail.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"OpenAI image download failed: {detail or exc}") from exc
        if not downloaded.stdout:
            raise RuntimeError("OpenAI image download returned empty data")
        return downloaded.stdout, image_url

    raise RuntimeError("OpenAI response contained neither base64 image data nor image URL")


def _generate_one_openai_edits(
    prompt: str, size: str, refs: list[Path],
) -> tuple[bytes, str | None]:
    """Image-to-image via the OpenAI ``/images/edits`` multipart endpoint.

    The first ref is sent as the ``image`` field; an optional second ref
    is sent as ``mask``.  Additional refs beyond 2 are silently ignored
    (the edits endpoint accepts at most one image + one mask).
    """
    import base64
    import requests as http_requests

    image_path = refs[0]
    mask_path = refs[1] if len(refs) >= 2 else None

    logger.info(
        "OpenAI i2i: image=%s%s",
        image_path.name,
        f" mask={mask_path.name}" if mask_path else "",
    )

    try:
        # Read image files into memory for multipart upload
        files: dict = {}
        with open(image_path, "rb") as fh:
            files["image"] = (image_path.name, fh.read(), _mime_for_path(image_path))
        if mask_path:
            with open(mask_path, "rb") as fh:
                files["mask"] = (mask_path.name, fh.read(), _mime_for_path(mask_path))
    except OSError as exc:
        raise RuntimeError(f"OpenAI i2i: cannot read ref file: {exc}") from exc

    data: dict = {
        "prompt": prompt,
        "model": OPENAI_IMAGE_MODEL,
        "size": size,
        "response_format": "b64_json",
    }

    url = f"{OPENAI_BASE_URL}/images/edits"

    try:
        resp = http_requests.post(
            url,
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            data=data,
            files=files,
            timeout=float(OPENAI_IMAGE_TIMEOUT),
        )
        resp.raise_for_status()
        body = resp.json()
    except http_requests.exceptions.RequestException as exc:
        detail = str(exc)
        if hasattr(exc, "response") and exc.response is not None:
            try:
                detail = exc.response.text[:500]
            except Exception:
                pass
        raise RuntimeError(f"OpenAI i2i edits request failed: {detail}") from exc
    except ValueError as exc:
        raise RuntimeError(f"OpenAI i2i edits response not valid JSON: {exc}") from exc

    try:
        item = body["data"][0]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(
            f"OpenAI i2i edits response did not contain image data: "
            f"{json.dumps(body)[:300]}"
        ) from exc

    # b64_json preferred, then url
    if isinstance(item.get("b64_json"), str):
        try:
            return base64.b64decode(item["b64_json"]), None
        except (ValueError, base64.binascii.Error) as exc:
            raise RuntimeError("OpenAI i2i: invalid base64 image data") from exc

    if isinstance(item.get("url"), str):
        image_url = item["url"]
        logger.info("Downloading i2i result from %s...", image_url[:80])
        return download_with_retry(image_url), image_url

    raise RuntimeError("OpenAI i2i edits: no b64_json or url in response")


def _mime_for_path(path: Path) -> str:
    """Return a MIME type string for *path* based on its extension."""
    mapping = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }
    return mapping.get(path.suffix.lower(), "application/octet-stream")


def _generate_one_openai_sdk(prompt: str, size: str) -> tuple[bytes, str | None]:
    """Generate one image through the OpenAI Python SDK."""
    import base64
    from openai import OpenAI

    try:
        client = OpenAI(
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL,
            timeout=float(OPENAI_IMAGE_TIMEOUT),
            max_retries=0,
        )
        result = client.images.generate(
            model=OPENAI_IMAGE_MODEL,
            prompt=prompt,
            size=size,
            response_format="b64_json",
        )
        encoded = result.data[0].b64_json
        if not encoded:
            raise RuntimeError("OpenAI SDK response did not contain base64 image data")
        return base64.b64decode(encoded), None
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"OpenAI SDK request failed: {exc}") from exc



_PROVIDERS: dict[str, tuple] = {
    "agnes": (
        _generate_one_agnes, "AGNES_API_KEY", lambda: AGNES_API_KEY, False,
    ),
    "gemini": (
        _generate_one_gemini, "GEMINI_API_KEY", lambda: GEMINI_API_KEY, True,
    ),
    "openai": (
        _generate_one_openai, "OPENAI_API_KEY", lambda: OPENAI_API_KEY, True,
    ),
}

# Provider i2i capability: True = supports image_to_image operation
_IMAGE_PROVIDER_I2I: dict[str, bool] = {
    provider: bool(info[3]) for provider, info in _PROVIDERS.items()
}

def _check_i2i_capability(refs: list | None) -> None:
    """Raise ``provider_capability_unsupported`` if *refs* are provided
    but the active ``IMAGE_PROVIDER`` does not support image-to-image."""
    if refs and not _IMAGE_PROVIDER_I2I.get(IMAGE_PROVIDER, False):
        supported = sorted(
            p for p, ok in _IMAGE_PROVIDER_I2I.items() if ok
        )
        raise RuntimeError(
            f"provider_capability_unsupported: IMAGE_PROVIDER={IMAGE_PROVIDER} "
            f"does not support image-to-image (image_refs / --ref). "
            f"Supported providers: {', '.join(supported)}. "
            "Set IMAGE_PROVIDER=openai (default) or IMAGE_PROVIDER=gemini "
            "in skills/.env."
        )


def _resolve_provider():
    """Return the generate function for IMAGE_PROVIDER, validating its API key."""
    if IMAGE_PROVIDER not in _PROVIDERS:
        raise RuntimeError(
            f"Unknown IMAGE_PROVIDER '{IMAGE_PROVIDER}'. "
            f"Supported: {', '.join(sorted(_PROVIDERS))}."
        )
    generate_fn, key_name, key_getter, _i2i = _PROVIDERS[IMAGE_PROVIDER]
    if not key_getter():
        raise RuntimeError(
            f"{key_name} is not set (required by IMAGE_PROVIDER={IMAGE_PROVIDER}). "
            "Set it in skills/.env or as an environment variable."
        )
    return generate_fn


# ---------------------------------------------------------------------------
# Single image generation
# ---------------------------------------------------------------------------

def generate_one_image(
    prompt: str,
    size: str | None = None,
    output_path: str | Path | None = None,
    refs: list[Path] | None = None,
) -> dict:
    """Generate a single image and save to *output_path*.

    The provider is selected by ``IMAGE_PROVIDER``.

    Parameters
    ----------
    prompt : str
        Image generation prompt (text instruction).
    size : str
        Image size in ``WxH`` format.
    output_path : str or Path or None
        Where to save the image.  If ``None``, saves to ``output.png``
        in the current directory.
    refs : list[Path] or None
        Reference images for image-to-image mode.  ``None`` or empty
        for text-to-image.  Max 4 paths; first ref is the base image,
        optional second is a mask (OpenAI) or additional reference
        (Gemini).

    Returns
    -------
    dict
        ``file_path`` (str or None), ``url`` (str or None), ``prompt`` (str).
    """
    _check_i2i_capability(refs)

    # Let each provider use its own configured default while preserving an
    # explicit --size override from callers.
    if size is None:
        size = AGNES_IMAGE_SIZE_DEFAULT if IMAGE_PROVIDER == "agnes" else IMAGE_SIZE_DEFAULT

    generate_fn = _resolve_provider()

    out = Path(output_path or "output.png")
    out.parent.mkdir(parents=True, exist_ok=True)

    url = None
    saved = False

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            mode = "i2i" if refs else "t2i"
            logger.info(
                "Generating image via %s [%s] (attempt %d/%d)...",
                IMAGE_PROVIDER, mode, attempt, MAX_RETRIES,
            )
            img_bytes, url = generate_fn(prompt, size, refs=refs)

            if len(img_bytes) < 1000:
                logger.warning("Image too small (%d bytes), retrying", len(img_bytes))
                continue

            out.write_bytes(img_bytes)
            saved = True
            logger.info("Saved %s (%d bytes)", out.name, len(img_bytes))
            break

        except Exception as exc:
            logger.warning("Attempt %d failed: %s", attempt, exc)
            if attempt < MAX_RETRIES:
                time.sleep(2)

    return {
        "file_path": str(out.resolve()) if saved else None,
        "url": url if saved else None,
        "prompt": prompt,
    }


# ---------------------------------------------------------------------------
# Batch image generation
# ---------------------------------------------------------------------------


def generate_images(
    segments: list[dict],
    name: str | None = None,
    size: str | None = None,
    output_dir: str | Path = "output",
    prompt_key: str = "image_prompt",
    cli_refs: list[Path] | None = None,
) -> list[dict]:
    """Generate an image for each segment via the configured provider.

    The provider is selected by ``IMAGE_PROVIDER`` (openai / gemini / agnes).
    Images are saved to *output_dir*.  File naming uses the optional
    top-level ``name`` and segment-level ``slug`` values, falling back to
    ``{index:03d}.png`` when neither is set.

    Per-segment ``image_refs`` (when present in the JSON) take precedence
    over *cli_refs*.  Segments without ``image_refs`` use *cli_refs* if
    provided, or text-to-image otherwise — mixed text-to-image and
    image-to-image within one batch is supported.

    Parameters
    ----------
    segments : list[dict]
        Segments from :func:`common.load_segments_json`.  Each must have an
        ``index`` and the *prompt_key* field.  May optionally have
        ``image_refs`` for per-segment i2i.
    name : str or None
        Optional top-level project name for filename prefixes (kebab-case).
    size : str
        Image size in ``WxH`` format (e.g. ``"1024x768"``).  For Gemini the
        size is mapped to the nearest supported aspect ratio.
    output_dir : str or Path
        Directory to save generated images.
    prompt_key : str
        Which segment key holds the image generation prompt.
        Default: ``"image_prompt"``.
    cli_refs : list[Path] or None
        Reference images from CLI ``--ref`` (applied to all segments that
        lack their own ``image_refs``).

    Returns
    -------
    list[dict]
        Each dict has ``index``, ``title``, ``file_path``, ``url``, and
        ``prompt`` keys.  ``url`` is the source URL for URL-based providers
        (Agnes) and ``None`` for inline-bytes providers (Gemini, OpenAI).
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    results = []
    total = len(segments)

    for seg in sorted(segments, key=lambda s: s.get("index", 0)):
        idx = seg.get("index", 0)
        title = seg.get("title", f"segment-{idx}")
        prompt = seg.get(prompt_key, "")

        if not prompt:
            logger.warning("[%d/%d] No prompt for segment %d, skipping", idx + 1, total, idx)
            results.append({
                "index": idx,
                "title": title,
                "file_path": None,
                "url": None,
                "prompt": prompt,
                "error": f"No '{prompt_key}' field",
            })
            continue

        # Per-segment refs take precedence; fall back to CLI refs.
        # image_refs are absolute paths (resolved by load_segments_json).
        seg_refs = None
        seg_image_refs = seg.get("image_refs")
        if isinstance(seg_image_refs, list) and seg_image_refs:
            seg_refs = [Path(p) for p in seg_image_refs]
        elif cli_refs:
            seg_refs = cli_refs

        file_path = out / build_filename(name, seg.get("slug"), idx, ".png")
        mode_label = "[i2i]" if seg_refs else "[t2i]"
        logger.info("[%d/%d] %s Generating image for '%s'...", idx + 1, total, mode_label, title)

        result = generate_one_image(prompt, size, file_path, refs=seg_refs)
        results.append({
            "index": idx,
            "title": title,
            **result,
        })

    # Summary
    succeeded = sum(1 for r in results if r["file_path"])
    logger.info("Done: %d/%d images generated → %s", succeeded, total, out.resolve())
    return results
