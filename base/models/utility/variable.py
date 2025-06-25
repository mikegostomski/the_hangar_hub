from django.db import models
from base.classes.util.log import Log
from base.classes.util.date_helper import DateHelper
from decimal import Decimal
from base.services import utility_service, message_service, auth_service
from base.models.utility.error import Error

log = Log()


class Variable(models.Model):
    """
    Variables/Settings that can be edited via a UI
    """
    code = models.CharField(
        max_length=30, unique=True,
        blank=False, null=False, db_index=True
    )
    title = models.CharField(
        max_length=80,
        blank=True, null=True
    )
    data_type = models.CharField(
        max_length=10,
        blank=False, null=False
    )
    current_value = models.CharField(
        max_length=80,
        blank=True, null=True
    )
    previous_value = models.CharField(
        max_length=80,
        blank=True, null=True
    )

    version = models.IntegerField(blank=False, null=False)
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    last_user = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)

    @staticmethod
    def data_type_options():
        """Valid data-types handled by base Variables"""
        return {
            'string': 'String',
            'int': 'Integer',
            'decimal': 'Decimal',
            'date': 'Date',
            'timestamp': 'Timestamp',
            'boolean': 'Boolean',
            'yn': 'Yes/No',
        }

    @property
    def value(self):
        """Gets the value of this variable"""
        return self._decode_variable_value(self.current_value, self.data_type)

    def set_value(self, new_value):
        """
        Set the value of a previously-saved Variable
        (not used for initial creation or a new Variable)
        """
        try:
            encoded_value = self._encode_variable_value(new_value, self.data_type)
            if new_value is not None and encoded_value is None:
                # If encoding failed, do not save the value
                return False

            self.previous_value = self.current_value
            self.current_value = encoded_value
            self.last_pidm = auth_service.get_user().pidm
            self.version = self.version + 1
            self.save()
            return True
        except Exception as ee:
            Error.unexpected("Unable to update variable", ee)
            return False

    @classmethod
    def get_value(cls, code, default_value=None, data_type=None):
        # Look for existing Variable
        variable_instance = cls.get(code)

        # If found, check for a value changed at the code level
        if variable_instance:
            # Only update with code changes if not changed via the UI
            if variable_instance.version == 0:
                compare = cls._encode_variable_value(default_value, variable_instance.data_type)
                if variable_instance.current_value != compare:
                    try:
                        variable_instance.previous_value = variable_instance.current_value
                        variable_instance.current_value = compare
                        # Not updating version since this is a code-induced change
                        variable_instance.save()
                    except Exception as ee:
                        Error.record(ee, f"Update value of {variable_instance}")
                        variable_instance.current_value = variable_instance.previous_value

        # If not found, create a new Variable
        else:
            variable_instance = cls._create_variable(code, default_value, data_type)

        # If found/created, return the decoded value
        if variable_instance:
            return variable_instance.value

        # If unable to locate/create the Variable, at least convert the default_value to the given data_type
        if "str" in str(type(default_value)).lower() and data_type is not None:
            try:
                return cls._decode_variable_value(default_value, data_type)
            except:
                log.error(f"Unable to encode default_value for {code}: {default_value}")

        # If all else fails, return default value exactly as given
        return default_value

    @classmethod
    def get(cls, identifier):
        """
        Get a variable instance from its ID or Code
        """
        # If given a record's ID
        if str(identifier).isnumeric():
            try:
                return cls.objects.get(pk=identifier)
            except cls.DoesNotExist:
                return None

        # If given a variable's CODE
        else:
            try:
                vv = cls.objects.get(code=identifier)
                return vv
            except cls.DoesNotExist:
                return None

    @classmethod
    def _encode_variable_value(cls, value, data_type):
        """
        Turn the given value into a string that can be stored in
        the database and turned back into its intended data type when
        queried in the future
        """
        if str(value) == "None":
            return None

        elif data_type.lower() == 'int':
            try:
                return str(int(str(value)))
            except:
                message_service.post_error(f'Invalid variable value. "{value}" is not an integer.')
                return None

        elif data_type.lower() == 'decimal':
            try:
                amount_str = str(value).replace(",", "").replace("$", "")
                amount_decimal = Decimal(amount_str)
                return "{0:.2f}".format(amount_decimal)
            except:
                message_service.post_error(f'Invalid variable value. "{value}" is not a decimal number.')
                return None

        elif data_type.lower() == 'date':
            cd = DateHelper(value)
            if cd.datetime_instance:
                return cd.date_field()
            return None

        elif data_type.lower() == 'timestamp':
            cd = DateHelper(value)
            if cd.datetime_instance:
                return cd.timestamp()
            return None

        elif data_type.lower() == 'boolean':
            return str(str(value).lower()[0] in ['t', 'y'])

        elif data_type.lower() == 'yn':
            return 'Y' if str(value).lower()[0] in ['t', 'y'] else 'N'

        else:
            # String
            return str(value)

    @classmethod
    def _decode_variable_value(cls, value, data_type):
        """
        Turn the string representation of a variable into the intended data type
        """
        if str(value) == "None":
            return None

        elif data_type.lower() == 'int':
            try:
                return int(value)
            except:
                message_service.post_error(f'Invalid variable value. "{value}" is not an integer.')
                return None

        elif data_type.lower() == 'decimal':
            try:
                amount_str = value.replace(",", "").replace("$", "")
                amount_decimal = Decimal(amount_str)
                return amount_decimal
            except:
                message_service.post_error(f'Invalid variable value. "{value}" is not a decimal number.')
                return None

        elif data_type.lower() == 'date':
            cd = DateHelper(value)
            return cd.datetime_instance

        elif data_type.lower() == 'timestamp':
            cd = DateHelper(value)
            return cd.datetime_instance

        elif data_type.lower() == 'boolean':
            return value.lower() == 'true'

        elif data_type.lower() == 'yn':
            return value if value in ['Y', 'N'] else None

        else:
            # String
            return value

    @classmethod
    def _create_variable(cls, code, default_value=None, data_type=None):
        """
        Called internally to create a new Variable.  This happens when a
        requested Variable is not found in the database
        """
        log.trace([code, default_value, data_type])

        if not data_type:
            # Auto-detect integer (common and easy), otherwise default to string
            if str(default_value).isnumeric():
                data_type = "int"
            else:
                data_type = "string"

        if data_type not in cls.data_type_options():
            message_service.post_error(f"Invalid datatype for variable '{code}': {data_type}")
            return None

        encoded_value = cls._encode_variable_value(default_value, data_type)
        if default_value is not None and encoded_value is None:
            message_service.post_error(f"Failed to encode variable: {code}")
            return None

        try:
            app_code = utility_service.get_app_code()
            new_variable = cls()
            new_variable.app_code = app_code
            new_variable.code = code
            new_variable.version = 0
            new_variable.data_type = data_type
            new_variable.current_value = encoded_value
            new_variable.save()
            # This is an auto-creation, do not save pidm of current user
            return new_variable
        except Exception as ee:
            Error.record(ee)

        return None
