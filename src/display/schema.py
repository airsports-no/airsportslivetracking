"""drf-spectacular customizations.

Imported from DisplayConfig.ready() so the extension below is registered
before schema generation runs.
"""

from drf_spectacular.authentication import TokenScheme
from drf_spectacular.extensions import OpenApiAuthenticationExtension


class FirebaseAuthenticationScheme(OpenApiAuthenticationExtension):
    """Gives FirebaseAuthentication its own security scheme name.

    FirebaseAuthentication subclasses rest_framework.authentication.TokenAuthentication,
    so drf-spectacular's built-in TokenScheme (match_subclasses=True) also matches it,
    and both authentication classes end up sharing the "tokenAuth" component name. This
    extension matches FirebaseAuthentication specifically and, with a higher priority
    than TokenScheme's, wins the match so the two schemes get distinct names.
    """

    target_class = "drf_firebase_auth.authentication.FirebaseAuthentication"
    name = "firebaseAuth"
    priority = 1

    def get_security_definition(self, auto_schema):
        return TokenScheme.get_security_definition(self, auto_schema)
