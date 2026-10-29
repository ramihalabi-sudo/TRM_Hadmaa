"""Detector lookup with the Claude API (web search + web fetch).

`lookup(name)` asks Claude to find the datasheet of a named focal plane array / camera core, extracts
the parameters that TRM4 uses, and returns them as a list of suggested field values.  Datasheet PDFs
found during the search are downloaded into DATASHEET_DIR/<detector name>/.

Requires the `anthropic` package and credentials (ANTHROPIC_API_KEY, or an `ant auth login` profile).
"""
import json
import os
import re
import urllib.request

MODEL = "claude-opus-5-5"
DATASHEET_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Detector datasheets")

# key -> (project path or None, label, unit, description for the model)
FIELDS = [
    ("imager_type", "imager_type", "Imager type (Thermal)", "", "'cooled' or 'uncooled' (thermal detectors only)"),
    ("n_h", "detector.n_h", "Number of horizontal detectors", "", "active pixels horizontally"),
    ("n_v", "detector.n_v", "Number of vertical detectors", "", "active pixels vertically"),
    ("pitch_h_um", "detector.pitch_h_um", "Horizontal detector pitch", "um", "pixel pitch"),
    ("pitch_v_um", "detector.pitch_v_um", "Vertical detector pitch", "um", "pixel pitch"),
    ("active_h_um", "detector.a_h_um", "Horizontal dimension (active)", "um",
     "active (photosensitive) pixel width; if only fill factor is given, pitch*sqrt(fill factor)"),
    ("active_v_um", "detector.a_v_um", "Vertical dimension (active)", "um", "active pixel height"),
    ("frame_rate_hz", "basic.frame_rate", "Frame rate", "Hz", "full-frame rate (max or nominal)"),
    ("well_capacity_e", "detector.storage_e", "Storage capacity", "carriers",
     "charge handling / well capacity in electrons (use the mode a thermal imager would normally use)"),
    ("readout_noise_e", "detector.noise_floor_e", "Noise floor (additive)", "e-", "readout / temporal noise floor in electrons rms"),
    ("dark_current_A", "detector.dark_A", "Dark current", "A", "dark current per pixel in amperes (convert from A/cm2 with pixel area if needed)"),
    ("adc_lsb_e", "detector.lsb_e", "LSB", "carriers", "well capacity / 2^ADC bits"),
    ("netd_mK", "detector.netd_mK", "NETD", "mK", "NETD in mK (state F-number and scene temperature in the note)"),
    ("operating_temp_K", "detector.T_sensor_K", "Sensor operating temperature", "K",
     "FPA operating temperature (cooled detectors)"),
    ("cold_shield_F", "detector.cs_F", "Cold shield effective F-number", "", "F-number of the cold shield / dewar"),
    ("thermal_time_ms", "detector.t_th_ms", "Detector thermal time constant", "ms", "microbolometer thermal time constant"),
    ("cut_on_um", "detector.cuton_um", "Cut-on wavelength", "um", "lower 50 % spectral limit"),
    ("cut_off_um", "detector.cutoff_um", "Cut-off wavelength", "um", "upper 50 % spectral limit"),
]

# Found values come back as a list of {key, value} (absent = not found) and imager_type as an enum with
# "unknown": the API allows at most 16 nullable / union-typed parameters per schema.
SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["detector_name", "manufacturer", "summary", "category", "imager_type", "values", "notes",
                 "qe_curve", "datasheet_urls", "sources"],
    "properties": {
        "detector_name": {"type": "string"},
        "manufacturer": {"type": "string"},
        "summary": {"type": "string"},
        "category": {"type": "string", "enum": ["Thermal", "Visible", "General"]},
        "imager_type": {"type": "string", "enum": ["cooled", "uncooled", "unknown"]},
        "values": {
            "type": "array",
            "items": {"type": "object", "additionalProperties": False, "required": ["key", "value"],
                      "properties": {"key": {"type": "string",
                                             "enum": [k for k, *_ in FIELDS if k != "imager_type"]},
                                     "value": {"type": "number"}}},
        },
        "notes": {
            "type": "array",
            "items": {"type": "object", "additionalProperties": False, "required": ["field", "note"],
                      "properties": {"field": {"type": "string"}, "note": {"type": "string"}}},
        },
        "qe_curve": {
            "type": "array",
            "items": {"type": "object", "additionalProperties": False, "required": ["lambda_um", "qe_pct"],
                      "properties": {"lambda_um": {"type": "number"}, "qe_pct": {"type": "number"}}},
        },
        "datasheet_urls": {
            "type": "array",
            "items": {"type": "object", "additionalProperties": False, "required": ["title", "url"],
                      "properties": {"title": {"type": "string"}, "url": {"type": "string"}}},
        },
        "sources": {"type": "array", "items": {"type": "string"}},
    },
}

RESEARCH_PROMPT = """Find the manufacturer datasheet / specifications for this infrared or visible detector \
(focal plane array or camera core): "{name}".

Search the web, prefer the manufacturer's own datasheet (PDF if available), and read it. Use 2-3 sources \
at most: the manufacturer datasheet first, then one or two others only for values it lacks. Report these \
parameters as numbers in the stated units, only when a source states them or they follow directly \
from stated values (say so when derived):
{fields}
Also report: the imager category (Thermal for MWIR/LWIR, Visible for VIS/NIR/SWIR), the spectral quantum \
efficiency curve as (wavelength um, QE %) points if one is published (otherwise approximate it from the \
spectral band and the stated QE, and say it is approximate), and the direct URLs of every datasheet PDF \
you found.

Do not guess values that no source gives. For each value, note the source and any conditions (e.g. NETD \
at F/2, 300 K)."""

EXTRACT_PROMPT = """Convert these research notes on the detector "{name}" into the JSON schema. List in \
`values` only the values the notes give (leave the others out); set imager_type to "unknown" if the notes \
do not say cooled or uncooled, or the detector is not thermal. Put the source and conditions of each value in `notes` (field = value key). \
Only include datasheet_urls that are direct links to PDF datasheets.

Research notes:
{notes}"""


class DetectorLookupError(Exception):
    pass


def _client(api_key=None):
    try:
        import anthropic
    except ImportError:
        raise DetectorLookupError("The 'anthropic' package is not installed. Run:  python -m pip install anthropic")
    return anthropic, anthropic.Anthropic(api_key=api_key or None)


def _text(message):
    return "\n".join(b.text for b in message.content if b.type == "text")


def _research(anthropic, client, name, progress):
    fields = "\n".join("- %s [%s]: %s" % (k, unit or "-", desc) for k, _, _, unit, desc in FIELDS)
    messages = [{"role": "user", "content": RESEARCH_PROMPT.format(name=name, fields=fields)}]
    for _ in range(6):  # pause_turn continuations
        with client.beta.messages.stream(
            model=MODEL,
            max_tokens=32000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": "high"},
            tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 4},
                   {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 3}],
            messages=messages,
        ) as stream:
            for ev in stream:
                if ev.type == "content_block_start" and ev.content_block.type == "server_tool_use":
                    progress("Searching the web (%s)..." % ev.content_block.name)
            response = stream.get_final_message()
        if response.stop_reason == "refusal":
            raise DetectorLookupError("The request was declined by the model.")
        if response.stop_reason != "pause_turn":
            break
        messages = [messages[0], {"role": "assistant", "content": response.content}]
    return response


def _extract(client, name, notes):
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": EXTRACT_PROMPT.format(name=name, notes=notes)}],
    )
    if response.stop_reason == "refusal":
        raise DetectorLookupError("The request was declined by the model.")
    info = json.loads(_text(response))
    # Back to {key: value or None} for all FIELDS, as the rest of the code expects.
    found = {v["key"]: v["value"] for v in info["values"]}
    imager_type = info.pop("imager_type")
    found["imager_type"] = imager_type if imager_type != "unknown" else None
    info["values"] = {k: found.get(k) for k, *_ in FIELDS}
    return info


def _pdf_urls_from(response):
    """PDF links that web search / fetch actually returned."""
    urls = []
    for b in response.content:
        if b.type == "web_search_tool_result" and isinstance(b.content, list):
            urls += [r.url for r in b.content if getattr(r, "url", "")]
        elif b.type == "web_fetch_tool_result" and getattr(b.content, "url", None):
            urls.append(b.content.url)
    return [u for u in urls if u.lower().split("?")[0].endswith(".pdf")]


def safe_name(s):
    return re.sub(r'[<>:"/\\|?*\s]+', "_", s).strip("_.")[:80] or "detector"


def download_pdfs(urls, folder, progress=lambda m: None):
    os.makedirs(folder, exist_ok=True)
    saved, failed = [], []
    for url in dict.fromkeys(urls):
        fn = os.path.join(folder, safe_name(os.path.basename(url.split("?")[0])) or "datasheet.pdf")
        if not fn.lower().endswith(".pdf"):
            fn += ".pdf"
        progress("Downloading %s" % url)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (TRM4 detector lookup)"})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read(50 * 1024 * 1024)
            if not data.startswith(b"%PDF"):
                raise ValueError("not a PDF")
            with open(fn, "wb") as fh:
                fh.write(data)
            saved.append(fn)
        except Exception as e:
            failed.append("%s (%s)" % (url, e))
    return saved, failed


def lookup(name, api_key=None, progress=lambda m: None, download=True):
    """Return a dict: info (extracted JSON), suggestions [(key, path, label, unit, value, note)],
    qe_custom (text or ''), folder, pdfs, pdf_failures."""
    anthropic, client = _client(api_key)
    try:
        progress("Asking Claude to research %s..." % name)
        research = _research(anthropic, client, name, progress)
        progress("Extracting parameters...")
        info = _extract(client, name, _text(research))
    except anthropic.AuthenticationError as e:
        if api_key:
            src = "the key entered in the dialog (%d characters, starts with %r)" % (len(api_key), api_key[:7])
        elif os.environ.get("ANTHROPIC_API_KEY"):
            src = "ANTHROPIC_API_KEY from the environment"
        else:
            src = "no key: the dialog field is empty and ANTHROPIC_API_KEY is not set for this program"
        raise DetectorLookupError("Invalid or missing Anthropic API key.\nKey used: %s.\nAPI response: %s\n\n"
                                  "Set ANTHROPIC_API_KEY or enter a key in the dialog." % (src, getattr(e, "message", e)))
    except anthropic.RateLimitError:
        raise DetectorLookupError("Rate limited by the Anthropic API - try again in a minute.")
    except anthropic.APIConnectionError:
        raise DetectorLookupError("Could not reach the Anthropic API - check the internet connection.")
    except anthropic.APIStatusError as e:
        raise DetectorLookupError("Anthropic API error %s: %s" % (e.status_code, e.message))

    notes = {n["field"]: n["note"] for n in info["notes"]}
    vals = info["values"]
    suggestions = [(k, path, label, unit, vals.get(k), notes.get(k, ""))
                   for k, path, label, unit, _ in FIELDS if vals.get(k) is not None]
    pts = sorted((p["lambda_um"], p["qe_pct"]) for p in info["qe_curve"])
    qe_custom = "\n".join("%g %g" % p for p in pts) if len(pts) >= 2 else ""

    folder = os.path.join(DATASHEET_DIR, safe_name(info["detector_name"] or name))
    pdfs, failed = [], []
    if download:
        urls = [d["url"] for d in info["datasheet_urls"]] + _pdf_urls_from(research)
        pdfs, failed = download_pdfs(urls, folder, progress)
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "lookup.json"), "w", encoding="utf-8") as fh:
            json.dump({"query": name, **info}, fh, indent=2)
    return {"info": info, "suggestions": suggestions, "qe_custom": qe_custom, "qe_note": notes.get("qe_curve", ""),
            "folder": folder, "pdfs": pdfs, "pdf_failures": failed}
