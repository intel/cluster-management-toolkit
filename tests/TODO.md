# TODO

## validate_schemas:

## validate_views:
* NOT IMPLEMENTED
* This could be made possible if all built-in fields were defined in views too;
  that way the validator could cross-reference all fields against the union of builtin_fields + fields,
  and error out if a referenced fields is missing, warn about unused and shadowed fields
