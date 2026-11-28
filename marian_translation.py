"""Local English/Greek translation with pinned public OPUS-MT models.

Model setup downloads only fixed model archives, never transcript text. Original
Marian weights are converted locally to CTranslate2 int8. The model publisher's
license and attribution remain beside the converted files.
"""
from __future__ import annotations

import argparse
from functools import lru_cache
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile
import threading
import time
from typing import Any
import urllib.request
import zipfile


class TranslationError(Exception):
    """A local translator/setup error that can be shown to the user."""


MODEL_SPECS = {
    "en-el": {
        "repository": "Helsinki-NLP/opus-mt-tc-big-en-el",
        "revision": "bb9aa4d8929451dd2396f399f7aa184c788d565b",
        "url": "https://object.pouta.csc.fi/Tatoeba-MT-models/eng-ell/opusTCv20210807+bt_transformer-big_2022-03-13.zip",
        "archive_bytes": 878914486,
        "archive_sha256": "7e72c7407c86b68582571ba45ec77799b54ffd3bc5b3ffb8cbbf92d0644c7829",
    },
    "el-en": {
        "repository": "Helsinki-NLP/opus-mt-tc-big-el-en",
        "revision": "a69108562775c6727edf3540346f9d8900b73634",
        "url": "https://object.pouta.csc.fi/Tatoeba-MT-models/ell-eng/opusTCv20210807+bt_transformer-big_2022-02-25.zip",
        "archive_bytes": 878830047,
        "archive_sha256": "7f44ee3eddd632b1934bedbae79ad7ba2650fb932803a098234da3a76ccd4f47",
    },
}
WEIGHTS_NAME = "opusTCv20210807+bt.spm32k-spm32k.transformer-big.model1.npz.best-perplexity.npz"
VOCAB_NAME = "opusTCv20210807+bt.spm32k-spm32k.vocab.yml"
EXTRACT_FILES = {WEIGHTS_NAME, VOCAB_NAME, "source.spm", "target.spm", "LICENSE", "README.md"}
RUNTIME_FILES = {"model.bin", "config.json", "shared_vocabulary.json", "source.spm", "target.spm", "LICENSE", "README.md"}
MAX_SOURCE_TOKENS = 128
MAX_TARGET_TOKENS = 1024
MAX_OUTPUT_BYTES = 16384
MAX_BATCH_ITEMS = 8
_setup_lock = threading.Lock()


def cache_root() -> Path:
    value = os.getenv("LINKSCRIBE_TRANSLATION_CACHE")
    if value is not None and (not value.strip() or len(value) > 1000):
        raise TranslationError("Set LINKSCRIBE_TRANSLATION_CACHE to a valid local folder.")
    return Path(value).expanduser() if value else Path(__file__).resolve().parent / "data/models/translation"


def _pair(source: str, target: str) -> str:
    pair = f"{source}-{target}"
    if pair not in MODEL_SPECS:
        raise TranslationError("The dedicated local translator supports English to Greek and Greek to English. Choose the source language or select the Ollama translation backend for another language.")
    return pair


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(4 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _read_manifest(directory: Path, pair: str, *, verify_files: bool) -> dict[str, Any]:
    try:
        if (directory / "manifest.json").stat().st_size > 65536:
            raise ValueError("Manifest is too large")
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        if (manifest["format"] != "linkscribe-marian-v1" or manifest["pair"] != pair
                or manifest["source"] != MODEL_SPECS[pair]
                or manifest["quantization"] != "int8"
                or set(manifest["files"]) != RUNTIME_FILES):
            raise ValueError("Model identity mismatch")
        for name, info in manifest["files"].items():
            path = directory / name
            if path.is_symlink() or not path.is_file() or path.stat().st_size != info["bytes"]:
                raise ValueError("Model file size mismatch")
            if verify_files and _sha256(path) != info["sha256"]:
                raise ValueError("Model file checksum mismatch")
        return manifest
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise TranslationError(f"The cached {pair} translator is incomplete or damaged. Run `python -m marian_translation --pair {pair} --repair` to rebuild this model cache.") from exc


def cache_status() -> dict[str, Any]:
    """Inspect local manifests/sizes without importing ML packages or networking."""
    pairs = {}
    for pair in MODEL_SPECS:
        try:
            _read_manifest(cache_root() / pair, pair, verify_files=False)
            pairs[pair] = True
        except TranslationError:
            pairs[pair] = False
    return {"backend": "marian", "pairs_cached": pairs,
            "first_use_download_bytes_per_pair": {pair: spec["archive_bytes"] for pair, spec in MODEL_SPECS.items()}}


def _download_archive(spec: dict[str, Any], destination: Path) -> None:
    request = urllib.request.Request(spec["url"], headers={"User-Agent": "LinkScribe/model-setup"})
    start = time.monotonic()
    size = 0
    digest = hashlib.sha256()
    try:
        with urllib.request.urlopen(request, timeout=60) as response, destination.open("wb") as output:
            while chunk := response.read(4 * 1024 * 1024):
                size += len(chunk)
                if size > spec["archive_bytes"] or time.monotonic() - start > 600:
                    raise TranslationError("Translation model download exceeded its size or time limit. Please retry model setup.")
                output.write(chunk)
                digest.update(chunk)
    except (OSError, TimeoutError) as exc:
        raise TranslationError("Unable to download the public translation model. Check the connection and retry; the original transcript is retained.") from exc
    if size != spec["archive_bytes"] or digest.hexdigest() != spec["archive_sha256"]:
        raise TranslationError("The translation model download failed its checksum. No model was installed; retry model setup.")


def _extract_model(archive_path: Path, output: Path) -> None:
    with zipfile.ZipFile(archive_path) as archive:
        selected = []
        for info in archive.infolist():
            path = Path(info.filename)
            if (path.is_absolute() or len(path.parts) != 1 or "\\" in info.filename
                    or path.name in {".", ".."} or stat.S_ISLNK(info.external_attr >> 16)
                    or info.flag_bits & 1):
                raise TranslationError("The model archive contains an unsafe member.")
            if info.filename in EXTRACT_FILES:
                selected.append(info)
        if ({item.filename for item in selected} != EXTRACT_FILES or len(selected) != len(EXTRACT_FILES)
                or sum(item.file_size for item in selected) > 1_100_000_000):
            raise TranslationError("The model archive contents do not match the expected model.")
        for info in selected:
            with archive.open(info) as source, (output / info.filename).open("wb") as destination:
                shutil.copyfileobj(source, destination, 4 * 1024 * 1024)


def prepare_model(pair: str, *, repair: bool = False) -> Path:
    if pair not in MODEL_SPECS:
        raise TranslationError("Select en-el or el-en for model setup.")
    root = cache_root()
    directory = root / pair
    with _setup_lock:
        if directory.exists() and not repair:
            _read_manifest(directory, pair, verify_files=True)
            return directory
        try:
            from ctranslate2.converters import MarianConverter
            import sentencepiece  # noqa: F401: check all required runtime packages before downloading.
        except ImportError as exc:
            raise TranslationError("Install the core dependencies from requirements.txt, including sentencepiece, for local English/Greek translation.") from exc
        root.mkdir(parents=True, exist_ok=True)
        if shutil.disk_usage(root).free < 2_200_000_000:
            raise TranslationError("Translation model setup needs about 2.2 GB of temporary free disk space. The final model uses about 250 MB per direction.")
        try:
            with tempfile.TemporaryDirectory(prefix=".prepare-", dir=root) as temporary:
                work = Path(temporary)
                archive = work / "source.zip"
                _download_archive(MODEL_SPECS[pair], archive)
                original = work / "original"
                original.mkdir()
                _extract_model(archive, original)
                converted = work / "converted"
                MarianConverter(str(original / WEIGHTS_NAME), [str(original / VOCAB_NAME)]).convert(
                    str(converted), quantization="int8")
                for name in ("source.spm", "target.spm", "LICENSE", "README.md"):
                    shutil.copyfile(original / name, converted / name)
                manifest = {"format": "linkscribe-marian-v1", "pair": pair,
                            "source": MODEL_SPECS[pair], "license": "CC-BY-4.0",
                            "quantization": "int8", "converter_version": importlib.metadata.version("ctranslate2"),
                            "files": {name: {"bytes": (converted / name).stat().st_size,
                                              "sha256": _sha256(converted / name)} for name in sorted(RUNTIME_FILES)}}
                (converted / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                _read_manifest(converted, pair, verify_files=True)
                # A repair retains the previous cache until its verified replacement
                # is ready. It never touches transcripts or another model's directory.
                if directory.exists():
                    previous = work / "previous"
                    directory.rename(previous)
                    try:
                        converted.rename(directory)
                    except OSError:
                        previous.rename(directory)
                        raise
                else:
                    converted.rename(directory)
                _load_model.cache_clear()
        except TranslationError:
            raise
        except (OSError, ValueError, RuntimeError, zipfile.BadZipFile) as exc:
            raise TranslationError("The local translation model could not be prepared. Check free disk space and installed dependencies, then retry setup.") from exc
    return directory


def _threads() -> int:
    raw = os.getenv("LINKSCRIBE_TRANSLATION_THREADS", "4").strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise TranslationError("LINKSCRIBE_TRANSLATION_THREADS must be an integer from 1 through 32.") from exc
    if not 1 <= value <= 32:
        raise TranslationError("LINKSCRIBE_TRANSLATION_THREADS must be an integer from 1 through 32.")
    return value


@lru_cache(maxsize=1)
def _load_model(pair: str, root: str, threads: int):
    try:
        import ctranslate2
        import sentencepiece
        directory = Path(root) / pair
        if not directory.exists():
            directory = prepare_model(pair)
        _read_manifest(directory, pair, verify_files=True)
        engine = ctranslate2.Translator(str(directory), device="cpu", compute_type="int8",
                                       inter_threads=1, intra_threads=threads)
        source = sentencepiece.SentencePieceProcessor(model_file=str(directory / "source.spm"))
        target = sentencepiece.SentencePieceProcessor(model_file=str(directory / "target.spm"))
        return engine, source, target
    except TranslationError:
        raise
    except (ImportError, OSError, RuntimeError, ValueError) as exc:
        raise TranslationError("The local English/Greek translator could not start. Check its model setup and dependencies.") from exc


def model_details(source: str, target: str) -> dict[str, Any]:
    pair = _pair(source, target)
    _load_model(pair, str(cache_root()), _threads())
    manifest = _read_manifest(cache_root() / pair, pair, verify_files=False)
    return {"backend": "marian-ctranslate2", "pair": pair, "repository": MODEL_SPECS[pair]["repository"],
            "revision": MODEL_SPECS[pair]["revision"], "archive_sha256": MODEL_SPECS[pair]["archive_sha256"],
            "model_sha256": manifest["files"]["model.bin"]["sha256"], "license": "CC-BY-4.0",
            "ctranslate2": importlib.metadata.version("ctranslate2"),
            "sentencepiece": importlib.metadata.version("sentencepiece"),
            "settings": {"device": "cpu", "compute_type": "int8", "beam_size": 4, "length_penalty": 1.0,
                         "max_source_tokens": MAX_SOURCE_TOKENS, "max_decoding_length": MAX_TARGET_TOKENS,
                         "max_input_length": 0, "inter_threads": 1, "intra_threads": _threads()}}


def _fragments(text: str, tokenizer):
    """Bound actual tokens without dropping any source characters."""
    start = 0
    while start < len(text):
        remaining = text[start:]
        if len(tokenizer.encode(remaining, out_type=str)) <= MAX_SOURCE_TOKENS:
            yield remaining
            return
        low, high, length = 1, len(remaining), 0
        while low <= high:
            middle = (low + high) // 2
            if len(tokenizer.encode(remaining[:middle], out_type=str)) <= MAX_SOURCE_TOKENS:
                length = middle
                low = middle + 1
            else:
                high = middle - 1
        if not length:
            raise TranslationError("A source character cannot fit in the translation model input.")
        # Prefer a complete sentence where possible, otherwise a word boundary.
        sentences = [i + 1 for i, char in enumerate(remaining[:length])
                     if char.isspace() and i > 0 and remaining[i - 1] in ".!?;·"]
        words = [i + 1 for i, char in enumerate(remaining[:length]) if char.isspace()]
        boundaries = [i for i in sentences if i >= length // 2] or [i for i in words if i >= length // 2]
        if boundaries:
            length = max(boundaries)
        # Token counts need not be monotone at subword boundaries. Always check
        # the selected prefix itself, and decrease it until the limit is real.
        while length and len(tokenizer.encode(remaining[:length], out_type=str)) > MAX_SOURCE_TOKENS:
            length -= 1
        if not length:
            raise TranslationError("Unable to split this source within the translation model limit.")
        yield remaining[:length]
        start += length


def _sentence_units(text: str, source: str):
    """Use sentence-sized inputs for this sentence-trained translation model.

    Every character remains in a unit, including the whitespace between units.
    Common titles/initials and decimal points are not sentence boundaries.
    """
    punctuation = r"[.!?;\u037e]" if source == "el" else r"[.!?]"
    abbreviations = {"mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st", "vs", "etc",
                     "e.g", "i.e", "κ", "κα", "δρ", "π.χ", "μ.μ", "π.μ"}
    start = 0
    for boundary in re.finditer(f"({punctuation})(\\s+)", text):
        if boundary.group(1) == ".":
            match = re.search(r"([\w.]+)$", text[:boundary.start()])
            preceding = match.group(1) if match else ""
            if (preceding.casefold() in abbreviations or
                    (len(preceding) == 1 and preceding.isupper()) or
                    (preceding.replace(".", "").isupper() and
                     re.fullmatch(r"(?:[^\W\d_]\.)+[^\W\d_]", preceding))):
                continue
        yield text[start:boundary.end()]
        start = boundary.end()
    if start < len(text):
        yield text[start:]


def _text_units(text: str, source: str):
    """Translate quoted content separately while preserving its delimiters.

    Marian can copy or distort an embedded foreign-language quotation. Splitting
    that content into an ordinary translation request keeps it as quoted text;
    it is never interpreted as an instruction. Apostrophes inside words remain
    ordinary text. Unmatched quotation marks are retained rather than dropped.
    """
    quotes = {'"': '"', "'": "'", "«": "»", "“": "”", "‘": "’"}
    start = index = 0
    while index < len(text):
        opening = text[index]
        closing = quotes.get(opening)
        if (closing is None or
                (opening in {"'", '"'} and index > 0 and text[index - 1].isalnum())):
            index += 1
            continue
        end = index + 1
        while end < len(text):
            if text[end] == closing:
                apostrophe = (closing in {"'", "’"} and end > 0 and end + 1 < len(text)
                              and text[end - 1].isalnum() and text[end + 1].isalnum())
                if not apostrophe:
                    break
            end += 1
        if end == len(text):
            index += 1
            continue
        for sentence in _sentence_units(text[start:index], source):
            yield True, sentence
        yield False, opening
        for sentence in _sentence_units(text[index + 1:end], source):
            yield True, sentence
        yield False, closing
        start = index = end + 1
    for sentence in _sentence_units(text[start:], source):
        yield True, sentence


def _translate_batch(engine, source_tokenizer, target_tokenizer, texts: list[str]) -> list[str]:
    """One observable real inference boundary, also used by evaluation tooling."""
    tokens = [source_tokenizer.encode(text, out_type=str) for text in texts]
    if not tokens or any(not item or len(item) > MAX_SOURCE_TOKENS for item in tokens):
        raise TranslationError("A translation input exceeded the tokenizer limit.")
    try:
        outputs = engine.translate_batch(tokens, beam_size=4, length_penalty=1.0,
                                         max_decoding_length=MAX_TARGET_TOKENS, max_input_length=0,
                                         return_end_token=True)
    except (RuntimeError, ValueError, MemoryError) as exc:
        raise TranslationError("The local translator could not finish. The original transcript is retained.") from exc
    if len(outputs) != len(texts):
        raise TranslationError("The local translator returned an incomplete batch.")
    translated = []
    for output in outputs:
        hypothesis = output.hypotheses[0] if output.hypotheses else []
        if not hypothesis or hypothesis[-1] != "</s>" or len(hypothesis) >= MAX_TARGET_TOKENS:
            raise TranslationError("The local translator reached its output limit or returned incomplete text; the original transcript is retained.")
        text = target_tokenizer.decode(hypothesis[:-1]).strip()
        if not text or len(text.encode("utf-8")) > MAX_OUTPUT_BYTES:
            raise TranslationError("The local translator returned empty or oversized text.")
        translated.append(text)
    return translated


def translate_segments(segments: list[dict[str, Any]], source: str, target: str) -> list[dict[str, Any]]:
    if not isinstance(segments, list):
        raise TranslationError("A transcript must contain a list of text segments.")
    for segment in segments:
        if not isinstance(segment, dict) or not isinstance(segment.get("text"), str):
            raise TranslationError("Every transcript segment must contain text.")
        try:
            segment["text"].encode("utf-8")
        except UnicodeError as exc:
            raise TranslationError("Transcript text contains invalid Unicode.") from exc
    if source == target or not any(segment["text"].strip() for segment in segments):
        return [dict(segment) for segment in segments]
    pair = _pair(source, target)
    engine, source_sp, target_sp = _load_model(pair, str(cache_root()), _threads())
    parts: list[list[str | None]] = [[] for _ in segments]
    batch: list[tuple[int, int, str, str, str]] = []

    def finish():
        if not batch:
            return
        translated = _translate_batch(engine, source_sp, target_sp, [text for _, _, _, text, _ in batch])
        for (index, position, before, _, after), text in zip(batch, translated):
            parts[index][position] = before + text + after
        batch.clear()

    for index, segment in enumerate(segments):
        for translate, unit in _text_units(segment["text"], source):
            if not translate or not unit.strip():
                parts[index].append(unit)
                continue
            for fragment in _fragments(unit, source_sp):
                if not fragment.strip():
                    parts[index].append(fragment)
                    continue
                before = fragment[:len(fragment) - len(fragment.lstrip())]
                after = fragment[len(fragment.rstrip()):]
                position = len(parts[index])
                parts[index].append(None)
                batch.append((index, position, before, fragment.strip(), after))
                if len(batch) == MAX_BATCH_ITEMS:
                    finish()
    finish()
    return [{**segment, "text": "".join(translated) if translated else segment["text"]}
            for segment, translated in zip(segments, parts)]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prepare local English/Greek translation models (no token or paid API).")
    parser.add_argument("--pair", choices=["en-el", "el-en", "both"], default="both")
    parser.add_argument("--repair", action="store_true", help="Rebuild selected caches from verified upstream archives.")
    arguments = parser.parse_args()
    try:
        for selected in MODEL_SPECS if arguments.pair == "both" else [arguments.pair]:
            print(f"Preparing {selected}: initial download about 879 MB; final model about 250 MB.", flush=True)
            print(prepare_model(selected, repair=arguments.repair), flush=True)
    except TranslationError as error:
        parser.exit(1, str(error) + "\n")
