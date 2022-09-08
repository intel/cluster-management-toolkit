# TODO

## validate_schemas:
* Add command line option parsing; we want to be able to enable/disable verbosity, abort on fail, etc.
* Add "--resume-from"
* Add ANSI colours

## validate_views:
* NOT IMPLEMENTED
* This could be made possible if all built-in fields were defined in views too;
  that way the validator could cross-reference all fields against the union of builtin_fields + fields,
  and error out if a referenced fields is missing, warn about unused and shadowed fields
