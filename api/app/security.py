import re
from typing import Optional
from langsmith import traceable


class InputSanitizer:
    """Flags likely prompt-injection attempts in user input."""

    INJECTION_PATTERNS = [
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"forget\s+(all\s+)?previous",
        r"new\s+instructions\s*:",
        r"system\s*prompt",
        r"---\s*end\s*(of)?\s*prompt",
        r"pretend\s+you\s+are",
        r"act\s+as\s+(if\s+)?you",
        r"bypass\s+(all\s+)?restrictions",
        r"reveal\s+(your|the)\s+(system|instructions|prompt)",
        r"you\s+are\s+now\s+(DAN|jailbroken)",
    ]

    def __init__(self) -> None:

        self._patterns = [re.compile(p, re.IGNORECASE) for p in self.INJECTION_PATTERNS]

    def check(self, text: str) -> tuple[bool, Optional[str]]:
        """Return (True, reason) if the input looks like an injection attempt."""
        for pattern in self._patterns:
            if pattern.search(text):
                return True, "Potential prompt injection detected"
        return False, None

    def clean(self, text: str) -> str:
        """Remove delimiters commonly used to fake the end of a prompt section."""
        text = re.sub(r"-{3,}", "", text)
        text = re.sub(r"={3,}", "", text)
        # Break template braces apart so the text can't become a placeholder
        # if it ever ends up inside a prompt template string.
        text = text.replace("{{", "{ {").replace("}}", "} }")
        return text.strip()


class PIIDectector:
    """Detects potential PII in user input."""

    PATTERNS = {
        "email": re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"),
        "phone": re.compile(r"\+?\d[\d\s\-()]{7,}\d"),
        "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        "credit_card": re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
    }

    MASK_MAP = {
        "email": "[EMAIL]",
        "phone": "[PHONE]",
        "ssn": "[SSN]",
        "credit_card": "[CREDIT_CARD]",
    }

    def detect(self, text: str) -> dict[str, list[str]]:
        """Detects potential PII in the input text and returns a dictionary of detected types and their values."""
        detected = {}
        for pii_type, pattern in self.PATTERNS.items():
            matches = pattern.findall(text)
            if matches:
                detected[pii_type] = matches
        return detected

    def mask(self, text: str) -> str:
        """Masks detected PII in the input text."""
        for pii_type, pattern in self.PATTERNS.items():
            text = pattern.sub(self.MASK_MAP[pii_type], text)
        return text


class OutputValidator:
    """Validates the output from the model to ensure it doesn't contain PII or prompt injections."""

    HARMFUL_PATTERNS = [
        re.compile(r"here('?s| is) (how|the way) to (hack|steal|attack)", re.I),
        re.compile(r"password\s+is\s+", re.I),
        re.compile(r"api[_\s]?key\s*[:=]", re.I),
    ]

    def __init__(self):
        self.pii_detector = PIIDectector()

    def validate(self, output: str) -> tuple[str, list[str]]:
        """Validates the output and returns a tuple of (cleaned_output, issues)."""

        warnings = []
        pii_issues = self.pii_detector.detect(output)
        if pii_issues:
            output = self.pii_detector.mask(output)
            warnings.append(f"Detected PII: {pii_issues}")

        for pattern in self.HARMFUL_PATTERNS:
            if pattern.search(output):
                output = ["Response removed due to harmful content."]
                warnings.append(f"Detected harmful content: {pattern.pattern}")
                break

        return output, warnings


class SecurityManager:
    """Manages security checks for user input and model output."""

    def __init__(self):
        self.sanitizer = InputSanitizer()
        self.pii_detector = PIIDectector()
        self.output_validator = OutputValidator()

    @traceable(name="Security Input Check")
    def check_input(self, user_input: str) -> tuple[bool, list[str]]:
        """
        Check through security checks
        Return: (is_safe, cleaned_input, warnings)
        """
        warnings = []

        # check for prompt injection
        is_safe, reason = self.sanitizer.check(user_input)
        if not is_safe:
            return False, "", [reason]

        # Clean the input to remove any delimiters
        cleaned_input = self.sanitizer.clean(user_input)

        # check for PII
        pii_issues = self.pii_detector.detect(cleaned_input)
        if pii_issues:
            cleaned_input = self.pii_detector.mask(cleaned_input)
            warnings.append(f"Detected PII: {pii_issues}")

        return True, cleaned_input, warnings

    def validate_output(self, model_output: str) -> tuple[str, list[str]]:
        """
        Validate the model output for PII and harmful content.
        Return: (cleaned_output, warnings)
        """
        return self.output_validator.validate(model_output)
