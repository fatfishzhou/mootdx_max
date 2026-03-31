from tdxpy.exceptions import TdxConnectionError
from tdxpy.exceptions import TdxFunctionCallError
from tdxpy.exceptions import ValidationException


class MootdxException(Exception):
    """Base mootdx exception."""

    def __init__(self, *args, **kwargs):
        """
        Looks for ``provider``, ``message`` and ``data`` in kwargs
        :param args: Exception arguments
        :param kwargs: Exception kwargs
        """
        self.provider = kwargs.get('provider')
        self.response = kwargs.get('response')

        self.message = kwargs.get('message')
        self.data = kwargs.get('data')

        super().__init__(self.message)

    def __repr__(self):
        return f'<MOOTDXError: {self.message}>'


class MootdxValidationException(ValidationException):
    def __init__(self, message=None, *args, **kwargs):
        super().__init__(message)
        self.message = message
        self.args = (message,) if message is not None else args


class MootdxConnectionError(TdxConnectionError):
    def __init__(self, message=None, *, endpoint=None, original_exception=None):
        super().__init__(message or 'connection failed')
        self.endpoint = endpoint
        self.original_exception = original_exception


class MootdxConnectionTimeoutError(MootdxConnectionError):
    pass


class MootdxNotConnectedError(MootdxConnectionError):
    pass


class MootdxRequestError(TdxFunctionCallError):
    def __init__(self, message=None, *, endpoint=None, response=None, original_exception=None):
        super().__init__(message or 'request failed')
        self.endpoint = endpoint
        self.response = response
        self.original_exception = original_exception


class MootdxEmptyResponseError(MootdxRequestError):
    pass


class MootdxModuleNotFoundError(Exception):
    def __init__(self, *args, **kwargs):
        pass


class FileNeedRefresh(FileNotFoundError):
    pass
