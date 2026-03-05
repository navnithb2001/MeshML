"""Model validation service for custom PyTorch models."""

import ast
import sys
import tempfile
import importlib.util
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import logging
import traceback
from io import BytesIO

from app.core.storage import get_model_storage
from app.schemas.model import ModelMetadata
from app.services.error_reporting import categorize_model_validation_results, ValidationReport

logger = logging.getLogger(__name__)


class ModelValidationError(Exception):
    """Custom exception for model validation errors."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class ModelValidator:
    """Validator for custom PyTorch model files."""
    
    REQUIRED_FUNCTIONS = ["create_model", "create_dataloader"]
    REQUIRED_METADATA_FIELDS = ["task_type", "input_shape", "output_shape", "framework"]
    
    def __init__(self):
        self.validation_results: Dict[str, Any] = {
            "syntax_valid": False,
            "has_create_model": False,
            "has_create_dataloader": False,
            "has_model_metadata": False,
            "metadata_valid": False,
            "model_instantiable": False,
            "errors": [],
            "warnings": [],
        }
    
    def get_validation_report(self, model_id: str) -> ValidationReport:
        """
        Generate a structured ValidationReport from validation results.
        
        Args:
            model_id: Model identifier for the report
            
        Returns:
            ValidationReport instance
        """
        return categorize_model_validation_results(
            validation_results=self.validation_results,
            model_id=model_id
        )
    
    def validate_syntax(self, code: str) -> bool:
        """
        Validate Python syntax using AST parsing.
        
        Args:
            code: Python source code as string
            
        Returns:
            True if syntax is valid
            
        Raises:
            ModelValidationError: If syntax is invalid
        """
        try:
            ast.parse(code)
            self.validation_results["syntax_valid"] = True
            logger.info("Syntax validation passed")
            return True
        except SyntaxError as e:
            error_msg = f"Syntax error at line {e.lineno}: {e.msg}"
            self.validation_results["errors"].append(error_msg)
            logger.error(f"Syntax validation failed: {error_msg}")
            raise ModelValidationError(
                "Invalid Python syntax",
                details={
                    "line": e.lineno,
                    "offset": e.offset,
                    "text": e.text,
                    "message": e.msg
                }
            )
    
    def validate_structure(self, code: str) -> Tuple[bool, Optional[ast.AST]]:
        """
        Validate that required functions and variables exist.
        
        Args:
            code: Python source code
            
        Returns:
            Tuple of (is_valid, AST tree)
            
        Raises:
            ModelValidationError: If required components are missing
        """
        try:
            tree = ast.parse(code)
        except SyntaxError:
            # Already handled by validate_syntax
            return False, None
        
        # Find all top-level function definitions
        functions = {
            node.name for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
        }
        
        # Find all top-level variable assignments
        variables = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        variables.add(target.id)
        
        # Check for required functions
        missing_functions = []
        for func_name in self.REQUIRED_FUNCTIONS:
            if func_name in functions:
                self.validation_results[f"has_{func_name}"] = True
            else:
                missing_functions.append(func_name)
                self.validation_results["errors"].append(f"Missing required function: {func_name}()")
        
        # Check for MODEL_METADATA
        if "MODEL_METADATA" in variables:
            self.validation_results["has_model_metadata"] = True
        else:
            self.validation_results["errors"].append("Missing required variable: MODEL_METADATA")
        
        if missing_functions or "MODEL_METADATA" not in variables:
            error_parts = []
            if missing_functions:
                error_parts.append(f"Missing functions: {', '.join(missing_functions)}")
            if "MODEL_METADATA" not in variables:
                error_parts.append("Missing MODEL_METADATA dict")
            
            raise ModelValidationError(
                "Model structure validation failed",
                details={
                    "missing_functions": missing_functions,
                    "has_model_metadata": "MODEL_METADATA" in variables,
                    "found_functions": list(functions),
                }
            )
        
        logger.info("Structure validation passed")
        return True, tree
    
    def validate_metadata(self, metadata: Dict[str, Any]) -> bool:
        """
        Validate MODEL_METADATA dict completeness.
        
        Args:
            metadata: MODEL_METADATA dictionary
            
        Returns:
            True if metadata is valid
            
        Raises:
            ModelValidationError: If metadata is invalid
        """
        if not isinstance(metadata, dict):
            self.validation_results["errors"].append("MODEL_METADATA must be a dictionary")
            raise ModelValidationError(
                "MODEL_METADATA must be a dictionary",
                details={"type": type(metadata).__name__}
            )
        
        # Check required fields
        missing_fields = [
            field for field in self.REQUIRED_METADATA_FIELDS
            if field not in metadata
        ]
        
        if missing_fields:
            error_msg = f"MODEL_METADATA missing required fields: {', '.join(missing_fields)}"
            self.validation_results["errors"].append(error_msg)
            raise ModelValidationError(
                "Incomplete MODEL_METADATA",
                details={
                    "missing_fields": missing_fields,
                    "required_fields": self.REQUIRED_METADATA_FIELDS,
                    "provided_fields": list(metadata.keys())
                }
            )
        
        # Validate field types and values
        errors = []
        
        # task_type should be a string
        if not isinstance(metadata.get("task_type"), str):
            errors.append("task_type must be a string")
        
        # input_shape should be a list of integers
        input_shape = metadata.get("input_shape")
        if not isinstance(input_shape, list) or not all(isinstance(x, int) for x in input_shape):
            errors.append("input_shape must be a list of integers")
        
        # output_shape should be a list of integers
        output_shape = metadata.get("output_shape")
        if not isinstance(output_shape, list) or not all(isinstance(x, int) for x in output_shape):
            errors.append("output_shape must be a list of integers")
        
        # framework should be a string
        if not isinstance(metadata.get("framework"), str):
            errors.append("framework must be a string")
        
        # Optional: num_classes should be positive integer
        if "num_classes" in metadata:
            num_classes = metadata["num_classes"]
            if not isinstance(num_classes, int) or num_classes <= 0:
                errors.append("num_classes must be a positive integer")
        
        # Optional: learning_rate should be positive float
        if "learning_rate" in metadata:
            lr = metadata["learning_rate"]
            if not isinstance(lr, (int, float)) or lr <= 0:
                errors.append("learning_rate must be a positive number")
        
        if errors:
            self.validation_results["errors"].extend(errors)
            raise ModelValidationError(
                "MODEL_METADATA validation failed",
                details={"errors": errors, "metadata": metadata}
            )
        
        self.validation_results["metadata_valid"] = True
        logger.info("Metadata validation passed")
        return True
    
    def test_model_instantiation(self, model_file_path: Path) -> bool:
        """
        Test if model can be instantiated by importing and calling create_model().
        
        Args:
            model_file_path: Path to model.py file
            
        Returns:
            True if model instantiates successfully
            
        Raises:
            ModelValidationError: If instantiation fails
        """
        try:
            # Load module dynamically
            spec = importlib.util.spec_from_file_location("custom_model", model_file_path)
            if spec is None or spec.loader is None:
                raise ModelValidationError(
                    "Failed to load module",
                    details={"path": str(model_file_path)}
                )
            
            module = importlib.util.module_from_spec(spec)
            sys.modules["custom_model"] = module
            spec.loader.exec_module(module)
            
            # Check if create_model exists and is callable
            if not hasattr(module, "create_model"):
                raise ModelValidationError(
                    "create_model() function not found",
                    details={"available_functions": dir(module)}
                )
            
            if not callable(module.create_model):
                raise ModelValidationError(
                    "create_model is not callable",
                    details={"type": type(module.create_model).__name__}
                )
            
            # Try to instantiate model
            model = module.create_model()
            
            # Basic sanity check - model should have parameters
            if hasattr(model, "parameters"):
                param_count = sum(1 for _ in model.parameters())
                if param_count == 0:
                    self.validation_results["warnings"].append(
                        "Model has no parameters - is this intentional?"
                    )
            
            self.validation_results["model_instantiable"] = True
            logger.info(f"Model instantiation test passed")
            
            # Clean up
            del sys.modules["custom_model"]
            del module
            
            return True
            
        except Exception as e:
            error_msg = f"Model instantiation failed: {str(e)}"
            self.validation_results["errors"].append(error_msg)
            logger.error(f"{error_msg}\n{traceback.format_exc()}")
            
            # Clean up
            if "custom_model" in sys.modules:
                del sys.modules["custom_model"]
            
            raise ModelValidationError(
                "Model instantiation failed",
                details={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "traceback": traceback.format_exc()
                }
            )
    
    def validate_dataloader_function(self, model_file_path: Path) -> bool:
        """
        Validate that create_dataloader() function exists and is callable.
        
        Args:
            model_file_path: Path to model.py file
            
        Returns:
            True if dataloader function is valid
            
        Raises:
            ModelValidationError: If validation fails
        """
        try:
            # Load module
            spec = importlib.util.spec_from_file_location("custom_model", model_file_path)
            if spec is None or spec.loader is None:
                raise ModelValidationError("Failed to load module")
            
            module = importlib.util.module_from_spec(spec)
            sys.modules["custom_model"] = module
            spec.loader.exec_module(module)
            
            # Check if create_dataloader exists and is callable
            if not hasattr(module, "create_dataloader"):
                raise ModelValidationError("create_dataloader() function not found")
            
            if not callable(module.create_dataloader):
                raise ModelValidationError("create_dataloader is not callable")
            
            # Note: We don't actually call create_dataloader() because it might
            # require dataset files that aren't available yet
            
            logger.info("create_dataloader() validation passed")
            
            # Clean up
            del sys.modules["custom_model"]
            del module
            
            return True
            
        except ModelValidationError:
            raise
        except Exception as e:
            error_msg = f"Dataloader validation failed: {str(e)}"
            self.validation_results["errors"].append(error_msg)
            
            # Clean up
            if "custom_model" in sys.modules:
                del sys.modules["custom_model"]
            
            raise ModelValidationError(
                "create_dataloader() validation failed",
                details={"error": str(e), "traceback": traceback.format_exc()}
            )
    
    def get_metadata_from_file(self, model_file_path: Path) -> Optional[Dict[str, Any]]:
        """
        Extract MODEL_METADATA from model file.
        
        Args:
            model_file_path: Path to model.py file
            
        Returns:
            MODEL_METADATA dict or None
        """
        try:
            spec = importlib.util.spec_from_file_location("custom_model", model_file_path)
            if spec is None or spec.loader is None:
                return None
            
            module = importlib.util.module_from_spec(spec)
            sys.modules["custom_model"] = module
            spec.loader.exec_module(module)
            
            metadata = getattr(module, "MODEL_METADATA", None)
            
            # Clean up
            del sys.modules["custom_model"]
            del module
            
            return metadata
            
        except Exception as e:
            logger.error(f"Failed to extract metadata: {e}")
            return None


async def validate_model_file(
    model_id: int,
    gcs_path: str,
    skip_instantiation: bool = False
) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str], Dict[str, Any]]:
    """
    Complete model validation workflow.
    
    Args:
        model_id: Model database ID
        gcs_path: GCS path to model.py file
        skip_instantiation: Skip model instantiation test (for testing)
        
    Returns:
        Tuple of (is_valid, metadata_dict, error_message, validation_details)
    """
    validator = ModelValidator()
    temp_file = None
    
    try:
        # Extract blob path from GCS path
        # Format: gs://bucket-name/path/to/file -> path/to/file
        storage_client = get_model_storage()
        blob_path = gcs_path.split(f"{storage_client.bucket_name}/", 1)[-1]
        
        # Download file from GCS to temporary location
        temp_file = tempfile.NamedTemporaryFile(
            mode='wb',
            suffix='.py',
            delete=False
        )
        
        with BytesIO() as file_buffer:
            storage_client.download_file(blob_path, file_buffer)
            file_buffer.seek(0)
            code = file_buffer.read().decode('utf-8')
            temp_file.write(file_buffer.getvalue())
        
        temp_file.close()
        temp_path = Path(temp_file.name)
        
        logger.info(f"Starting validation for model {model_id}")
        
        # Step 1: Validate syntax
        validator.validate_syntax(code)
        
        # Step 2: Validate structure
        validator.validate_structure(code)
        
        # Step 3: Extract and validate metadata
        metadata = validator.get_metadata_from_file(temp_path)
        if metadata:
            validator.validate_metadata(metadata)
        else:
            raise ModelValidationError("Failed to extract MODEL_METADATA")
        
        # Step 4: Test model instantiation (optional)
        if not skip_instantiation:
            validator.test_model_instantiation(temp_path)
            validator.validate_dataloader_function(temp_path)
        
        # All validations passed
        logger.info(f"Model {model_id} validation successful")
        
        return True, metadata, None, validator.validation_results
        
    except ModelValidationError as e:
        logger.warning(f"Model {model_id} validation failed: {e.message}")
        return False, None, e.message, validator.validation_results
        
    except Exception as e:
        logger.error(f"Unexpected error during validation of model {model_id}: {e}")
        error_msg = f"Validation error: {str(e)}"
        validator.validation_results["errors"].append(error_msg)
        return False, None, error_msg, validator.validation_results
        
    finally:
        # Clean up temporary file
        if temp_file and Path(temp_file.name).exists():
            try:
                Path(temp_file.name).unlink()
            except Exception as e:
                logger.warning(f"Failed to delete temp file: {e}")
