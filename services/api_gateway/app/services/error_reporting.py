"""Validation error reporting and categorization."""

from enum import Enum
from typing import Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


class ErrorSeverity(str, Enum):
    """Error severity levels."""
    CRITICAL = "critical"      # Blocks validation completely
    ERROR = "error"            # Validation fails, must fix
    WARNING = "warning"        # Validation passes but user should be aware
    INFO = "info"              # Informational message


class ErrorCategory(str, Enum):
    """Error categories for better organization."""
    SYNTAX = "syntax"                  # Python syntax errors
    STRUCTURE = "structure"            # Missing required components
    METADATA = "metadata"              # Invalid or incomplete metadata
    INSTANTIATION = "instantiation"    # Model/dataloader instantiation fails
    FORMAT = "format"                  # Dataset format issues
    SIZE = "size"                      # Size/limit violations
    CONTENT = "content"                # Content validation (file types, etc.)
    PERMISSION = "permission"          # Access/permission issues
    NETWORK = "network"                # GCS/network errors
    UNKNOWN = "unknown"                # Uncategorized errors


class ValidationError(BaseModel):
    """Structured validation error."""
    severity: ErrorSeverity
    category: ErrorCategory
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Technical details")
    suggestion: Optional[str] = Field(None, description="How to fix this error")
    location: Optional[str] = Field(None, description="Where the error occurred (file, line, etc.)")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        use_enum_values = True


class ValidationReport(BaseModel):
    """Complete validation report with categorized errors."""
    validation_type: str = Field(..., description="Type: 'model' or 'dataset'")
    resource_id: Optional[str] = Field(None, description="Model ID or dataset path")
    is_valid: bool
    errors: List[ValidationError] = Field(default_factory=list)
    warnings: List[ValidationError] = Field(default_factory=list)
    info: List[ValidationError] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    def add_error(
        self,
        message: str,
        category: ErrorCategory,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        details: Optional[Dict[str, Any]] = None,
        suggestion: Optional[str] = None,
        location: Optional[str] = None
    ):
        """Add a validation error to the report."""
        error = ValidationError(
            severity=severity,
            category=category,
            message=message,
            details=details,
            suggestion=suggestion,
            location=location
        )
        
        if severity == ErrorSeverity.ERROR or severity == ErrorSeverity.CRITICAL:
            self.errors.append(error)
            self.is_valid = False
        elif severity == ErrorSeverity.WARNING:
            self.warnings.append(error)
        else:
            self.info.append(error)
    
    def get_errors_by_category(self, category: ErrorCategory) -> List[ValidationError]:
        """Get all errors for a specific category."""
        return [e for e in self.errors if e.category == category]
    
    def get_errors_by_severity(self, severity: ErrorSeverity) -> List[ValidationError]:
        """Get all errors of a specific severity."""
        all_messages = self.errors + self.warnings + self.info
        return [e for e in all_messages if e.severity == severity]
    
    def get_summary_text(self) -> str:
        """Generate human-readable summary."""
        if self.is_valid:
            return f"✅ Validation passed with {len(self.warnings)} warnings"
        else:
            return f"❌ Validation failed with {len(self.errors)} errors and {len(self.warnings)} warnings"
    
    class Config:
        use_enum_values = True


# Error message templates with suggestions
ERROR_TEMPLATES = {
    # Model validation errors
    "syntax_error": {
        "message": "Python syntax error at line {line}: {error}",
        "category": ErrorCategory.SYNTAX,
        "suggestion": "Fix the syntax error in your model.py file. Check for missing colons, unmatched parentheses, or invalid indentation."
    },
    "missing_function": {
        "message": "Missing required function: {function_name}()",
        "category": ErrorCategory.STRUCTURE,
        "suggestion": "Add the {function_name}() function to your model.py file. See the template at examples/custom_model_template.py"
    },
    "missing_metadata": {
        "message": "Missing required variable: MODEL_METADATA",
        "category": ErrorCategory.STRUCTURE,
        "suggestion": "Add MODEL_METADATA dictionary with required fields: task_type, input_shape, output_shape, framework"
    },
    "incomplete_metadata": {
        "message": "MODEL_METADATA missing required fields: {missing_fields}",
        "category": ErrorCategory.METADATA,
        "suggestion": "Add the missing fields to your MODEL_METADATA dictionary. Required: {required_fields}"
    },
    "invalid_metadata_type": {
        "message": "Invalid type for {field}: expected {expected_type}, got {actual_type}",
        "category": ErrorCategory.METADATA,
        "suggestion": "Fix the type of '{field}' in MODEL_METADATA. It should be {expected_type}."
    },
    "instantiation_failed": {
        "message": "Failed to instantiate model: {error}",
        "category": ErrorCategory.INSTANTIATION,
        "suggestion": "Ensure create_model() can run without errors. Test it locally first. Error: {error}"
    },
    
    # Dataset validation errors
    "no_classes": {
        "message": "No class directories found in ImageFolder dataset",
        "category": ErrorCategory.FORMAT,
        "suggestion": "Organize your images into class subdirectories. Structure: dataset/class1/img1.jpg, dataset/class2/img2.jpg"
    },
    "too_many_classes": {
        "message": "Dataset has {num_classes} classes (max: {max_classes})",
        "category": ErrorCategory.SIZE,
        "suggestion": "Reduce the number of classes or consider a different dataset structure. Maximum allowed: {max_classes}"
    },
    "invalid_coco": {
        "message": "Invalid COCO format: missing required keys: {missing_keys}",
        "category": ErrorCategory.FORMAT,
        "suggestion": "COCO annotations JSON must contain 'images', 'annotations', and 'categories' keys."
    },
    "dataset_too_large": {
        "message": "Dataset size {size_gb}GB exceeds limit of {max_gb}GB",
        "category": ErrorCategory.SIZE,
        "suggestion": "Reduce dataset size by compressing images, removing duplicates, or splitting into smaller datasets."
    },
    "too_many_files": {
        "message": "Dataset has {file_count} files (max: {max_files})",
        "category": ErrorCategory.SIZE,
        "suggestion": "Reduce the number of files or split into multiple datasets. Maximum: {max_files:,} files"
    },
    "empty_dataset": {
        "message": "Dataset directory is empty",
        "category": ErrorCategory.CONTENT,
        "suggestion": "Upload your dataset files to GCS before validation. Use: gsutil -m cp -r /path/to/dataset gs://bucket/path"
    },
    "invalid_json": {
        "message": "Failed to parse JSON file: {error}",
        "category": ErrorCategory.FORMAT,
        "suggestion": "Fix the JSON syntax errors in your annotations file. Use a JSON validator to check."
    },
    
    # General errors
    "gcs_access_denied": {
        "message": "Access denied to GCS path: {path}",
        "category": ErrorCategory.PERMISSION,
        "suggestion": "Ensure the service account has read permissions on the GCS bucket."
    },
    "gcs_not_found": {
        "message": "GCS path not found: {path}",
        "category": ErrorCategory.NETWORK,
        "suggestion": "Verify the GCS path is correct and the files have been uploaded."
    },
}


def create_error_from_template(
    template_key: str,
    severity: ErrorSeverity = ErrorSeverity.ERROR,
    location: Optional[str] = None,
    **kwargs
) -> ValidationError:
    """
    Create a ValidationError from a template.
    
    Args:
        template_key: Key in ERROR_TEMPLATES
        severity: Error severity
        location: Where the error occurred
        **kwargs: Template variables
        
    Returns:
        ValidationError instance
    """
    if template_key not in ERROR_TEMPLATES:
        # Fallback for unknown templates
        return ValidationError(
            severity=severity,
            category=ErrorCategory.UNKNOWN,
            message=kwargs.get("message", "Unknown error"),
            details=kwargs,
            location=location
        )
    
    template = ERROR_TEMPLATES[template_key]
    message = template["message"].format(**kwargs)
    suggestion = template.get("suggestion", "").format(**kwargs) if template.get("suggestion") else None
    
    return ValidationError(
        severity=severity,
        category=template["category"],
        message=message,
        details=kwargs,
        suggestion=suggestion,
        location=location
    )


def format_validation_report_for_user(report: ValidationReport) -> str:
    """
    Format validation report as user-friendly text.
    
    Args:
        report: ValidationReport instance
        
    Returns:
        Formatted text report
    """
    lines = []
    lines.append("=" * 70)
    lines.append(f"Validation Report: {report.validation_type.upper()}")
    lines.append("=" * 70)
    lines.append("")
    
    # Summary
    lines.append(report.get_summary_text())
    lines.append("")
    
    # Critical/Errors
    if report.errors:
        lines.append(f"ERRORS ({len(report.errors)}):")
        lines.append("-" * 70)
        for i, error in enumerate(report.errors, 1):
            lines.append(f"{i}. [{error.category.upper()}] {error.message}")
            if error.location:
                lines.append(f"   Location: {error.location}")
            if error.suggestion:
                lines.append(f"   💡 Suggestion: {error.suggestion}")
            if error.details:
                lines.append(f"   Details: {error.details}")
            lines.append("")
    
    # Warnings
    if report.warnings:
        lines.append(f"WARNINGS ({len(report.warnings)}):")
        lines.append("-" * 70)
        for i, warning in enumerate(report.warnings, 1):
            lines.append(f"{i}. [{warning.category.upper()}] {warning.message}")
            if warning.suggestion:
                lines.append(f"   💡 Suggestion: {warning.suggestion}")
            lines.append("")
    
    # Info
    if report.info:
        lines.append(f"INFO ({len(report.info)}):")
        lines.append("-" * 70)
        for info_msg in report.info:
            lines.append(f"ℹ️  {info_msg.message}")
        lines.append("")
    
    # Summary stats
    if report.summary:
        lines.append("SUMMARY:")
        lines.append("-" * 70)
        for key, value in report.summary.items():
            lines.append(f"  {key}: {value}")
        lines.append("")
    
    lines.append("=" * 70)
    
    return "\n".join(lines)


def categorize_model_validation_results(
    validation_results: Dict[str, Any],
    model_id: int
) -> ValidationReport:
    """
    Convert raw model validation results to structured report.
    
    Args:
        validation_results: Results from ModelValidator
        model_id: Model database ID
        
    Returns:
        ValidationReport instance
    """
    report = ValidationReport(
        validation_type="model",
        resource_id=str(model_id),
        is_valid=all([
            validation_results.get("syntax_valid", False),
            validation_results.get("has_create_model", False),
            validation_results.get("has_create_dataloader", False),
            validation_results.get("has_model_metadata", False),
            validation_results.get("metadata_valid", False),
        ])
    )
    
    # Process errors from validation_results
    for error_msg in validation_results.get("errors", []):
        # Try to categorize known error patterns
        if "syntax error" in error_msg.lower():
            report.add_error(
                message=error_msg,
                category=ErrorCategory.SYNTAX,
                severity=ErrorSeverity.ERROR,
                suggestion="Fix the syntax error in your model.py file."
            )
        elif "missing required function" in error_msg.lower():
            func_name = error_msg.split(":")[-1].strip()
            report.add_error(
                message=error_msg,
                category=ErrorCategory.STRUCTURE,
                severity=ErrorSeverity.ERROR,
                suggestion=f"Add the {func_name} function to your model.py file."
            )
        elif "MODEL_METADATA" in error_msg:
            report.add_error(
                message=error_msg,
                category=ErrorCategory.METADATA,
                severity=ErrorSeverity.ERROR,
                suggestion="Add or fix MODEL_METADATA dictionary in your model.py file."
            )
        elif "instantiation failed" in error_msg.lower():
            report.add_error(
                message=error_msg,
                category=ErrorCategory.INSTANTIATION,
                severity=ErrorSeverity.ERROR,
                suggestion="Ensure create_model() can run without errors. Test locally first."
            )
        else:
            report.add_error(
                message=error_msg,
                category=ErrorCategory.UNKNOWN,
                severity=ErrorSeverity.ERROR
            )
    
    # Process warnings
    for warning_msg in validation_results.get("warnings", []):
        report.add_error(
            message=warning_msg,
            category=ErrorCategory.UNKNOWN,
            severity=ErrorSeverity.WARNING
        )
    
    # Add summary
    report.summary = {
        "syntax_valid": validation_results.get("syntax_valid", False),
        "has_create_model": validation_results.get("has_create_model", False),
        "has_create_dataloader": validation_results.get("has_create_dataloader", False),
        "has_model_metadata": validation_results.get("has_model_metadata", False),
        "metadata_valid": validation_results.get("metadata_valid", False),
        "model_instantiable": validation_results.get("model_instantiable", False),
    }
    
    return report


def categorize_dataset_validation_results(
    validation_results: Dict[str, Any],
    gcs_path: str
) -> ValidationReport:
    """
    Convert raw dataset validation results to structured report.
    
    Args:
        validation_results: Results from DatasetValidator
        gcs_path: GCS path to dataset
        
    Returns:
        ValidationReport instance
    """
    report = ValidationReport(
        validation_type="dataset",
        resource_id=gcs_path,
        is_valid=all([
            validation_results.get("format_valid", False),
            validation_results.get("structure_valid", False),
            validation_results.get("content_valid", False),
            validation_results.get("size_valid", False),
        ])
    )
    
    # Process errors
    for error_msg in validation_results.get("errors", []):
        # Categorize known patterns
        if "no class" in error_msg.lower() or "no directories" in error_msg.lower():
            report.add_error(
                message=error_msg,
                category=ErrorCategory.FORMAT,
                severity=ErrorSeverity.ERROR,
                suggestion="Organize your images into class subdirectories for ImageFolder format."
            )
        elif "too many classes" in error_msg.lower() or "too large" in error_msg.lower() or "too many files" in error_msg.lower():
            report.add_error(
                message=error_msg,
                category=ErrorCategory.SIZE,
                severity=ErrorSeverity.ERROR,
                suggestion="Reduce dataset size or split into smaller chunks."
            )
        elif "json" in error_msg.lower() or "coco" in error_msg.lower():
            report.add_error(
                message=error_msg,
                category=ErrorCategory.FORMAT,
                severity=ErrorSeverity.ERROR,
                suggestion="Check COCO annotations JSON format and required keys."
            )
        elif "empty" in error_msg.lower():
            report.add_error(
                message=error_msg,
                category=ErrorCategory.CONTENT,
                severity=ErrorSeverity.ERROR,
                suggestion="Upload dataset files to GCS before validation."
            )
        else:
            report.add_error(
                message=error_msg,
                category=ErrorCategory.UNKNOWN,
                severity=ErrorSeverity.ERROR
            )
    
    # Process warnings
    for warning_msg in validation_results.get("warnings", []):
        report.add_error(
            message=warning_msg,
            category=ErrorCategory.UNKNOWN,
            severity=ErrorSeverity.WARNING
        )
    
    # Add summary
    report.summary = {
        "format": validation_results.get("format"),
        "format_valid": validation_results.get("format_valid", False),
        "structure_valid": validation_results.get("structure_valid", False),
        "content_valid": validation_results.get("content_valid", False),
        "size_valid": validation_results.get("size_valid", False),
        "num_classes": validation_results.get("num_classes", 0),
        "total_samples": validation_results.get("total_samples", 0),
        "total_size_bytes": validation_results.get("total_size_bytes", 0),
    }
    
    return report
