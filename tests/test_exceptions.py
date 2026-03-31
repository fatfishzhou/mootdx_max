from mootdx.exceptions import MootdxConnectionError
from mootdx.exceptions import MootdxEmptyResponseError
from mootdx.exceptions import MootdxNotConnectedError
from mootdx.exceptions import MootdxRequestError
from mootdx.exceptions import MootdxValidationException
from tdxpy.exceptions import TdxConnectionError
from tdxpy.exceptions import TdxFunctionCallError
from tdxpy.exceptions import ValidationException


def test_exception_hierarchy_preserves_compatibility():
    assert issubclass(MootdxValidationException, ValidationException)
    assert issubclass(MootdxConnectionError, TdxConnectionError)
    assert issubclass(MootdxNotConnectedError, MootdxConnectionError)
    assert issubclass(MootdxRequestError, TdxFunctionCallError)
    assert issubclass(MootdxEmptyResponseError, MootdxRequestError)
