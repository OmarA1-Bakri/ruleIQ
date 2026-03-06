from fastapi import UploadFile, File, HTTPException, status
from typing import List, Optional, Tuple
import os
import hashlib
import re
import mimetypes
import time
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
from config.settings import get_settings
from config.logging_config import get_logger
import logging


logger = logging.getLogger(__name__)
# Constants
CONFIDENCE_THRESHOLD = 0.8
DEFAULT_RETRIES = 5
HALF_RATIO = 0.5

MAX_FILENAME_LENGTH = 100
MAX_PK_COUNT = 100
MAX_EXIF_SIZE = 65535
settings = get_settings()
logger = get_logger(__name__)
try:
    import magic

    MAGIC_AVAILABLE = True
except ImportError:
    MAGIC_AVAILABLE = False
    logger.warning("python-magic not available. Using fallback MIME type detection.")


class ValidationResult(Enum):
    """Validation result status."""

    CLEAN = "clean"
    SUSPICIOUS = "suspicious"
    MALICIOUS = "malicious"
    QUARANTINED = "quarantined"


@dataclass
class FileAnalysisReport:
    """Comprehensive file analysis report."""

    filename: str
    original_filename: str
    content_type: str
    detected_type: str
    file_size: int
    file_hash: str
    validation_result: ValidationResult
    security_score: float
    threats_detected: List[str]
    recommendations: List[str]
    validation_time: float


FILE_SIGNATURES = {
    "application/pdf": [b"%PDF"],
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/png": [b"\x89PNG\r\n\x1a\n"],
    "image/gif": [b"GIF87a", b"GIF89a"],
    "application/zip": [b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"],
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [b"PK\x03\x04"],
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [b"PK\x03\x04"],
    "text/plain": None,
    "text/csv": None,
}
DANGEROUS_PATTERNS = ["\\.\\./", "\\.\\.\\\\", "[<>:|?*]", "[\\x00-\\x1f\\x7f]"]
DANGEROUS_EXTENSIONS = [
    ".exe",
    ".dll",
    ".scr",
    ".bat",
    ".cmd",
    ".com",
    ".pif",
    ".js",
    ".vbs",
    ".jar",
    ".app",
    ".dmg",
    ".deb",
    ".rpm",
    ".sh",
    ".bash",
    ".ps1",
    ".psm1",
    ".msi",
    ".cab",
]
MALWARE_BYTE_PATTERNS = [
    b"MZ\x90\x00",
    b"\x7fELF",
    b"\xca\xfe\xba\xbe",
    b"<?php",
    b"<%@",
    b"<script",
    b"eval(",
    b"base64_decode",
    b"shell_exec",
    b"system(",
    b"exec(",
]


def detect_mime_type_fallback(file_content: bytes, filename: str = "") -> str:
    """
    Fallback MIME type detection when python-magic is not available.
    Uses file signatures and file extensions for detection.
    """
    if not file_content:
        return "application/octet-stream"
    for mime_type, signatures in FILE_SIGNATURES.items():
        if signatures is not None:
            for signature in signatures:
                if file_content.startswith(signature):
                    return mime_type
    if filename:
        guessed_type, _ = mimetypes.guess_type(filename)
        if guessed_type:
            return guessed_type
    try:
        file_content.decode("utf-8")
        if filename.lower().endswith(".csv"):
            return "text/csv"
        elif filename.lower().endswith(".json"):
            return "application/json"
        elif filename.lower().endswith(".xml"):
            return "application/xml"
        return "text/plain"
    except UnicodeDecodeError:
        pass
    return "application/octet-stream"


def get_file_mime_type(file_content: bytes, filename: str = "") -> str:
    """
    Get MIME type using python-magic if available, otherwise use fallback detection.
    """
    if MAGIC_AVAILABLE:
        try:
            return magic.from_buffer(file_content, mime=True)
        except OSError as e:
            logger.warning("Magic detection failed: %s, using fallback" % e)
            return detect_mime_type_fallback(file_content, filename)
    else:
        return detect_mime_type_fallback(file_content, filename)


TYPE_SIZE_LIMITS = {
    "image/jpeg": 10 * 1024 * 1024,
    "image/png": 10 * 1024 * 1024,
    "image/gif": 5 * 1024 * 1024,
    "application/pdf": 50 * 1024 * 1024,
    "text/csv": 10 * 1024 * 1024,
    "text/plain": 5 * 1024 * 1024,
}


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent security issues."""
    filename = os.path.basename(filename)
    filename = re.sub("[^\\w\\s.-]", "_", filename)
    filename = re.sub("\\.{2,}", ".", filename)
    name, ext = os.path.splitext(filename)
    if len(name) > MAX_FILENAME_LENGTH:
        name = name[:100]
    filename = name + ext
    return filename


def validate_file_content(file_content: bytes, content_type: str, filename: str = "") -> bool:
    """Validate file content matches declared content type."""
    signatures = FILE_SIGNATURES.get(content_type)
    if signatures is not None and not any(file_content.startswith(sig) for sig in signatures):
        return False
    try:
        detected_type = get_file_mime_type(file_content, filename)
        if content_type.startswith("text/") and detected_type.startswith("text/"):
            return True
        if content_type != detected_type:
            logger.warning(
                "Content type mismatch: declared=%s, detected=%s" % (content_type, detected_type)
            )
            return False
    except OSError as e:
        logger.error("Error detecting file type: %s" % e)
        return False
    return True


def check_for_malicious_content(file_content: bytes, filename: str) -> bool:
    """Check for potentially malicious content patterns."""
    _, ext = os.path.splitext(filename.lower())
    if ext in DANGEROUS_EXTENSIONS:
        return False
    if file_content.startswith(b"PK"):
        for pattern in MALWARE_BYTE_PATTERNS[:3]:
            if pattern.encode() in file_content:
                logger.warning("Possible embedded executable in %s" % filename)
                return False
    if filename.endswith((".txt", ".csv", ".json", ".xml")):
        try:
            text_content = file_content.decode("utf-8", errors="ignore")
            suspicious_patterns = [
                "<script[^>]*>",
                "javascript:",
                "on\\w+\\s*=",
                "eval\\s*\\(",
                "exec\\s*\\(",
            ]
            for pattern in suspicious_patterns:
                if re.search(pattern, text_content, re.IGNORECASE):
                    logger.warning("Suspicious pattern found in %s" % filename)
                    return False
        except (OSError, KeyError, IndexError):
            pass
    return True


def analyze_file_comprehensively(
    file_content: bytes, filename: str, content_type: str
) -> FileAnalysisReport:
    """Perform comprehensive multi-layered file analysis."""
    start_time = time.time()
    threats_detected = []
    recommendations = []
    security_score = 0.0
    file_size = len(file_content)
    file_hash = calculate_file_hash(file_content)
    detected_type = get_file_mime_type(file_content, filename) if file_content else "unknown"
    safe_filename = sanitize_filename(filename)
    max_size = TYPE_SIZE_LIMITS.get(content_type, settings.max_file_size)
    if file_size > max_size:
        threats_detected.append(f"File size ({file_size}) exceeds limit for type {content_type}")
        security_score += 0.3
    if content_type != detected_type:
        threats_detected.append(
            f"MIME type mismatch: declared={content_type}, detected={detected_type}"
        )
        security_score += 0.4
    _, ext = os.path.splitext(filename.lower())
    if ext in DANGEROUS_EXTENSIONS:
        threats_detected.append(f"Dangerous file extension: {ext}")
        security_score += 0.8
    for pattern in MALWARE_BYTE_PATTERNS:
        if pattern.encode() in file_content:
            threats_detected.append(f"Malware pattern detected: {pattern}")
            security_score += 0.7
    if content_type.startswith("text/"):
        try:
            text_content = file_content.decode("utf-8", errors="ignore")
            if len(re.findall("[A-Za-z0-9+/]{50,}", text_content)) > DEFAULT_RETRIES:
                threats_detected.append("Possible base64-encoded content detected")
                security_score += 0.3
            url_patterns = re.findall('https?://[^\\s<>"{}|\\^`\\[\\]]+', text_content)
            if len(url_patterns) > 10:
                threats_detected.append(f"High number of URLs detected: {len(url_patterns)}")
                security_score += 0.2
        except UnicodeDecodeError:
            threats_detected.append("Text file contains non-UTF8 content")
            security_score += 0.2
    if file_content.startswith(b"PK"):
        pk_count = file_content.count(b"PK")
        if pk_count > MAX_PK_COUNT:
            threats_detected.append(f"Possible zip bomb: {pk_count} PK signatures")
            security_score += 0.6
    if content_type.startswith("image/"):
        if b"<?php" in file_content or b"<script" in file_content:
            threats_detected.append("Suspicious script content in image file")
            security_score += 0.8
        if content_type == "image/jpeg" and file_content[2:4] == b"\xff\xe1":
            exif_size = int.from_bytes(file_content[4:6], "big")
            if exif_size > MAX_EXIF_SIZE:
                threats_detected.append("Abnormally large EXIF metadata")
                security_score += 0.4
    if security_score >= CONFIDENCE_THRESHOLD:
        validation_result = ValidationResult.MALICIOUS
    elif security_score >= HALF_RATIO:
        validation_result = ValidationResult.SUSPICIOUS
    elif security_score >= 0.2:
        validation_result = ValidationResult.QUARANTINED
    else:
        validation_result = ValidationResult.CLEAN
    if threats_detected:
        recommendations.append("File should be quarantined for manual review")
        if security_score >= HALF_RATIO:
            recommendations.append("Block file upload immediately")
        if "MIME type mismatch" in str(threats_detected):
            recommendations.append("Verify file type with multiple detection methods")
        if any("URL" in threat for threat in threats_detected):
            recommendations.append("Scan URLs for malicious domains")
    else:
        recommendations.append("File appears safe for upload")
    validation_time = time.time() - start_time
    return FileAnalysisReport(
        filename=safe_filename,
        original_filename=filename,
        content_type=content_type,
        detected_type=detected_type,
        file_size=file_size,
        file_hash=file_hash,
        validation_result=validation_result,
        security_score=min(security_score, 1.0),
        threats_detected=threats_detected,
        recommendations=recommendations,
        validation_time=validation_time,
    )


def get_file_validator(
    max_size: int = None,
    allowed_types: List[str] = None,
    enable_content_validation: bool = True,
    enable_malware_check: bool = True,
    security_level: str = "standard",
) -> callable:
    """Get a file validator with multi-layered security checks."""
    if max_size is None:
        max_size = settings.max_file_size
    if allowed_types is None:
        allowed_types = settings.allowed_file_types
        if isinstance(allowed_types, str):
            allowed_types = [allowed_types]

    async def validator(file: UploadFile = File(...)) -> Tuple[UploadFile, FileAnalysisReport]:
        if file.size and file.size > max_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size exceeds the limit of {max_size / 1024 / 1024} MB",
            )
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"File type '{file.content_type}' is not allowed",
            )
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Filename is required"
            )
        for pattern in DANGEROUS_PATTERNS:
            if re.search(pattern, file.filename):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid filename contains dangerous patterns",
                )
        content = await file.read()
        await file.seek(0)
        analysis_report = analyze_file_comprehensively(content, file.filename, file.content_type)
        if security_level == "strict":
            if analysis_report.validation_result in [
                ValidationResult.SUSPICIOUS,
                ValidationResult.MALICIOUS,
            ]:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"File rejected - Security analysis: {', '.join(analysis_report.threats_detected)}",
                )
        elif security_level == "standard":
            if analysis_report.validation_result == ValidationResult.MALICIOUS:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"File rejected - Malicious content detected: {', '.join(analysis_report.threats_detected)}",
                )
        if enable_content_validation:
            if not validate_file_content(content, file.content_type, file.filename):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="File content does not match declared type",
                )
        if enable_malware_check and not check_for_malicious_content(content, file.filename):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="File contains potentially dangerous content",
            )
        file.filename = analysis_report.filename
        logger.info(
            "File validation complete: %s (Result: %s, Score: %s, Time: %ss)"
            % (
                analysis_report.filename,
                analysis_report.validation_result.value,
                analysis_report.security_score,
                analysis_report.validation_time,
            )
        )
        if analysis_report.threats_detected:
            logger.warning(
                "Threats detected in %s: %s"
                % (analysis_report.filename, analysis_report.threats_detected)
            )
        return file, analysis_report

    return validator


def calculate_file_hash(content: bytes) -> str:
    """Calculate SHA-256 hash of file content."""
    return hashlib.sha256(content).hexdigest()


def get_safe_upload_path(filename: str, upload_dir: str = None) -> Path:
    """Get a safe upload path preventing directory traversal."""
    if upload_dir is None:
        upload_dir = settings.upload_dir
    safe_filename = sanitize_filename(filename)
    upload_path = Path(upload_dir).resolve()
    file_path = upload_path / safe_filename
    if not str(file_path.resolve()).startswith(str(upload_path)):
        raise ValueError("Invalid file path")
    return file_path


def quarantine_file(file_content: bytes, analysis_report: FileAnalysisReport) -> str:
    """Quarantine a suspicious file for manual review."""
    quarantine_dir = Path(settings.upload_dir) / "quarantine"
    quarantine_dir.mkdir(exist_ok=True)
    timestamp = int(time.time())
    quarantine_filename = (
        f"{timestamp}_{analysis_report.file_hash[:8]}_{analysis_report.filename}",
    )
    quarantine_path = quarantine_dir / quarantine_filename
    with open(quarantine_path, "wb") as f:
        f.write(file_content)
    report_path = quarantine_path.with_suffix(".json")
    import json

    with open(report_path, "w") as f:
        json.dump(
            {
                "filename": analysis_report.filename,
                "original_filename": analysis_report.original_filename,
                "content_type": analysis_report.content_type,
                "detected_type": analysis_report.detected_type,
                "file_size": analysis_report.file_size,
                "file_hash": analysis_report.file_hash,
                "validation_result": analysis_report.validation_result.value,
                "security_score": analysis_report.security_score,
                "threats_detected": analysis_report.threats_detected,
                "recommendations": analysis_report.recommendations,
                "validation_time": analysis_report.validation_time,
                "quarantined_at": timestamp,
            },
            indent=2,
        )
    logger.warning(
        "File quarantined: %s - %s" % (quarantine_filename, analysis_report.threats_detected)
    )
    return str(quarantine_path)


class EnhancedFileValidator:
    """Enhanced file validator with advanced security features."""

    def __init__(
        self,
        max_size: int = None,
        allowed_types: List[str] = None,
        security_level: str = "standard",
        enable_quarantine: bool = True,
    ) -> None:
        self.max_size = max_size or settings.max_file_size
        self.allowed_types = allowed_types or settings.allowed_file_types
        self.security_level = security_level
        self.enable_quarantine = enable_quarantine
        if isinstance(self.allowed_types, str):
            self.allowed_types = [self.allowed_types]

    async def validate_and_analyze(
        self, file: UploadFile
    ) -> Tuple[UploadFile, FileAnalysisReport, Optional[str]]:
        """Validate file with comprehensive analysis and optional quarantine."""
        if file.size and file.size > self.max_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size exceeds the limit of {self.max_size / 1024 / 1024} MB",
            )
        if file.content_type not in self.allowed_types:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"File type '{file.content_type}' is not allowed",
            )
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Filename is required"
            )
        content = await file.read()
        await file.seek(0)
        analysis_report = analyze_file_comprehensively(content, file.filename, file.content_type)
        file.filename = analysis_report.filename
        quarantine_path = None
        if self.security_level == "strict":
            if analysis_report.validation_result in [
                ValidationResult.SUSPICIOUS,
                ValidationResult.MALICIOUS,
            ]:
                if self.enable_quarantine:
                    quarantine_path = quarantine_file(content, analysis_report)
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="File rejected - Security risk detected",
                )
        elif self.security_level == "standard":
            if analysis_report.validation_result == ValidationResult.MALICIOUS:
                if self.enable_quarantine:
                    quarantine_path = quarantine_file(content, analysis_report)
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="File rejected - Malicious content detected",
                )
            elif (
                analysis_report.validation_result == ValidationResult.SUSPICIOUS
                and self.enable_quarantine
            ):
                quarantine_path = quarantine_file(content, analysis_report)
        return file, analysis_report, quarantine_path
